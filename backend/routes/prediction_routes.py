import json
import hashlib
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import LoanApplication, ModelLog, ApplicationStatusHistory
from ..schemas import (
    LoanApplicationRequest,
    LoanPredictionResponse,
    ApplicationListResponse,
    ApplicationResponse,
    RiskEvaluationResponse,
    CounterfactualRequest,
    CounterfactualResponse,
    StatusHistoryResponse,
    WorkflowTransitionRequest
)
from ..dependencies import require_authenticated_user, normalize_role
from ..services.prediction_service import run_prediction, run_counterfactual_simulation
from ..services.workflow_service import transition_application, sync_legacy_approval_status
from ..services.audit_service import log_audit_event
from ..limiter import limiter

router = APIRouter(tags=["Predictions"])

_MODEL_VERSIONS = {
    "loan_approval": "b70d0fd7",
    "loan_amount": "963bff7f",
    "credit_score": "89794865",
    "credit_risk": "044aa75d",
}

def _save(db, user, x, result, elapsed, client_ip=None, user_agent=None):
    raw_status = result["loan_status"]
    prob = result.get("approval_probability")

    # Workflow status determination:
    # If borderline (0.40 <= prob <= 0.60): MANUAL_REVIEW
    if prob is not None and 0.40 <= prob <= 0.60:
        initial_status = "MANUAL_REVIEW"
        approval_status = "Manual Review"
    elif raw_status == "Approved":
        initial_status = "APPROVED"
        approval_status = "Approved"
    else:
        initial_status = "REJECTED"
        approval_status = "Rejected"

    application = LoanApplication(
        user_id=user.id, applicant_name=x.applicant_name, age=x.age, city=x.city, region=x.region,
        annual_income=x.annual_income, loan_amount=x.requested_loan_amount, loan_term_months=x.loan_term,
        interest_rate=x.interest_rate, credit_score=x.credit_score, debt_to_income_ratio=x.debt_to_income_ratio,
        employment_type=x.employment_type, education=x.education, marital_status=x.marital_status,
        dependents=x.dependents, savings=x.savings, bank_balance=x.bank_balance, assets=x.assets,
        previous_loans=x.previous_loans, previous_defaults=x.previous_defaults, payment_history=x.payment_history,
        credit_utilization=x.credit_utilization, gender=x.gender, credit_history=x.credit_history,
        loan_type=x.loan_type, collateral_value=x.collateral_value,
        approval_status=approval_status, predicted_loan_amount=result["approved_loan_amount"],
        predicted_credit_score=result["credit_score"], risk_level=result["risk_level"],
        status=initial_status,
        ai_decision=raw_status,
        ai_probability=prob
    )
    db.add(application)
    db.flush()
    
    entries = [
        ("loan_approval", {"status": result["loan_status"], "probability": result["approval_probability"]}),
        ("loan_amount", result["approved_loan_amount"]),
        ("credit_score", result["credit_score"]),
        ("credit_risk", {"risk_level": result["risk_level"], "probabilities": result["risk_probabilities"]}),
    ]
    for name, prediction in entries:
        db.add(ModelLog(
            user_id=user.id,
            application_id=application.id,
            model_name=name,
            model_version=_MODEL_VERSIONS.get(name, "v2.0"),
            decision=result["loan_status"] if name == "loan_approval" else None,
            status="SUCCESS",
            explanation_generated=1 if name == "loan_approval" else 0,
            prediction=json.dumps(prediction),
            inference_time_ms=elapsed,
            processing_duration_ms=elapsed
        ))

    # Initial transition history entry
    now = datetime.utcnow()
    role_norm = normalize_role(user.role)
    prob_str = f"{prob:.4f}" if prob is not None else "N/A"
    db.add(ApplicationStatusHistory(
        application_id=application.id,
        previous_status="SUBMITTED",
        new_status=initial_status,
        changed_by=user.id,
        changed_by_role=role_norm,
        timestamp=now,
        reason=f"AI credit assessment complete: {raw_status} (score: {result['credit_score']}, prob: {prob_str})"
    ))

    # Audit events
    log_audit_event(
        db=db,
        action="APPLICATION_CREATED",
        user=user,
        role=role_norm,
        resource_type="loan_application",
        resource_id=str(application.id),
        ip_address=client_ip,
        user_agent=user_agent,
        status="SUCCESS",
        metadata={
            "applicant_name": x.applicant_name,
            "loan_amount": x.requested_loan_amount,
            "loan_type": x.loan_type
        }
    )
    log_audit_event(
        db=db,
        action="APPLICATION_SUBMITTED",
        user=user,
        role=role_norm,
        resource_type="loan_application",
        resource_id=str(application.id),
        ip_address=client_ip,
        user_agent=user_agent,
        status="SUCCESS",
        before_value="DRAFT",
        after_value=initial_status,
        metadata={
            "ai_decision": raw_status,
            "ai_probability": prob,
            "status": initial_status
        }
    )

    db.commit()
    db.refresh(application)
    return application

@router.post("/predict/loan", response_model=LoanPredictionResponse)
@limiter.limit("60/minute")
def loan(request: Request, x: LoanApplicationRequest, user=Depends(require_authenticated_user), db: Session = Depends(get_db)):
    try:
        result, elapsed = run_prediction(x.model_dump(), include_explanations=True)
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        _save(db, user, x, result, elapsed, client_ip=client_ip, user_agent=user_agent)
        return {"approved": result["loan_status"] == "Approved", **result}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Unable to process the prediction: {exc}") from exc

