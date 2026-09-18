import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)
PROD_ORIGIN = "https://bank-loan-credit-risk-analysis-frontend.onrender.com"

def test_production_frontend_cors_preflight_options_register():
    headers = {
        "Origin": PROD_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, Authorization",
    }
    res = client.options("/auth/register", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == PROD_ORIGIN
    assert res.headers.get("access-control-allow-credentials") == "true"
    methods = [m.strip() for m in res.headers.get("access-control-allow-methods", "").split(",")]
    assert "POST" in methods
    assert "OPTIONS" in methods

def test_production_frontend_cors_preflight_options_login():
    headers = {
        "Origin": PROD_ORIGIN,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type, Authorization",
    }
    res = client.options("/auth/login", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == PROD_ORIGIN
    assert res.headers.get("access-control-allow-credentials") == "true"

def test_production_frontend_cors_headers_on_actual_request():
    headers = {
        "Origin": PROD_ORIGIN,
        "Content-Type": "application/json",
    }
    res = client.post("/auth/login", json={"email": "nonexistent@example.com", "password": "test"}, headers=headers)
    # Even on 401 Unauthorized, CORS headers must be returned to the browser
    assert res.headers.get("access-control-allow-origin") == PROD_ORIGIN
    assert res.headers.get("access-control-allow-credentials") == "true"

def test_localhost_dev_cors_supported():
    for origin in ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:3000"]:
        headers = {
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        res = client.options("/auth/login", headers=headers)
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == origin

def test_disallowed_origin_rejected():
    headers = {
        "Origin": "https://unauthorized-attacker.example.com",
        "Access-Control-Request-Method": "POST",
    }
    res = client.options("/auth/login", headers=headers)
    assert res.status_code == 400
    assert "access-control-allow-origin" not in res.headers
