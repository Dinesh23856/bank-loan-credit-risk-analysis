from pathlib import Path
import os
import time
import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from dotenv import load_dotenv

load_dotenv()

from backend.main import app
from backend.database import SessionLocal
from backend.models import User, LoanApplication, ChatConversation
from backend.db.encrypted_type import EncryptedString, EncryptedFloat, _deterministic_encrypt
from cryptography.fernet import Fernet
from tests.test_project import demo

client = TestClient(app)

@pytest.fixture(scope="module")
def admin_token():
    email = os.getenv("ADMIN_EMAIL", "dineshmore90@gmail.com")
    pw = os.getenv("ADMIN_PASSWORD", "Dinesh@9021")
    res = client.post("/auth/login", json={"email": email, "password": pw})
    assert res.status_code == 200
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def test_users(admin_token):
    # Create two test users for BOLA testing
    u1_email = "user_alpha@example.com"
    u2_email = "user_beta@example.com"
    pw = "SecureTest@123"

    # Clean up if existing
    db = SessionLocal()
    for em in [u1_email, u2_email]:
        ex = db.query(User).filter(User.email == em).first()
        if ex:
            convs = db.query(ChatConversation).filter(ChatConversation.user_id == ex.id).all()
            for c in convs:
                db.delete(c)
            db.delete(ex)
    db.commit()
    db.close()

    r1 = client.post("/auth/register", json={"name": "User Alpha", "email": u1_email, "password": pw})
    r2 = client.post("/auth/register", json={"name": "User Beta", "email": u2_email, "password": pw})

    l1 = client.post("/auth/login", json={"email": u1_email, "password": pw})
    l2 = client.post("/auth/login", json={"email": u2_email, "password": pw})

    return {
        "user1": {"token": l1.json()["access_token"], "email": u1_email},
        "user2": {"token": l2.json()["access_token"], "email": u2_email},
    }

def test_admin_account_integrity(admin_token):
    res = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "admin"
    assert data["name"] == "DineshMore"
    assert data["email"] == "dineshmore90@gmail.com"

