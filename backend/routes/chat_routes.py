from __future__ import annotations
import uuid
import time
import json
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, LoanApplication, ChatConversation, ChatMessage, ChatUsageLog
from ..dependencies import require_authenticated_user
from ..limiter import limiter
from ..schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatConversationResponse,
    ChatConversationDetailResponse,
    ChatMessageItem
)
from ..services.ai_provider import (
    get_ai_provider,
    AIProviderError,
    AIProviderUnavailableError,
    AIProviderTimeoutError,
    AIProviderRateLimitError
)
from ..services.chat_safety import (
    BANKING_AI_SYSTEM_PROMPT,
    sanitize_user_input,
    validate_assistant_output,
    build_degraded_fallback_response
)
from ..services.chat_context_service import (
    get_user_application,
    get_user_application_summary,
    get_user_application_history,
    get_user_prediction,
    get_user_shap_explanation,
    get_user_adverse_action_reasons,
    get_admin_metrics,
    get_admin_drift_summary,
    get_admin_fairness_summary,
    get_admin_chat_usage_metrics
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Banking AI Assistant"])

@router.post("", response_model=ChatMessageResponse)
@limiter.limit("30/minute")
async def send_chat_message(
    request: Request,
    body: ChatMessageRequest,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """Secure conversational interface for Banking AI Assistant."""
    clean_message, injection_flag = sanitize_user_input(body.message)
    if not clean_message:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Message cannot be empty.")

    # 1. Resolve or verify conversation ownership (BOLA / IDOR protection)
    conv = None
    if body.conversation_id:
        conv = db.query(ChatConversation).filter(ChatConversation.id == body.conversation_id).first()
        if not conv:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
        if conv.user_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: You do not own this conversation.")
    else:
        conv_id = str(uuid.uuid4())
        conv = ChatConversation(
            id=conv_id,
            user_id=user.id,
            title=clean_message[:60] if len(clean_message) > 60 else clean_message,
            application_id=body.application_id
        )
        db.add(conv)
        db.flush()

    # If application_id was passed or already attached to conversation, verify ownership
    app_id = body.application_id or conv.application_id
    if app_id:
        # Update conv if newly linked
        if conv.application_id != app_id:
            conv.application_id = app_id

    # 2. Assemble Ground Truth Context via Typed Services
    context_data = {}
    sources = []
    is_admin = (user.role == "admin")

    if app_id:
        try:
            app_summary = get_user_application(db, user.id, app_id, is_admin=is_admin)
            context_data["application"] = app_summary
            sources.append(f"Application #{app_id} Record")

            # If applicant asks about status, decision, or factors, pull SHAP
            shap_data = get_user_shap_explanation(db, user.id, app_id, is_admin=is_admin)
            context_data["shap_factors"] = {
                "positive": shap_data.get("top_positive_factors", []),
                "negative": shap_data.get("top_negative_factors", []),
                "base_value": shap_data.get("base_value")
            }
            context_data["adverse_action_reasons"] = shap_data.get("adverse_action_reasons", [])
            sources.append("TreeSHAP Explainability Engine")
        except PermissionError as exc:
            db.rollback()
            raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc)) from exc

    # Check for admin queries
    query_lower = clean_message.lower()
    admin_keywords = ["approval rate", "drift", "fairness", "risk distribution", "metrics", "how many applications", "chatbot usage"]
    if any(k in query_lower for k in admin_keywords):
        if is_admin:
            context_data["metrics"] = get_admin_metrics(db, user)
            context_data["drift"] = get_admin_drift_summary(db, user)
            context_data["chat_usage"] = get_admin_chat_usage_metrics(db, user)
            sources.append("Admin Operational Analytics")
        else:
            context_data["admin_notice"] = "Cross-user aggregate metrics and administration analytics are restricted to bank administrators."

    # If no application explicitly selected, provide user's application history overview
    if not app_id and not is_admin:
        history = get_user_application_history(db, user.id, limit=3)
        if history:
            context_data["recent_applications"] = history
            sources.append("User Application Portfolio")

    # 3. Formulate prompt with strict boundaries
    context_instruction = ""
    if context_data:
        context_instruction = (
            f"\n\n[GROUND TRUTH SYSTEM CONTEXT]\n"
            f"{json.dumps(context_data, indent=2)}\n"
            f"[END OF CONTEXT]\n"
            f"Use only the verified data above to answer the applicant. Never invent numbers, rates, or status."
        )

    # 4. Multi-turn history retrieval
    past_messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv.id
    ).order_by(ChatMessage.created_at.asc()).limit(8).all()

    formatted_messages = []
    for pm in past_messages:
        formatted_messages.append({"role": pm.role, "content": pm.content})

    current_prompt = clean_message
    if context_instruction:
        current_prompt += context_instruction
    formatted_messages.append({"role": "user", "content": current_prompt})

    # Determine thinking level
    thinking_level = "low"
    if is_admin:
        thinking_level = "high"
    elif app_id or "why" in query_lower or "explain" in query_lower:
        thinking_level = "medium"

    provider = get_ai_provider()
    start_time = time.perf_counter()
    assistant_text = ""
    degraded = False
    tokens_prompt = 0
    tokens_completion = 0
    tokens_total = 0
    status_label = "SUCCESS"
    err_cat = None

    try:
        resp = await provider.generate_response(
            messages=formatted_messages,
            system_instruction=BANKING_AI_SYSTEM_PROMPT,
            thinking_level=thinking_level,
            context=context_data
        )
        assistant_text = resp.get("text", "")
        tokens_prompt = resp.get("prompt_tokens", 0)
        tokens_completion = resp.get("completion_tokens", 0)
        tokens_total = resp.get("total_tokens", 0)
    except (AIProviderUnavailableError, AIProviderTimeoutError, AIProviderRateLimitError, AIProviderError) as exc:
        logger.warning("AI Provider failure (%s). Engaging deterministic fallback.", exc)
        degraded = True
        status_label = "DEGRADED"
        err_cat = exc.__class__.__name__
        assistant_text, fallback_sources = build_degraded_fallback_response(clean_message, context_data, is_admin=is_admin)
        for fs in fallback_sources:
            if fs not in sources:
                sources.append(fs)
    except Exception as exc:
        logger.error("Unexpected error in chat pipeline: %s", exc)
        degraded = True
        status_label = "DEGRADED"
        err_cat = "UnexpectedException"
        assistant_text, fallback_sources = build_degraded_fallback_response(clean_message, context_data, is_admin=is_admin)
        for fs in fallback_sources:
            if fs not in sources:
                sources.append(fs)

    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # 5. Output safety validation
    safe_text, was_modified = validate_assistant_output(assistant_text)

    # 6. Persist user & assistant messages
    user_msg = ChatMessage(
        conversation_id=conv.id,
        role="user",
        content=clean_message,
        sources=None
    )
    db.add(user_msg)

    assistant_msg = ChatMessage(
        conversation_id=conv.id,
        role="assistant",
        content=safe_text,
        sources=json.dumps(sources)
    )
    db.add(assistant_msg)

    # Update conversation updated_at
    conv.updated_at = datetime.utcnow()

    raw_model = getattr(provider, "model", "gemini-3.5-flash-lite")
    if not isinstance(raw_model, str):
        raw_model = "gemini-3.5-flash-lite"

    # 7. Record Telemetry (NO PII, NO SECRETS)
    telemetry = ChatUsageLog(
        user_id=user.id,
        conversation_id=conv.id,
        provider="gemini",
        model=raw_model,
        status=status_label,
        latency_ms=round(latency_ms, 2),
        prompt_tokens=tokens_prompt,
        completion_tokens=tokens_completion,
        total_tokens=tokens_total,
        error_category=err_cat
    )
    db.add(telemetry)
    db.commit()

    return {
        "message": safe_text,
        "conversation_id": conv.id,
        "sources": sources,
        "degraded": degraded
    }

