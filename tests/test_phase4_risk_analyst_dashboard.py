import os
import json
import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

from backend.main import app
from backend.database import SessionLocal
from backend.models import User, AuditLog, LoanApplication
from backend.auth import hash_password

client = TestClient(app)

IMMUTABLE_HASHES = {
    "models/loan_approval.joblib": "b70d0fd7ef583b3492e0ac57acf4cea5b0689844ad6615a3cbd6a46466c02f26",
    "models/loan_amount.joblib": "963bff7f4317a6d373fd0aa0e324f698a32cabee2d7a4d12d9fdef5048fcabe6",
    "models/credit_score.joblib": "897948653b3982012b327746955a79b8487834f2bb0dcefa02dd0b9f3a553f59",
    "models/credit_risk.joblib": "044aa75d7741d1bb6b448d3795b145350cacc65c8c6e598cff6e6df219d55922",
    "data/raw/loan_data.csv": "cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a",
    "data/raw/credit_risk_data.csv": "f579fb61724b5abf61e1af563ba3b3e6b71657bb949042ac315d68f3f4d22c2c"
}

@pytest.fixture(scope="module")
def admin_token():
    email = os.getenv("ADMIN_EMAIL", "dineshmore90@gmail.com")
    pw = os.getenv("ADMIN_PASSWORD", "Dinesh@9021")
    res = client.post("/auth/login", json={"email": email, "password": pw})
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def rbac_users():
    pw = "Phase4Test@9021"
    roles = {
        "customer": ("phase4_customer@example.com", "CUSTOMER"),
        "underwriter": ("phase4_underwriter@example.com", "UNDERWRITER"),
        "analyst": ("phase4_analyst@example.com", "RISK_ANALYST"),
    }
    tokens = {}
    db = SessionLocal()
    for key, (email, role_name) in roles.items():
        existing = db.query(User).filter(User.email == email).first()
        if not existing:
            existing = User(
                name=f"Phase4 {role_name}",
                email=email,
                password_hash=hash_password(pw),
                role=role_name
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
        else:
            existing.role = role_name
            db.commit()
            db.refresh(existing)

        login_res = client.post("/auth/login", json={"email": email, "password": pw})
        assert login_res.status_code == 200
        tokens[key] = {
            "token": login_res.json()["access_token"],
            "user_id": existing.id,
            "role": role_name,
            "email": email
        }
    db.close()
    return tokens


# ========================================================
# 1. RBAC ACCESS CONTROL TESTS
# ========================================================

def test_01_unauthenticated_access_rejected():
    """Verify unauthenticated requests to /risk-analyst/overview receive 401."""
    res = client.get("/risk-analyst/overview")
    assert res.status_code == 401

def test_02_customer_access_forbidden(rbac_users):
    """Verify CUSTOMER role cannot access /risk-analyst/overview (403 Forbidden)."""
    token = rbac_users["customer"]["token"]
    res = client.get("/risk-analyst/overview", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

def test_03_underwriter_access_forbidden(rbac_users):
    """Verify UNDERWRITER role cannot access /risk-analyst/overview (403 Forbidden)."""
    token = rbac_users["underwriter"]["token"]
    res = client.get("/risk-analyst/overview", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

def test_04_risk_analyst_access_allowed(rbac_users):
    """Verify RISK_ANALYST role can access /risk-analyst/overview (200 OK)."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/overview", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200

def test_05_admin_access_allowed(admin_token):
    """Verify ADMIN role can access /risk-analyst/overview (200 OK)."""
    res = client.get("/risk-analyst/overview", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


# ========================================================
# 2. CORE PORTFOLIO & RISK KPI OVERVIEW
# ========================================================

def test_06_portfolio_overview_structure_and_values(rbac_users):
    """Verify /risk-analyst/overview returns core portfolio KPIs with valid relationships."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/overview", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    required_keys = [
        "total_applications",
        "approved_applications",
        "rejected_applications",
        "approval_rate",
        "average_requested_loan_amount",
        "average_approved_loan_amount",
        "average_predicted_credit_score",
        "high_risk_applicant_count",
        "medium_risk_applicant_count",
        "low_risk_applicant_count"
    ]
    for k in required_keys:
        assert k in data, f"Missing KPI {k}"

    assert data["total_applications"] >= 0
    assert data["approved_applications"] >= 0
    assert data["rejected_applications"] >= 0
    assert data["approved_applications"] + data["rejected_applications"] <= data["total_applications"]
    assert 0.0 <= data["approval_rate"] <= 1.0


# ========================================================
# 3. 12-STATE WORKFLOW BREAKDOWN
# ========================================================

def test_07_workflow_status_breakdown_12_states(rbac_users):
    """Verify /risk-analyst/workflow-status returns full 12-state funnel breakdown."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/workflow-status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "total_applications" in data
    assert "breakdown" in data
    states = data["breakdown"]
    assert len(states) >= 10

    state_names = {s["status"] for s in states}
    expected_states = {
        "SUBMITTED", "KYC_PENDING", "DOCUMENTS_PENDING", "CREDIT_CHECKING",
        "AI_ASSESSED", "MANUAL_REVIEW", "APPROVED", "REJECTED", "OFFERED", "ACCEPTED", "CLOSED"
    }
    assert expected_states.issubset(state_names)

    sum_counts = sum(s["count"] for s in states)
    assert sum_counts == data["total_applications"]


# ========================================================
# 4. CROSS-TABULATION & CREDIT SCORE DISTRIBUTION
# ========================================================

def test_08_approval_rejection_analysis(rbac_users):
    """Verify /risk-analyst/approval-analysis returns cross-tabulation by risk and tier."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/approval-analysis", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "by_risk_level" in data
    assert "by_loan_amount" in data
    assert "by_credit_score" in data
    assert "overall" in data

    risk_levels = set(data["by_risk_level"].keys())
    assert {"High", "Medium", "Low"}.issubset(risk_levels)

def test_09_credit_score_analysis_bureau_vs_predicted(rbac_users):
    """Verify /risk-analyst/credit-score-analysis returns stats and distributions for predicted vs bureau."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/credit-score-analysis", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "predicted_credit_score" in data
    assert "bureau_credit_score" in data

    pred = data["predicted_credit_score"]
    bureau = data["bureau_credit_score"]

    assert "stats" in pred and "distribution" in pred
    assert "stats" in bureau and "distribution" in bureau

    assert len(pred["distribution"]) >= 4
    assert len(bureau["distribution"]) >= 4

def test_10_loan_amount_tier_analysis(rbac_users):
    """Verify /risk-analyst/loan-amount-analysis returns ticket tiers and risk relationships."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/loan-amount-analysis", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "distribution_tiers" in data
    assert "risk_relationship" in data
    assert "requested_amount_stats" in data

    tiers = data["distribution_tiers"]
    assert len(tiers) >= 4
    for t in tiers:
        assert "tier" in t
        assert "label" in t
        assert "count" in t
        assert "percentage" in t

def test_11_risk_distribution(rbac_users):
    """Verify /risk-analyst/risk-distribution returns portfolio percentages."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/risk-distribution", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "distribution" in data
    dist = data["distribution"]
    assert len(dist) == 3
    tiers = {d["risk_level"] for d in dist}
    assert tiers == {"High", "Medium", "Low"}


# ========================================================
# 5. MODEL PERFORMANCE & CONFUSION MATRICES
# ========================================================

def test_12_model_performance_and_confusion_matrices(rbac_users):
    """Verify /risk-analyst/model-performance returns all 4 models and real confusion matrices."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/model-performance", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "modules" in data
    model_names = set(data["modules"].keys())
    assert model_names == {"loan_approval", "loan_amount", "credit_score", "credit_risk"}

    # Check confusion matrices from offline evaluation
    modules = data["modules"]
    assert "confusion_matrix" in modules["loan_approval"]["test"]
    assert modules["loan_approval"]["test"]["confusion_matrix"] == [[1729, 135], [409, 127]]

    assert "confusion_matrix" in modules["credit_risk"]["test"]
    assert modules["credit_risk"]["test"]["confusion_matrix"] == [[1625, 0, 165], [4, 13, 73], [186, 9, 325]]
    assert modules["credit_risk"]["classes"] == ["High", "Low", "Medium"]

    # Check operational latency and hashes
    assert "operational" in data
    assert "average_latency_ms" in data["operational"]
    assert "model_hashes" in data["operational"]
    for m in ["loan_approval", "loan_amount", "credit_score", "credit_risk"]:
        assert m in data["operational"]["model_hashes"]


# ========================================================
# 6. DRIFT MONITORING (MULTI-WINDOW)
# ========================================================

def test_13_drift_monitoring_with_window_options(rbac_users):
    """Verify /risk-analyst/drift supports multi-window evaluation (PSI & KS)."""
    token = rbac_users["analyst"]["token"]

    # Default window
    res = client.get("/risk-analyst/drift", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "features" in data
    assert len(data["features"]) > 0
    for f in data["features"]:
        assert "feature" in f
        assert "psi" in f
        assert "ks_statistic" in f
        assert "status" in f

    # 14-day window
    res14 = client.get("/risk-analyst/drift?window_days=14", headers={"Authorization": f"Bearer {token}"})
    assert res14.status_code == 200
    assert "features" in res14.json()


# ========================================================
# 7. DEMOGRAPHIC PARITY & ACADEMIC NON-LEGAL PHRASING
# ========================================================

def test_14_demographic_parity_academic_non_legal_phrasing(rbac_users):
    """Verify fairness endpoint uses academic non-legal phrasing and includes disclaimers."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/fairness?attribute=gender", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()

    assert "disparate_impact_ratio" in data
    assert "status" in data
    assert "disclaimer" in data
    assert "groups" in data

    # Verify NON-LEGAL status phrasing
    status_str = data["status"]
    assert "violation" not in status_str.lower()
    assert "illegal" not in status_str.lower()
    assert "unlawful" not in status_str.lower()
    if not data["four_fifths_rule_passed"]:
        assert "potential disparity indicator" in status_str.lower()
        assert "0.80 benchmark" in status_str.lower()

    # Verify academic/educational disclaimer
    disclaimer_str = data["disclaimer"].lower()
    assert "academic" in disclaimer_str or "educational" in disclaimer_str
    assert "legal" in disclaimer_str


# ========================================================
# 8. TIME TRENDS
# ========================================================

def test_15_time_trends_endpoint(rbac_users):
    """Verify /risk-analyst/time-trends returns aggregate daily/weekly points."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/time-trends?interval=daily&days=30", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert "interval" in data
    assert "points" in data
    for pt in data["points"]:
        assert "date" in pt
        assert "applications" in pt
        assert "approved" in pt
        assert "rejected" in pt


# ========================================================
# 9. CSV EXPORT & NON-PII PRIVACY COMPLIANCE
# ========================================================

def test_16_csv_export_privacy_and_structure(rbac_users):
    """Verify /risk-analyst/export-csv produces structured CSV with NO customer PII."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/risk-analyst/export-csv", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]

    content = res.text
    # Verify presence of summary sections
    assert "PORTFOLIO AGGREGATE SUMMARY" in content
    assert "ANONYMIZED APPLICATION PORTFOLIO RECORDS" in content
    assert "ACADEMIC" in content

    # Verify NO PII leak
    pii_keywords = ["customer_name", "first_name", "last_name", "phone_number", "ssn", "aadhaar", "email_address"]
    for kw in pii_keywords:
        assert kw not in content.lower()


# ========================================================
# 10. AUDIT LOGGING VERIFICATION
# ========================================================

def test_17_audit_logging_recorded_for_risk_analytics(rbac_users):
    """Verify risk analyst requests emit persistent audit logs with proper action codes."""
    token = rbac_users["analyst"]["token"]

    # Trigger view actions
    client.get("/risk-analyst/overview", headers={"Authorization": f"Bearer {token}"})
    client.get("/risk-analyst/drift?window_days=30", headers={"Authorization": f"Bearer {token}"})
    client.get("/risk-analyst/fairness?attribute=gender", headers={"Authorization": f"Bearer {token}"})

    db = SessionLocal()
    recent_logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(15).all()
    actions = {log.action for log in recent_logs}
    db.close()

    assert "RISK_ANALYTICS_VIEW" in actions or "DRIFT_VIEW" in actions or "FAIRNESS_VIEW" in actions


# ========================================================
# 11. IMMUTABLE ARTIFACT HASH VERIFICATION
# ========================================================

def test_18_immutable_artifact_hashes_byte_for_byte():
    """Verify all 4 models and 2 raw datasets remain byte-for-byte identical to baseline."""
    root_dir = Path(__file__).resolve().parent.parent

    for rel_path, expected_hash in IMMUTABLE_HASHES.items():
        full_path = root_dir / rel_path
        assert full_path.is_file(), f"Artifact missing: {rel_path}"

        hasher = hashlib.sha256()
        with open(full_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()

        assert actual_hash == expected_hash, (
            f"CRITICAL IMMUTABILITY VIOLATION: {rel_path}\n"
            f"Expected: {expected_hash}\n"
            f"Actual:   {actual_hash}"
        )
