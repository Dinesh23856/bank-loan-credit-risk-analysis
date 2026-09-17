from __future__ import annotations
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, ModelLog
from backend.dependencies import require_risk_analyst, normalize_role
from backend.services.analytics_service import (
    get_portfolio_overview,
    get_workflow_status_breakdown,
    get_approval_rejection_analysis,
    get_credit_score_analysis,
    get_loan_amount_analysis,
    get_risk_distribution,
    get_time_trends,
    export_analytics_csv
)
from backend.services.drift_service import drift_summary
from backend.services.fairness_service import calculate_fairness_metrics
from backend.services.audit_service import log_audit_event
from backend.schemas import (
    PortfolioOverviewResponse,
    WorkflowStatusBreakdownResponse,
    ApprovalRejectionAnalysisResponse,
    CreditScoreAnalysisResponse,
    LoanAmountAnalysisResponse,
    RiskDistributionResponse,
    TimeTrendsResponse,
    FairnessReportResponse
)
from backend.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk-analyst", tags=["Risk Analytics & Monitoring"])

MODEL_SHA256_HASHES = {
    "loan_amount": "963bff7f4317a6d373fd0aa0e324f698a32cabee2d7a4d12d9fdef5048fcabe6",
    "loan_approval": "b70d0fd7ef583b3492e0ac57acf4cea5b0689844ad6615a3cbd6a46466c02f26",
    "credit_score": "897948653b3982012b327746955a79b8487834f2bb0dcefa02dd0b9f3a553f59",
    "credit_risk": "044aa75d7741d1bb6b448d3795b145350cacc65c8c6e598cff6e6df219d55922"
}

@router.get("/overview", response_model=PortfolioOverviewResponse)
def portfolio_overview_endpoint(
    request: Request,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Computes 10 core portfolio & risk metrics.
    Protected by server-side RBAC for RISK_ANALYST and ADMIN roles.
    """
    has_filters = bool(date_from or date_to or risk_level or region)
    action_type = "RISK_ANALYTICS_FILTER" if has_filters else "RISK_ANALYTICS_VIEW"
    client_ip = request.client.host if request.client else None

    log_audit_event(
        db=db,
        action=action_type,
        user=user,
        role=normalize_role(user.role),
        resource_type="analytics",
        resource_id="portfolio_overview",
        ip_address=client_ip,
        metadata={
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "risk_level": risk_level,
            "region": region
        }
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    return get_portfolio_overview(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

@router.get("/workflow-status", response_model=WorkflowStatusBreakdownResponse)
def workflow_status_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Breakdown of counts and percentages across all 12 guarded workflow states.
    """
    return get_workflow_status_breakdown(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

@router.get("/approval-analysis", response_model=ApprovalRejectionAnalysisResponse)
def approval_rejection_analysis_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Cross-tabulates approval/rejection rates against risk level, credit score, loan amount, and employment.
    """
    return get_approval_rejection_analysis(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

@router.get("/credit-score-analysis", response_model=CreditScoreAnalysisResponse)
def credit_score_analysis_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Provides summary statistics and distribution histograms for predicted vs bureau credit scores.
    """
    return get_credit_score_analysis(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

@router.get("/loan-amount-analysis", response_model=LoanAmountAnalysisResponse)
def loan_amount_analysis_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Requested and approved loan amounts, tier distributions, and risk correlations.
    """
    return get_loan_amount_analysis(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

@router.get("/risk-distribution", response_model=RiskDistributionResponse)
def risk_distribution_endpoint(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Low, Medium, High risk distribution with approval rate correlation.
    """
    return get_risk_distribution(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

@router.get("/model-performance")
def model_performance_endpoint(
    request: Request,
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Retrieves offline evaluation benchmarks, real confusion matrices,
    and live operational inference statistics from model_logs.
    """
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="MODEL_METRICS_VIEW",
        user=user,
        role=normalize_role(user.role),
        resource_type="model_governance",
        resource_id="model_performance_benchmarks",
        ip_address=client_ip
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    metrics_path = Path(__file__).resolve().parents[2] / "reports" / "training_metrics.json"
    data = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {"modules": {}}

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
def drift_endpoint(
    request: Request,
    window_days: Optional[int] = Query(None, ge=1, le=365),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Data drift monitoring using PSI and KS statistics against loan_data.csv baseline.
    """
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="DRIFT_VIEW",
        user=user,
        role=normalize_role(user.role),
        resource_type="analytics",
        resource_id="drift_summary",
        ip_address=client_ip,
        metadata={"window_days": window_days}
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    return drift_summary(db, window_days=window_days)

@router.get("/fairness", response_model=FairnessReportResponse)
def fairness_endpoint(
    request: Request,
    attribute: str = Query("gender"),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Demographic parity and disparate impact ratio (DIR) evaluation.
    Heuristic indicator only — not a legal determination.
    """
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="FAIRNESS_VIEW",
        user=user,
        role=normalize_role(user.role),
        resource_type="analytics",
        resource_id=f"fairness_{attribute}",
        ip_address=client_ip,
        metadata={"attribute": attribute}
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    return calculate_fairness_metrics(db, attribute=attribute)

@router.get("/time-trends", response_model=TimeTrendsResponse)
def time_trends_endpoint(
    interval: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=7, le=365),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Time-series trend points for applications, approvals, rejections, and risk distribution.
    """
    return get_time_trends(
        db=db,
        interval=interval,
        days=days,
        risk_level=risk_level,
        region=region
    )

@router.get("/export-csv")
@limiter.limit("10/minute")
def export_csv_endpoint(
    request: Request,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    risk_level: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Exports summary portfolio analytics and anonymized non-PII records to CSV.
    Zero passwords, hashes, tokens, or encryption keys are exported.
    """
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="ANALYTICS_EXPORT",
        user=user,
        role=normalize_role(user.role),
        resource_type="analytics",
        resource_id="portfolio_export_csv",
        ip_address=client_ip,
        metadata={
            "format": "csv",
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "risk_level": risk_level,
            "region": region
        }
    )
    try:
        db.commit()
    except Exception:
        db.rollback()

    csv_data = export_analytics_csv(
        db=db,
        date_from=date_from,
        date_to=date_to,
        risk_level=risk_level,
        region=region
    )

    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"risk_portfolio_analytics_{timestamp_str}.csv"

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
