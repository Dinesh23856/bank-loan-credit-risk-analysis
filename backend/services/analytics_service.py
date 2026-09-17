from __future__ import annotations
import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import numpy as np
from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session
from ..models import User, LoanApplication, ModelLog

ALL_WORKFLOW_STATES = [
    "DRAFT",
    "SUBMITTED",
    "KYC_PENDING",
    "DOCUMENTS_PENDING",
    "CREDIT_CHECKING",
    "AI_ASSESSED",
    "MANUAL_REVIEW",
    "APPROVED",
    "REJECTED",
    "OFFERED",
    "ACCEPTED",
    "CLOSED"
]

def _apply_filters(
    query,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None,
    decision: Optional[str] = None,
    status: Optional[str] = None
):
    if date_from:
        query = query.filter(LoanApplication.created_at >= date_from)
    if date_to:
        effective_to = (
            date_to.replace(hour=23, minute=59, second=59, microsecond=999999)
            if (date_to.hour == 0 and date_to.minute == 0 and date_to.second == 0 and date_to.microsecond == 0)
            else date_to
        )
        query = query.filter(LoanApplication.created_at <= effective_to)
    if risk_level:
        query = query.filter(func.lower(LoanApplication.risk_level) == risk_level.strip().lower())
    if region:
        query = query.filter(func.lower(LoanApplication.region) == region.strip().lower())
    if decision:
        query = query.filter(func.lower(LoanApplication.approval_status) == decision.strip().lower())
    if status:
        query = query.filter(func.lower(LoanApplication.status) == status.strip().lower())
    return query

def summary(db: Session) -> Dict[str, Any]:
    """Legacy summary endpoint preserving backward compatibility."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.query(func.count(LoanApplication.id)).scalar() or 0
    approved = db.query(func.count(LoanApplication.id)).filter(LoanApplication.approval_status == "Approved").scalar() or 0
    amount = db.query(func.coalesce(func.sum(LoanApplication.predicted_loan_amount), 0)).scalar() or 0
    risk_rows = db.query(LoanApplication.risk_level, func.count(LoanApplication.id)).group_by(LoanApplication.risk_level).all()
    region_rows = db.query(LoanApplication.region, func.count(LoanApplication.id)).group_by(LoanApplication.region).order_by(func.count(LoanApplication.id).desc()).limit(10).all()
    daily_rows = []
    for days_ago in range(13, -1, -1):
        day = (now - timedelta(days=days_ago)).date()
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        count = db.query(func.count(LoanApplication.id)).filter(
            LoanApplication.created_at >= start, LoanApplication.created_at < end
        ).scalar() or 0
        daily_rows.append({"date": day.isoformat(), "applications": count})
    return {
        "total_users": db.query(func.count(User.id)).scalar() or 0,
        "total_applications": total,
        "approved": approved,
        "rejected": total - approved,
        "approval_rate": round(approved / total, 4) if total else 0,
        "total_predicted_loan_amount": float(amount),
        "average_predicted_amount": float(amount / approved) if approved else 0,
        "predictions_today": db.query(func.count(ModelLog.id)).filter(ModelLog.created_at >= start_today).scalar() or 0,
        "predictions_this_month": db.query(func.count(ModelLog.id)).filter(ModelLog.created_at >= start_month).scalar() or 0,
        "risk_distribution": [{"risk_level": k or "Unknown", "count": v} for k, v in risk_rows],
        "regional_distribution": [{"region": k or "Unknown", "count": v} for k, v in region_rows],
        "applications_over_time": daily_rows,
    }

def get_portfolio_overview(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes the 10 core portfolio and risk KPIs required by Phase 4.
    Safely handles empty datasets without division by zero.
    """
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.all()

    total_applications = len(apps)
    if total_applications == 0:
        return {
            "total_applications": 0,
            "approved_applications": 0,
            "rejected_applications": 0,
            "approval_rate": 0.0,
            "average_requested_loan_amount": 0.0,
            "average_approved_loan_amount": 0.0,
            "average_predicted_credit_score": 0.0,
            "high_risk_applicant_count": 0,
            "medium_risk_applicant_count": 0,
            "low_risk_applicant_count": 0,
        }

    approved_apps = [a for a in apps if (a.approval_status or "").title() == "Approved"]
    rejected_apps = [a for a in apps if (a.approval_status or "").title() == "Rejected"]

    approved_count = len(approved_apps)
    rejected_count = len(rejected_apps)
    approval_rate = round(approved_count / total_applications, 4) if total_applications > 0 else 0.0

    # Loan amounts
    requested_amounts = [float(a.loan_amount) for a in apps if a.loan_amount is not None]
    avg_requested = round(float(sum(requested_amounts) / len(requested_amounts)), 2) if requested_amounts else 0.0

    approved_amounts = [float(a.predicted_loan_amount) for a in approved_apps if a.predicted_loan_amount is not None and a.predicted_loan_amount > 0]
    if not approved_amounts:
        # Fallback to requested amount on approved loans if predicted is null
        approved_amounts = [float(a.loan_amount) for a in approved_apps if a.loan_amount is not None]
    avg_approved = round(float(sum(approved_amounts) / len(approved_amounts)), 2) if approved_amounts else 0.0

    # Predicted credit scores (EncryptedFloat auto-decrypts)
    predicted_scores = []
    for a in apps:
        sc = getattr(a, "predicted_credit_score", None)
        if sc is not None:
            try:
                predicted_scores.append(float(sc))
            except (ValueError, TypeError):
                pass
    avg_predicted_score = round(float(sum(predicted_scores) / len(predicted_scores)), 1) if predicted_scores else 0.0

    # Risk level counts
    high_risk_count = sum(1 for a in apps if (a.risk_level or "").title() == "High")
    med_risk_count = sum(1 for a in apps if (a.risk_level or "").title() == "Medium")
    low_risk_count = sum(1 for a in apps if (a.risk_level or "").title() == "Low")

    return {
        "total_applications": total_applications,
        "approved_applications": approved_count,
        "rejected_applications": rejected_count,
        "approval_rate": approval_rate,
        "average_requested_loan_amount": avg_requested,
        "average_approved_loan_amount": avg_approved,
        "average_predicted_credit_score": avg_predicted_score,
        "high_risk_applicant_count": high_risk_count,
        "medium_risk_applicant_count": med_risk_count,
        "low_risk_applicant_count": low_risk_count,
    }