@router.post("/predict/risk", response_model=RiskEvaluationResponse)
@limiter.limit("60/minute")
def risk(request: Request, x: LoanApplicationRequest, user=Depends(require_authenticated_user), db: Session = Depends(get_db)):
    try:
        result, elapsed = run_prediction(x.model_dump(), include_explanations=False)
        db.add(ModelLog(
            user_id=user.id,
            application_id=None,
            model_name="credit_risk",
            model_version=_MODEL_VERSIONS.get("credit_risk", "v2.0"),
            decision=result["risk_level"],
            status="SUCCESS",
            explanation_generated=0,
            prediction=json.dumps({"risk_level": result["risk_level"], "probabilities": result["risk_probabilities"]}),
            inference_time_ms=elapsed,
            processing_duration_ms=elapsed
        ))
        db.commit()
        return {k: result[k] for k in ("credit_score", "risk_level", "risk_probabilities")}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, "Unable to process the risk prediction.") from exc

@router.post("/predict/counterfactual", response_model=CounterfactualResponse)
@limiter.limit("60/minute")
def counterfactual(request: Request, req: CounterfactualRequest, user=Depends(require_authenticated_user)):
    try:
        applicant = req.applicant_data.model_dump()
        proposed = {
            "requested_loan_amount": req.requested_loan_amount,
            "loan_term": req.loan_term,
            "collateral_value": req.collateral_value,
            "savings": req.savings,
            "debt_to_income_ratio": req.debt_to_income_ratio,
        }
        res = run_counterfactual_simulation(applicant, proposed)
        return res
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Counterfactual simulation failed: {exc}") from exc

@router.get("/applications", response_model=ApplicationListResponse)
def applications(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 user=Depends(require_authenticated_user), db: Session = Depends(get_db)):
    q = db.query(LoanApplication).filter(LoanApplication.user_id == user.id)
    total = q.count()
    items = q.order_by(LoanApplication.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.get("/applications/{application_id}", response_model=ApplicationResponse)
def application(application_id: int, user=Depends(require_authenticated_user), db: Session = Depends(get_db)):
    query = db.query(LoanApplication).filter(LoanApplication.id == application_id)
    norm_role = normalize_role(user.role)
    if norm_role not in ("UNDERWRITER", "ADMIN"):
        query = query.filter(LoanApplication.user_id == user.id)
    item = query.first()
    if not item:
        raise HTTPException(404, "Application not found.")

    approval_prob = item.ai_probability
    if approval_prob is None:
        approval_log = db.query(ModelLog).filter(
            ModelLog.application_id == application_id,
            ModelLog.model_name == "loan_approval"
        ).order_by(ModelLog.created_at.desc(), ModelLog.id.desc()).first()
        if approval_log and approval_log.prediction:
            try:
                pred_data = json.loads(approval_log.prediction)
                if isinstance(pred_data, dict):
                    approval_prob = pred_data.get("probability") or pred_data.get("approval_probability")
                elif isinstance(pred_data, (int, float)):
                    approval_prob = float(pred_data)
            except Exception:
                approval_prob = None

    resp = ApplicationResponse.model_validate(item)
    resp.approval_probability = approval_prob
    if resp.ai_probability is None:
        resp.ai_probability = approval_prob
    if resp.ai_decision is None:
        resp.ai_decision = item.approval_status
    if resp.status is None:
        resp.status = (
            "APPROVED" if item.approval_status == "Approved" else
            "REJECTED" if item.approval_status == "Rejected" else
            "MANUAL_REVIEW" if item.approval_status == "Manual Review" else
            "SUBMITTED"
        )
    return resp

@router.get("/applications/{application_id}/history", response_model=list[StatusHistoryResponse])
def application_history(application_id: int, user=Depends(require_authenticated_user), db: Session = Depends(get_db)):
    """
    Authenticated status history timeline endpoint.
    BOLA protection: User owns application OR role is UNDERWRITER/ADMIN.
    """
    app_record = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(404, f"Application #{application_id} not found.")

    norm_role = normalize_role(user.role)
    if norm_role not in ("UNDERWRITER", "ADMIN") and app_record.user_id != user.id:
        raise HTTPException(403, "Forbidden: You do not have permission to view this application's history.")

    history_records = (
        db.query(ApplicationStatusHistory)
        .filter(ApplicationStatusHistory.application_id == application_id)
        .order_by(ApplicationStatusHistory.timestamp.asc(), ApplicationStatusHistory.id.asc())
        .all()
    )
    return history_records

@router.post("/applications/{application_id}/transition", response_model=ApplicationResponse)
def transition_application_endpoint(
    application_id: int,
    req_body: WorkflowTransitionRequest,
    req: Request,
    user=Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """
    Workflow state transition endpoint:
    - Enforces state machine allowed transitions
    - Validates role permissions (e.g. customer cannot approve/reject)
    - Records persistent status history and audit log
    """
    app_record = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
    if not app_record:
        raise HTTPException(404, f"Application #{application_id} not found.")

    norm_role = normalize_role(user.role)
    if norm_role not in ("UNDERWRITER", "ADMIN") and app_record.user_id != user.id:
        raise HTTPException(403, "Forbidden: You do not have permission to transition this application.")

    client_ip = req.client.host if req.client else None
    transition_application(
        db=db,
        application=app_record,
        target_status=req_body.target_status,
        user=user,
        reason=req_body.reason,
        ip_address=client_ip,
        reviewer_comments=req_body.reviewer_comments
    )
    db.commit()
    db.refresh(app_record)

    resp = ApplicationResponse.model_validate(app_record)
    resp.approval_probability = app_record.ai_probability
    return resp

