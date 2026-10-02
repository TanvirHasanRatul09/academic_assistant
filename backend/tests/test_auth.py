from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.auth import ProfileInput

client = TestClient(app)


def test_google_start_uses_state_nonce_and_pkce() -> None:
    response = client.get("/api/auth/google/start")

    assert response.status_code == 200
    query = parse_qs(urlparse(response.json()["authorization_url"]).query)
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert "prompt" not in query
    assert len(query["state"][0]) >= 32
    assert len(query["nonce"][0]) >= 32
    cookies = response.headers.get_list("set-cookie")
    assert all("HttpOnly" in cookie for cookie in cookies)
    assert any("academic_oauth_verifier=" in cookie for cookie in cookies)


def test_private_endpoint_requires_authentication() -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}


def test_profile_rejects_invalid_timezone_and_preferences() -> None:
    with pytest.raises(ValidationError):
        ProfileInput(timezone="Not/A-Timezone")
    with pytest.raises(ValidationError):
        ProfileInput(notification_preferences={"sms": True})


def test_profile_normalizes_section_and_rejects_duplicate_courses() -> None:
    profile = ProfileInput(section="  Section   A ")
    assert profile.section == "Section A"

    course_id = "f825f23b-d461-4de7-a9a3-c904ca69f6a4"
    with pytest.raises(ValidationError):
        ProfileInput(selected_course_ids=[course_id, course_id])


def test_profile_normalizes_academic_context() -> None:
    profile = ProfileInput(
        academic_level="  Third   Year ",
        program=" Computer   Science and Engineering ",
        section=" sec   A ",
        lab_group=" A-1 ",
    )
    assert profile.academic_level == "Third Year"
    assert profile.program == "Computer Science and Engineering"
    assert profile.section == "sec A"
    assert profile.lab_group == "A-1"


def test_profile_endpoint_requires_authentication() -> None:
    response = client.get("/api/auth/profile")
    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
