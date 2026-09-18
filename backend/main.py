from __future__ import annotations
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException, Request, Depends, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

load_dotenv()

from src.predict import predict_all
from src.pipeline_utils import validate_input
from .database import get_db
from .models import LoanApplication, User
from .dependencies import require_authenticated_user
from .services.shap_service import init_shap_explainer, explain_loan_approval
from .services.task_queue import submit_application_task, get_task_status
from .services.pdf_service import generate_adverse_action_pdf, generate_approval_letter_pdf
from .schemas import TaskResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("loan-risk-api")

# Rate Limiter setup
from .limiter import limiter

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize TreeSHAP once during lifespan startup
    try:
        init_shap_explainer()
    except Exception as exc:
        logger.warning("Failed to initialize SHAP during startup: %s", exc)

    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        database_url = (os.getenv("DATABASE_URL") or os.getenv("AIVEN_DATABASE_URL") or "").strip().strip(' \t\r\n"\'')
        if database_url.startswith("mysql://"):
            database_url = "mysql+pymysql://" + database_url[len("mysql://"):]
        secret = os.getenv("JWT_SECRET_KEY", "")
        if not database_url.startswith("mysql+pymysql://"):
            raise RuntimeError("Production requires DATABASE_URL using mysql+pymysql://.")
        if len(secret) < 32:
            raise RuntimeError("Production requires JWT_SECRET_KEY of at least 32 characters.")
    yield

app = FastAPI(title="Bank Loan & Customer Credit Risk API", version="4.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for e in exc.errors():
        loc = e.get("loc", ())
        errors.append({"field": str(loc[-1]) if loc else "request", "message": e.get("msg", "Invalid value")})
    return JSONResponse(status_code=422, content={"detail": "Request validation failed.", "errors": errors})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "error_type": type(exc).__name__, "message": str(exc)},
    )

production_origin = "https://bank-loan-credit-risk-analysis-frontend.onrender.com"
dev_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]
env_origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "")).split(",") if x.strip()]
origins = list(dict.fromkeys([production_origin] + env_origins + dev_origins))

app.add_middleware(GZipMiddleware, minimum_size=100)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin", "X-Requested-With"],
)

class ApplicantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    applicant_name: str = Field(default="Applicant", min_length=2, max_length=120)
    city: str = Field(default="", max_length=100)
    region: str = Field(default="", max_length=100)
    age: int = Field(ge=18, le=75)
    dependents: int = Field(ge=0, le=5)
    gender: str = Field(min_length=1, max_length=30)
    marital_status: str = Field(min_length=1, max_length=30)
    education: str = Field(min_length=1, max_length=50)
    employment_type: str = Field(min_length=1, max_length=50)
    annual_income: float = Field(gt=0, le=50_000_000)
    debt_to_income_ratio: float = Field(ge=0, le=1)
    savings: float = Field(ge=0, le=50_000_000)
    bank_balance: float = Field(ge=0, le=20_000_000)
    assets: float = Field(ge=0, le=100_000_000)
    credit_history: str = Field(min_length=1, max_length=50)
    previous_loans: int = Field(ge=0, le=30)
    previous_defaults: int = Field(ge=0, le=20)
    payment_history: float = Field(ge=0, le=100)
    credit_utilization: float = Field(ge=0, le=1)
    credit_score: float = Field(ge=300, le=850)
    loan_type: str = Field(min_length=1, max_length=50)
    requested_loan_amount: float = Field(gt=0, le=100_000_000)
    loan_term: int = Field(gt=0, le=480)
    collateral_value: float = Field(ge=0, le=500_000_000)
    interest_rate: float = Field(gt=0, le=100)

def _run(x: ApplicantInput):
    data = x.model_dump()
    data["monthly_income"] = data["annual_income"] / 12
    data["monthly_debt"] = data["monthly_income"] * data["debt_to_income_ratio"]
    try:
        validate_input(data)
        return predict_all(data)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception:
        logger.exception("Prediction failed")
        raise HTTPException(500, "Prediction failed. Please try again later.")

