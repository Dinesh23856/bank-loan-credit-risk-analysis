from __future__ import annotations
import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models import LoanApplication, User, ModelLog
from backend.schemas import (
    ApplicationResponse,
    UnderwriterQueueListResponse,
    UnderwriterQueueItemResponse,
    UnderwriterReviewRequest
)
from backend.dependencies import require_underwriter, normalize_role
from backend.services.workflow_service import (
    ApplicationStatus,
    transition_application
)
from backend.services.shap_service import explain_loan_approval
from backend.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/underwriter", tags=["underwriter"])

@router.get("/queue", response_model=UnderwriterQueueListResponse)
def get_underwriter_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_underwriter)
):
    """
    Retrieves applications eligible for underwriter inspection.
    By default filters for applications in 'MANUAL_REVIEW'.
    """
    q = db.query(LoanApplication)
    target_status = (status_filter or ApplicationStatus.MANUAL_REVIEW.value).upper()
    q = q.filter(LoanApplication.status == target_status)

    total = q.count()
    items = q.order_by(desc(LoanApplication.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    queue_items = []
    for app in items:
        # Retrieve actual probability from ai_probability or model_logs
        prob = app.ai_probability
        if prob is None:
            latest_log = db.query(ModelLog).filter(
                ModelLog.application_id == app.id,
                ModelLog.model_name == "loan_approval"
            ).order_by(desc(ModelLog.id)).first()
            if latest_log:
                try:
                    payload = json.loads(latest_log.prediction) if isinstance(latest_log.prediction, str) else latest_log.prediction
                    prob = payload.get("approval_probability") or payload.get("probability")
                except Exception:
                    pass

        queue_items.append(UnderwriterQueueItemResponse(
            id=app.id,
            applicant_name=app.applicant_name or "Applicant",
            loan_amount=app.loan_amount,
            credit_score=app.credit_score,
            predicted_credit_score=app.predicted_credit_score,
            risk_level=app.risk_level,
            approval_probability=prob,
            ai_decision=app.ai_decision or app.approval_status,
            status=app.status or "MANUAL_REVIEW",
            created_at=app.created_at
        ))

    return UnderwriterQueueListResponse(
        items=queue_items,
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/applications/{id}", response_model=ApplicationResponse)
def get_underwriter_application_detail(
    id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_underwriter)
):
    """
    Underwriter detailed inspection of an application, including status history,
    model metrics, and underwriter decision state.
    """
    app = db.get(LoanApplication, id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Loan application #{id} not found.")

    prob = app.ai_probability
    if prob is None:
        latest_log = db.query(ModelLog).filter(
            ModelLog.application_id == app.id,
            ModelLog.model_name == "loan_approval"
        ).order_by(desc(ModelLog.id)).first()
        if latest_log:
            try:
                payload = json.loads(latest_log.prediction) if isinstance(latest_log.prediction, str) else latest_log.prediction
                prob = payload.get("approval_probability") or payload.get("probability")
            except Exception:
                pass

    return ApplicationResponse(
        id=app.id,
        applicant_name=app.applicant_name or "Applicant",
        city=app.city,
        region=app.region,
        loan_amount=app.loan_amount,
        approval_status=app.approval_status,
        predicted_loan_amount=app.predicted_loan_amount,
        credit_score=app.credit_score,
        predicted_credit_score=app.predicted_credit_score,
        risk_level=app.risk_level,
        created_at=app.created_at,
        approval_probability=prob,
        status=app.status,
        ai_decision=app.ai_decision or app.approval_status,
        ai_probability=prob,
        underwriter_decision=app.underwriter_decision,
        underwriter_reason=app.underwriter_reason,
        reviewer_comments=app.reviewer_comments,
        reviewer_id=app.reviewer_id,
        reviewer_role=app.reviewer_role,
        reviewed_at=app.reviewed_at,
        status_history=app.status_history or []
    )

@router.post("/applications/{id}/review", response_model=ApplicationResponse)
def review_loan_application(
    id: int,
    request_data: UnderwriterReviewRequest,
    req: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_underwriter)
):
    """
    Human-in-the-loop Underwriter review action:
    - Verifies the application is currently in MANUAL_REVIEW
    - Transitions application status to APPROVED or REJECTED
    - Preserves the original AI decision and model probability
    - Stores underwriter decision, mandatory reason, and reviewer metadata
    - Creates persistent history entry and audit log record
    """
    app = db.get(LoanApplication, id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Loan application #{id} not found.")

    curr_status = app.status or (
        "APPROVED" if app.approval_status == "Approved" else
        "REJECTED" if app.approval_status == "Rejected" else
        "SUBMITTED"
    )

    if curr_status != ApplicationStatus.MANUAL_REVIEW.value:
        raise HTTPException(
            status_code=400,
            detail=f"Application #{id} is currently in '{curr_status}', not 'MANUAL_REVIEW'. Only applications in manual review can be decided by an underwriter."
        )

    client_ip = req.client.host if req.client else None
    action_type = f"UNDERWRITER_{request_data.decision}"

    # Execute workflow transition
    transition_application(
        db=db,
        application=app,
        target_status=request_data.decision,
        user=user,
        reason=request_data.reason,
        ip_address=client_ip,
        underwriter_decision=request_data.decision,
        reviewer_comments=request_data.reviewer_comments
    )

    # Specific underwriter audit record
    log_audit_event(
        db=db,
        action=action_type,
        user=user,
        role=normalize_role(user.role),
        resource_type="loan_application",
        resource_id=str(app.id),
        ip_address=client_ip,
        reason=request_data.reason,
        before_value=ApplicationStatus.MANUAL_REVIEW.value,
        after_value=request_data.decision,
        metadata={
            "application_id": app.id,
            "decision": request_data.decision,
            "ai_decision": app.ai_decision,
            "ai_probability": app.ai_probability,
            "reviewer_comments": request_data.reviewer_comments
        }
    )

    db.commit()
    db.refresh(app)

    return ApplicationResponse(
        id=app.id,
        applicant_name=app.applicant_name,
        city=app.city,
        region=app.region,
        loan_amount=app.loan_amount,
        approval_status=app.approval_status,
        predicted_loan_amount=app.predicted_loan_amount,
        credit_score=app.credit_score,
        predicted_credit_score=app.predicted_credit_score,
        risk_level=app.risk_level,
        created_at=app.created_at,
        approval_probability=app.ai_probability,
        status=app.status,
        ai_decision=app.ai_decision,
        ai_probability=app.ai_probability,
        underwriter_decision=app.underwriter_decision,
        underwriter_reason=app.underwriter_reason,
        reviewer_comments=app.reviewer_comments,
        reviewer_id=app.reviewer_id,
        reviewer_role=app.reviewer_role,
        reviewed_at=app.reviewed_at,
        status_history=app.status_history or []
    )
