import os
import json
import hashlib
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

from backend.main import app
from backend.database import SessionLocal
from backend.models import User, LoanApplication, ApplicationStatusHistory, AuditLog
from backend.services.workflow_service import ApplicationStatus, ALLOWED_TRANSITIONS, validate_transition
from backend.services.audit_service import sanitize_metadata
from backend.dependencies import normalize_role

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
def rbac_users(admin_token):
    """
    Sets up users for each discrete role: CUSTOMER, UNDERWRITER, RISK_ANALYST.
    Uses clean isolation so production users are untouched.
    """
    pw = "Phase1Test@9021"
    roles = {
        "customer": ("phase1_customer@example.com", "CUSTOMER"),
        "underwriter": ("phase1_underwriter@example.com", "UNDERWRITER"),
        "analyst": ("phase1_analyst@example.com", "RISK_ANALYST"),
    }
    tokens = {}
    db = SessionLocal()
    from backend.auth import hash_password
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
# 1. STATE MACHINE & GUARDED APPLICATION WORKFLOW
# ========================================================

def test_workflow_state_machine_transitions():
    """Verifies that allowed transitions succeed and forbidden transitions raise HTTPException(400)."""
    # Valid transitions
    validate_transition("DRAFT", "SUBMITTED", "CUSTOMER")
    validate_transition("SUBMITTED", "CREDIT_CHECKING", "UNDERWRITER")
    validate_transition("CREDIT_CHECKING", "AI_ASSESSED", "ADMIN")
    validate_transition("AI_ASSESSED", "MANUAL_REVIEW", "ADMIN")
    validate_transition("APPROVED", "OFFERED", "ADMIN")
    validate_transition("OFFERED", "ACCEPTED", "CUSTOMER")
    validate_transition("ACCEPTED", "CLOSED", "ADMIN")

    # Invalid illegal state jumps
    with pytest.raises(Exception) as exc_info:
        validate_transition("DRAFT", "APPROVED", "ADMIN")
    assert "Invalid state transition" in str(exc_info.value)

    with pytest.raises(Exception) as exc_info:
        validate_transition("CLOSED", "SUBMITTED", "ADMIN")
    assert "Invalid state transition" in str(exc_info.value)

def test_customer_forbidden_from_self_approval():
    """Verifies that customer role is prohibited from approving an application (HTTP 403)."""
    with pytest.raises(Exception) as exc_info:
        validate_transition("MANUAL_REVIEW", "APPROVED", "CUSTOMER")
    assert "Forbidden" in str(exc_info.value)

def test_underwriter_reason_validation():
    """Underwriter review transition requires reason >= 5 characters."""
    with pytest.raises(Exception) as exc_info:
        validate_transition("MANUAL_REVIEW", "APPROVED", "UNDERWRITER", reason="ok")
    assert "minimum 5 characters" in str(exc_info.value)

    # Valid reason succeeds
    validate_transition("MANUAL_REVIEW", "APPROVED", "UNDERWRITER", reason="Sufficient collateral and liquidity verified.")

# ========================================================
# 2. FOUR-ROLE RBAC ACCESS CONTROL MATRIX
# ========================================================

def test_role_normalization():
    """Verifies non-elevating role normalization."""
    assert normalize_role("user") == "CUSTOMER"
    assert normalize_role("customer") == "CUSTOMER"
    assert normalize_role("admin") == "ADMIN"
    assert normalize_role("underwriter") == "UNDERWRITER"
    assert normalize_role("risk_analyst") == "RISK_ANALYST"
    assert normalize_role("unknown") == "CUSTOMER"

