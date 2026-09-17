from __future__ import annotations
import time
import json
from copy import deepcopy
from src.predict import predict_all
from src.pipeline_utils import validate_input
from .shap_service import explain_loan_approval

PROTECTED_ATTRIBUTES = {"age", "gender", "marital_status", "education", "dependents"}

def run_prediction(payload: dict, include_explanations: bool = True):
    payload = dict(payload)
    payload["monthly_income"] = payload["annual_income"] / 12.0
    payload["monthly_debt"] = payload["monthly_income"] * payload["debt_to_income_ratio"]
    validate_input(payload)
    started = time.perf_counter()
    result = predict_all(payload)
    elapsed = (time.perf_counter() - started) * 1000

    if include_explanations:
        explanations = explain_loan_approval(payload, result["loan_status"], result["approval_probability"])
        result.update(explanations)

    return result, elapsed

def run_counterfactual_simulation(applicant_data: dict, proposed_changes: dict) -> dict:
    """
    Simulate what-if financial adjustments for counterfactual recourse.
    Strictly forbids altering protected demographic attributes.
    """
    for attr in PROTECTED_ATTRIBUTES:
        if attr in proposed_changes and proposed_changes[attr] != applicant_data.get(attr):
            raise ValueError(f"Modification of protected demographic variable '{attr}' is strictly prohibited in counterfactual simulations.")

    # Base prediction
    base_res, _ = run_prediction(applicant_data, include_explanations=False)
    base_prob = base_res["approval_probability"]

    # Clone applicant data and apply permitted mutable financial adjustments
    simulated = deepcopy(applicant_data)
    changes_recorded = []

    mutable_bounds = {
        "requested_loan_amount": (10_000.0, 100_000_000.0),
        "loan_term": (6, 480),
        "collateral_value": (0.0, 500_000_000.0),
        "savings": (0.0, 50_000_000.0),
        "debt_to_income_ratio": (0.01, 0.95),
    }

    for key, (min_val, max_val) in mutable_bounds.items():
        if key in proposed_changes and proposed_changes[key] is not None:
            new_val = type(applicant_data[key])(proposed_changes[key])
            if not (min_val <= float(new_val) <= max_val):
                raise ValueError(f"Proposed '{key}' value {new_val} is outside realistic boundary [{min_val}, {max_val}].")
            old_val = applicant_data[key]
            if new_val != old_val:
                simulated[key] = new_val
                changes_recorded.append({
                    "variable": key,
                    "original": old_val,
                    "proposed": new_val,
                    "delta": new_val - old_val if isinstance(new_val, (int, float)) else None
                })

    sim_res, _ = run_prediction(simulated, include_explanations=False)
    sim_prob = sim_res["approval_probability"]
    sim_decision = sim_res["loan_status"]

    feasible = sim_prob >= 0.50

    return {
        "original_probability": round(base_prob, 4),
        "approval_probability": round(sim_prob, 4),
        "estimated_decision": sim_decision,
        "changes": changes_recorded,
        "feasible": feasible,
        "disclaimer": "This counterfactual scenario is an indicative simulation based on statistical underwriting models. It does not constitute a formal loan offer or a guarantee of credit approval."
    }
