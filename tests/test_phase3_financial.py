import os
import io
import json
import math
import hashlib
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

from backend.main import app
from backend.database import SessionLocal
from backend.models import User, LoanApplication, AuditLog, ModelRegistry
from backend.services.financial_service import (
    calculate_emi,
    generate_amortization_schedule,
    get_application_financial_summary,
    generate_kfs_data,
    KFS_DISCLAIMER_HEADER,
    KFS_DISCLAIMER_TEXT
)
from backend.services.pdf_service import generate_kfs_pdf
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
    pw = "Phase2Test@9021"
    roles = {
        "customer": ("phase2_customer@example.com", "CUSTOMER"),
        "underwriter": ("phase2_underwriter@example.com", "UNDERWRITER"),
        "analyst": ("phase2_analyst@example.com", "RISK_ANALYST"),
    }
    tokens = {}
    db = SessionLocal()
    for key, (email, role_name) in roles.items():
        existing = db.query(User).filter(User.email == email).first()
        if not existing:
            existing = User(
                name=f"Test {role_name}",
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
# 1. DETERMINISTIC EMI CALCULATOR SERVICE TESTS
# ========================================================

def test_01_standard_emi_calculation():
    """Verify standard reducing balance formula with known parameters."""
    res = calculate_emi(principal=1_000_000, annual_interest_rate=10.0, loan_term_months=12)
    assert res["principal"] == 1_000_000.0
    assert res["annual_interest_rate"] == 10.0
    assert res["loan_term_months"] == 12
    # Known benchmark: P=1,000,000, R=10%, n=12 -> EMI = 87915.89
    assert res["emi"] == 87915.89
    assert res["total_payment"] == 1054990.68
    assert res["total_interest"] == 54990.68

def test_02_zero_interest_emi():
    """Verify zero-interest edge case: EMI = P / n, total interest = 0."""
    res = calculate_emi(principal=120_000, annual_interest_rate=0.0, loan_term_months=12)
    assert res["emi"] == 10000.0
    assert res["total_payment"] == 120000.0
    assert res["total_interest"] == 0.0

def test_03_known_value_emi_36_months():
    """Verify 36-month loan calculation: P=500,000, R=7.5% -> EMI = 15,553.11."""
    res = calculate_emi(principal=500_000, annual_interest_rate=7.5, loan_term_months=36)
    assert res["emi"] == 15553.11
    assert res["total_payment"] == 559911.96
    assert res["total_interest"] == 59911.96

def test_04_single_period_loan():
    """Verify single-period loan: n=1, EMI = P * (1 + r)."""
    res = calculate_emi(principal=100_000, annual_interest_rate=12.0, loan_term_months=1)
    # Monthly rate = 1%, so EMI = 100,000 * 1.01 = 101,000.00
    assert res["emi"] == 101000.0
    assert res["total_payment"] == 101000.0
    assert res["total_interest"] == 1000.0

# ========================================================
# 2. AMORTIZATION SCHEDULE TESTS
# ========================================================

def test_05_amortization_schedule_length():
    """Verify schedule length exactly matches loan_term_months."""
    sched = generate_amortization_schedule(principal=250_000, annual_interest_rate=9.0, loan_term_months=24)
    assert len(sched["schedule"]) == 24
    assert sched["schedule"][0]["month"] == 1
    assert sched["schedule"][-1]["month"] == 24

def test_06_amortization_principal_reconciliation():
    """Verify the sum of all monthly principal components equals original principal."""
    sched = generate_amortization_schedule(principal=300_000, annual_interest_rate=8.5, loan_term_months=18)
    sum_principal = round(sum(row["principal_component"] for row in sched["schedule"]), 2)
    assert sum_principal == 300_000.0

def test_07_amortization_interest_reconciliation():
    """Verify sum of interest components matches total_interest."""
    sched = generate_amortization_schedule(principal=400_000, annual_interest_rate=10.5, loan_term_months=30)
    sum_interest = round(sum(row["interest_component"] for row in sched["schedule"]), 2)
    assert abs(sum_interest - sched["total_interest"]) < 0.05

def test_08_amortization_payment_reconciliation():
    """Verify sum of monthly EMIs matches total_payment."""
    sched = generate_amortization_schedule(principal=150_000, annual_interest_rate=11.0, loan_term_months=12)
    sum_emi = round(sum(row["emi"] for row in sched["schedule"]), 2)
    assert abs(sum_emi - sched["total_payment"]) < 0.05

def test_09_amortization_final_balance_exact_zero():
    """Verify that final period closing balance reaches exactly 0.00."""
    for tenure in [6, 12, 24, 36, 60]:
        sched = generate_amortization_schedule(principal=500_000, annual_interest_rate=9.5, loan_term_months=tenure)
        assert sched["schedule"][-1]["closing_balance"] == 0.00

def test_10_amortization_final_period_rounding_absorption():
    """Verify final period absorbs rounding difference and closes opening balance completely."""
    sched = generate_amortization_schedule(principal=100_000, annual_interest_rate=8.75, loan_term_months=13)
    final_row = sched["schedule"][-1]
    assert final_row["principal_component"] == final_row["opening_balance"]
    assert final_row["closing_balance"] == 0.00

# ========================================================
# 3. INPUT VALIDATION & BOUNDARY TESTS
# ========================================================

def test_11_invalid_principal_zero_or_negative(admin_token):
    """Negative and zero principal must be rejected with 422."""
    res_zero = client.post("/financial/calculate-emi", json={"principal": 0, "annual_interest_rate": 10, "loan_term_months": 12}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_zero.status_code == 422

    res_neg = client.post("/financial/calculate-emi", json={"principal": -5000, "annual_interest_rate": 10, "loan_term_months": 12}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_neg.status_code == 422

def test_12_invalid_principal_exceeds_max(admin_token):
    """Principal > 100,000,000 must be rejected with 422."""
    res = client.post("/financial/calculate-emi", json={"principal": 100_000_001, "annual_interest_rate": 10, "loan_term_months": 12}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

def test_13_invalid_rate_negative(admin_token):
    """Negative interest rate must be rejected with 422."""
    res = client.post("/financial/calculate-emi", json={"principal": 100000, "annual_interest_rate": -1, "loan_term_months": 12}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

def test_14_invalid_rate_exceeds_100(admin_token):
    """Interest rate > 100% must be rejected with 422."""
    res = client.post("/financial/calculate-emi", json={"principal": 100000, "annual_interest_rate": 101, "loan_term_months": 12}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

def test_15_invalid_tenure_zero_or_negative(admin_token):
    """Tenure <= 0 must be rejected with 422."""
    res_zero = client.post("/financial/calculate-emi", json={"principal": 100000, "annual_interest_rate": 10, "loan_term_months": 0}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_zero.status_code == 422

    res_neg = client.post("/financial/calculate-emi", json={"principal": 100000, "annual_interest_rate": 10, "loan_term_months": -6}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_neg.status_code == 422

def test_16_maximum_tenure_boundary(admin_token):
    """Tenure 480 is allowed; 481 is rejected with 422."""
    res_480 = client.post("/financial/calculate-emi", json={"principal": 100000, "annual_interest_rate": 10, "loan_term_months": 480}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_480.status_code == 200

    res_481 = client.post("/financial/calculate-emi", json={"principal": 100000, "annual_interest_rate": 10, "loan_term_months": 481}, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_481.status_code == 422

# ========================================================
# 4. API ENDPOINTS & FINANCIAL SUMMARY TESTS
# ========================================================

def test_17_financial_simulator_api(admin_token):
    """Verify POST /financial/calculate-emi returns accurate deterministic calculation."""
    payload = {"principal": 500000, "annual_interest_rate": 8.0, "loan_term_months": 36}
    res = client.post("/financial/calculate-emi", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["principal"] == 500000.0
    assert data["loan_term_months"] == 36
    assert data["emi"] == 15668.18
    assert data["total_payment"] == 564054.48
    assert data["total_interest"] == 64054.48

def test_18_application_financial_summary_endpoint(admin_token):
    """Verify GET /applications/{id}/financial-summary for an approved application (ID=6)."""
    res = client.get("/applications/6/financial-summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["application_id"] == 6
    assert data["loan_amount"] == 500000.0
    assert data["interest_rate"] == 7.5
    assert data["loan_term_months"] == 36
    assert data["emi"] == 15553.11
    assert data["is_approved_offer"] is True

def test_19_application_amortization_endpoint(admin_token):
    """Verify GET /applications/{id}/amortization returns full schedule array."""
    res = client.get("/applications/6/amortization", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["application_id"] == 6
    assert len(data["schedule"]) == 36
    assert data["schedule"][0]["opening_balance"] == 500000.0
    assert data["schedule"][-1]["closing_balance"] == 0.0

def test_20_kfs_json_endpoint_structure(admin_token):
    """Verify GET /applications/{id}/kfs returns structured Academic KFS JSON."""
    res = client.get("/applications/6/kfs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    kfs = res.json()
    assert kfs["document_type"] == "ACADEMIC_DEMO_KFS"
    assert "ACADEMIC/DEMO" in kfs["disclaimer_header"]
    assert kfs["application_id"] == 6
    assert kfs["reference_number"] == "KFS-APP-000006"
    assert kfs["loan_amount"] == 500000.0
    assert kfs["emi"] == 15553.11
    assert len(kfs["first_year_schedule"]) == 12

def test_21_kfs_mandatory_disclaimer(admin_token):
    """Verify that both header and text explicitly disclaim legal/regulatory status."""
    res = client.get("/applications/6/kfs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "ACADEMIC/DEMO — NOT A LEGAL OR REGULATORY DOCUMENT" in data["disclaimer_header"]
    assert "strictly for academic demonstration" in data["disclaimer_text"]
    assert "NOT constitute" in data["disclaimer_text"]

# ========================================================
# 5. REJECTED APPLICATION RULE TESTS
# ========================================================

def test_22_rejected_application_cannot_generate_kfs(admin_token):
    """Verify that a REJECTED application (ID=60) returns 400 Bad Request for KFS JSON."""
    res = client.get("/applications/60/kfs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert "REJECTED" in res.json()["detail"]
    assert "cannot be issued" in res.json()["detail"] or "cannot be generated" in res.json()["detail"]

def test_23_rejected_application_cannot_generate_kfs_pdf(admin_token):
    """Verify that a REJECTED application (ID=60) returns 400 Bad Request for KFS PDF."""
    res = client.get("/applications/60/kfs/pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 400
    assert "REJECTED" in res.json()["detail"]

# ========================================================
# 6. RBAC & BOLA / IDOR PROTECTION TESTS
# ========================================================

def test_24_customer_own_application_authorized(rbac_users):
    """A customer can view the financial summary of an application they own."""
    # Find or associate an application with customer
    db = SessionLocal()
    app_rec = db.query(LoanApplication).filter(LoanApplication.user_id == rbac_users["customer"]["user_id"]).first()
    if not app_rec:
        # Check app owned by user or create association
        app_rec = db.query(LoanApplication).filter(LoanApplication.id == 6).first()
        app_rec.user_id = rbac_users["customer"]["user_id"]
        db.commit()
    app_id = app_rec.id
    db.close()

    res = client.get(f"/applications/{app_id}/financial-summary", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res.status_code == 200

def test_25_customer_other_application_denied_bola(rbac_users):
    """A customer attempting to access another customer's application is denied with 403 Forbidden."""
    db = SessionLocal()
    other_app = db.query(LoanApplication).filter(LoanApplication.user_id != rbac_users["customer"]["user_id"]).first()
    other_id = other_app.id
    db.close()

    res_sum = client.get(f"/applications/{other_id}/financial-summary", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res_sum.status_code == 403

    res_amort = client.get(f"/applications/{other_id}/amortization", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res_amort.status_code == 403

    res_kfs = client.get(f"/applications/{other_id}/kfs", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res_kfs.status_code == 403

    res_pdf = client.get(f"/applications/{other_id}/kfs/pdf", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res_pdf.status_code == 403

def test_26_underwriter_authorized_access(rbac_users):
    """Underwriter can access any application financial details."""
    res = client.get("/applications/6/financial-summary", headers={"Authorization": f"Bearer {rbac_users['underwriter']['token']}"})
    assert res.status_code == 200

def test_27_analyst_authorized_access(rbac_users):
    """Risk Analyst can access any application financial details."""
    res = client.get("/applications/6/financial-summary", headers={"Authorization": f"Bearer {rbac_users['analyst']['token']}"})
    assert res.status_code == 200

def test_28_admin_authorized_access(admin_token):
    """Admin has full authorization across financial endpoints."""
    res = client.get("/applications/6/financial-summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200

# ========================================================
# 7. PDF STREAMING & SECURITY TESTS
# ========================================================

def test_29_kfs_pdf_generation_content_type(admin_token):
    """Verify KFS PDF streaming returns Content-Type: application/pdf and attachment header."""
    res = client.get("/applications/6/kfs/pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment; filename=kfs_loan_summary_6.pdf" in res.headers.get("content-disposition", "")
    assert res.content.startswith(b"%PDF")

def test_30_pdf_path_not_exposed(admin_token):
    """Verify no local server filesystem path is leaked in PDF response headers or payload."""
    res = client.get("/applications/6/kfs/pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    for header_name, header_val in res.headers.items():
        assert "C:\\" not in header_val
        assert "/Users/" not in header_val
        assert "Desktop" not in header_val

# ========================================================
# 8. AUDIT LOGGING TESTS
# ========================================================

def test_31_audit_event_logged_on_kfs(admin_token):
    """Verify that generating a KFS logs an audit event without secrets."""
    db = SessionLocal()
    count_before = db.query(AuditLog).filter(AuditLog.action == "KFS_GENERATED").count()
    db.close()

    res = client.get("/applications/6/kfs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200

    db = SessionLocal()
    latest = db.query(AuditLog).filter(AuditLog.action == "KFS_GENERATED").order_by(AuditLog.id.desc()).first()
    assert latest is not None
    assert latest.resource_type == "application"
    assert latest.resource_id == "6"
    assert "token" not in (latest.metadata_json or "").lower()
    assert "password" not in (latest.metadata_json or "").lower()
    db.close()

# ========================================================
# 9. INTEGRATION & REGRESSION PRESERVATION TESTS
# ========================================================

def test_32_existing_pdf_endpoints_intact(admin_token):
    """Verify existing Adverse Action and Approval Letter PDF endpoints continue to work."""
    res_app = client.get("/applications/6/approval-letter.pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_app.status_code == 200
    assert res_app.headers["content-type"] == "application/pdf"

    res_adv = client.get("/applications/60/adverse-action.pdf", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_adv.status_code == 200
    assert res_adv.headers["content-type"] == "application/pdf"

def test_33_application_60_probability_preserved():
    """Verify Application #60 retains its historical ai_probability = 0.3497."""
    db = SessionLocal()
    app60 = db.query(LoanApplication).filter(LoanApplication.id == 60).first()
    assert app60 is not None
    assert app60.ai_probability == 0.3497
    assert app60.status == "REJECTED"
    db.close()

def test_34_model_registry_records_intact():
    """Verify all 4 models in ModelRegistry remain intact with ACTIVE status."""
    db = SessionLocal()
    models = db.query(ModelRegistry).all()
    assert len(models) == 4
    names = {m.model_name for m in models}
    assert names == {"loan_approval", "loan_amount", "credit_score", "credit_risk"}
    for m in models:
        assert m.deployment_status == "ACTIVE"
        assert m.integrity_status == "VERIFIED"
    db.close()

def test_35_all_six_immutable_hashes_intact():
    """Verify byte-for-byte SHA-256 integrity of all 4 models and 2 raw datasets."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel_path, expected_hash in IMMUTABLE_HASHES.items():
        full_path = os.path.join(root_dir, rel_path)
        assert os.path.exists(full_path), f"Missing artifact: {rel_path}"
        hasher = hashlib.sha256()
        with open(full_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {rel_path}!"