@router.get("/conversations", response_model=List[ChatConversationResponse])
def list_conversations(
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """List all conversations owned by the authenticated user."""
    convs = db.query(ChatConversation).filter(
        ChatConversation.user_id == user.id
    ).order_by(ChatConversation.updated_at.desc()).all()
    return convs

@router.get("/conversations/{conversation_id}", response_model=ChatConversationDetailResponse)
def get_conversation_detail(
    conversation_id: str,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """Fetch complete conversation history with messages."""
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id
    ).first()
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    if conv.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: Access denied to conversation.")

    msg_items = []
    for m in conv.messages:
        srcs = None
        if m.sources:
            try:
                srcs = json.loads(m.sources)
            except Exception:
                srcs = [m.sources]
        msg_items.append(ChatMessageItem(
            id=m.id,
            role=m.role,
            content=m.content,
            sources=srcs,
            created_at=m.created_at
        ))

    return ChatConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        application_id=conv.application_id,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=msg_items
    )

@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db)
):
    """Delete a conversation owned by the authenticated user."""
    conv = db.query(ChatConversation).filter(
        ChatConversation.id == conversation_id
    ).first()
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found.")
    if conv.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden: Access denied to conversation.")

    db.delete(conv)
    db.commit()
    return {"detail": "Conversation deleted successfully."}
