import io
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from app.services.ai import gemini
from app.services.ai.gemini import GeminiError, check_gemini_health, summarize_with_gemini
from app.services.ai.tools import AcademicRecord


class FakeResponse:
    def __init__(self, payload: bytes = b"{}") -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def http_error(code: int, body: bytes = b"") -> HTTPError:
    return HTTPError("https://example.invalid", code, "safe", {}, io.BytesIO(body))


def record() -> AcademicRecord:
    return AcademicRecord(
        title="Lab final",
        body="Tuesday",
        course_name="CSE 3208",
        source_url="https://classroom.google.com/c/1",
        event_type="exam",
        starts_at=datetime(2026, 9, 29, 10, tzinfo=UTC),
        due_at=None,
        priority=3,
        completed=False,
    )


def test_gemini_health_reports_safe_states(monkeypatch) -> None:
    assert check_gemini_health(None, "model") == "not_configured"

    monkeypatch.setattr(gemini, "urlopen", lambda *_args, **_kwargs: FakeResponse())
    assert check_gemini_health("secret", "model") == "reachable"

    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error(401))
    )
    assert check_gemini_health("secret", "model") == "invalid_credentials"

    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error(429))
    )
    assert check_gemini_health("secret", "model") == "rate_limited"

    monkeypatch.setattr(
        gemini,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error(429, b"quota exceeded")),
    )
    assert check_gemini_health("secret", "model") == "quota_exceeded"

    monkeypatch.setattr(
        gemini,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError(TimeoutError())),
    )
    assert check_gemini_health("secret", "model") == "timeout"


def test_gemini_structured_success(monkeypatch) -> None:
    payload = json.dumps(
        {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps({"answer": "Verified explanation"})}]}}
            ]
        }
    ).encode()
    monkeypatch.setattr(gemini, "urlopen", lambda *_args, **_kwargs: FakeResponse(payload))
    assert (
        summarize_with_gemini("secret", "model", "question", [record()]) == "Verified explanation"
    )


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (http_error(403), "invalid_credentials"),
        (http_error(429), "rate_limited"),
        (http_error(429, b"RESOURCE_EXHAUSTED quota"), "quota_exceeded"),
        (URLError(TimeoutError()), "timeout"),
    ],
)
def test_gemini_generation_classifies_failures(monkeypatch, error, status) -> None:
    monkeypatch.setattr(gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
    with pytest.raises(GeminiError) as raised:
        summarize_with_gemini("secret", "model", "question", [record()])
    assert raised.value.status == status


def test_assistant_keeps_deterministic_answer_when_gemini_fails(monkeypatch) -> None:
    from app.services.ai import service

    monkeypatch.setattr(service, "_execute", lambda *_args: [record()])
    monkeypatch.setattr(
        service,
        "resolve_course_intent",
        lambda *_args: SimpleNamespace(course_names=[], ambiguous=False),
    )
    monkeypatch.setattr(service, "last_successful_sync", lambda *_args: None)
    monkeypatch.setattr(
        service,
        "summarize_with_gemini",
        lambda *_args: (_ for _ in ()).throw(GeminiError("timeout")),
    )
    output = service.answer_question(
        None,
        SimpleNamespace(id="user", timezone="UTC"),
        "find database normalization details",
        SimpleNamespace(gemini_api_key="configured", gemini_model="model"),
    )
    assert output.mode == "local"
    assert output.gemini_status == "timeout"
    assert output.data_available is True
    assert "Lab final" in output.answer


def test_gemini_health_distinguishes_network_and_provider_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("dns"))
    )
    assert check_gemini_health("secret", "model") == "network_error"

    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error(500))
    )
    assert check_gemini_health("secret", "model") == "provider_error"

    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(http_error(404))
    )
    assert check_gemini_health("secret", "model") == "model_unavailable"


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({"promptFeedback": {"blockReason": "SAFETY"}}, "blocked_response"),
        ({"candidates": [{"finishReason": "SAFETY"}]}, "blocked_response"),
        ({"candidates": []}, "malformed_response"),
        ({"candidates": [{"content": {"parts": []}}]}, "malformed_response"),
    ],
)
def test_gemini_generation_classifies_unusable_responses(monkeypatch, payload, status) -> None:
    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: FakeResponse(json.dumps(payload).encode())
    )
    with pytest.raises(GeminiError) as raised:
        summarize_with_gemini("secret", "model", "private question", [record()])
    assert raised.value.status == status
    assert raised.value.request_id


def test_gemini_logs_safe_correlation_data_without_prompt(monkeypatch, caplog) -> None:
    monkeypatch.setattr(
        gemini, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("dns"))
    )
    with caplog.at_level("WARNING"):
        with pytest.raises(GeminiError):
            summarize_with_gemini("secret-key", "model", "private academic question", [record()])
    text = caplog.text
    assert "request_id=" in text
    assert "status=network_error" in text
    assert "secret-key" not in text
    assert "private academic question" not in text
