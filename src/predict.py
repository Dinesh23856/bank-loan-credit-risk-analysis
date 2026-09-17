from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from .pipeline_utils import CONFIG, NUMERIC, ROOT, feature_frame, validate_input


def _load(name: str):
    path = ROOT / "models" / name
    if not path.exists():
        raise FileNotFoundError(f"Missing model file: {path}")
    return joblib.load(path)


# Load each model once per Python process. The API imports this registry rather than
# loading a second copy of every model.
MODELS = {
    "loan_amount": _load("loan_amount.joblib"),
    "loan_approval": _load("loan_approval.joblib"),
    "credit_score": _load("credit_score.joblib"),
    "credit_risk": _load("credit_risk.joblib"),
}


def _pipeline_columns(model) -> tuple[list[str], list[str]]:
    prep = model.named_steps.get("prep")
    if prep is None:
        raise ValueError("Model is missing the expected preprocessing step.")
    num_cols: list[str] = []
    cat_cols: list[str] = []
    for name, _, cols in prep.transformers:
        if cols is None:
            continue
        if name == "num":
            num_cols = list(cols)
        elif name == "cat":
            cat_cols = list(cols)
    return num_cols, cat_cols


def _expected_columns(feature_names: list[str], *, exclude_derived: set[str] | None = None) -> tuple[list[str], list[str]]:
    derived = [
        "disposable_income", "wealth_to_income", "savings_months", "default_rate",
        "payment_quality", "loan_to_income", "loan_to_assets", "credit_strength",
    ]
    exclude_derived = exclude_derived or set()
    all_cols = feature_names + [
        c for c in derived
        if c not in feature_names and c not in exclude_derived and (
            c not in {"loan_to_income", "loan_to_assets"}
            or "requested_loan_amount" in feature_names
        )
    ]
    numeric_derived = {
        "disposable_income", "wealth_to_income", "savings_months", "default_rate",
        "payment_quality", "loan_to_income", "loan_to_assets", "credit_strength",
    }
    numeric = [c for c in all_cols if c in NUMERIC or c in numeric_derived]
    categorical = [c for c in all_cols if c not in numeric]
    return numeric, categorical


def validate_model_schemas() -> None:
    for name, configured in CONFIG["features"].items():
        model = MODELS[name]
        if isinstance(model, dict):
            model = model.get("pipeline")
        actual_num, actual_cat = _pipeline_columns(model)
        excluded = {"credit_score", "credit_strength"} if name == "credit_risk" else set()
        expected_num, expected_cat = _expected_columns(list(configured), exclude_derived=excluded)
        if actual_num != expected_num or actual_cat != expected_cat:
            raise RuntimeError(
                f"Model schema mismatch for {name}: serialized preprocessing columns do not match the configured inference schema."
            )

    risk = MODELS["credit_risk"]
    if not isinstance(risk, dict) or "pipeline" not in risk or "label_encoder" not in risk:
        raise RuntimeError("Credit-risk model bundle is incomplete.")
    classes = list(risk["label_encoder"].classes_)
    if set(classes) != {"Low", "Medium", "High"}:
        raise RuntimeError("Credit-risk model labels are incompatible with the API contract.")


validate_model_schemas()


def predict_all(applicant: dict) -> dict:
    validate_input(applicant)
    row = pd.DataFrame([applicant])

    approval_X = feature_frame(row, CONFIG["features"]["loan_approval"])
    approval_model = MODELS["loan_approval"]
    approval_prob = float(approval_model.predict_proba(approval_X)[0, 1])
    status = "Approved" if approval_prob >= CONFIG["thresholds"]["approval_probability"] else "Rejected"

    amount = 0.0
    if status == "Approved":
        amount_X = feature_frame(row, CONFIG["features"]["loan_amount"])
        raw = float(MODELS["loan_amount"].predict(amount_X)[0])
        amount = float(np.clip(raw, 0, float(applicant["requested_loan_amount"])))

    score_X = feature_frame(row, CONFIG["features"]["credit_score"])
    predicted_score = float(np.clip(MODELS["credit_score"].predict(score_X)[0], 300, 850))

    risk_X = feature_frame(row, CONFIG["features"]["credit_risk"]).drop(columns=["credit_score", "credit_strength"], errors="ignore")
    bundle = MODELS["credit_risk"]
    probs = bundle["pipeline"].predict_proba(risk_X)[0]
    idx = int(np.argmax(probs))
    risk = str(bundle["label_encoder"].inverse_transform([idx])[0])

    return {
        "loan_status": status,
        "approval_probability": round(approval_prob, 4),
        "approved_loan_amount": round(amount, 2),
        "credit_score": round(predicted_score, 0),
        "risk_level": risk,
        "risk_probabilities": {
            str(c): round(float(p), 4)
            for c, p in zip(bundle["label_encoder"].classes_, probs)
        },
    }
