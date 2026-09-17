"""Opt-in live MySQL E2E tests.

These are intentionally skipped unless a real MySQL DATABASE_URL and the full
production dependencies are available. They never substitute SQLite.
"""
import os
import uuid
import pytest

if not os.getenv("DATABASE_URL", "").startswith("mysql+pymysql://"):
    pytest.skip("Live E2E requires DATABASE_URL=mysql+pymysql://...", allow_module_level=True)

pytest.importorskip("pymysql")
pytest.importorskip("bcrypt")
pytest.importorskip("jose")

from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine, SessionLocal
from backend.models import User, LoanApplication, ModelLog
from backend.auth import hash_password
from tests.test_project import demo


def _register(client, name, email, password):
    r = client.post("/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


def test_live_mysql_auth_prediction_rbac_and_isolation():
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)
    suffix = uuid.uuid4().hex[:12]
    password = "Strong-test-password-123!"
    email1 = f"e2e1-{suffix}@example.com"
    email2 = f"e2e2-{suffix}@example.com"
    admin_email = f"admin-{suffix}@example.com"
    created_user_ids = []
    created_app_ids = []
    try:
        # Anonymous access is rejected before business logic is reached.
        assert client.get("/applications").status_code == 401
        assert client.get("/admin/summary").status_code == 401

        user = _register(client, "E2E User One", email1, password)
        created_user_ids.append(user["id"])
        duplicate = client.post("/auth/register", json={"name": "Dup", "email": email1, "password": password})
        assert duplicate.status_code == 409
        injected = client.post("/auth/register", json={"name": "Injected", "email": f"inject-{suffix}@example.com", "password": password, "role": "admin"})
        assert injected.status_code == 422

        login = client.post("/auth/login", json={"email": email1, "password": password})
        assert login.status_code == 200
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        assert client.get("/auth/me", headers=headers).status_code == 200
        assert client.post("/auth/login", json={"email": email1, "password": "wrong-password"}).status_code == 401
        assert client.get("/applications", headers={"Authorization": "Bearer invalid"}).status_code == 401

        payload = demo()
        prediction = client.post("/predict/loan", json=payload, headers=headers)
        assert prediction.status_code == 200, prediction.text
        body = prediction.json()
        assert body["loan_status"] in {"Approved", "Rejected"}

        apps = client.get("/applications", headers=headers)
        assert apps.status_code == 200 and apps.json()["total"] == 1
        app_id = apps.json()["items"][0]["id"]
        created_app_ids.append(app_id)
        assert client.get(f"/applications/{app_id}", headers=headers).status_code == 200
        assert client.post("/predict/risk", json=payload, headers=headers).status_code == 200
        invalid = dict(payload); invalid["age"] = 999
        assert client.post("/predict/loan", json=invalid, headers=headers).status_code == 422

        # Risk-only prediction must not create another application row.
        assert client.get("/applications", headers=headers).json()["total"] == 1

        # Second user cannot access the first user's application.
        user2 = _register(client, "E2E User Two", email2, password)
        created_user_ids.append(user2["id"])
        token2 = client.post("/auth/login", json={"email": email2, "password": password}).json()["access_token"]
        assert client.get(f"/applications/{app_id}", headers={"Authorization": f"Bearer {token2}"}).status_code == 404
        assert client.get("/admin/summary", headers={"Authorization": f"Bearer {token2}"}).status_code == 403

        # Admin-only paths are tested with a real database user, not a mocked role.
        db = SessionLocal()
        try:
            admin = User(name="E2E Admin", email=admin_email, password_hash=hash_password(password), role="admin")
            db.add(admin); db.commit(); db.refresh(admin); created_user_ids.append(admin.id)
        finally:
            db.close()
        admin_token = client.post("/auth/login", json={"email": admin_email, "password": password}).json()["access_token"]
        ah = {"Authorization": f"Bearer {admin_token}"}
        for path in ("/admin/summary", "/admin/users", "/admin/applications", "/admin/metrics"):
            assert client.get(path, headers=ah).status_code == 200
    finally:
        db = SessionLocal()
        try:
            for uid in created_user_ids:
                user = db.get(User, uid)
                if user:
                    db.delete(user)
            db.commit()
        finally:
            db.close()
