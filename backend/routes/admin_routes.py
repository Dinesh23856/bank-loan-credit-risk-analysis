import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, LoanApplication, ModelLog, AuditLog
from ..dependencies import require_admin, normalize_role
from ..services.analytics_service import summary
from ..services.drift_service import drift_summary
from ..services.fairness_service import calculate_fairness_metrics
from ..services.audit_service import log_audit_event
from ..schemas import (
    AdminUserResponse,
    AdminUserListResponse,
    ApplicationListResponse,
    FairnessReportResponse,
    AuditLogResponse,
    AuditLogListResponse,
    UserRoleUpdateRequest
)

router = APIRouter(prefix="/admin", tags=["Admin"])

MODEL_SHA256_HASHES = {
    "loan_approval": "b70d0fd7ef583b3492e0ac57acf4cea5b0689844ad6615a3cbd6a46466c02f26",
    "loan_amount": "963bff7f4317a6d373fd0aa0e324f698a32cabee2d7a4d12d9fdef5048fcabe6",
    "credit_score": "897948653b3982012b327746955a79b8487834f2bb0dcefa02dd0b9f3a553f59",
    "credit_risk": "044aa75d7741d1bb6b448d3795b145350cacc65c8c6e598cff6e6df219d55922"
}

@router.get("/summary")
def admin_summary(user=Depends(require_admin), db: Session=Depends(get_db)):
    return summary(db)

@router.get("/users", response_model=AdminUserListResponse)
def users(page: int=Query(1, ge=1), page_size: int=Query(20, ge=1, le=100),
          user=Depends(require_admin), db: Session=Depends(get_db)):
    q = db.query(User)
    total = q.count()
    rows = q.order_by(User.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    items = [{"id": u.id, "name": u.name, "email": u.email, "role": u.role,
              "created_at": u.created_at,
              "application_count": db.query(func.count(LoanApplication.id)).filter(
                  LoanApplication.user_id == u.id).scalar() or 0} for u in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.put("/users/{id}/role", response_model=AdminUserResponse)
def update_user_role(
    id: int,
    req_body: UserRoleUpdateRequest,
    req: Request,
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Administrative role assignment mechanism.
    Permits assigning CUSTOMER, UNDERWRITER, RISK_ANALYST, or ADMIN roles with persistent audit logging.
    """
    target_user = db.get(User, id)
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User #{id} not found.")

    old_role = target_user.role
    new_role = normalize_role(req_body.role)

    target_user.role = new_role
    db.flush()

    client_ip = req.client.host if req.client else None
    log_audit_event(
        db=db,
        action="ROLE_CHANGED",
        user=user,
        role=normalize_role(user.role),
        resource_type="user",
        resource_id=str(target_user.id),
        ip_address=client_ip,
        reason=req_body.reason or f"Role updated from {old_role} to {new_role}",
        before_value=old_role,
        after_value=new_role,
        metadata={
            "target_user_id": target_user.id,
            "target_email": target_user.email,
            "old_role": old_role,
            "new_role": new_role,
            "admin_id": user.id
        }
    )

    db.commit()
    db.refresh(target_user)

    app_count = db.query(func.count(LoanApplication.id)).filter(LoanApplication.user_id == target_user.id).scalar() or 0
    return {
        "id": target_user.id,
        "name": target_user.name,
        "email": target_user.email,
        "role": target_user.role,
        "created_at": target_user.created_at,
        "application_count": app_count
    }

@router.get("/audit-logs", response_model=AuditLogListResponse)
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    role: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    user=Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Administrative audit log explorer with multi-criteria filtering:
    - date_from / date_to
    - user_id
    - role
    - action
    - resource_type
    """
    q = db.query(AuditLog)

    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if role:
        q = q.filter(AuditLog.role == role.upper())
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if date_from:
        q = q.filter(AuditLog.timestamp >= date_from)
    if date_to:
        effective_date_to = (
            date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            if (date_to.hour == 0 and date_to.minute == 0 and date_to.second == 0 and date_to.microsecond == 0)
            else date_to
        )
        q = q.filter(AuditLog.timestamp <= effective_date_to)

    total = q.count()
    rows = q.order_by(desc(AuditLog.timestamp)).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for r in rows:
        items.append(AuditLogResponse(
            id=r.id,
            timestamp=r.timestamp,
            user_id=r.user_id,
            role=r.role,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            ip_address=r.ip_address,
            metadata_json=r.metadata_json,
            reason=r.reason,
            before_value=r.before_value,
            after_value=r.after_value
        ))

    return AuditLogListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/applications", response_model=ApplicationListResponse)
def apps(page: int=Query(1, ge=1), page_size: int=Query(20, ge=1, le=100),
          search: str|None=Query(None, max_length=120), status: str|None=Query(None),
          region: str|None=Query(None, max_length=100),
          date_from: datetime|None=Query(None), date_to: datetime|None=Query(None),
          user=Depends(require_admin), db: Session=Depends(get_db)):
    q = db.query(LoanApplication)
    if search:
        term = search.strip()
        q = q.filter(LoanApplication.applicant_name.ilike(f"%{term}%"))
    if status:
        q = q.filter(LoanApplication.approval_status == status)
    if region:
        q = q.filter(LoanApplication.region == region)
    if date_from:
        q = q.filter(LoanApplication.created_at >= date_from)
    if date_to:
        effective_date_to = (
            date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            if (date_to.hour == 0 and date_to.minute == 0 and date_to.second == 0 and date_to.microsecond == 0)
            else date_to
        )
        q = q.filter(LoanApplication.created_at <= effective_date_to)
    total = q.count()
    items = q.order_by(LoanApplication.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.get("/metrics")
def metrics(user=Depends(require_admin), db: Session=Depends(get_db)):
    path = Path(__file__).resolve().parents[2] / "reports" / "training_metrics.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"modules": {}}
    
    # Calculate live operational latency and counts from model_logs
    logs = db.query(ModelLog).all()
    latencies = [l.inference_time_ms for l in logs if l.inference_time_ms is not None]
    
    avg_latency = float(sum(latencies) / len(latencies)) if latencies else 0.0
    p95_latency = float(__import__("numpy").percentile(latencies, 95)) if latencies else 0.0
    p99_latency = float(__import__("numpy").percentile(latencies, 99)) if latencies else 0.0

    total_predictions = len(logs)
    failure_count = sum(1 for l in logs if getattr(l, "status", "") == "FAILED")

    data["operational"] = {
        "model_hashes": MODEL_SHA256_HASHES,
        "total_predictions": total_predictions,
        "failure_count": failure_count,
        "average_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "p99_latency_ms": round(p99_latency, 2),
    }
    return data

@router.get("/drift")
def drift(window_days: int | None = Query(None, ge=1, le=365), user=Depends(require_admin), db: Session=Depends(get_db)):
    return drift_summary(db, window_days=window_days)

@router.get("/fairness", response_model=FairnessReportResponse)
def fairness(attribute: str = Query("gender", pattern="^(gender|marital_status|education|employment_type)$"),
             user=Depends(require_admin), db: Session=Depends(get_db)):
    return calculate_fairness_metrics(db, attribute=attribute)

@router.get("/chat/analytics")
def admin_chat_analytics(user=Depends(require_admin), db: Session=Depends(get_db)):
    from ..services.chat_context_service import get_admin_chat_usage_metrics
    return get_admin_chat_usage_metrics(db, user)
