import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

from backend.main import app
from backend.database import SessionLocal
from backend.models import User, ModelRegistry, AuditLog, LoanApplication
from backend.services.model_registry_service import (
    compute_file_sha256,
    verify_model_artifact_integrity,
    update_model_status,
    record_governance_review,
    generate_model_card,
    ALLOWED_LIFECYCLE_TRANSITIONS,
    ROOT_DIR
)
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
def rbac_users(admin_token):
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
# 1. MODEL REGISTRATION & INVENTORY VERIFICATION
# ========================================================

def test_01_four_models_registered_in_database():
    """Verify that exactly four immutable models are registered in the model_registry table."""
    db = SessionLocal()
    models = db.query(ModelRegistry).all()
    db.close()
    names = {m.model_name for m in models}
    assert names == {"loan_approval", "loan_amount", "credit_score", "credit_risk"}
    assert len(models) == 4

def test_02_correct_artifact_paths():
    """Verify each registered model points to its exact expected serialized .joblib file."""
    db = SessionLocal()
    models = {m.model_name: m.artifact_path for m in db.query(ModelRegistry).all()}
    db.close()
    assert models["loan_approval"] == "models/loan_approval.joblib"
    assert models["loan_amount"] == "models/loan_amount.joblib"
    assert models["credit_score"] == "models/credit_score.joblib"
    assert models["credit_risk"] == "models/credit_risk.joblib"

def test_03_correct_sha256_signatures():
    """Verify each registered model stores the exact verified baseline SHA-256 signature."""
    db = SessionLocal()
    models = {m.model_name: m.artifact_sha256 for m in db.query(ModelRegistry).all()}
    db.close()
    for rel_path, expected_hash in IMMUTABLE_HASHES.items():
        if rel_path.startswith("models/"):
            m_name = rel_path.split("/")[1].replace(".joblib", "")
            assert models[m_name] == expected_hash

def test_04_correct_model_metadata():
    """Verify architecture, task types, target variables, and version metadata."""
    db = SessionLocal()
    models = {m.model_name: m for m in db.query(ModelRegistry).all()}
    db.close()

    assert models["loan_approval"].model_version == "2.0.0"
    assert models["loan_approval"].task == "binary_classification"
    assert models["loan_approval"].model_type == "RandomForestClassifier"
    assert models["loan_approval"].target_variable == "loan_status"

    assert models["loan_amount"].task == "regression"
    assert models["loan_amount"].model_type == "RandomForestRegressor"
    assert models["loan_amount"].target_variable == "approved_loan_amount"

    assert models["credit_score"].task == "regression"
    assert models["credit_score"].model_type == "GradientBoostingRegressor"
    assert models["credit_score"].target_variable == "predicted_credit_score"

    assert models["credit_risk"].task == "multiclass_classification"
    assert models["credit_risk"].model_type == "RandomForestClassifier"
    assert models["credit_risk"].target_variable == "risk_level"

def test_05_correct_training_metrics_in_registry():
    """Verify that actual metrics from reports/training_metrics.json are preserved in the registry."""
    db = SessionLocal()
    approval = db.query(ModelRegistry).filter(ModelRegistry.model_name == "loan_approval").first()
    db.close()
    metrics = json.loads(approval.metrics_json)
    assert abs(metrics["accuracy"] - 0.7733333333333333) < 1e-4
    assert abs(metrics["roc_auc"] - 0.7426283950419577) < 1e-4
    assert "confusion_matrix" in metrics

# ========================================================
# 2. MODEL CARDS GENERATION
# ========================================================

