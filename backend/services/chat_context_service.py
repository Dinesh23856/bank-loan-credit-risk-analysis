from __future__ import annotations
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..models import User, LoanApplication, ModelLog, ChatUsageLog
from .shap_service import explain_loan_approval
from .prediction_service import run_counterfactual_simulation
from .analytics_service import summary as get_analytics_summary
from .drift_service import drift_summary
from .fairness_service import calculate_fairness_metrics

logger = logging.getLogger(__name__)

def _safe_float(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default

def _safe_int(val, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

# ========================================================
# USER CONTEXT RETRIEVAL TOOLS (Strict Server-Side Auth)
# ========================================================

def get_user_application(db: Session, user_id: int, application_id: int, is_admin: bool = False) -> Dict[str, Any]:
    """Retrieve full application data verifying caller ownership."""
    query = db.query(LoanApplication).filter(LoanApplication.id == application_id)
    if not is_admin:
        query = query.filter(LoanApplication.user_id == user_id)
    app = query.first()
    if not app:
        raise PermissionError(f"Application #{application_id} not found or access denied.")

    return {
        "id": app.id,
        "applicant_name": str(app.applicant_name or "Applicant"),
        "city": app.city or "",
        "region": app.region or "",
        "age": _safe_int(app.age, 30),
        "gender": app.gender or "Male",
        "marital_status": app.marital_status or "Single",
        "dependents": _safe_int(app.dependents, 0),
        "education": app.education or "Graduate",
        "employment_type": app.employment_type or "Salaried",
        "annual_income": _safe_float(app.annual_income, 50000.0),
        "loan_amount": _safe_float(app.loan_amount, 20000.0),
        "loan_term_months": _safe_int(app.loan_term_months, 36),
        "interest_rate": _safe_float(app.interest_rate, 8.5),
        "credit_score": _safe_float(app.credit_score, 700.0),
        "debt_to_income_ratio": _safe_float(app.debt_to_income_ratio, 0.3),
        "savings": _safe_float(app.savings, 10000.0),
        "bank_balance": _safe_float(app.bank_balance, 5000.0),
        "assets": _safe_float(app.assets, 100000.0),
        "previous_loans": _safe_int(app.previous_loans, 0),
        "previous_defaults": _safe_int(app.previous_defaults, 0),
        "payment_history": _safe_float(app.payment_history, 0.9),
        "credit_utilization": _safe_float(app.credit_utilization, 0.3),
        "credit_history": app.credit_history or "Good",
        "loan_type": app.loan_type or "Personal",
        "collateral_value": _safe_float(app.collateral_value, 0.0),
        "approval_status": app.approval_status or "Reviewed",
        "predicted_loan_amount": _safe_float(app.predicted_loan_amount, app.loan_amount),
        "predicted_credit_score": _safe_float(app.predicted_credit_score, app.credit_score),
        "risk_level": app.risk_level or "Low",
        "created_at": app.created_at.isoformat() if app.created_at else None
    }

def get_user_application_summary(db: Session, user_id: int, application_id: int, is_admin: bool = False) -> Dict[str, Any]:
    """Provide a concise financial summary of the target application."""
    data = get_user_application(db, user_id, application_id, is_admin=is_admin)
    return {
        "id": data["id"],
        "approval_status": data["approval_status"],
        "loan_amount": data["loan_amount"],
        "predicted_loan_amount": data["predicted_loan_amount"],
        "annual_income": data["annual_income"],
        "debt_to_income_ratio": data["debt_to_income_ratio"],
        "credit_score": data["credit_score"],
        "predicted_credit_score": data["predicted_credit_score"],
        "risk_level": data["risk_level"],
        "loan_term_months": data["loan_term_months"]
    }

def get_user_application_history(db: Session, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieve recent application history for the authenticated user."""
    apps = db.query(LoanApplication).filter(
        LoanApplication.user_id == user_id
    ).order_by(LoanApplication.created_at.desc()).limit(limit).all()

    return [
        {
            "id": a.id,
            "created_at": a.created_at.strftime("%Y-%m-%d") if a.created_at else "",
            "loan_amount": _safe_float(a.loan_amount),
            "approval_status": a.approval_status or "Pending",
            "risk_level": a.risk_level or "Unknown"
        }
        for a in apps
    ]

def get_user_prediction(db: Session, user_id: int, application_id: int, is_admin: bool = False) -> Dict[str, Any]:
    """Retrieve verified machine learning predictions for an application."""
    app = get_user_application(db, user_id, application_id, is_admin=is_admin)
    return {
        "application_id": app["id"],
        "approval_status": app["approval_status"],
        "predicted_loan_amount": app["predicted_loan_amount"],
        "predicted_credit_score": app["predicted_credit_score"],
        "risk_level": app["risk_level"]
    }

def get_user_shap_explanation(db: Session, user_id: int, application_id: int, is_admin: bool = False) -> Dict[str, Any]:
    """Generate exact TreeSHAP feature attributions using the cached TreeExplainer."""
    app = get_user_application(db, user_id, application_id, is_admin=is_admin)
    ann_income = app["annual_income"]
    dti = app["debt_to_income_ratio"]

    payload = {
        "applicant_name": app["applicant_name"],
        "annual_income": ann_income,
        "debt_to_income_ratio": dti,
        "savings": app["savings"],
        "bank_balance": app["bank_balance"],
        "credit_score": app["credit_score"],
        "credit_utilization": app["credit_utilization"],
        "previous_defaults": app["previous_defaults"],
        "payment_history": app["payment_history"],
        "loan_term": app["loan_term_months"],
        "requested_loan_amount": app["loan_amount"],
        "collateral_value": app["collateral_value"],
        "interest_rate": app["interest_rate"],
        "age": app["age"],
        "dependents": app["dependents"],
        "gender": app["gender"],
        "marital_status": app["marital_status"],
        "education": app["education"],
        "employment_type": app["employment_type"],
        "assets": app["assets"],
        "credit_history": app["credit_history"],
        "previous_loans": app["previous_loans"],
        "loan_type": app["loan_type"],
        "monthly_income": ann_income / 12,
        "monthly_debt": (ann_income / 12) * dti
    }

    shap_info = explain_loan_approval(payload, app["approval_status"], 0.5)
    return {
        "application_id": app["id"],
        "approval_status": app["approval_status"],
        "base_value": shap_info.get("base_value", 0.5),
        "top_positive_factors": shap_info.get("positive_factors", [])[:5],
        "top_negative_factors": shap_info.get("negative_factors", [])[:5],
        "adverse_action_reasons": shap_info.get("adverse_action_reasons", [])
    }

def get_user_adverse_action_reasons(db: Session, user_id: int, application_id: int, is_admin: bool = False) -> List[Dict[str, Any]]:
    """Retrieve regulatory adverse action reasons for rejected applications."""
    info = get_user_shap_explanation(db, user_id, application_id, is_admin=is_admin)
    return info.get("adverse_action_reasons", [])

def get_user_what_if_result(
    db: Session,
    user_id: int,
    application_id: int,
    proposed_changes: Dict[str, Any],
    is_admin: bool = False
) -> Dict[str, Any]:
    """Run counterfactual recourse simulation, strictly guarding protected demographic attributes."""
    app = get_user_application(db, user_id, application_id, is_admin=is_admin)

    # Discard any attempted alterations to protected demographic attributes
    safe_proposed = {}
    allowed_keys = {
        "requested_loan_amount",
        "loan_term",
        "collateral_value",
        "savings",
        "debt_to_income_ratio"
    }
    for k in allowed_keys:
        if k in proposed_changes:
            safe_proposed[k] = proposed_changes[k]

    applicant_data = {
        "applicant_name": app["applicant_name"],
        "city": app["city"],
        "region": app["region"],
        "age": app["age"],
        "dependents": app["dependents"],
        "gender": app["gender"],
        "marital_status": app["marital_status"],
        "education": app["education"],
        "employment_type": app["employment_type"],
        "annual_income": app["annual_income"],
        "debt_to_income_ratio": app["debt_to_income_ratio"],
        "savings": app["savings"],
        "bank_balance": app["bank_balance"],
        "assets": app["assets"],
        "credit_history": app["credit_history"],
        "previous_loans": app["previous_loans"],
        "previous_defaults": app["previous_defaults"],
        "payment_history": app["payment_history"],
        "credit_utilization": app["credit_utilization"],
        "credit_score": app["credit_score"],
        "loan_type": app["loan_type"],
        "requested_loan_amount": app["loan_amount"],
        "loan_term": app["loan_term_months"],
        "collateral_value": app["collateral_value"],
        "interest_rate": app["interest_rate"]
    }

    result = run_counterfactual_simulation(applicant_data, safe_proposed)
    return {
        "application_id": app["id"],
        "original_status": result.get("original_status"),
        "simulated_status": result.get("simulated_status"),
        "original_probability": result.get("original_probability"),
        "simulated_probability": result.get("simulated_probability"),
        "status_changed": result.get("status_changed"),
        "applied_changes": safe_proposed
    }

# ========================================================
# ADMIN CONTEXT RETRIEVAL TOOLS (Strict RBAC Authorization)
# ========================================================

def get_admin_metrics(db: Session, user: User) -> Dict[str, Any]:
    """Retrieve executive KPI metrics. Authorized for admins only."""
    if user.role != "admin":
        raise PermissionError("Access denied: Administrative privileges required.")
    return get_analytics_summary(db)

def get_admin_drift_summary(db: Session, user: User, window_days: Optional[int] = None) -> Dict[str, Any]:
    """Retrieve drift detection metrics. Authorized for admins only."""
    if user.role != "admin":
        raise PermissionError("Access denied: Administrative privileges required.")
    return drift_summary(db, window_days=window_days)

def get_admin_fairness_summary(db: Session, user: User, attribute: str = "gender") -> Dict[str, Any]:
    """Retrieve demographic fairness metrics. Authorized for admins only."""
    if user.role != "admin":
        raise PermissionError("Access denied: Administrative privileges required.")
    return calculate_fairness_metrics(db, attribute=attribute)

def get_admin_chat_usage_metrics(db: Session, user: User) -> Dict[str, Any]:
    """Retrieve chatbot operational telemetry. Authorized for admins only."""
    if user.role != "admin":
        raise PermissionError("Access denied: Administrative privileges required.")

    total_chats = db.query(func.count(ChatUsageLog.id)).scalar() or 0
    success_count = db.query(func.count(ChatUsageLog.id)).filter(ChatUsageLog.status == "SUCCESS").scalar() or 0
    degraded_count = db.query(func.count(ChatUsageLog.id)).filter(ChatUsageLog.status == "DEGRADED").scalar() or 0
    avg_latency = db.query(func.avg(ChatUsageLog.latency_ms)).scalar() or 0.0

    return {
        "total_requests": total_chats,
        "successful_requests": success_count,
        "degraded_requests": degraded_count,
        "average_latency_ms": round(float(avg_latency), 2),
        "service_availability": round((success_count + degraded_count) / total_chats * 100, 1) if total_chats else 100.0
    }
