from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ModelRegistry, User
from backend.dependencies import require_risk_analyst, require_admin, normalize_role
from backend.schemas import (
    ModelRegistryResponse,
    ModelRegistryListResponse,
    ModelCardResponse,
    ModelStatusUpdateRequest,
    ModelReviewRequest,
    ModelIntegrityCheckResponse
)
from backend.services.model_registry_service import (
    verify_model_artifact_integrity,
    update_model_status,
    record_governance_review,
    generate_model_card
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Model Registry & Governance"])

def _find_model(db: Session, model_id_or_name: str) -> ModelRegistry:
    record = None
    if model_id_or_name.isdigit():
        record = db.get(ModelRegistry, int(model_id_or_name))
    if record is None:
        record = db.query(ModelRegistry).filter(ModelRegistry.model_name == model_id_or_name).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Registered model '{model_id_or_name}' not found.")
    return record

@router.get("", response_model=ModelRegistryListResponse)
def list_models(
    lifecycle_status: Optional[str] = Query(None),
    deployment_status: Optional[str] = Query(None),
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    List all registered models with their metadata, metrics, and governance status.
    Accessible to RISK_ANALYST and ADMIN roles.
    """
    q = db.query(ModelRegistry)
    if lifecycle_status:
        q = q.filter(ModelRegistry.lifecycle_status == lifecycle_status.upper())
    if deployment_status:
        q = q.filter(ModelRegistry.deployment_status == deployment_status.upper())

    items = q.order_by(ModelRegistry.id.asc()).all()
    return ModelRegistryListResponse(items=items, total=len(items))

@router.get("/{model_id}", response_model=ModelRegistryResponse)
def get_model(
    model_id: str,
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Retrieve full registry record for a specific model by ID or model_name.
    Accessible to RISK_ANALYST and ADMIN roles.
    """
    return _find_model(db, model_id)

@router.get("/{model_id}/card", response_model=ModelCardResponse)
def get_model_card(
    model_id: str,
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Generate and retrieve the structured dynamic Model Card for the specified model.
    Accessible to RISK_ANALYST and ADMIN roles.
    """
    record = _find_model(db, model_id)
    card_dict = generate_model_card(record)
    return ModelCardResponse.model_validate(card_dict)

@router.post("/{model_id}/verify-integrity", response_model=ModelIntegrityCheckResponse)
def verify_integrity(
    model_id: str,
    req: Request,
    user: User = Depends(require_risk_analyst),
    db: Session = Depends(get_db)
):
    """
    Performs on-demand SHA-256 integrity verification of the serialized model artifact on disk.
    Compares the calculated hash with the immutable registered hash.
    Accessible to RISK_ANALYST and ADMIN roles.
    """
    record = _find_model(db, model_id)
    client_ip = req.client.host if req.client else None
    res = verify_model_artifact_integrity(db, record, user=user, ip_address=client_ip)
    return ModelIntegrityCheckResponse(
        model_name=res["model_name"],
        status=res["status"],
        message=res["message"],
        expected_hash=res["expected_hash"],
        actual_hash=res.get("actual_hash"),
        verified_at=res["verified_at"]
    )

@router.put("/{model_id}/status", response_model=ModelRegistryResponse)
def update_status(
    model_id: str,
    req_body: ModelStatusUpdateRequest,
    req: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Updates the lifecycle status or deployment status of a model.
    Restricted to ADMIN role only.
    Enforces valid lifecycle transitions and prevents activating a model with integrity failures.
    """
    record = _find_model(db, model_id)
    client_ip = req.client.host if req.client else None
    updated = update_model_status(
        db=db,
        model_record=record,
        lifecycle_status=req_body.lifecycle_status,
        deployment_status=req_body.deployment_status,
        user=user,
        reason=req_body.reason,
        ip_address=client_ip
    )
    return updated

@router.post("/{model_id}/review", response_model=ModelRegistryResponse)
def review_model(
    model_id: str,
    req_body: ModelReviewRequest,
    req: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Records an official administrative governance review for a model.
    Restricted to ADMIN role only.
    Decision: 'APPROVED' or 'REJECTED'.
    """
    record = _find_model(db, model_id)
    client_ip = req.client.host if req.client else None
    updated = record_governance_review(
        db=db,
        model_record=record,
        decision=req_body.decision,
        user=user,
        review_notes=req_body.review_notes,
        ip_address=client_ip
    )
    return updated
