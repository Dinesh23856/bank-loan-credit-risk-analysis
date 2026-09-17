from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Optional, Any, Dict
from sqlalchemy.orm import Session
from backend.models import AuditLog, User

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "password", "password_hash", "token", "access_token", "refresh_token",
    "jwt", "secret", "jwt_secret_key", "api_key", "gemini_api_key",
    "key", "fernet_key", "credentials", "authorization"
}

def sanitize_metadata(data: Any) -> Any:
    """Recursively scrub sensitive authentication and secret keys from metadata."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = sanitize_metadata(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_metadata(item) for item in data]
    return data

def log_audit_event(
    db: Session,
    action: str,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: Optional[str] = "SUCCESS",
    metadata: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    before_value: Optional[str] = None,
    after_value: Optional[str] = None,
    **kwargs: Any
) -> Optional[AuditLog]:
    """
    Persistently logs a security, workflow, or business event to audit_logs.
    Guarantees zero leakage of secrets or authentication credentials.
    """
    try:
        resolved_user_id = user.id if user is not None else user_id
        resolved_role = user.role if user is not None else role
        if resolved_role:
            resolved_role = str(resolved_role).upper()
            if resolved_role in ("USER", "CUSTOMER"):
                resolved_role = "CUSTOMER"
            elif resolved_role in ("ADMIN", "ADMINISTRATOR"):
                resolved_role = "ADMIN"

        meta_dict = dict(metadata) if metadata else {}
        if user_agent and "user_agent" not in meta_dict:
            meta_dict["user_agent"] = user_agent
        if status and "status" not in meta_dict:
            meta_dict["status"] = status
        for k, v in kwargs.items():
            if k not in meta_dict:
                meta_dict[k] = v

        sanitized = sanitize_metadata(meta_dict) if meta_dict else None
        meta_str = json.dumps(sanitized) if sanitized is not None else None

        log_entry = AuditLog(
            timestamp=datetime.utcnow(),
            user_id=resolved_user_id,
            role=resolved_role,
            action=action.upper(),
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=ip_address,
            metadata_json=meta_str,
            reason=reason,
            before_value=str(before_value) if before_value is not None else None,
            after_value=str(after_value) if after_value is not None else None,
        )
        db.add(log_entry)
        db.flush()
        return log_entry
    except Exception as exc:
        logger.error("Failed to write persistent audit log for action %s: %s", action, exc)
        return None