def test_treeshap_explainability_and_adverse_action(admin_token):
    payload = demo()
    res = client.post("/predict/loan", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()

    # Core contracts preserved
    assert data["loan_status"] in {"Approved", "Rejected"}
    assert "adverse_action_reasons" in data
    assert "positive_factors" in data
    assert "explanation_metadata" in data

    meta = data["explanation_metadata"]
    assert meta.get("method") == "TreeSHAP"
    assert meta.get("model_name") == "loan_approval"
    assert "base_value" in meta

    # Check reason formatting
    for r in data["adverse_action_reasons"]:
        assert "feature" in r
        assert "contribution" in r
        assert "description" in r
        assert len(r["description"]) > 15
        assert "internal scoring criteria" not in r["description"].lower()

def test_counterfactual_recourse_simulation(admin_token):
    payload = demo()
    cf_req = {
        "applicant_data": payload,
        "requested_loan_amount": payload["requested_loan_amount"] * 0.7,
        "debt_to_income_ratio": 0.25,
        "savings": payload["savings"] + 50000
    }
    res = client.post("/predict/counterfactual", json=cf_req, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "original_probability" in data
    assert "approval_probability" in data
    assert "estimated_decision" in data
    assert "changes" in data
    assert "feasible" in data
    assert "simulation" in data["disclaimer"].lower()

def test_counterfactual_protects_demographic_attributes(admin_token):
    payload = demo()
    # Attempting to modify gender in recourse should be rejected both via API (HTTP 422) and core simulation logic
    cf_req = {
        "applicant_data": payload,
        "gender": "Female" if payload["gender"] == "Male" else "Male"
    }
    res = client.post("/predict/counterfactual", json=cf_req, headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 422

    from backend.services.prediction_service import run_counterfactual_simulation
    with pytest.raises(ValueError) as exc:
        run_counterfactual_simulation(payload, {"gender": "Female"})
    assert "protected demographic variable" in str(exc.value)

def test_field_encryption_and_rotation():
    orig_key = os.environ.get("FIELD_ENCRYPTION_KEY")
    orig_fallback = os.environ.get("FIELD_ENCRYPTION_KEY_FALLBACK")
    try:
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        os.environ["FIELD_ENCRYPTION_KEY"] = key1
        os.environ.pop("FIELD_ENCRYPTION_KEY_FALLBACK", None)
        s = EncryptedString()
        enc1 = s.process_bind_param("Confidential PII", None)
        assert enc1.startswith("gAAAAA")

        # Rotate key: key2 primary, key1 fallback
        os.environ["FIELD_ENCRYPTION_KEY"] = key2
        os.environ["FIELD_ENCRYPTION_KEY_FALLBACK"] = key1

        s_rot = EncryptedString()
        dec = s_rot.process_result_value(enc1, None)
        assert dec == "Confidential PII"

        # Numeric encryption
        f = EncryptedFloat()
        enc_f = f.process_bind_param(125000.75, None)
        assert enc_f.startswith("gAAAAA")
        assert abs(f.process_result_value(enc_f, None) - 125000.75) < 1e-4
    finally:
        if orig_key is not None:
            os.environ["FIELD_ENCRYPTION_KEY"] = orig_key
        else:
            os.environ.pop("FIELD_ENCRYPTION_KEY", None)
        if orig_fallback is not None:
            os.environ["FIELD_ENCRYPTION_KEY_FALLBACK"] = orig_fallback
        else:
            os.environ.pop("FIELD_ENCRYPTION_KEY_FALLBACK", None)

def test_async_task_workflow(admin_token):
    db = SessionLocal()
    app_rec = db.query(LoanApplication).order_by(LoanApplication.id.desc()).first()
    app_id = app_rec.id
    db.close()

    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.post(f"/applications/{app_id}/process", headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "PENDING"
    task_id = data["task_id"]

    # Poll status
    time.sleep(0.5)
    t_res = client.get(f"/tasks/{task_id}", headers=headers)
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert t_data["status"] in {"PROCESSING", "SUCCESS"}

def test_regulatory_pdf_generation(admin_token):
    db = SessionLocal()
    app_rec = db.query(LoanApplication).order_by(LoanApplication.id.desc()).first()
    app_id = app_rec.id
    db.close()

    headers = {"Authorization": f"Bearer {admin_token}"}
    pdf1 = client.post(f"/applications/{app_id}/generate-adverse-action-pdf", headers=headers)
    assert pdf1.status_code == 200
    assert pdf1.content.startswith(b"%PDF-")

    pdf2 = client.post(f"/applications/{app_id}/generate-approval-letter", headers=headers)
    assert pdf2.status_code == 200
    assert pdf2.content.startswith(b"%PDF-")

def test_hardened_auth_rotation_and_replay_detection():
    email = os.getenv("ADMIN_EMAIL", "dineshmore90@gmail.com")
    pw = os.getenv("ADMIN_PASSWORD", "Dinesh@9021")

    res = client.post("/auth/login", json={"email": email, "password": pw})
    assert res.status_code == 200
    cookie1 = res.cookies.get("refresh_token")
    assert cookie1 is not None

    # Rotate
    ref_res = client.post("/auth/refresh", cookies={"refresh_token": cookie1})
    assert ref_res.status_code == 200
    cookie2 = ref_res.cookies.get("refresh_token")
    assert cookie2 != cookie1

    # Replay detection
    replay_res = client.post("/auth/refresh", cookies={"refresh_token": cookie1})
    assert replay_res.status_code == 401
    assert "Token reuse detected" in replay_res.json().get("detail", "")

def test_owasp_bola_object_level_authorization(test_users):
    u1_token = test_users["user1"]["token"]
    u2_token = test_users["user2"]["token"]

    # User 1 creates an application
    payload = demo()
    res1 = client.post("/predict/loan", json=payload, headers={"Authorization": f"Bearer {u1_token}"})
    assert res1.status_code == 200

    db = SessionLocal()
    u1 = db.query(User).filter(User.email == test_users["user1"]["email"]).first()
    app1 = db.query(LoanApplication).filter(LoanApplication.user_id == u1.id).order_by(LoanApplication.id.desc()).first()
    app1_id = app1.id
    db.close()

    # User 1 can view it
    get_u1 = client.get(f"/applications/{app1_id}", headers={"Authorization": f"Bearer {u1_token}"})
    assert get_u1.status_code == 200

    # User 2 MUST BE FORBIDDEN (BOLA prevention)
    get_u2 = client.get(f"/applications/{app1_id}", headers={"Authorization": f"Bearer {u2_token}"})
    assert get_u2.status_code in {403, 404}

    # User 2 cannot download User 1's adverse action PDF
    pdf_u2 = client.post(f"/applications/{app1_id}/generate-adverse-action-pdf", headers={"Authorization": f"Bearer {u2_token}"})
    assert pdf_u2.status_code == 403

def test_owasp_bfla_admin_route_protection(test_users):
    u1_token = test_users["user1"]["token"]
    for path in ["/admin/summary", "/admin/users", "/admin/applications", "/admin/metrics", "/admin/drift", "/admin/fairness"]:
        res = client.get(path, headers={"Authorization": f"Bearer {u1_token}"})
        assert res.status_code == 403

def test_admin_monitoring_drift_and_fairness(admin_token):
    headers = {"Authorization": f"Bearer {admin_token}"}
    m = client.get("/admin/metrics", headers=headers)
    assert m.status_code == 200
    assert "operational" in m.json()

    d7 = client.get("/admin/drift?window_days=7", headers=headers)
    assert d7.status_code == 200
    assert d7.json().get("window_days") == 7

    d30 = client.get("/admin/drift?window_days=30", headers=headers)
    assert d30.status_code == 200

    fairness = client.get("/admin/fairness?attribute=gender", headers=headers)
    assert fairness.status_code == 200
    f_data = fairness.json()
    assert "disparate_impact_ratio" in f_data
    assert "four_fifths_rule_passed" in f_data

def test_application_consistency_and_probability_integrity(test_users):
    u1_token = test_users["user1"]["token"]
    u2_token = test_users["user2"]["token"]

    # 1. User 1 submits an application
    payload = {
        "applicant_name": "Integrity Applicant",
        "city": "Mumbai",
        "region": "Maharashtra",
        "age": 32,
        "dependents": 1,
        "gender": "Female",
        "marital_status": "Married",
        "education": "Graduate",
        "employment_type": "Salaried",
        "annual_income": 850000.0,
        "debt_to_income_ratio": 0.28,
        "savings": 250000.0,
        "bank_balance": 120000.0,
        "assets": 500000.0,
        "credit_history": "Good",
        "previous_loans": 1,
        "previous_defaults": 0,
        "payment_history": 92.0,
        "credit_utilization": 0.25,
        "credit_score": 740.0,
        "loan_type": "Personal",
        "requested_loan_amount": 300000.0,
        "loan_term": 36,
        "collateral_value": 400000.0,
        "interest_rate": 9.5
    }
    pred_res = client.post("/predict/loan", headers={"Authorization": f"Bearer {u1_token}"}, json=payload)
    assert pred_res.status_code == 200
    pred_data = pred_res.json()
    model_prob = pred_data["approval_probability"]
    pred_score = pred_data["credit_score"]

    # 2. Query GET /applications to find the created application id
    apps_res = client.get("/applications", headers={"Authorization": f"Bearer {u1_token}"})
    assert apps_res.status_code == 200
    app_id = apps_res.json()["items"][0]["id"]

    # 3. GET /applications/{id} must return approval_probability, applicant credit_score, and predicted_credit_score
    detail_res = client.get(f"/applications/{app_id}", headers={"Authorization": f"Bearer {u1_token}"})
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["approval_probability"] is not None
    assert abs(detail_data["approval_probability"] - model_prob) < 1e-4
    assert detail_data["credit_score"] == 740.0
    assert detail_data["predicted_credit_score"] == pred_score

    # 4. Verify BOLA: User 2 cannot access User 1's application
    u2_get = client.get(f"/applications/{app_id}", headers={"Authorization": f"Bearer {u2_token}"})
    assert u2_get.status_code in {403, 404}

    # 5. Verify Frontend ApplicationDetail.jsx has no hardcoded 25% and distinguishes credit scores
    frontend_detail_path = Path("frontend/src/pages/ApplicationDetail.jsx")
    if frontend_detail_path.exists():
        content = frontend_detail_path.read_text(encoding="utf-8")
        assert "isApproved ? 0.75 : 0.25" not in content, "Hardcoded 25% waterfall probability found"
        assert "originalProbability={0.25}" not in content, "Hardcoded 25% recourse probability found"
        assert "row.approval_probability" in content, "Dynamic row.approval_probability must be used"
        assert "Applicant Credit Score" in content, "Missing Applicant Credit Score label"
        assert "Predicted Credit Score" in content, "Missing Predicted Credit Score label"

    # 6. Verify Banking AI Assistant fallback distinguishes Applicant Credit Score vs Predicted Credit Score
    with patch("backend.routes.chat_routes.get_ai_provider") as mock_provider:
        from backend.services.ai_provider import AIProviderUnavailableError
        provider = AsyncMock()
        provider.generate_response.side_effect = AIProviderUnavailableError("Offline")
        mock_provider.return_value = provider

        chat_res = client.post(
            "/chat",
            headers={"Authorization": f"Bearer {u1_token}"},
            json={"message": "Summarize my application", "application_id": app_id}
        )
        assert chat_res.status_code == 200
        chat_msg = chat_res.json()["message"]
        assert "Applicant Credit Score" in chat_msg
        assert "Predicted Credit Score" in chat_msg
        assert str(detail_data["credit_score"]) in chat_msg
