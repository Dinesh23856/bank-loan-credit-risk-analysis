from pathlib import Path
import json, math
import pandas as pd
from fastapi.testclient import TestClient
from backend.main import app, _run, ApplicantInput
from src.predict import MODELS, predict_all, validate_model_schemas

ROOT=Path(__file__).resolve().parents[1]
client=TestClient(app)

def demo():
    r=pd.read_csv(ROOT/"data/raw/loan_data.csv").iloc[0].to_dict()
    return {"age":int(r["age"]),"dependents":int(r["dependents"]),"gender":r["gender"],"marital_status":r["marital_status"],
    "education":r["education"],"employment_type":r["employment_type"],"annual_income":float(r["annual_income"]),
    "debt_to_income_ratio":float(r["debt_to_income_ratio"]),"savings":float(r["savings"]),"bank_balance":float(r["bank_balance"]),
    "assets":float(r["assets"]),"credit_history":r["credit_history"],"previous_loans":int(r["previous_loans"]),
    "previous_defaults":int(r["previous_defaults"]),"payment_history":float(r["payment_history"]),
    "credit_utilization":float(r["credit_utilization"]),"credit_score":float(r["credit_score"]),"loan_type":r["loan_type"],
    "requested_loan_amount":float(r["requested_loan_amount"]),"loan_term":int(r["loan_term"]),
    "collateral_value":float(r["collateral_value"]),"interest_rate":10.0}

def test_raw_datasets():
    loan=pd.read_csv(ROOT/"data/raw/loan_data.csv"); risk=pd.read_csv(ROOT/"data/raw/credit_risk_data.csv")
    assert loan.shape[0]==12000 and risk.shape[0]==12000
    assert loan.customer_id.is_unique and risk.customer_id.is_unique

def test_prediction_contract():
    out=predict_all(demo())
    assert out["loan_status"] in {"Approved","Rejected"} and 0<=out["approval_probability"]<=1
    assert 0<=out["approved_loan_amount"]<=demo()["requested_loan_amount"]
    assert 300<=out["credit_score"]<=850 and out["risk_level"] in {"Low","Medium","High"}

def test_prediction_service():
    out=_run(ApplicantInput(**demo()))
    assert out["loan_status"] in {"Approved","Rejected"} and out["risk_level"] in {"Low","Medium","High"}

def test_protected_fullstack_routes():
    # Full protected endpoints require the configured MySQL runtime; live auth is covered as an environment test.
    assert any(getattr(route,"path","")=="/auth/me" for route in app.routes)

def test_validation():
    bad=demo(); bad["age"]=10
    try: ApplicantInput(**bad)
    except Exception: pass
    else: assert False

def test_extra_fields_rejected():
    bad=demo(); bad["unexpected"]="not allowed"
    try: ApplicantInput(**bad)
    except Exception: pass
    else: assert False

def test_invalid_business_rules():
    bad=demo(); bad["previous_defaults"]=bad["previous_loans"]+1
    try: _run(ApplicantInput(**bad))
    except Exception: pass
    else: assert False

def test_gzip_compression():
    response=client.get("/openapi.json",headers={"Accept-Encoding":"gzip"})
    assert response.status_code==200 and response.headers.get("content-encoding")=="gzip"

def test_basic_routes():
    assert client.get("/").status_code==200
    assert client.get("/health").json()=={"status":"ok"}
    assert client.get("/docs").status_code==200

def test_model_schema_validation():
    validate_model_schemas()
    assert set(MODELS)=={"loan_amount","loan_approval","credit_score","credit_risk"}
    risk_prep=MODELS["credit_risk"]["pipeline"].named_steps["prep"]
    risk_cols=[c for _,_,cols in risk_prep.transformers for c in (list(cols) if cols is not None else [])]
    assert "credit_score" not in risk_cols and "credit_strength" not in risk_cols

def test_invalid_request_matrix():
    payload=demo()
    for change in [{"age":None},{"requested_loan_amount":-1},{"credit_score":9999},{"loan_term":0},{"interest_rate":float("inf")}]:
        candidate=payload.copy(); candidate.update(change)
        try: ApplicantInput(**candidate)
        except Exception: continue
        assert False, change
    try: ApplicantInput(**{})
    except Exception: pass
    else: assert False

def test_risk_score_independence():

    a=demo(); b=a.copy(); b["credit_score"]=850
    ra=predict_all(a); rb=predict_all(b)
    assert ra["risk_level"]==rb["risk_level"]
    assert ra["risk_probabilities"]==rb["risk_probabilities"]

def test_cors_policy():
    allowed=client.get("/health",headers={"Origin":"http://localhost:5173"})
    assert allowed.headers.get("access-control-allow-origin")=="http://localhost:5173"
    denied=client.get("/health",headers={"Origin":"https://evil.example"})
    assert "access-control-allow-origin" not in denied.headers
