from __future__ import annotations
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..models import LoanApplication

def calculate_fairness_metrics(db: Session, attribute: str = "gender") -> dict:
    """
    Calculate selection rate by demographic group and Disparate Impact Ratio (DIR).
    Used exclusively for compliance monitoring and audit reporting.
    """
    valid_attributes = {"gender", "marital_status", "education", "employment_type"}
    if attribute not in valid_attributes:
        attribute = "gender"

    col = getattr(LoanApplication, attribute)
    records = db.query(
        col,
        LoanApplication.approval_status,
        func.count(LoanApplication.id)
    ).group_by(col, LoanApplication.approval_status).all()

    groups_data: Dict[str, Dict[str, Any]] = {}
    for group_val, status, count in records:
        group_key = str(group_val) if group_val is not None else "Unknown"
        if group_key not in groups_data:
            groups_data[group_key] = {"total": 0, "approved": 0, "rejected": 0, "approval_rate": 0.0}
        
        groups_data[group_key]["total"] += count
        if status == "Approved":
            groups_data[group_key]["approved"] += count
        else:
            groups_data[group_key]["rejected"] += count

    # Compute approval rates
    for grp, data in groups_data.items():
        if data["total"] > 0:
            data["approval_rate"] = round(data["approved"] / data["total"], 4)
        else:
            data["approval_rate"] = 0.0

    if not groups_data:
        return {
            "group_attribute": attribute,
            "groups": {},
            "disparate_impact_ratio": 1.0,
            "favorable_group": "N/A",
            "protected_group": "N/A",
            "four_fifths_rule_passed": True,
            "status": "No application records available for fairness monitoring.",
            "disclaimer": "Diagnostic and monitoring metric only. Decisions are evaluated on financial risk factors without altering protected demographic features."
        }

    # Find highest approval rate group as reference
    sorted_groups = sorted(groups_data.items(), key=lambda x: x[1]["approval_rate"], reverse=True)
    favorable_grp, fav_data = sorted_groups[0]
    fav_rate = fav_data["approval_rate"]

    # Compare against lowest group
    lowest_grp, low_data = sorted_groups[-1]
    low_rate = low_data["approval_rate"]

    if fav_rate > 0:
        dir_val = round(low_rate / fav_rate, 4)
    else:
        dir_val = 1.0

    four_fifths_passed = dir_val >= 0.80
    status_msg = "Parity Guideline Met (DIR >= 0.80)" if four_fifths_passed else "Potential Disparity Indicator: DIR is below the 0.80 benchmark."

    return {
        "group_attribute": attribute,
        "groups": groups_data,
        "disparate_impact_ratio": dir_val,
        "favorable_group": favorable_grp,
        "protected_group": lowest_grp,
        "four_fifths_rule_passed": four_fifths_passed,
        "status": status_msg,
        "disclaimer": "Fairness monitoring heuristic for academic/demo analysis; not a legal compliance determination. Model decisions are evaluated on financial risk factors without altering protected demographic features."
    }
