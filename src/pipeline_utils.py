from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd
import yaml
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config.yaml"

with CONFIG_PATH.open(encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

LOAN_REQUIRED = {
    "customer_id","age","gender","marital_status","dependents","education","employment_type",
    "monthly_income","annual_income","existing_loan","existing_loan_amount","monthly_debt",
    "debt_to_income_ratio","savings","bank_balance","assets","credit_history","previous_loans",
    "previous_defaults","payment_history","credit_utilization","credit_score","loan_type",
    "requested_loan_amount","loan_term","interest_rate","collateral_value","approved_loan_amount","loan_status"
}
RISK_REQUIRED = LOAN_REQUIRED - {"existing_loan","existing_loan_amount","loan_type","requested_loan_amount","loan_term","interest_rate","collateral_value","approved_loan_amount","loan_status"} | {"risk_level"}

NUMERIC = [
    "age","dependents","monthly_income","annual_income","monthly_debt","debt_to_income_ratio","savings",
    "bank_balance","assets","previous_loans","previous_defaults","payment_history","credit_utilization","credit_score",
    "requested_loan_amount","loan_term","collateral_value"
]
CATEGORICAL = ["gender","marital_status","education","employment_type","credit_history","loan_type"]

def clean_common(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    for c in NUMERIC:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    for c in CATEGORICAL + ["loan_status","risk_level","existing_loan"]:
        if c in x.columns:
            x[c] = x[c].astype("string")
    x["monthly_income"] = x["annual_income"] / 12.0
    x["monthly_debt"] = x["monthly_income"] * x["debt_to_income_ratio"]
    x = x.replace([np.inf, -np.inf], np.nan)
    return x

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    income = x["annual_income"].replace(0, np.nan)
    monthly = x["monthly_income"].replace(0, np.nan)
    x["disposable_income"] = x["monthly_income"] - x["monthly_debt"]
    x["wealth_to_income"] = x["assets"] / income
    x["savings_months"] = x["savings"] / monthly
    x["default_rate"] = np.where(x["previous_loans"] > 0, x["previous_defaults"] / x["previous_loans"], 0.0)
    x["payment_quality"] = x["payment_history"] * (1 - x["credit_utilization"])
    if "requested_loan_amount" in x:
        x["loan_to_income"] = x["requested_loan_amount"] / income
        x["loan_to_assets"] = x["requested_loan_amount"] / x["assets"].replace(0, np.nan)
    x["credit_strength"] = x["credit_score"] * (1 - x["credit_utilization"])
    return x.replace([np.inf, -np.inf], np.nan)

def make_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    num_cols = X.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = [c for c in X.columns if c not in num_cols]
    return ColumnTransformer(
        [("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), num_cols),
         ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), cat_cols)],
        remainder="drop"
    )

def feature_frame(df: pd.DataFrame, feature_names: list[str]) -> pd.DataFrame:
    x = add_features(clean_common(df))
    derived = ["disposable_income","wealth_to_income","savings_months","default_rate","payment_quality","loan_to_income","loan_to_assets","credit_strength"]
    cols = feature_names + [c for c in derived if c in x.columns and c not in feature_names]
    missing = [c for c in cols if c not in x.columns]
    if missing:
        raise ValueError(f"Missing model features: {missing}")
    return x.loc[:, cols].copy()

def validate_input(row: dict) -> None:
    required = [
        "age", "dependents", "education", "employment_type", "annual_income",
        "debt_to_income_ratio", "savings", "bank_balance", "assets", "credit_history",
        "previous_loans", "previous_defaults", "payment_history", "credit_utilization",
        "credit_score", "loan_type", "requested_loan_amount", "loan_term",
        "collateral_value", "interest_rate",
    ]
    missing = [c for c in required if c not in row or row[c] is None or (isinstance(row[c], str) and not row[c].strip())]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    checks = {
        "age": (18, 75), "dependents": (0, 5), "annual_income": (10000, 50000000),
        "debt_to_income_ratio": (0, 1), "savings": (0, 50000000),
        "bank_balance": (0, 20000000), "assets": (0, 100000000),
        "previous_loans": (0, 30), "previous_defaults": (0, 20),
        "payment_history": (0, 100), "credit_utilization": (0, 1),
        "credit_score": (300, 850), "requested_loan_amount": (0.01, 100000000),
        "loan_term": (1, 480), "collateral_value": (0, 500000000),
        "interest_rate": (0.01, 100),
    }
    for c, (lo, hi) in checks.items():
        try:
            v = float(row[c])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{c} must be a number") from exc
        if not np.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"{c} must be between {lo} and {hi}")

    if int(row["previous_defaults"]) > int(row["previous_loans"]):
        raise ValueError("previous_defaults cannot exceed previous_loans")

    allowed = {
        "gender": {"Male", "Female"},
        "marital_status": {"Single", "Married", "Divorced"},
        "education": {"Undergraduate", "Graduate", "Postgraduate"},
        "employment_type": {"Business", "Contract", "Salaried", "Self-employed"},
        "credit_history": {"Good", "Average", "Poor"},
        "loan_type": {"Education", "Business", "Personal", "Home", "Auto"},
    }
    for field, values in allowed.items():
        value = row.get(field)
        if not isinstance(value, str) or value not in values:
            raise ValueError(f"{field} must be one of: {', '.join(sorted(values))}")


def save_json(obj, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=float), encoding="utf-8")
