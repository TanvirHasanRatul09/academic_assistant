# ruff: noqa: B008
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_csrf
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.models.entities import AuditEvent, User
from app.db.session import get_db
from app.schemas.assistant import AssistantOutput, AssistantQuery, GeminiHealth, GeminiStatus
from app.services.ai.gemini import get_gemini_health
from app.services.ai.service import answer_question

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
DAILY_LIMIT = 100


@router.get(
    "/gemini-health",
    response_model=GeminiHealth,
    dependencies=[Depends(rate_limit("gemini-health", 6, 60))],
)
def gemini_health(_user: User = Depends(get_current_user)) -> GeminiHealth:
    settings = get_settings()
    result = get_gemini_health(settings.gemini_api_key, settings.gemini_model)
    messages: dict[GeminiStatus, str] = {
        "configured": "Gemini is configured but has not been contacted.",
        "not_configured": "Set GEMINI_API_KEY and restart the backend.",
        "reachable": "Gemini is configured and reachable.",
        "invalid_credentials": "Verify GEMINI_API_KEY and its API restrictions.",
        "rate_limited": "Gemini is rate limited; retry after a short delay.",
        "quota_exceeded": "The Gemini project quota is exhausted; review its quota or billing.",
        "timeout": "Gemini did not respond before the provider timeout.",
        "network_error": "The backend could not reach the Gemini API.",
        "model_unavailable": "The configured Gemini model is unavailable to this API key.",
        "provider_error": "Gemini returned a provider error; use the request ID to inspect logs.",
        "blocked_response": "Gemini blocked the response; deterministic answers remain available.",
        "malformed_response": (
            "Gemini returned an unusable response; deterministic answers remain available."
        ),
    }
    return GeminiHealth(
        status=result.status,
        model=result.model,
        message=messages[result.status],
        request_id=result.request_id,
    )


@router.post(
    "/query",
    response_model=AssistantOutput,
    dependencies=[Depends(require_csrf), Depends(rate_limit("assistant", 20, 60))],
)
def query_assistant(
    payload: AssistantQuery, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AssistantOutput:
    today = datetime.now(UTC).date()
    used = (
        db.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.user_id == user.id,
                AuditEvent.event_type == "assistant.request",
                func.date(AuditEvent.created_at) == today,
            )
        )
        or 0
    )
    if used >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429, detail="Daily assistant limit reached; try again tomorrow"
        )
    output = answer_question(db, user, payload.message, get_settings(), payload.history)
    db.add(
        AuditEvent(
            user_id=user.id,
            event_type="assistant.request",
            outcome="success",
            safe_metadata={
                "tool": output.tool,
                "mode": output.mode,
                "results": len(output.sources),
            },
        )
    )
    db.commit()
    return output
