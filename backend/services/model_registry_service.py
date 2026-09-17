from __future__ import annotations
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Set
from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models import ModelRegistry, User
from backend.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]

ALLOWED_LIFECYCLE_TRANSITIONS: Dict[str, Set[str]] = {
    "DRAFT": {"APPROVED", "RETIRED"},
    "APPROVED": {"ACTIVE", "RETIRED"},
    "ACTIVE": {"RETIRED"},
    "RETIRED": set()  # Terminal state
}

def get_project_root() -> Path:
    return ROOT_DIR

def compute_file_sha256(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(f"Model artifact not found at {file_path}")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()

def verify_model_artifact_integrity(
    db: Session,
    model_record: ModelRegistry,
    user: Optional[User] = None,
    ip_address: Optional[str] = None
) -> Dict[str, Any]:
    """
    Locates the registered model artifact, calculates its SHA-256 hash,
    and compares it against the immutable registered hash.
    Does NOT modify the model file or overwrite the registered hash.
    """
    artifact_path = ROOT_DIR / model_record.artifact_path
    now = datetime.utcnow()
    expected_hash = model_record.artifact_sha256.lower().strip()

    if not artifact_path.exists():
        model_record.integrity_status = "MISMATCH"
        model_record.last_integrity_check = now
        model_record.deployment_status = "INACTIVE"
        db.flush()

        log_audit_event(
            db=db,
            action="MODEL_INTEGRITY_MISMATCH",
            user=user,
            resource_type="model",
            resource_id=model_record.model_name,
            ip_address=ip_address,
            reason=f"Model artifact missing at {model_record.artifact_path}",
            metadata={
                "model_name": model_record.model_name,
                "expected_hash": expected_hash,
                "actual_hash": "FILE_NOT_FOUND",
                "status": "MISMATCH"
            }
        )
        db.commit()
        return {
            "model_name": model_record.model_name,
            "status": "MISMATCH",
            "message": f"Artifact file missing at {model_record.artifact_path}",
            "expected_hash": expected_hash,
            "actual_hash": None,
            "verified_at": now
        }

    actual_hash = compute_file_sha256(artifact_path)
    is_match = (actual_hash == expected_hash)

    if is_match:
        model_record.integrity_status = "VERIFIED"
        model_record.last_integrity_check = now
        db.flush()

        log_audit_event(
            db=db,
            action="MODEL_INTEGRITY_VERIFIED",
            user=user,
            resource_type="model",
            resource_id=model_record.model_name,
            ip_address=ip_address,
            reason="Artifact SHA-256 signature verified successfully.",
            metadata={
                "model_name": model_record.model_name,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "status": "MATCH"
            }
        )
        db.commit()
        return {
            "model_name": model_record.model_name,
            "status": "MATCH",
            "message": "Model artifact SHA-256 signature verified successfully.",
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "verified_at": now
        }
    else:
        # Integrity failure
        model_record.integrity_status = "MISMATCH"
        model_record.last_integrity_check = now
        # Deactivate compromised or altered model
        model_record.deployment_status = "INACTIVE"
        db.flush()

        log_audit_event(
            db=db,
            action="MODEL_INTEGRITY_MISMATCH",
            user=user,
            resource_type="model",
            resource_id=model_record.model_name,
            ip_address=ip_address,
            reason=f"Integrity check failed: Expected {expected_hash}, found {actual_hash}",
            before_value=expected_hash,
            after_value=actual_hash,
            metadata={
                "model_name": model_record.model_name,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
                "status": "MISMATCH"
            }
        )
        db.commit()
        return {
            "model_name": model_record.model_name,
            "status": "MISMATCH",
            "message": "SHA-256 mismatch detected. Artifact may be altered or corrupted.",
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "verified_at": now
        }

def update_model_status(
    db: Session,
    model_record: ModelRegistry,
    lifecycle_status: Optional[str] = None,
    deployment_status: Optional[str] = None,
    user: Optional[User] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None
) -> ModelRegistry:
    """
    Updates the lifecycle status or deployment status of a registered model.
    Validates lifecycle transitions.
    Requires successful integrity verification prior to activation.
    """
    curr_lifecycle = model_record.lifecycle_status.upper()
    old_deploy = model_record.deployment_status.upper()

    if lifecycle_status is not None:
        target_lifecycle = lifecycle_status.upper()
        if target_lifecycle != curr_lifecycle:
            allowed = ALLOWED_LIFECYCLE_TRANSITIONS.get(curr_lifecycle, set())
            if target_lifecycle not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid lifecycle transition: Cannot transition model from '{curr_lifecycle}' to '{target_lifecycle}'. Allowed transitions: {sorted(list(allowed))}."
                )

            # If activating lifecycle, verify integrity
            if target_lifecycle == "ACTIVE":
                integrity = verify_model_artifact_integrity(db, model_record, user=user, ip_address=ip_address)
                if integrity["status"] != "MATCH":
                    raise HTTPException(
                        status_code=400,
                        detail="Cannot activate model: Artifact SHA-256 integrity verification failed."
                    )
                model_record.deployment_status = "ACTIVE"

            if target_lifecycle == "RETIRED":
                model_record.deployment_status = "INACTIVE"

            model_record.lifecycle_status = target_lifecycle
            log_audit_event(
                db=db,
                action="MODEL_STATUS_CHANGED",
                user=user,
                resource_type="model",
                resource_id=model_record.model_name,
                ip_address=ip_address,
                reason=reason or f"Lifecycle updated to {target_lifecycle}",
                before_value=curr_lifecycle,
                after_value=target_lifecycle,
                metadata={
                    "model_name": model_record.model_name,
                    "old_lifecycle": curr_lifecycle,
                    "new_lifecycle": target_lifecycle,
                    "reason": reason
                }
            )

    if deployment_status is not None:
        target_deploy = deployment_status.upper()
        if target_deploy not in ("ACTIVE", "INACTIVE"):
            raise HTTPException(status_code=400, detail="deployment_status must be 'ACTIVE' or 'INACTIVE'.")

        if target_deploy == "ACTIVE":
            if model_record.lifecycle_status.upper() not in ("APPROVED", "ACTIVE"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot activate model in lifecycle state '{model_record.lifecycle_status}'. Model must be 'APPROVED' or 'ACTIVE'."
                )
            integrity = verify_model_artifact_integrity(db, model_record, user=user, ip_address=ip_address)
            if integrity["status"] != "MATCH":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot activate deployment: Artifact SHA-256 integrity check failed."
                )

        if target_deploy != old_deploy:
            model_record.deployment_status = target_deploy
            action_name = "MODEL_ACTIVATED" if target_deploy == "ACTIVE" else "MODEL_DEACTIVATED"
            log_audit_event(
                db=db,
                action=action_name,
                user=user,
                resource_type="model",
                resource_id=model_record.model_name,
                ip_address=ip_address,
                reason=reason or f"Deployment status set to {target_deploy}",
                before_value=old_deploy,
                after_value=target_deploy,
                metadata={
                    "model_name": model_record.model_name,
                    "old_deployment": old_deploy,
                    "new_deployment": target_deploy
                }
            )

    model_record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(model_record)
    return model_record

