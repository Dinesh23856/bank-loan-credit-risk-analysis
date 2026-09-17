from __future__ import annotations
import os
import time
import uuid
import json
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try to connect to Redis
_redis_client = None
try:
    import redis
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    r = redis.Redis.from_url(redis_url, socket_timeout=1.0)
    r.ping()
    _redis_client = r
    logger.info("Connected to Redis successfully.")
except Exception as exc:
    logger.info("Redis not available; falling back to in-memory task runner: %s", exc)
    _redis_client = None

# In-memory storage fallback
_in_memory_tasks: Dict[str, Dict[str, Any]] = {}
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="loan_worker")

def _set_task(task_id: str, data: dict, ttl_seconds: int = 86400) -> None:
    if _redis_client:
        try:
            _redis_client.setex(f"task:{task_id}", ttl_seconds, json.dumps(data))
            return
        except Exception as exc:
            logger.warning("Failed to save task to Redis, using in-memory: %s", exc)
    _in_memory_tasks[task_id] = data

def get_task_status(task_id: str) -> Optional[dict]:
    if _redis_client:
        try:
            raw = _redis_client.get(f"task:{task_id}")
            if raw:
                return json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        except Exception as exc:
            logger.warning("Failed to fetch task from Redis: %s", exc)
    return _in_memory_tasks.get(task_id)

def _background_process(task_id: str, application_id: int, applicant_data: dict, user_id: int) -> None:
    from ..database import SessionLocal
    from ..models import LoanApplication, ModelLog
    from .prediction_service import run_prediction

    # Update state to PROCESSING
    state = {
        "task_id": task_id,
        "application_id": application_id,
        "status": "PROCESSING",
        "result": None,
        "error": None,
        "updated_at": datetime.utcnow().isoformat()
    }
    _set_task(task_id, state)

    db = SessionLocal()
    try:
        result, elapsed = run_prediction(applicant_data, include_explanations=True)

        app = db.query(LoanApplication).filter(LoanApplication.id == application_id).first()
        if app:
            app.approval_status = result["loan_status"]
            app.predicted_loan_amount = result["approved_loan_amount"]
            app.predicted_credit_score = result["credit_score"]
            app.risk_level = result["risk_level"]

            entries = [
                ("loan_approval", {"status": result["loan_status"], "probability": result["approval_probability"]}),
                ("loan_amount", result["approved_loan_amount"]),
                ("credit_score", result["credit_score"]),
                ("credit_risk", {"risk_level": result["risk_level"], "probabilities": result["risk_probabilities"]}),
            ]
            for name, prediction in entries:
                db.add(ModelLog(
                    user_id=user_id,
                    application_id=application_id,
                    model_name=name,
                    model_version="v2.0-enterprise",
                    decision=result["loan_status"] if name == "loan_approval" else None,
                    status="SUCCESS",
                    explanation_generated=1 if name == "loan_approval" else 0,
                    prediction=json.dumps(prediction),
                    inference_time_ms=elapsed,
                    processing_duration_ms=elapsed
                ))
            db.commit()

        state["status"] = "SUCCESS"
        state["result"] = {"approved": result["loan_status"] == "Approved", **result}
        state["updated_at"] = datetime.utcnow().isoformat()
        _set_task(task_id, state)
        logger.info("Task %s completed successfully.", task_id)
    except Exception as exc:
        db.rollback()
        logger.exception("Error processing background task %s: %s", task_id, exc)
        state["status"] = "FAILED"
        state["error"] = str(exc)
        state["updated_at"] = datetime.utcnow().isoformat()
        _set_task(task_id, state)
    finally:
        db.close()

def submit_application_task(application_id: int, applicant_data: dict, user_id: int) -> str:
    task_id = str(uuid.uuid4())
    initial_state = {
        "task_id": task_id,
        "application_id": application_id,
        "status": "PENDING",
        "result": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat()
    }
    _set_task(task_id, initial_state)
    _executor.submit(_background_process, task_id, application_id, applicant_data, user_id)
    return task_id
