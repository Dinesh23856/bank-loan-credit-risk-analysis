from __future__ import annotations
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
load_dotenv()

# PRODUCTION DATABASE = MYSQL ONLY.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
Base = declarative_base()

# Production startup must fail clearly if DATABASE_URL is missing or not mysql+pymysql://
if ENVIRONMENT == "production":
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Production database requires MYSQL ONLY (mysql+pymysql://).")
    if not DATABASE_URL.startswith("mysql+pymysql://"):
        raise RuntimeError("DATABASE_URL must use mysql+pymysql:// for production. Other engines are strictly prohibited.")
else:
    if DATABASE_URL and not DATABASE_URL.startswith("mysql+pymysql://"):
        raise RuntimeError("DATABASE_URL must use mysql+pymysql:// for this application.")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "5")),
) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) if engine else None

def get_db():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
