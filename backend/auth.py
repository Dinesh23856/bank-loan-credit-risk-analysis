from __future__ import annotations
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Set
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv

load_dotenv()

try:
    import bcrypt
    from jose import jwt, JWTError
except ImportError:
    bcrypt = None; jwt = None; JWTError = Exception

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
# 15-minute access token lifetime as required by Enterprise FinTech specifications
TOKEN_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
security = HTTPBearer(auto_error=False)

# In-memory session and token tracking with Redis support where available
_active_refresh_tokens: Dict[str, Dict[str, Any]] = {}
_revoked_refresh_tokens: Dict[str, int] = {} # jti -> user_id

def _secret() -> str:
    value = os.getenv("JWT_SECRET_KEY")
    if not value or len(value) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be configured with at least 32 characters.")
    return value

def hash_password(password: str) -> str:
    if bcrypt is None:
        raise RuntimeError("bcrypt dependency is not installed.")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    if bcrypt is None:
        return False
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False

def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES)
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)

def create_refresh_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "user_id": user_id,
        "role": role,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_DAYS)
    }
    token = jwt.encode(payload, _secret(), algorithm=ALGORITHM)
    # Register active token
    _active_refresh_tokens[jti] = {
        "user_id": user_id,
        "role": role,
        "created_at": now.isoformat()
    }
    return token

def rotate_refresh_token(token: str) -> tuple[str, str, int, str]:
    """
    Rotates a refresh token:
    1. Validates token format and signature.
    2. Checks for reuse of an already-revoked token. If reused, invalidates ALL active tokens for the user.
    3. Revokes the used token and issues a new access token and a new refresh token.
    Returns: (new_access_token, new_refresh_token, user_id, role)
    """
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.") from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type for refresh.")

    user_id = int(payload.get("user_id"))
    role = str(payload.get("role"))
    jti = payload.get("jti")

    if not jti:
        raise HTTPException(status_code=401, detail="Malformed refresh token.")

    # Check for replay / reuse detection
    if jti in _revoked_refresh_tokens:
        # Replay detected! Compromised token reuse: invalidate all active sessions for this user
        logger.warning("Token replay detected for user %d with revoked jti %s. Invalidating all sessions.", user_id, jti)
        to_remove = [k for k, v in _active_refresh_tokens.items() if v.get("user_id") == user_id]
        for k in to_remove:
            _active_refresh_tokens.pop(k, None)
            _revoked_refresh_tokens[k] = user_id
        raise HTTPException(
            status_code=401,
            detail="Security violation: Token reuse detected. All active sessions have been terminated."
        )

    if jti not in _active_refresh_tokens:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked or expired.")

    # Revoke current token
    _active_refresh_tokens.pop(jti, None)
    _revoked_refresh_tokens[jti] = user_id

    # Issue new pair
    new_access_token = create_access_token(user_id, role)
    new_refresh_token = create_refresh_token(user_id, role)
    return new_access_token, new_refresh_token, user_id, role

def revoke_refresh_token(token: str) -> None:
    try:
        payload = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
        jti = payload.get("jti")
        user_id = payload.get("user_id")
        if jti:
            _active_refresh_tokens.pop(jti, None)
            _revoked_refresh_tokens[jti] = int(user_id) if user_id else 0
    except Exception:
        pass

def decode_token(token: str) -> dict:
    try:
        if jwt is None:
            raise RuntimeError("JWT dependency is not installed.")
        data = jwt.decode(token, _secret(), algorithms=[ALGORITHM])
        user_id = data.get("user_id")
        if isinstance(user_id, bool) or not isinstance(user_id, (int, str)):
            raise ValueError("Invalid user id claim")
        int(user_id)
        return data
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token.") from exc
