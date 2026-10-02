from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.entities import OAuthAccount
from app.services.classroom.client import ClassroomError
from app.services.token_encryption import TokenEncryption


def access_token(account: OAuthAccount, db: Session) -> str:
    settings = get_settings()
    encryption = TokenEncryption(settings.token_encryption_key)
    now = datetime.now(UTC)
    if account.encrypted_access_token and account.access_token_expires_at:
        if account.access_token_expires_at > now + timedelta(seconds=60):
            return encryption.decrypt(account.encrypted_access_token)
    if not account.encrypted_refresh_token:
        raise ClassroomError("reauthorization_required")
    try:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": encryption.decrypt(account.encrypted_refresh_token),
                "grant_type": "refresh_token",
            },
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ClassroomError("reauthorization_required") from exc
    payload = response.json()
    token = payload.get("access_token")
    if not isinstance(token, str):
        raise ClassroomError("invalid_provider_response")
    account.encrypted_access_token = encryption.encrypt(token)
    account.access_token_expires_at = now + timedelta(seconds=int(payload.get("expires_in", 3600)))
    db.commit()
    return token