def record_governance_review(
    db: Session,
    model_record: ModelRegistry,
    decision: str,
    user: User,
    review_notes: Optional[str] = None,
    ip_address: Optional[str] = None
) -> ModelRegistry:
    """
    Records an administrative governance review for a model.
    Decision: 'APPROVED' or 'REJECTED'.
    """
    decision_clean = decision.strip().upper()
    if decision_clean not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Review decision must be 'APPROVED' or 'REJECTED'.")

    now = datetime.utcnow()
    old_lifecycle = model_record.lifecycle_status

    if decision_clean == "APPROVED":
        model_record.lifecycle_status = "APPROVED"
    else:
        model_record.lifecycle_status = "RETIRED"
        model_record.deployment_status = "INACTIVE"

    model_record.reviewed_by = user.id
    model_record.reviewed_at = now
    model_record.review_notes = review_notes
    model_record.updated_at = now

    log_audit_event(
        db=db,
        action="MODEL_REVIEWED",
        user=user,
        resource_type="model",
        resource_id=model_record.model_name,
        ip_address=ip_address,
        reason=review_notes or f"Governance review: {decision_clean}",
        before_value=old_lifecycle,
        after_value=model_record.lifecycle_status,
        metadata={
            "model_name": model_record.model_name,
            "decision": decision_clean,
            "reviewer_id": user.id,
            "reviewer_role": user.role,
            "review_notes": review_notes
        }
    )

    db.commit()
    db.refresh(model_record)
    return model_record

def generate_model_card(model_record: ModelRegistry) -> Dict[str, Any]:
    """
    Constructs a comprehensive, structured Model Card from repository and registry metadata.
    """
    try:
        features = json.loads(model_record.features_json) if model_record.features_json else []
    except Exception:
        features = []

    try:
        metrics = json.loads(model_record.metrics_json) if model_record.metrics_json else {}
    except Exception:
        metrics = {}

    return {
        "model_name": model_record.model_name,
        "model_version": model_record.model_version,
        "task": model_record.task,
        "model_type": model_record.model_type,
        "purpose": model_record.intended_use,
        "intended_use": model_record.intended_use,
        "out_of_scope_use": "Automated adverse underwriting actions without human oversight; non-retail lending; applications in jurisdictions outside model training demographics.",
        "input_features": features,
        "feature_count": len(features),
        "target_variable": model_record.target_variable,
        "dataset": {
            "reference": model_record.dataset_reference,
            "sha256": model_record.dataset_sha256
        },
        "evaluation_metrics": metrics,
        "explainability": {
            "method": model_record.explainability_method or "Feature importances and sensitivity curves.",
            "scope": "Local waterfall attribution for individual decisions; global feature importance rankings."
        },
        "limitations": model_record.limitations,
        "known_risks": model_record.known_risks,
        "artifact": {
            "path": model_record.artifact_path,
            "sha256": model_record.artifact_sha256,
            "integrity_status": model_record.integrity_status,
            "last_integrity_check": model_record.last_integrity_check
        },
        "governance": {
            "lifecycle_status": model_record.lifecycle_status,
            "deployment_status": model_record.deployment_status,
            "reviewed_by": model_record.reviewed_by,
            "reviewed_at": model_record.reviewed_at,
            "review_notes": model_record.review_notes
        },
        "regulatory_disclaimer": "Academic and internal demonstration model governance specification. Does not constitute certification for live banking production or regulatory warranty under FCRA/ECOA."
    }
