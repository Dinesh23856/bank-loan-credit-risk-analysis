from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta
from typing import Iterable, Optional
import math
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from ..models import LoanApplication

ROOT = Path(__file__).resolve().parents[2]

NUMERIC_PAIRS = {
    "age": ("age", "age"),
    "annual_income": ("annual_income", "annual_income"),
    "debt_to_income_ratio": ("debt_to_income_ratio", "debt_to_income_ratio"),
    "savings": ("savings", "savings"),
    "bank_balance": ("bank_balance", "bank_balance"),
    "assets": ("assets", "assets"),
    "previous_loans": ("previous_loans", "previous_loans"),
    "previous_defaults": ("previous_defaults", "previous_defaults"),
    "payment_history": ("payment_history", "payment_history"),
    "credit_utilization": ("credit_utilization", "credit_utilization"),
    "credit_score": ("credit_score", "credit_score"),
    "requested_loan_amount": ("requested_loan_amount", "loan_amount"),
    "loan_term": ("loan_term", "loan_term_months"),
    "collateral_value": ("collateral_value", "collateral_value"),
    "interest_rate": ("interest_rate", "interest_rate"),
}

def _psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = expected[np.isfinite(expected)]
    actual = actual[np.isfinite(actual)]
    if len(expected) < 2 or len(actual) < 2:
        return 0.0
    edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return 0.0
    edges[0] = -np.inf
    edges[-1] = np.inf
    e = np.histogram(expected, bins=edges)[0].astype(float)
    a = np.histogram(actual, bins=edges)[0].astype(float)
    e = np.clip(e / max(e.sum(), 1.0), 1e-6, None)
    a = np.clip(a / max(a.sum(), 1.0), 1e-6, None)
    return float(np.sum((a - e) * np.log(a / e)))

def _ks(expected: np.ndarray, actual: np.ndarray) -> float:
    expected = np.sort(expected[np.isfinite(expected)])
    actual = np.sort(actual[np.isfinite(actual)])
    if len(expected) == 0 or len(actual) == 0:
        return 0.0
    values = np.sort(np.unique(np.concatenate([expected, actual])))
    ecdf_e = np.searchsorted(expected, values, side="right") / len(expected)
    ecdf_a = np.searchsorted(actual, values, side="right") / len(actual)
    return float(np.max(np.abs(ecdf_e - ecdf_a)))

def _status(psi: float, ks: float) -> str:
    if psi >= 0.20 or ks >= 0.20:
        return "high"
    if psi >= 0.10 or ks >= 0.10:
        return "moderate"
    return "stable"

def drift_summary(db: Session, window_days: Optional[int] = None) -> dict:
    baseline_path = ROOT / "data" / "raw" / "loan_data.csv"
    if not baseline_path.exists():
        return {
            "status": "unavailable",
            "message": "Baseline dataset is unavailable.",
            "features": [],
        }

    baseline = pd.read_csv(baseline_path)
    
    query = db.query(LoanApplication)
    period_start = None
    if window_days:
        period_start = datetime.utcnow() - timedelta(days=window_days)
        query = query.filter(LoanApplication.created_at >= period_start)
    
    rows = query.order_by(LoanApplication.created_at.asc()).all()
    current = pd.DataFrame([{
        "age": r.age,
        "annual_income": r.annual_income,
        "debt_to_income_ratio": r.debt_to_income_ratio,
        "savings": r.savings,
        "bank_balance": r.bank_balance,
        "assets": r.assets,
        "previous_loans": r.previous_loans,
        "previous_defaults": r.previous_defaults,
        "payment_history": r.payment_history,
        "credit_utilization": r.credit_utilization,
        "credit_score": r.credit_score,
        "loan_amount": r.loan_amount,
        "loan_term_months": r.loan_term_months,
        "collateral_value": r.collateral_value,
        "interest_rate": r.interest_rate,
    } for r in rows])

    features = []
    for name, (bcol, ccol) in NUMERIC_PAIRS.items():
        if bcol not in baseline.columns or ccol not in current.columns:
            continue
        b = pd.to_numeric(baseline[bcol], errors="coerce").dropna().to_numpy(dtype=float)
        c = pd.to_numeric(current[ccol], errors="coerce").dropna().to_numpy(dtype=float)
        if len(b) < 2 or len(c) < 2:
            continue
        psi = _psi(b, c)
        ks = _ks(b, c)
        features.append({
            "feature": name,
            "psi": round(psi, 6),
            "ks_statistic": round(ks, 6),
            "status": _status(psi, ks),
            "baseline_count": int(len(b)),
            "current_count": int(len(c)),
        })

    high = sum(x["status"] == "high" for x in features)
    moderate = sum(x["status"] == "moderate" for x in features)
    overall = "high" if high else ("moderate" if moderate else "stable")
    return {
        "status": overall,
        "window_days": window_days or "all",
        "period_start": period_start.isoformat() if period_start else None,
        "period_end": datetime.utcnow().isoformat(),
        "thresholds": {
            "psi_stable": "< 0.10",
            "psi_moderate": "0.10 - 0.20",
            "psi_significant": "> 0.20",
            "note": "Thresholds are diagnostic monitoring guidelines and do not trigger automatic model retraining.",
        },
        "baseline_source": "data/raw/loan_data.csv",
        "baseline_count": int(len(baseline)),
        "current_count": int(len(current)),
        "features": features,
    }
