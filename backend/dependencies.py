from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .auth import security, decode_token

def current_user(credentials=Depends(security), db: Session = Depends(get_db)):
    if credentials is None:
        raise HTTPException(401, "Authentication required.")
    data = decode_token(credentials.credentials)
    try:
        user_id = int(data.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "Invalid authentication token.") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Authentication required.")
    return user

def require_authenticated_user(user=Depends(current_user)):
    return user

def normalize_role(role: str) -> str:
    r = (role or "").strip().upper()
    if r in ("ADMIN", "ADMINISTRATOR"):
        return "ADMIN"
    if r in ("UNDERWRITER",):
        return "UNDERWRITER"
    if r in ("RISK_ANALYST", "ANALYST"):
        return "RISK_ANALYST"
    return "CUSTOMER"

def require_customer(user=Depends(current_user)):
    """Baseline authenticated access for applicant / customer operations."""
    return user

def require_underwriter(user=Depends(current_user)):
    """Restricted to UNDERWRITER and ADMIN roles."""
    role = normalize_role(user.role)
    if role not in ("UNDERWRITER", "ADMIN"):
        raise HTTPException(403, "Underwriter access required.")
    return user

def require_risk_analyst(user=Depends(current_user)):
    """Restricted to RISK_ANALYST and ADMIN roles."""
    role = normalize_role(user.role)
    if role not in ("RISK_ANALYST", "ADMIN"):
        raise HTTPException(403, "Risk Analyst access required.")
    return user

def require_admin(user=Depends(current_user)):
    """Strictly restricted to ADMIN role."""
    role = normalize_role(user.role)
    if role != "ADMIN":
        raise HTTPException(403, "Administrator access required.")
    return user
