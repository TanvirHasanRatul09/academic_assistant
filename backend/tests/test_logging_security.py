from app.core.logging import RedactingFilter, redact


def test_logging_redacts_sensitive_fields_recursively() -> None:
    value = {
        "authorization": "Bearer secret",
        "nested": {"refresh_token": "secret", "email": "student@example.test"},
        "safe": "sync_started",
    }
    assert redact(value) == {
        "authorization": "[REDACTED]",
        "nested": {"refresh_token": "[REDACTED]", "email": "[REDACTED]"},
        "safe": "sync_started",
    }
    assert isinstance(RedactingFilter(), RedactingFilter)
