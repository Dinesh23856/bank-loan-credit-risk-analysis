from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_mysql_and_auth_architecture():
    text=(ROOT/"backend/database.py").read_text()
    assert (ROOT/"backend/database.py").exists()
    assert "mysql+pymysql://" in text
    assert "sqlite" not in text.lower()
    assert "pool_pre_ping=True" in text

def test_routes_and_frontend_architecture():
    for f in ["auth_routes.py","prediction_routes.py","admin_routes.py"]:
        assert (ROOT/"backend/routes"/f).exists()
    for f in ["Login.jsx","Register.jsx","UserDashboard.jsx","LoanApplication.jsx","ApplicationHistory.jsx","ApplicationDetail.jsx","AdminDashboard.jsx"]:
        p=ROOT/"frontend/src/pages"/f
        assert p.exists() and "return null" not in p.read_text()
    for f in ["Navbar.jsx","Sidebar.jsx","ProtectedRoute.jsx","AdminRoute.jsx","Loading.jsx","ErrorMessage.jsx"]:
        p=ROOT/"frontend/src/components"/f
        assert p.exists() and "return null" not in p.read_text()
    pkg=(ROOT/"frontend/package.json").read_text()
    assert "react-router-dom" in pkg and "recharts" in pkg

def test_no_public_admin_registration():
    text=(ROOT/"backend/routes/auth_routes.py").read_text()
    assert 'role="user"' in text
    assert "role" not in text.split("def register",1)[1].split("def login",1)[0].replace('role="user"','')

def test_production_render_command():
    text=(ROOT/"render.yaml").read_text()
    assert "0.0.0.0" in text and "$PORT" in text and "/health" in text
    assert "ENVIRONMENT" in text and "production" in text
    assert "DATABASE_URL" in text and "JWT_SECRET_KEY" in text

def test_production_guards_and_sql_safety():
    main=(ROOT/"backend/main.py").read_text()
    assert "Production requires DATABASE_URL" in main
    routes=(ROOT/"backend/routes/admin_routes.py").read_text()
    assert "ilike(f" in routes
    assert "INSERT" not in routes and "UPDATE" not in routes and "DELETE" not in routes

def test_pwa_has_install_icons():
    manifest=(ROOT/"frontend/public/manifest.webmanifest").read_text()
    assert "icon-192.png" in manifest and "icon-512.png" in manifest
    assert (ROOT/"frontend/public/icons/icon-192.png").exists()
    assert (ROOT/"frontend/public/icons/icon-512.png").exists()

def test_user_isolation_is_enforced_server_side():
    text=(ROOT/"backend/routes/prediction_routes.py").read_text()
    assert "LoanApplication.user_id==user.id" in text or "LoanApplication.user_id == user.id" in text
    assert "application_id" in text and "user.id" in text

def test_mysql_schema_indexes_and_risk_log_contract():
    from backend.models import Base, ModelLog
    from sqlalchemy.dialects import mysql
    from sqlalchemy.schema import CreateTable
    ddl = str(CreateTable(Base.metadata.tables["model_logs"]).compile(dialect=mysql.dialect()))
    assert "FOREIGN KEY(user_id)" in ddl
    assert "FOREIGN KEY(application_id)" in ddl
    assert ModelLog.__table__.c.application_id.nullable is True
    app_indexes = {i.name for i in Base.metadata.tables["loan_applications"].indexes}
    assert {"ix_app_user_created", "ix_app_status_created", "ix_app_region_created"} <= app_indexes
    risk_source=(ROOT/"backend/routes/prediction_routes.py").read_text()
    assert 'application_id=None' in risk_source and 'model_name="credit_risk"' in risk_source