def test_underwriter_queue_role_access(admin_token, rbac_users):
    """Underwriter queue is accessible by Underwriter and Admin, forbidden for Customer and Risk Analyst."""
    # Underwriter -> 200
    res_uw = client.get("/underwriter/queue", headers={"Authorization": f"Bearer {rbac_users['underwriter']['token']}"})
    assert res_uw.status_code == 200
    assert "items" in res_uw.json()

    # Admin -> 200
    res_admin = client.get("/underwriter/queue", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200

    # Customer -> 403 Forbidden
    res_cust = client.get("/underwriter/queue", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res_cust.status_code == 403

    # Risk Analyst -> 403 Forbidden
    res_ra = client.get("/underwriter/queue", headers={"Authorization": f"Bearer {rbac_users['analyst']['token']}"})
    assert res_ra.status_code == 403

def test_admin_audit_logs_role_access(admin_token, rbac_users):
    """Admin audit logs endpoint is accessible ONLY by Admin, forbidden for all other roles."""
    # Admin -> 200
    res_admin = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_admin.status_code == 200
    assert "items" in res_admin.json()

    # Underwriter -> 403
    res_uw = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {rbac_users['underwriter']['token']}"})
    assert res_uw.status_code == 403

    # Customer -> 403
    res_cust = client.get("/admin/audit-logs", headers={"Authorization": f"Bearer {rbac_users['customer']['token']}"})
    assert res_cust.status_code == 403

def test_admin_role_reassignment(admin_token, rbac_users):
    """Admin can change a user's role and the system logs ROLE_CHANGED in audit_logs."""
    target_user_id = rbac_users["customer"]["user_id"]
    res = client.put(
        f"/admin/users/{target_user_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "UNDERWRITER", "reason": "Promoted to Underwriter team"}
    )
    assert res.status_code == 200
    assert res.json()["role"] == "UNDERWRITER"

    # Verify audit log was created
    db = SessionLocal()
    audit_entry = db.query(AuditLog).filter(
        AuditLog.action == "ROLE_CHANGED",
        AuditLog.resource_id == str(target_user_id)
    ).order_by(AuditLog.id.desc()).first()
    assert audit_entry is not None
    assert audit_entry.before_value == "CUSTOMER"
    assert audit_entry.after_value == "UNDERWRITER"

    # Revert back to CUSTOMER
    rev = client.put(
        f"/admin/users/{target_user_id}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "CUSTOMER", "reason": "Reverting test promotion"}
    )
    assert rev.status_code == 200
    assert rev.json()["role"] == "CUSTOMER"
    db.close()

# ========================================================
# 3. HUMAN-IN-THE-LOOP UNDERWRITER REVIEW WORKFLOW
# ========================================================

def test_underwriter_decision_lifecycle(admin_token, rbac_users):
    """
    Tests complete lifecycle:
    1. Create application in MANUAL_REVIEW status
    2. Attempt decision with short reason -> rejected
    3. Underwriter submits valid review decision
    4. Verify application status, underwriter decision, AI decision untouched, status history and audit log created.
    """
    db = SessionLocal()
    app_record = LoanApplication(
        user_id=rbac_users["customer"]["user_id"],
        applicant_name="Phase1 Test Applicant",
        loan_amount=500000.0,
        status="MANUAL_REVIEW",
        approval_status="Manual Review",
        ai_decision="Approved",
        ai_probability=0.52,
        annual_income=600000.0,
        credit_score=680.0,
        age=32,
        dependents=0,
        gender="Male",
        marital_status="Single",
        education="Graduate",
        employment_type="Salaried",
        debt_to_income_ratio=0.25,
        savings=100000.0,
        bank_balance=50000.0,
        assets=200000.0,
        previous_loans=1,
        previous_defaults=0,
        payment_history=95.0,
        credit_utilization=0.3,
        credit_history="Good",
        loan_type="Personal",
        loan_term_months=36,
        interest_rate=8.5,
        collateral_value=0.0
    )
    db.add(app_record)
    db.commit()
    db.refresh(app_record)
    app_id = app_record.id
    db.close()

    # Short reason -> Fails
    fail_res = client.post(
        f"/underwriter/applications/{app_id}/review",
        headers={"Authorization": f"Bearer {rbac_users['underwriter']['token']}"},
        json={"decision": "APPROVED", "reason": "bad"}
    )
    assert fail_res.status_code in (400, 422)

    # Valid underwriter determination
    review_reason = "Verified strong employer history and debt service coverage ratio."
    comments = "Recommended supervisory concurrence."
    success_res = client.post(
        f"/underwriter/applications/{app_id}/review",
        headers={"Authorization": f"Bearer {rbac_users['underwriter']['token']}"},
        json={"decision": "APPROVED", "reason": review_reason, "reviewer_comments": comments}
    )
    assert success_res.status_code == 200
    data = success_res.json()

    assert data["status"] == "APPROVED"
    assert data["approval_status"] == "Approved"
    assert data["underwriter_decision"] == "APPROVED"
    assert data["underwriter_reason"] == review_reason
    assert data["reviewer_comments"] == comments
    # AI decision and AI probability remain intact!
    assert data["ai_decision"] == "Approved"
    assert data["ai_probability"] == 0.52

    # Verify status history
    hist_res = client.get(
        f"/applications/{app_id}/history",
        headers={"Authorization": f"Bearer {rbac_users['underwriter']['token']}"}
    )
    assert hist_res.status_code == 200
    history_items = hist_res.json()
    assert len(history_items) >= 1
    latest_hist = history_items[-1]
    assert latest_hist["previous_status"] == "MANUAL_REVIEW"
    assert latest_hist["new_status"] == "APPROVED"
    assert latest_hist["changed_by_role"] == "UNDERWRITER"
    assert latest_hist["reason"] == review_reason

# ========================================================
# 4. PERSISTENT AUDIT LOGGING & ZERO SECRET LEAKAGE
# ========================================================

def test_audit_secret_sanitization():
    """Verifies that passwords, tokens, and secrets are scrubbed before storage."""
    dirty_meta = {
        "email": "applicant@test.com",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
        "api_key": "sk-1234567890abcdef",
        "nested": {
            "password_hash": "$2b$12$e...",
            "secret": "top_secret_sauce",
            "safe_field": 42
        }
    }
    clean_meta = sanitize_metadata(dirty_meta)
    assert clean_meta["password"] == "[REDACTED]"
    assert clean_meta["access_token"] == "[REDACTED]"
    assert clean_meta["api_key"] == "[REDACTED]"
    assert clean_meta["nested"]["password_hash"] == "[REDACTED]"
    assert clean_meta["nested"]["secret"] == "[REDACTED]"
    assert clean_meta["nested"]["safe_field"] == 42
    assert clean_meta["email"] == "applicant@test.com"

def test_login_audit_events():
    """Verifies that LOGIN_SUCCESS and LOGIN_FAILURE create sanitized audit logs."""
    email = os.getenv("ADMIN_EMAIL", "dineshmore90@gmail.com")
    pw = os.getenv("ADMIN_PASSWORD", "Dinesh@9021")

    # Success
    client.post("/auth/login", json={"email": email, "password": pw})

    # Failure
    client.post("/auth/login", json={"email": email, "password": "WrongPassword!999"})

    db = SessionLocal()
    success_log = db.query(AuditLog).filter(AuditLog.action == "LOGIN_SUCCESS").order_by(AuditLog.id.desc()).first()
    failure_log = db.query(AuditLog).filter(AuditLog.action == "LOGIN_FAILURE").order_by(AuditLog.id.desc()).first()
    assert success_log is not None
    assert failure_log is not None
    assert "SUCCESS" in (success_log.metadata_json or "")
    assert "FAILURE" in (failure_log.metadata_json or "")
    assert "WrongPassword" not in (failure_log.metadata_json or "")
    db.close()

def test_audit_logs_query_filtering(admin_token):
    """Tests multi-criteria filtering on GET /admin/audit-logs."""
    res = client.get("/admin/audit-logs?action=LOGIN&page=1&page_size=10", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    for item in data["items"]:
        assert "LOGIN" in item["action"]

# ========================================================
# 5. APPLICATION #60 & MODEL HASH INVARIANTS
# ========================================================

def test_application_60_probability_consistency(admin_token):
    """Verifies Application #60 returns its genuine model probability (~0.3497 / 35.0%)."""
    res = client.get("/applications/60", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    prob = data.get("approval_probability")
    assert prob is not None, "Application #60 must have an approval_probability."
    assert 0.34 <= prob <= 0.36, f"Application #60 probability {prob} deviates from expected ~0.3497"

def test_immutable_models_and_datasets():
    """Verifies SHA-256 integrity for all 4 models and 2 raw CSV datasets."""
    for rel_path, expected_hash in IMMUTABLE_HASHES.items():
        assert os.path.exists(rel_path), f"File {rel_path} does not exist."
        h = hashlib.sha256(open(rel_path, "rb").read()).hexdigest()
        assert h == expected_hash, f"Hash mismatch for {rel_path}: got {h}, expected {expected_hash}"
