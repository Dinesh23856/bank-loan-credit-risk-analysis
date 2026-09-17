from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Optional, Set, Dict
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models import LoanApplication, ApplicationStatusHistory, User
from backend.services.audit_service import log_audit_event

class ApplicationStatus(str, Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    KYC_PENDING = "KYC_PENDING"
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"
    CREDIT_CHECKING = "CREDIT_CHECKING"
    AI_ASSESSED = "AI_ASSESSED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    CLOSED = "CLOSED"

# Explicit allowed state transition map
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    ApplicationStatus.DRAFT.value: {
        ApplicationStatus.SUBMITTED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.SUBMITTED.value: {
        ApplicationStatus.KYC_PENDING.value,
        ApplicationStatus.DOCUMENTS_PENDING.value,
        ApplicationStatus.CREDIT_CHECKING.value,
        ApplicationStatus.AI_ASSESSED.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.KYC_PENDING.value: {
        ApplicationStatus.DOCUMENTS_PENDING.value,
        ApplicationStatus.CREDIT_CHECKING.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.DOCUMENTS_PENDING.value: {
        ApplicationStatus.CREDIT_CHECKING.value,
        ApplicationStatus.KYC_PENDING.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.CREDIT_CHECKING.value: {
        ApplicationStatus.AI_ASSESSED.value,
        ApplicationStatus.MANUAL_REVIEW.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.AI_ASSESSED.value: {
        ApplicationStatus.APPROVED.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.MANUAL_REVIEW.value,
    },
    ApplicationStatus.MANUAL_REVIEW.value: {
        ApplicationStatus.APPROVED.value,
        ApplicationStatus.REJECTED.value,
    },
    ApplicationStatus.APPROVED.value: {
        ApplicationStatus.OFFERED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.REJECTED.value: {
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.OFFERED.value: {
        ApplicationStatus.ACCEPTED.value,
        ApplicationStatus.REJECTED.value,
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.ACCEPTED.value: {
        ApplicationStatus.CLOSED.value,
    },
    ApplicationStatus.CLOSED.value: set(),  # Terminal state
}

# Role permissions on state transitions
CUSTOMER_ALLOWED_TRANSITIONS: Set[tuple[str, str]] = {
    (ApplicationStatus.DRAFT.value, ApplicationStatus.SUBMITTED.value),
    (ApplicationStatus.DRAFT.value, ApplicationStatus.CLOSED.value),
    (ApplicationStatus.OFFERED.value, ApplicationStatus.ACCEPTED.value),
    (ApplicationStatus.OFFERED.value, ApplicationStatus.REJECTED.value),
}

def normalize_role_str(role: Optional[str]) -> str:
    r = (role or "").strip().upper()
    if r in ("ADMIN", "ADMINISTRATOR"):
        return "ADMIN"
    if r in ("UNDERWRITER",):
        return "UNDERWRITER"
    if r in ("RISK_ANALYST", "ANALYST"):
        return "RISK_ANALYST"
    return "CUSTOMER"

def validate_transition(
    current_status: str,
    target_status: str,
    user_role: str,
    reason: Optional[str] = None
) -> None:
    """
    Validates whether the transition from current_status to target_status
    is permissible under the state machine and user role authorization.
    """
    curr = current_status.upper()
    target = target_status.upper()
    norm_role = normalize_role_str(user_role)

    # 1. State machine transition check
    allowed_targets = ALLOWED_TRANSITIONS.get(curr)
    if allowed_targets is None or target not in allowed_targets:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition: Cannot transition application from '{curr}' to '{target}'."
        )

    # 2. Customer permission check
    if norm_role == "CUSTOMER":
        if (curr, target) not in CUSTOMER_ALLOWED_TRANSITIONS:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Customer role is not permitted to transition application to '{target}'."
            )

    # 3. Underwriter review requirement
    if curr == ApplicationStatus.MANUAL_REVIEW.value and target in (ApplicationStatus.APPROVED.value, ApplicationStatus.REJECTED.value):
        if norm_role not in ("UNDERWRITER", "ADMIN"):
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Only an UNDERWRITER or ADMIN may review and decide a loan in MANUAL_REVIEW."
            )
        if not reason or len(reason.strip()) < 5:
            raise HTTPException(
                status_code=400,
                detail="A detailed decision reason (minimum 5 characters) is required for underwriting reviews."
            )

def sync_legacy_approval_status(new_status: str) -> str:
    """
    Synchronizes legacy approval_status with new 12-state workflow status
    to guarantee zero regression for legacy views and tests.
    """
    s = new_status.upper()
    if s == ApplicationStatus.APPROVED.value:
        return "Approved"
    if s == ApplicationStatus.REJECTED.value:
        return "Rejected"
    if s == ApplicationStatus.MANUAL_REVIEW.value:
        return "Manual Review"
    if s in (ApplicationStatus.DRAFT.value, ApplicationStatus.SUBMITTED.value, ApplicationStatus.KYC_PENDING.value,
            ApplicationStatus.DOCUMENTS_PENDING.value, ApplicationStatus.CREDIT_CHECKING.value, ApplicationStatus.AI_ASSESSED.value):
        return "Pending"
    if s == ApplicationStatus.OFFERED.value:
        return "Offered"
    if s == ApplicationStatus.ACCEPTED.value:
        return "Accepted"
    if s == ApplicationStatus.CLOSED.value:
        return "Closed"
    return new_status

def transition_application(
    db: Session,
    application: LoanApplication,
    target_status: str,
    user: User,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    underwriter_decision: Optional[str] = None,
    reviewer_comments: Optional[str] = None
) -> ApplicationStatusHistory:
    """
    Executes a validated state transition:
    - Verifies allowed transitions and role authorization
    - Updates application.status and legacy application.approval_status
    - Records an immutable history log in application_status_history
    - Writes an audit log record to audit_logs
    """
    curr_status = application.status or (
        "APPROVED" if application.approval_status == "Approved" else
        "REJECTED" if application.approval_status == "Rejected" else
        "SUBMITTED"
    )
    target = target_status.upper()
    user_role = normalize_role_str(user.role)

    validate_transition(curr_status, target, user_role, reason=reason)

    # If this is an underwriter review transition from MANUAL_REVIEW
    if curr_status == ApplicationStatus.MANUAL_REVIEW.value and target in ("APPROVED", "REJECTED"):
        application.underwriter_decision = target
        application.underwriter_reason = reason
        application.reviewer_comments = reviewer_comments
        application.reviewer_id = user.id
        application.reviewer_role = user_role
        application.reviewed_at = datetime.utcnow()

    # Apply status changes
    application.status = target
    application.approval_status = sync_legacy_approval_status(target)

    # Create status history entry
    now = datetime.utcnow()
    history_entry = ApplicationStatusHistory(
        application_id=application.id,
        previous_status=curr_status,
        new_status=target,
        changed_by=user.id,
        changed_by_role=user_role,
        timestamp=now,
        reason=reason or f"Transitioned to {target}"
    )
    db.add(history_entry)

    # Log to persistent audit log
    log_audit_event(
        db=db,
        action="APPLICATION_STATUS_CHANGED",
        user=user,
        role=user_role,
        resource_type="loan_application",
        resource_id=str(application.id),
        ip_address=ip_address,
        reason=reason,
        before_value=curr_status,
        after_value=target,
        metadata={
            "application_id": application.id,
            "previous_status": curr_status,
            "new_status": target,
            "changed_by": user.id,
            "role": user_role
        }
    )

    db.commit()
    db.refresh(application)
    db.refresh(history_entry)
    return history_entry