@app.get("/")
def root():
    return {"service": "Bank Loan & Customer Credit Risk API", "docs": "/docs", "health": "/health"}

@app.get("/health")
def health():
    return {"status": "ok"}

# ========================================================
# ASYNCHRONOUS INFERENCE WORKFLOW (PHASE 2)
# ========================================================

def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def _safe_int(val, default=0):
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

@app.post("/applications/{application_id}/process", status_code=status.HTTP_202_ACCEPTED)
def process_application_async(
    application_id: int,
    user = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    app_record = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(404, "Application not found.")
    if user.role != "admin" and app_record.user_id != user.id:
        raise HTTPException(403, "Forbidden: You do not own this application.")

    payload = {
        "applicant_name": app_record.applicant_name or "Applicant",
        "city": app_record.city or "",
        "region": app_record.region or "",
        "age": _safe_int(app_record.age, 30),
        "dependents": _safe_int(app_record.dependents, 0),
        "gender": app_record.gender or "Male",
        "marital_status": app_record.marital_status or "Single",
        "education": app_record.education or "Graduate",
        "employment_type": app_record.employment_type or "Salaried",
        "annual_income": _safe_float(app_record.annual_income, 50000.0),
        "debt_to_income_ratio": _safe_float(app_record.debt_to_income_ratio, 0.3),
        "savings": _safe_float(app_record.savings, 10000.0),
        "bank_balance": _safe_float(app_record.bank_balance, 5000.0),
        "assets": _safe_float(app_record.assets, 100000.0),
        "credit_history": app_record.credit_history or "Good",
        "previous_loans": _safe_int(app_record.previous_loans, 0),
        "previous_defaults": _safe_int(app_record.previous_defaults, 0),
        "payment_history": _safe_float(app_record.payment_history, 0.9),
        "credit_utilization": _safe_float(app_record.credit_utilization, 0.3),
        "credit_score": _safe_float(app_record.credit_score, 700.0),
        "loan_type": app_record.loan_type or "Personal",
        "requested_loan_amount": _safe_float(app_record.loan_amount, 20000.0),
        "loan_term": _safe_int(app_record.loan_term_months, 36),
        "collateral_value": _safe_float(app_record.collateral_value, 0.0),
        "interest_rate": _safe_float(app_record.interest_rate, 8.5)
    }
    task_id = submit_application_task(application_id, payload, user.id)
    return {
        "application_id": application_id,
        "task_id": task_id,
        "status": "PENDING"
    }

@app.get("/tasks/{task_id}")
def check_task(task_id: str, user = Depends(require_authenticated_user)):
    st = get_task_status(task_id)
    if not st:
        raise HTTPException(404, "Task not found.")
    return st

# ========================================================
# REGULATORY PDF GENERATION (PHASE 2B)
# ========================================================

@app.get("/applications/{application_id}/generate-adverse-action-pdf", operation_id="get_generate_adverse_action_pdf")
@app.post("/applications/{application_id}/generate-adverse-action-pdf", operation_id="post_generate_adverse_action_pdf")
@app.get("/applications/{application_id}/adverse-action.pdf", operation_id="get_adverse_action_pdf")
@app.post("/applications/{application_id}/adverse-action.pdf", operation_id="post_adverse_action_pdf")
@limiter.limit("20/minute")
def adverse_action_pdf(
    request: Request,
    application_id: int,
    user = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    app_record = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(404, "Application not found.")
    if user.role != "admin" and app_record.user_id != user.id:
        raise HTTPException(403, "Forbidden: You do not have permission to view this notice.")

    # Reconstruct payload to get accurate adverse reasons via SHAP
    ann_income = _safe_float(app_record.annual_income, 50000.0)
    dti = _safe_float(app_record.debt_to_income_ratio, 0.3)
    payload = {
        "applicant_name": app_record.applicant_name or "Applicant",
        "annual_income": ann_income,
        "debt_to_income_ratio": dti,
        "savings": _safe_float(app_record.savings, 10000.0),
        "bank_balance": _safe_float(app_record.bank_balance, 5000.0),
        "credit_score": _safe_float(app_record.credit_score, 700.0),
        "credit_utilization": _safe_float(app_record.credit_utilization, 0.3),
        "previous_defaults": _safe_int(app_record.previous_defaults, 0),
        "payment_history": _safe_float(app_record.payment_history, 0.9),
        "loan_term": _safe_int(app_record.loan_term_months, 36),
        "requested_loan_amount": _safe_float(app_record.loan_amount, 20000.0),
        "collateral_value": _safe_float(app_record.collateral_value, 0.0),
        "interest_rate": _safe_float(app_record.interest_rate, 8.5),
        "age": _safe_int(app_record.age, 30),
        "dependents": _safe_int(app_record.dependents, 0),
        "gender": app_record.gender or "Male",
        "marital_status": app_record.marital_status or "Single",
        "education": app_record.education or "Graduate",
        "employment_type": app_record.employment_type or "Salaried",
        "assets": _safe_float(app_record.assets, 100000.0),
        "credit_history": app_record.credit_history or "Good",
        "previous_loans": _safe_int(app_record.previous_loans, 0),
        "loan_type": app_record.loan_type or "Personal",
        "monthly_income": ann_income / 12,
        "monthly_debt": (ann_income / 12) * dti
    }
    shap_info = explain_loan_approval(payload, app_record.approval_status or "Rejected", 0.1)
    reasons = shap_info.get("adverse_action_reasons", [])

    pdf_buffer = generate_adverse_action_pdf(app_record, reasons, str(app_record.applicant_name))
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=adverse_action_notice_{application_id}.pdf"}
    )

@app.get("/applications/{application_id}/generate-approval-letter", operation_id="get_generate_approval_letter")
@app.post("/applications/{application_id}/generate-approval-letter", operation_id="post_generate_approval_letter")
@app.get("/applications/{application_id}/approval-letter.pdf", operation_id="get_approval_letter_pdf")
@app.post("/applications/{application_id}/approval-letter.pdf", operation_id="post_approval_letter_pdf")
@limiter.limit("20/minute")
def approval_letter_pdf(
    request: Request,
    application_id: int,
    user = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    app_record = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(404, "Application not found.")
    if user.role != "admin" and app_record.user_id != user.id:
        raise HTTPException(403, "Forbidden: You do not have permission to view this letter.")

    terms = {
        "approved_amount": app_record.predicted_loan_amount or app_record.loan_amount,
        "interest_rate": app_record.interest_rate,
        "term_months": app_record.loan_term_months
    }
    pdf_buffer = generate_approval_letter_pdf(app_record, terms, str(app_record.applicant_name))
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=loan_approval_commitment_{application_id}.pdf"}
    )

try:
    from .routes.auth_routes import router as auth_router
    from .routes.prediction_routes import router as prediction_router
    from .routes.admin_routes import router as admin_router
    from .routes.chat_routes import router as chat_router
    from .routes.underwriter_routes import router as underwriter_router
    from .routes.model_registry_routes import router as model_registry_router
    from .routes.financial_routes import router as financial_router
    from .routes.risk_analyst_routes import router as risk_analyst_router
    app.include_router(auth_router)
    app.include_router(prediction_router)
    app.include_router(admin_router)
    app.include_router(chat_router)
    app.include_router(underwriter_router)
    app.include_router(model_registry_router)
    app.include_router(financial_router)
    app.include_router(risk_analyst_router)
except ImportError as exc:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError("Production dependencies for MySQL/auth routes are unavailable.") from exc
    logger.warning("Optional MySQL/auth routes unavailable: %s", exc)