def test_06_model_card_generation_via_api(admin_token):
    """Verify that dynamic model card endpoint returns full specifications without claims of regulatory warranty."""
    res = client.get("/models/loan_approval/card", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    card = res.json()
    assert card["model_name"] == "loan_approval"
    assert card["model_version"] == "2.0.0"
    assert card["feature_count"] == 29
    assert "dataset" in card
    assert card["dataset"]["reference"] == "data/raw/loan_data.csv"
    assert "explainability" in card
    assert "limitations" in card
    assert "regulatory_disclaimer" in card
    assert "Does not constitute certification" in card["regulatory_disclaimer"]

# ========================================================
# 3. RBAC AUTHORIZATION
# ========================================================

def test_07_risk_analyst_can_read_registry(rbac_users):
    """Verify RISK_ANALYST role can read model registry listing and model details."""
    token = rbac_users["analyst"]["token"]
    res = client.get("/models", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 4

    detail = client.get("/models/credit_score", headers={"Authorization": f"Bearer {token}"})
    assert detail.status_code == 200
    assert detail.json()["model_name"] == "credit_score"

def test_08_admin_can_read_registry(admin_token):
    """Verify ADMIN role can read model registry listing and cards."""
    res = client.get("/models", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 4

def test_09_customer_forbidden_from_registry(rbac_users):
    """Verify CUSTOMER role receives HTTP 403 when attempting to access model registry."""
    token = rbac_users["customer"]["token"]
    res = client.get("/models", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    res_card = client.get("/models/loan_approval/card", headers={"Authorization": f"Bearer {token}"})
    assert res_card.status_code == 403

def test_10_underwriter_forbidden_from_registry(rbac_users):
    """Verify UNDERWRITER role receives HTTP 403 when attempting to access model governance."""
    token = rbac_users["underwriter"]["token"]
    res = client.get("/models", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

def test_11_risk_analyst_forbidden_from_lifecycle_updates(rbac_users):
    """Verify RISK_ANALYST cannot alter model lifecycle or deployment status (HTTP 403)."""
    token = rbac_users["analyst"]["token"]
    res = client.put("/models/loan_approval/status", json={"deployment_status": "INACTIVE"}, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403

# ========================================================
# 4. GOVERNANCE REVIEW & LIFECYCLE STATE MACHINE
# ========================================================

def test_12_admin_governance_review(admin_token):
    """Verify ADMIN can submit an official governance review with notes."""
    res = client.post(
        "/models/loan_approval/review",
        json={"decision": "APPROVED", "review_notes": "Phase 2 baseline governance approval for retail loan evaluation."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["lifecycle_status"] == "APPROVED"
    assert "Phase 2 baseline governance approval" in data["review_notes"]

def test_13_invalid_lifecycle_transition_rejected(admin_token):
    """Verify that arbitrary illegal state jumps (e.g. ACTIVE -> DRAFT) are rejected with HTTP 400."""
    res = client.put(
        "/models/loan_approval/status",
        json={"lifecycle_status": "DRAFT"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 400
    assert "Invalid lifecycle transition" in res.json()["detail"]

# ========================================================
# 5. ARTIFACT INTEGRITY VERIFICATION & TAMPER DETECTION
# ========================================================

def test_14_integrity_match_detected_on_untouched_artifact(admin_token):
    """Verify that integrity verification returns MATCH for verified immutable models."""
    res = client.post("/models/loan_approval/verify-integrity", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "MATCH"
    assert body["expected_hash"] == IMMUTABLE_HASHES["models/loan_approval.joblib"]
    assert body["actual_hash"] == IMMUTABLE_HASHES["models/loan_approval.joblib"]

def test_15_integrity_mismatch_detected_safely():
    """Verify that if an artifact hash diverges, verify_model_artifact_integrity returns MISMATCH and fails safely."""
    db = SessionLocal()
    m = db.query(ModelRegistry).filter(ModelRegistry.model_name == "loan_approval").first()
    original_hash = m.artifact_sha256

    # Create a mock record with a deliberate non-matching hash
    test_record = ModelRegistry(
        model_name="mock_tampered_model",
        model_version="2.0.0",
        task="binary_classification",
        model_type="RandomForestClassifier",
        artifact_path="models/loan_approval.joblib",
        artifact_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        dataset_reference="data/raw/loan_data.csv",
        dataset_sha256="cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a",
        target_variable="loan_status",
        features_json="[]",
        metrics_json="{}",
        lifecycle_status="APPROVED",
        deployment_status="ACTIVE",
        integrity_status="VERIFIED"
    )
    db.add(test_record)
    db.commit()
    db.refresh(test_record)

    res = verify_model_artifact_integrity(db, test_record)
    assert res["status"] == "MISMATCH"
    assert test_record.integrity_status == "MISMATCH"
    assert test_record.deployment_status == "INACTIVE"  # Safe auto-deactivation
    assert test_record.artifact_sha256 == "0000000000000000000000000000000000000000000000000000000000000000"  # NEVER OVERWRITTEN

    # Clean up mock record
    db.delete(test_record)
    db.commit()
    db.close()

def test_16_mismatch_creates_audit_event():
    """Verify that MODEL_INTEGRITY_MISMATCH is logged in the persistent audit_logs table."""
    db = SessionLocal()
    recent_mismatch = (
        db.query(AuditLog)
        .filter(AuditLog.action == "MODEL_INTEGRITY_MISMATCH")
        .order_by(AuditLog.timestamp.desc())
        .first()
    )
    db.close()
    assert recent_mismatch is not None
    assert recent_mismatch.resource_type == "model"

def test_17_cannot_activate_model_with_failing_integrity(admin_token):
    """Verify server-side validation rejects activation if integrity verification fails."""
    db = SessionLocal()
    tampered = ModelRegistry(
        model_name="failing_integrity_test",
        model_version="2.0.0",
        task="regression",
        model_type="RandomForestRegressor",
        artifact_path="models/non_existent_artifact.joblib",
        artifact_sha256="1111111111111111111111111111111111111111111111111111111111111111",
        dataset_reference="data/raw/loan_data.csv",
        dataset_sha256="cee57f9c187a4cfd97ccf40030a279d6ab41bdd3c78bb80704c118a2ecf0554a",
        target_variable="approved_loan_amount",
        features_json="[]",
        metrics_json="{}",
        lifecycle_status="APPROVED",
        deployment_status="INACTIVE"
    )
    db.add(tampered)
    db.commit()
    db.refresh(tampered)

    res = client.put(
        f"/models/{tampered.id}/status",
        json={"deployment_status": "ACTIVE"},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 400
    assert "integrity" in res.json()["detail"].lower()

    db.delete(tampered)
    db.commit()
    db.close()

# ========================================================
# 6. EXISTING REGRESSION & PREDICTION INTEGRITY
# ========================================================

def test_18_existing_prediction_functionality_intact(admin_token):
    """Verify that existing /predict/loan continues to work seamlessly with immutable .joblib models."""
    sample_input = {
        "applicant_name": "Phase2 Regression Applicant",
        "city": "Mumbai",
        "region": "West",
        "age": 35,
        "dependents": 1,
        "gender": "Female",
        "marital_status": "Single",
        "education": "Graduate",
        "employment_type": "Salaried",
        "annual_income": 1200000.0,
        "debt_to_income_ratio": 0.22,
        "savings": 450000.0,
        "bank_balance": 200000.0,
        "assets": 1500000.0,
        "credit_history": "Good",
        "previous_loans": 1,
        "previous_defaults": 0,
        "payment_history": 98.0,
        "credit_utilization": 0.25,
        "credit_score": 760.0,
        "loan_type": "Personal",
        "requested_loan_amount": 500000.0,
        "loan_term": 36,
        "collateral_value": 0.0,
        "interest_rate": 8.5
    }
    res = client.post("/predict/loan", json=sample_input, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "loan_status" in data
    assert "approval_probability" in data
    assert isinstance(data["approval_probability"], float)

def test_19_existing_application_authorization_intact(rbac_users):
    """Verify BOLA protection is preserved: customer cannot read another user's application."""
    cust_token = rbac_users["customer"]["token"]
    # App 60 belongs to dineshmore90@gmail.com, customer must be rejected with 404
    res = client.get("/applications/60", headers={"Authorization": f"Bearer {cust_token}"})
    assert res.status_code == 404

def test_20_audit_logs_contain_no_secrets():
    """Verify that none of the audit logs written during Phase 2 contain passwords, tokens, or secrets."""
    db = SessionLocal()
    logs = db.query(AuditLog).all()
    db.close()
    for l in logs:
        raw_text = f"{l.metadata_json or ''} {l.before_value or ''} {l.after_value or ''} {l.reason or ''}"
        for secret_token in ["password_hash", "$2b$", "Bearer ", "SECRET", "fernet", "gemini_api_key"]:
            assert secret_token not in raw_text, f"Secret leak detected in audit log #{l.id}: {secret_token}"