def get_workflow_status_breakdown(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes exact counts and percentages across all 12 guarded workflow states.
    """
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.all()
    total = len(apps)

    status_counts = {st: 0 for st in ALL_WORKFLOW_STATES}
    for a in apps:
        curr_status = (a.status or "SUBMITTED").upper()
        if curr_status in status_counts:
            status_counts[curr_status] += 1
        else:
            # Map legacy or unknown to nearest equivalent
            if curr_status == "PENDING":
                status_counts["SUBMITTED"] += 1
            else:
                status_counts[curr_status] = status_counts.get(curr_status, 0) + 1

    breakdown = []
    for st, cnt in status_counts.items():
        percentage = round((cnt / total) * 100, 2) if total > 0 else 0.0
        breakdown.append({
            "status": st,
            "count": cnt,
            "percentage": percentage
        })

    return {
        "total_applications": total,
        "breakdown": breakdown
    }

def get_approval_rejection_analysis(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cross-tabulates approval and rejection rates against:
    - Risk levels (Low, Medium, High)
    - Credit score bands (<580, 580-669, 670-739, 740-799, 800+)
    - Loan amount tiers (<100k, 100k-250k, 250k-500k, 500k-1M, >1M)
    - Employment categories
    """
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.all()
    total = len(apps)

    approved_total = sum(1 for a in apps if (a.approval_status or "").title() == "Approved")
    rejected_total = sum(1 for a in apps if (a.approval_status or "").title() == "Rejected")

    def _calc_rates(app_subset):
        sub_total = len(app_subset)
        if sub_total == 0:
            return {"total": 0, "approved": 0, "rejected": 0, "approval_rate": 0.0, "rejection_rate": 0.0}
        appr = sum(1 for a in app_subset if (a.approval_status or "").title() == "Approved")
        rej = sum(1 for a in app_subset if (a.approval_status or "").title() == "Rejected")
        return {
            "total": sub_total,
            "approved": appr,
            "rejected": rej,
            "approval_rate": round(appr / sub_total, 4),
            "rejection_rate": round(rej / sub_total, 4)
        }

    # 1. By Risk Level
    by_risk = {}
    for r_tier in ["Low", "Medium", "High"]:
        subset = [a for a in apps if (a.risk_level or "").title() == r_tier]
        by_risk[r_tier] = _calc_rates(subset)

    # 2. By Credit Score Band (Bureau / Entered)
    score_bins = [
        ("< 580", lambda s: s < 580),
        ("580-669", lambda s: 580 <= s <= 669),
        ("670-739", lambda s: 670 <= s <= 739),
        ("740-799", lambda s: 740 <= s <= 799),
        ("800+", lambda s: s >= 800),
    ]
    by_score = {}
    for label, fn in score_bins:
        subset = [a for a in apps if a.credit_score is not None and fn(float(a.credit_score))]
        by_score[label] = _calc_rates(subset)

    # 3. By Loan Amount Range
    loan_bins = [
        ("< 100k", lambda p: p < 100_000),
        ("100k-250k", lambda p: 100_000 <= p <= 250_000),
        ("250k-500k", lambda p: 250_000 < p <= 500_000),
        ("500k-1M", lambda p: 500_000 < p <= 1_000_000),
        ("> 1M", lambda p: p > 1_000_000),
    ]
    by_loan_amount = {}
    for label, fn in loan_bins:
        subset = [a for a in apps if a.loan_amount is not None and fn(float(a.loan_amount))]
        by_loan_amount[label] = _calc_rates(subset)

    # 4. By Employment Type
    emp_types = sorted(list(set((a.employment_type or "Unknown").title() for a in apps)))
    by_employment = {}
    for emp in emp_types:
        subset = [a for a in apps if (a.employment_type or "Unknown").title() == emp]
        by_employment[emp] = _calc_rates(subset)

    return {
        "overall": {
            "total": total,
            "approved": approved_total,
            "rejected": rejected_total,
            "approval_rate": round(approved_total / total, 4) if total > 0 else 0.0,
            "rejection_rate": round(rejected_total / total, 4) if total > 0 else 0.0
        },
        "by_risk_level": by_risk,
        "by_credit_score": by_score,
        "by_loan_amount": by_loan_amount,
        "by_employment_type": by_employment
    }

def get_credit_score_analysis(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes summary metrics and distribution histograms for both:
    1. Predicted Credit Score (AI model output)
    2. Applicant / Bureau Credit Score
    Categorized into standard academic bands.
    """
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.all()

    pred_scores = []
    bureau_scores = []

    for a in apps:
        if a.credit_score is not None:
            bureau_scores.append(float(a.credit_score))
        sc = getattr(a, "predicted_credit_score", None)
        if sc is not None:
            try:
                pred_scores.append(float(sc))
            except (ValueError, TypeError):
                pass

    def _stats(arr):
        if not arr:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "median": 0.0}
        return {
            "count": len(arr),
            "mean": round(float(np.mean(arr)), 1),
            "min": round(float(np.min(arr)), 1),
            "max": round(float(np.max(arr)), 1),
            "median": round(float(np.median(arr)), 1)
        }

    bands_def = [
        ("< 580", "Poor", lambda x: x < 580),
        ("580-669", "Fair", lambda x: 580 <= x <= 669),
        ("670-739", "Good", lambda x: 670 <= x <= 739),
        ("740-799", "Very Good", lambda x: 740 <= x <= 799),
        ("800+", "Exceptional", lambda x: x >= 800)
    ]

    def _bucket_distribution(arr):
        total_items = len(arr)
        buckets = []
        for band_name, quality, condition in bands_def:
            c = sum(1 for val in arr if condition(val))
            pct = round((c / total_items) * 100, 2) if total_items > 0 else 0.0
            buckets.append({
                "band": band_name,
                "label": quality,
                "count": c,
                "percentage": pct
            })
        return buckets

    return {
        "predicted_credit_score": {
            "label": "Model Predicted Credit Score",
            "stats": _stats(pred_scores),
            "distribution": _bucket_distribution(pred_scores)
        },
        "bureau_credit_score": {
            "label": "Applicant Stored / Bureau Credit Score",
            "stats": _stats(bureau_scores),
            "distribution": _bucket_distribution(bureau_scores)
        }
    }

def get_loan_amount_analysis(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes requested and approved loan amount statistics, size tier distributions,
    and relationships with risk level and approval determination.
    """
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.all()

    req_amounts = [float(a.loan_amount) for a in apps if a.loan_amount is not None]
    appr_amounts = [float(a.predicted_loan_amount) for a in apps if a.predicted_loan_amount is not None and a.predicted_loan_amount > 0 and (a.approval_status or "").title() == "Approved"]

    def _stats(arr):
        if not arr:
            return {"count": 0, "mean": 0.0, "min": 0.0, "max": 0.0, "total": 0.0}
        return {
            "count": len(arr),
            "mean": round(float(np.mean(arr)), 2),
            "min": round(float(np.min(arr)), 2),
            "max": round(float(np.max(arr)), 2),
            "total": round(float(np.sum(arr)), 2)
        }

    # Distribution across tiers
    tiers = [
        ("< 100k", "< ₹100,000", lambda x: x < 100_000),
        ("100k-250k", "₹100,000 - ₹250,000", lambda x: 100_000 <= x <= 250_000),
        ("250k-500k", "₹250,000 - ₹500,000", lambda x: 250_000 < x <= 500_000),
        ("500k-1M", "₹500,000 - ₹1,000,000", lambda x: 500_000 < x <= 1_000_000),
        ("> 1M", "> ₹1,000,000", lambda x: x > 1_000_000)
    ]
    tot_req = len(req_amounts)
    dist_tiers = []
    for code, label, cond in tiers:
        cnt = sum(1 for val in req_amounts if cond(val))
        pct = round((cnt / tot_req) * 100, 2) if tot_req > 0 else 0.0
        dist_tiers.append({
            "tier": code,
            "label": label,
            "count": cnt,
            "percentage": pct
        })

    # Risk level vs Average requested amount
    risk_relation = []
    for r in ["Low", "Medium", "High"]:
        r_apps = [a for a in apps if (a.risk_level or "").title() == r]
        r_req = [float(a.loan_amount) for a in r_apps if a.loan_amount is not None]
        r_appr = [float(a.predicted_loan_amount) for a in r_apps if a.predicted_loan_amount is not None and a.predicted_loan_amount > 0 and (a.approval_status or "").title() == "Approved"]
        risk_relation.append({
            "risk_level": r,
            "count": len(r_apps),
            "avg_requested": round(float(np.mean(r_req)), 2) if r_req else 0.0,
            "avg_approved": round(float(np.mean(r_appr)), 2) if r_appr else 0.0
        })

    return {
        "requested_amount_stats": _stats(req_amounts),
        "approved_amount_stats": _stats(appr_amounts),
        "distribution_tiers": dist_tiers,
        "risk_relationship": risk_relation
    }

def get_risk_distribution(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes Low, Medium, High risk counts, percentages,
    and cross-tabulation with approval/rejection rates.
    """
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.all()
    total = len(apps)

    tiers = ["Low", "Medium", "High"]
    counts = {t: 0 for t in tiers}
    approved_map = {t: 0 for t in tiers}
    rejected_map = {t: 0 for t in tiers}

    for a in apps:
        r = (a.risk_level or "Medium").title()
        if r not in counts:
            r = "Medium"
        counts[r] += 1
        if (a.approval_status or "").title() == "Approved":
            approved_map[r] += 1
        elif (a.approval_status or "").title() == "Rejected":
            rejected_map[r] += 1

    distribution = []
    for t in tiers:
        cnt = counts[t]
        pct = round((cnt / total) * 100, 2) if total > 0 else 0.0
        appr = approved_map[t]
        rej = rejected_map[t]
        appr_rate = round(appr / cnt, 4) if cnt > 0 else 0.0
        distribution.append({
            "risk_level": t,
            "count": cnt,
            "percentage": pct,
            "approved": appr,
            "rejected": rej,
            "approval_rate": appr_rate
        })

    return {
        "total_applications": total,
        "distribution": distribution
    }

def get_time_trends(
    db: Session,
    interval: str = "daily",
    days: int = 30,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates time-series trend points for applications, approvals, rejections,
    and risk levels over the past N days.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_time = now - timedelta(days=days)

    q = _apply_filters(
        db.query(LoanApplication).filter(LoanApplication.created_at >= start_time),
        risk_level=risk_level,
        region=region
    )
    apps = q.order_by(LoanApplication.created_at.asc()).all()

    # Bucket by date
    timeline = {}
    for days_ago in range(days - 1, -1, -1):
        dt_str = (now - timedelta(days=days_ago)).date().isoformat()
        timeline[dt_str] = {
            "date": dt_str,
            "applications": 0,
            "approved": 0,
            "rejected": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0
        }

    for a in apps:
        if a.created_at:
            dt_str = a.created_at.date().isoformat()
            if dt_str in timeline:
                timeline[dt_str]["applications"] += 1
                if (a.approval_status or "").title() == "Approved":
                    timeline[dt_str]["approved"] += 1
                elif (a.approval_status or "").title() == "Rejected":
                    timeline[dt_str]["rejected"] += 1

                r = (a.risk_level or "").title()
                if r == "High":
                    timeline[dt_str]["high_risk"] += 1
                elif r == "Medium":
                    timeline[dt_str]["medium_risk"] += 1
                elif r == "Low":
                    timeline[dt_str]["low_risk"] += 1

    return {
        "interval": interval,
        "days": days,
        "points": list(timeline.values())
    }

def export_analytics_csv(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    risk_level: Optional[str] = None,
    region: Optional[str] = None
) -> str:
    """
    Generates a secure, non-PII CSV export of aggregate metrics and application records.
    Strictly excludes passwords, hashes, tokens, secret keys, or sensitive PII.
    """
    overview = get_portfolio_overview(db, date_from, date_to, risk_level, region)
    q = _apply_filters(db.query(LoanApplication), date_from, date_to, risk_level, region)
    apps = q.order_by(LoanApplication.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Header / Meta
    writer.writerow(["# BANK LOAN APPROVAL & CREDIT RISK ANALYSIS - PORTFOLIO ANALYTICS EXPORT"])
    writer.writerow(["# Export Timestamp (UTC)", datetime.utcnow().isoformat() + "Z"])
    writer.writerow(["# Academic Notice", "ACADEMIC/DEMO FINTECH PLATFORM - NOT A LEGAL BANKING LEDGER"])
    writer.writerow([])

    # Aggregate KPI Summary Section
    writer.writerow(["=== PORTFOLIO AGGREGATE SUMMARY ==="])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Total Applications Evaluated", overview["total_applications"]])
    writer.writerow(["Approved Applications", overview["approved_applications"]])
    writer.writerow(["Rejected Applications", overview["rejected_applications"]])
    writer.writerow(["Portfolio Approval Rate", f"{(overview['approval_rate'] * 100):.2f}%"])
    writer.writerow(["Average Requested Loan Amount (INR)", f"₹{overview['average_requested_loan_amount']:,.2f}"])
    writer.writerow(["Average Approved Loan Amount (INR)", f"₹{overview['average_approved_loan_amount']:,.2f}"])
    writer.writerow(["Average Predicted Credit Score", overview["average_predicted_credit_score"]])
    writer.writerow(["High Risk Applicants", overview["high_risk_applicant_count"]])
    writer.writerow(["Medium Risk Applicants", overview["medium_risk_applicant_count"]])
    writer.writerow(["Low Risk Applicants", overview["low_risk_applicant_count"]])
    writer.writerow([])

    # Application Records Section (Non-PII only)
    writer.writerow(["=== ANONYMIZED APPLICATION PORTFOLIO RECORDS ==="])
    writer.writerow([
        "Application ID",
        "Submission Date (UTC)",
        "Region",
        "Requested Loan Amount (INR)",
        "Loan Term (Months)",
        "Interest Rate (%)",
        "Bureau Credit Score",
        "Model Predicted Score",
        "Evaluated Risk Level",
        "Workflow Status",
        "Final Decision"
    ])

    for a in apps:
        sc = getattr(a, "predicted_credit_score", None)
        pred_sc_str = f"{float(sc):.0f}" if sc is not None else "N/A"
        writer.writerow([
            f"APP-{a.id:06d}",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "N/A",
            a.region or "Unknown",
            f"{float(a.loan_amount):,.2f}" if a.loan_amount is not None else "0.00",
            a.loan_term_months or 36,
            f"{float(a.interest_rate):.2f}" if a.interest_rate is not None else "10.00",
            f"{float(a.credit_score):.0f}" if a.credit_score is not None else "N/A",
            pred_sc_str,
            a.risk_level or "Medium",
            a.status or "SUBMITTED",
            a.approval_status or "Pending"
        ])

    return output.getvalue()

