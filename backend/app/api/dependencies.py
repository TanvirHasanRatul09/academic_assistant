import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.entities import User, UserSession
from app.db.session import get_db

SESSION_COOKIE = "academic_session"


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_current_session(
    request: Request,
    academic_session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> UserSession:
    if not academic_session:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = db.scalar(
        select(UserSession).where(UserSession.id == hash_secret(academic_session))
    )
    if not session or session.expires_at <= datetime.now(UTC):
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=401, detail="Authentication required")
    request.state.user_session = session
    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_csrf(
    session: UserSession = Depends(get_current_session),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    if not x_csrf_token or not secrets.compare_digest(
        hash_secret(x_csrf_token), session.csrf_token_hash
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def require_recent_reauthentication(
    session: UserSession = Depends(get_current_session),
) -> None:
    if session.reauthenticated_at < datetime.now(UTC) - timedelta(minutes=10):
        raise HTTPException(status_code=403, detail="Recent reauthentication required")
