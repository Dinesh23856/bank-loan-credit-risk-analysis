import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import SessionLocal, engine
from backend.models import Base, User
from backend.auth import hash_password

if __name__ == "__main__":
    if not SessionLocal or not engine:
        raise SystemExit("DATABASE_URL is required.")
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    name = os.getenv("ADMIN_NAME", "Administrator")
    if not email or not password:
        raise SystemExit("ADMIN_EMAIL and ADMIN_PASSWORD are required.")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.role == "admin").first()
        if admin:
            admin.name = name
            admin.email = email.lower()
            admin.password_hash = hash_password(password)
            db.commit()
            print("Admin updated.")
        else:
            existing_user = db.query(User).filter(User.email == email.lower()).first()
            if existing_user:
                raise SystemExit("Email is already registered as a non-admin user.")
            db.add(User(name=name, email=email.lower(), password_hash=hash_password(password), role="admin"))
            db.commit()
            print("Admin created.")
    finally:
        db.close()
