from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import LoanApplication, User
from backend.dependencies import require_authenticated_user, normalize_role
from backend.schemas import (
    EMICalculatorRequest,
    EMICalculatorResponse,
    AmortizationResponse,
    FinancialSummaryResponse,
    KFSResponse
)
from backend.services.financial_service import (
    calculate_emi,
    generate_amortization_schedule,
    get_application_financial_summary,
    generate_kfs_data
)
from backend.services.pdf_service import generate_kfs_pdf
from backend.services.audit_service import log_audit_event
from backend.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Financial Calculations & Academic KFS"])

def _get_authorized_application(application_id: int, user: User, db: Session) -> LoanApplication:
    """
    Enforces server-side BOLA/IDOR protection:
    - CUSTOMER role can only access their own application.
    - UNDERWRITER, RISK_ANALYST, and ADMIN roles can access any application.
    """
    app_record = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(status_code=404, detail=f"Application #{application_id} not found.")

    norm_role = normalize_role(user.role)
    if norm_role not in ("UNDERWRITER", "RISK_ANALYST", "ADMIN") and app_record.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have authorization to view this application's financial records."
        )
    return app_record

@router.post("/financial/calculate-emi", response_model=EMICalculatorResponse)
def calculate_emi_endpoint(
    req_body: EMICalculatorRequest,
    user: User = Depends(require_authenticated_user)
):
    """
    Standalone deterministic EMI calculation simulator for reducing-balance loans.
    Zero ML/LLM involvement. Fully validated numeric inputs.
    """
    return calculate_emi(
        principal=req_body.principal,
        annual_interest_rate=req_body.annual_interest_rate,
        loan_term_months=req_body.loan_term_months
    )

@router.get("/applications/{application_id}/financial-summary", response_model=FinancialSummaryResponse)
def application_financial_summary_endpoint(
    application_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves the official financial terms and computed EMI for a specific application.
    Enforces server-side BOLA/IDOR protection.
    """
    app_record = _get_authorized_application(application_id, user, db)
    return get_application_financial_summary(app_record)

@router.get("/applications/{application_id}/amortization", response_model=AmortizationResponse)
def application_amortization_endpoint(
    application_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Generates the month-by-month amortization schedule for a specific application.
    Absorbs final-period rounding so closing balance reaches exactly 0.00.
    Enforces server-side BOLA/IDOR protection.
    """
    app_record = _get_authorized_application(application_id, user, db)
    summary = get_application_financial_summary(app_record)
    schedule_data = generate_amortization_schedule(
        principal=summary["loan_amount"],
        annual_interest_rate=summary["interest_rate"],
        loan_term_months=summary["loan_term_months"]
    )
    schedule_data["application_id"] = app_record.id
    return schedule_data

@router.get("/applications/{application_id}/kfs", response_model=KFSResponse)
def application_kfs_json_endpoint(
    application_id: int,
    req: Request,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Generates structured Academic/Demo Key Fact Statement (KFS) JSON disclosure.
    Strictly rejected for REJECTED applications (returns HTTP 400).
    Enforces server-side BOLA/IDOR protection and logs audit event.
    """
    app_record = _get_authorized_application(application_id, user, db)
    applicant_name = str(app_record.applicant_name)
    kfs_data = generate_kfs_data(app_record, applicant_name)

    client_ip = req.client.host if req.client else None
    log_audit_event(
        db=db,
        action="KFS_GENERATED",
        user=user,
        resource_type="application",
        resource_id=str(application_id),
        ip_address=client_ip,
        reason="Academic/Demo KFS JSON generated for eligible application.",
        metadata={
            "application_id": application_id,
            "loan_amount": kfs_data["loan_amount"],
            "emi": kfs_data["emi"],
            "loan_term_months": kfs_data["loan_term_months"],
            "format": "JSON"
        }
    )
    db.commit()
    return kfs_data

@router.get("/applications/{application_id}/kfs/pdf", operation_id="get_application_kfs_pdf")
@router.get("/applications/{application_id}/kfs.pdf", operation_id="get_application_kfs_dot_pdf")
@limiter.limit("20/minute")
def application_kfs_pdf_endpoint(
    request: Request,
    application_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Streams an Academic/Demo Key Fact Statement (KFS) PDF document directly in-memory.
    Never exposes internal filesystem paths or stores documents publicly.
    Strictly rejected for REJECTED applications (returns HTTP 400).
    Enforces server-side BOLA/IDOR protection and rate limiting.
    """
    app_record = _get_authorized_application(application_id, user, db)
    applicant_name = str(app_record.applicant_name)
    kfs_data = generate_kfs_data(app_record, applicant_name)

    schedule_data = generate_amortization_schedule(
        principal=kfs_data["loan_amount"],
        annual_interest_rate=kfs_data["interest_rate"],
        loan_term_months=kfs_data["loan_term_months"]
    )

    pdf_buffer = generate_kfs_pdf(
        application=app_record,
        applicant_name=applicant_name,
        kfs_data=kfs_data,
        schedule=schedule_data["schedule"]
    )

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="KFS_GENERATED",
        user=user,
        resource_type="application",
        resource_id=str(application_id),
        ip_address=client_ip,
        reason="Academic/Demo KFS PDF generated and streamed.",
        metadata={
            "application_id": application_id,
            "loan_amount": kfs_data["loan_amount"],
            "emi": kfs_data["emi"],
            "loan_term_months": kfs_data["loan_term_months"],
            "format": "PDF"
        }
    )
    db.commit()

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=kfs_loan_summary_{application_id}.pdf"
        }
    )
