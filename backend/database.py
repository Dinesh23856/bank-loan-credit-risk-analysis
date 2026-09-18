from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
load_dotenv()

# PRODUCTION DATABASE = MYSQL ONLY.
DATABASE_URL = (os.getenv("DATABASE_URL") or os.getenv("AIVEN_DATABASE_URL") or "").strip().strip(' \t\r\n"\'')
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
Base = declarative_base()

# Auto-normalize mysql:// to mysql+pymysql:// if provided (e.g. from standard Aiven Service URI)
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = "mysql+pymysql://" + DATABASE_URL[len("mysql://"):]

# Production startup must fail clearly if DATABASE_URL is missing or not mysql+pymysql://
if ENVIRONMENT == "production":
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Production database requires MYSQL ONLY (mysql+pymysql://).")
    if not DATABASE_URL.startswith("mysql+pymysql://"):
        raise RuntimeError("DATABASE_URL must use mysql+pymysql:// for production. Other engines are strictly prohibited.")
else:
    if DATABASE_URL and not DATABASE_URL.startswith("mysql+pymysql://"):
        raise RuntimeError("DATABASE_URL must use mysql+pymysql:// for this application.")

connect_args = {
    "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
}
clean_db_url = DATABASE_URL.split("?")[0] if DATABASE_URL else ""

# Guard against accidental localhost/127.0.0.1 in production/cloud environments
is_cloud = bool(os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID") or ENVIRONMENT == "production")
if is_cloud and clean_db_url and ("localhost" in clean_db_url.lower() or "127.0.0.1" in clean_db_url):
    raise RuntimeError("DATABASE_URL points to localhost/127.0.0.1 in production. A remote MySQL database (e.g. Aiven) is required.")

if DATABASE_URL:
    # Handle SSL configuration for PyMySQL (e.g. Aiven or remote cloud MySQL)
    url_lower = DATABASE_URL.lower()
    is_aiven = "aivencloud.com" in url_lower
    has_ssl_param = any(param in url_lower for param in ("ssl_mode", "ssl-mode", "sslmode", "ssl_ca", "ssl-ca", "sslca"))
    db_ssl_env = os.getenv("DB_SSL", "").lower() in ("true", "1", "yes", "required")

    if is_aiven or has_ssl_param or db_ssl_env:
        import ssl
        clean_db_url = DATABASE_URL.split("?")[0]
        ssl_ctx = ssl.create_default_context()

        # Check for CA certificate via environment variable (file path or inline PEM data)
        ca_cert_path = os.getenv("DB_SSL_CA_PATH", os.getenv("AIVEN_CA_PATH", "")).strip()
        ca_cert_data = os.getenv("DB_SSL_CA_CERT", os.getenv("AIVEN_CA_CERT", "")).strip()

        if ca_cert_path and os.path.exists(ca_cert_path):
            ssl_ctx.load_verify_locations(cafile=ca_cert_path)
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            ssl_ctx.check_hostname = True
        elif ca_cert_data:
            ssl_ctx.load_verify_locations(cadata=ca_cert_data)
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            ssl_ctx.check_hostname = True
        else:
            # When no custom CA certificate is provided, enable TLS encryption
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

        connect_args["ssl"] = ssl_ctx

engine = create_engine(
    clean_db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "10")),
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
) if clean_db_url else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None

def get_db():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
