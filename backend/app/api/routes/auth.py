import base64
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import (
    SESSION_COOKIE,
    get_current_session,
    get_current_user,
    hash_secret,
    require_csrf,
    require_recent_reauthentication,
)
from app.core.config import get_settings
from app.core.rate_limit import rate_limit
from app.db.models.entities import (
    CourseMembership,
    OAuthAccount,
    OnboardingState,
    SyncRun,
    User,
    UserProfile,
    UserSession,
)
from app.db.session import get_db
from app.schemas.auth import (
    AuthorizationUrl,
    CourseOption,
    CsrfToken,
    ProfileInput,
    ProfileOutput,
    SessionUser,
)
from app.services.token_encryption import TokenEncryption

router = APIRouter(prefix="/api/auth", tags=["authentication"])
STATE_COOKIE = "academic_oauth_state"
VERIFIER_COOKIE = "academic_oauth_verifier"
NONCE_COOKIE = "academic_oauth_nonce"
PURPOSE_COOKIE = "academic_oauth_purpose"
OAUTH_COOKIE_AGE = 600
SESSION_AGE = 14 * 24 * 60 * 60
SCOPES = (
    "openid email profile "
    "https://www.googleapis.com/auth/classroom.courses.readonly "
    "https://www.googleapis.com/auth/classroom.announcements.readonly "
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly "
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly "
    "https://www.googleapis.com/auth/classroom.topics.readonly"
)


def _cookie_secure() -> bool:
    return get_settings().app_env == "production"


def _set_temporary_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=OAUTH_COOKIE_AGE,
        path="/api/auth/google",
    )


def _authorization_url(
    response: Response, purpose: str, *, force_consent: bool = False
) -> AuthorizationUrl:
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    _set_temporary_cookie(response, STATE_COOKIE, state)
    _set_temporary_cookie(response, NONCE_COOKIE, nonce)
    _set_temporary_cookie(response, VERIFIER_COOKIE, verifier)
    _set_temporary_cookie(response, PURPOSE_COOKIE, purpose)
    parameters = {
        "client_id": settings.google_client_id,
        "redirect_uri": str(settings.google_redirect_uri),
        "response_type": "code",
        "scope": SCOPES,
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "include_granted_scopes": "true",
    }
    if purpose == "reauth":
        parameters["prompt"] = "select_account"
    query = urlencode(parameters)
    return AuthorizationUrl(
        authorization_url=f"https://accounts.google.com/o/oauth2/v2/auth?{query}"
    )


@router.get(
    "/google/start",
    response_model=AuthorizationUrl,
    dependencies=[Depends(rate_limit("oauth-start", 10, 60))],
)
def google_start(response: Response) -> AuthorizationUrl:
    return _authorization_url(response, "login")


@router.get(
    "/google/reauth",
    response_model=AuthorizationUrl,
    dependencies=[Depends(rate_limit("oauth-reauth", 6, 60))],
)
def google_reauth(
    response: Response,
    _user: User = Depends(get_current_user),
) -> AuthorizationUrl:
    return _authorization_url(response, "reauth")


@router.get(
    "/google/reconnect",
    response_model=AuthorizationUrl,
    dependencies=[Depends(rate_limit("oauth-reconnect", 6, 60))],
)
def google_reconnect(
    response: Response,
    _user: User = Depends(get_current_user),
) -> AuthorizationUrl:
    return _authorization_url(response, "login", force_consent=True)


def _validated_claims(token_payload: dict[str, object], expected_nonce: str) -> dict[str, object]:
    settings = get_settings()
    raw_id_token = token_payload.get("id_token")
    if not isinstance(raw_id_token, str):
        raise HTTPException(status_code=400, detail="Identity token missing")
    try:
        validation = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": raw_id_token},
            timeout=10,
        )
        validation.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail="Identity validation failed") from exc
    claims = validation.json()
    if claims.get("aud") != settings.google_client_id:
        raise HTTPException(status_code=400, detail="Identity validation failed")
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=400, detail="Identity validation failed")
    if not secrets.compare_digest(str(claims.get("nonce", "")), expected_nonce):
        raise HTTPException(status_code=400, detail="Identity validation failed")
    if claims.get("email_verified") is not True:
        if claims.get("email_verified") != "true":
            raise HTTPException(status_code=400, detail="Unverified Google account")
    try:
        if int(claims.get("exp", 0)) <= int(datetime.now(UTC).timestamp()):
            raise HTTPException(status_code=400, detail="Identity token expired")
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Identity validation failed") from exc
    return claims


@router.get(
    "/google/callback",
    dependencies=[Depends(rate_limit("oauth-callback", 12, 60))],
)
def google_callback(
    request: Request,
    code: str = Query(min_length=1, max_length=4096),
    state: str = Query(min_length=1, max_length=256),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    expected_state = request.cookies.get(STATE_COOKIE, "")
    verifier = request.cookies.get(VERIFIER_COOKIE, "")
    nonce = request.cookies.get(NONCE_COOKIE, "")
    purpose = request.cookies.get(PURPOSE_COOKIE, "login")
    if not expected_state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    if not verifier or not nonce or purpose not in {"login", "reauth"}:
        raise HTTPException(status_code=400, detail="OAuth request expired")

    settings = get_settings()
    try:
        token_response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": str(settings.google_redirect_uri),
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=10,
        )
        token_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=400, detail="OAuth exchange failed") from exc
    token_payload = token_response.json()
    claims = _validated_claims(token_payload, nonce)
    subject = str(claims.get("sub", ""))
    email = str(claims.get("email", "")).casefold()
    if not subject or not email:
        raise HTTPException(status_code=400, detail="Identity validation failed")

    now = datetime.now(UTC)
    raw_existing_session = request.cookies.get(SESSION_COOKIE)
    existing_session = (
        db.get(UserSession, hash_secret(raw_existing_session)) if raw_existing_session else None
    )
    account = db.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_subject == subject,
        )
    )

    if purpose == "reauth":
        if not existing_session or not account or account.user_id != existing_session.user_id:
            raise HTTPException(status_code=403, detail="Reauthentication account mismatch")
        existing_session.reauthenticated_at = now
        db.commit()
        response = RedirectResponse(f"{settings.cors_origins[0]}/settings?reauthenticated=true")
    else:
        user = db.get(User, account.user_id) if account else None
        if not user:
            user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(
                email=email,
                display_name=str(claims.get("name") or email),
                timezone="UTC",
            )
            db.add(user)
            db.flush()
        encryption = TokenEncryption(settings.token_encryption_key)
        access_token = token_payload.get("access_token")
        refresh_token = token_payload.get("refresh_token")
        if not account:
            account = OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_subject=subject,
            )
            db.add(account)
        if isinstance(access_token, str):
            account.encrypted_access_token = encryption.encrypt(access_token)
        if isinstance(refresh_token, str):
            account.encrypted_refresh_token = encryption.encrypt(refresh_token)
        account.scopes = str(token_payload.get("scope", SCOPES)).split()
        expires_in = int(token_payload.get("expires_in", 3600))
        account.access_token_expires_at = now + timedelta(seconds=max(0, expires_in))
        if existing_session:
            db.delete(existing_session)
        raw_session = secrets.token_urlsafe(48)
        raw_csrf = secrets.token_urlsafe(32)
        db.add(
            UserSession(
                id=hash_secret(raw_session),
                user_id=user.id,
                expires_at=now + timedelta(seconds=SESSION_AGE),
                reauthenticated_at=now,
                csrf_token_hash=hash_secret(raw_csrf),
            )
        )
        db.commit()
        destination = (
            "dashboard" if user.onboarding_state == OnboardingState.COMPLETE else "onboarding"
        )
        response = RedirectResponse(f"{settings.cors_origins[0]}/{destination}")
        response.set_cookie(
            SESSION_COOKIE,
            raw_session,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            max_age=SESSION_AGE,
            path="/",
        )
        response.set_cookie(
            "academic_csrf",
            raw_csrf,
            httponly=False,
            secure=_cookie_secure(),
            samesite="strict",
            max_age=SESSION_AGE,
            path="/",
        )
    for cookie in (STATE_COOKIE, VERIFIER_COOKIE, NONCE_COOKIE, PURPOSE_COOKIE):
        response.delete_cookie(cookie, path="/api/auth/google")
    return response


@router.get("/me", response_model=SessionUser)
def me(user: User = Depends(get_current_user)) -> SessionUser:
    return SessionUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        onboarding_complete=user.onboarding_state == OnboardingState.COMPLETE,
    )


@router.get("/csrf", response_model=CsrfToken)
def csrf_token(
    request: Request,
    _session: UserSession = Depends(get_current_session),
) -> CsrfToken:
    token = request.cookies.get("academic_csrf")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return CsrfToken(csrf_token=token)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> None:
    raw_session = request.cookies.get(SESSION_COOKIE)
    if raw_session:
        db.execute(delete(UserSession).where(UserSession.id == hash_secret(raw_session)))
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie("academic_csrf", path="/")


def _profile_output(user: User, db: Session) -> ProfileOutput:
    profile = user.profile or UserProfile(user_id=user.id)
    memberships = list(
        db.scalars(
            select(CourseMembership)
            .where(CourseMembership.user_id == user.id)
            .options(joinedload(CourseMembership.course))
        )
    )
    latest_sync = db.scalar(
        select(SyncRun.finished_at)
        .where(SyncRun.user_id == user.id, SyncRun.status == "succeeded")
        .order_by(SyncRun.finished_at.desc())
        .limit(1)
    )
    connected = (
        db.scalar(
            select(OAuthAccount.id).where(
                OAuthAccount.user_id == user.id, OAuthAccount.provider == "google"
            )
        )
        is not None
    )
    return ProfileOutput(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        onboarding_complete=user.onboarding_state == OnboardingState.COMPLETE,
        academic_level=profile.academic_level,
        program=profile.program,
        section=profile.section,
        lab_group=profile.lab_group,
        timezone=user.timezone,
        selected_course_ids=[
            item.course_id
            for item in memberships
            if item.selected and item.enrollment_status == "ACTIVE"
        ],
        notification_preferences=profile.notification_preferences,
        courses=[
            CourseOption(
                id=item.course_id,
                name=item.course.name,
                selected=item.selected,
                enrollment_status=item.enrollment_status,
                eligible=item.enrollment_status == "ACTIVE",
            )
            for item in memberships
        ],
        classroom_connected=connected,
        last_successful_sync_at=latest_sync,
    )


@router.get("/profile", response_model=ProfileOutput)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileOutput:
    return _profile_output(user, db)


@router.get("/courses", response_model=list[CourseOption])
def available_courses(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CourseOption]:
    memberships = list(
        db.scalars(
            select(CourseMembership)
            .where(CourseMembership.user_id == user.id)
            .options(joinedload(CourseMembership.course))
        )
    )
    return [
        CourseOption(
            id=item.course_id,
            name=item.course.name,
            selected=item.selected,
            enrollment_status=item.enrollment_status,
            eligible=item.enrollment_status == "ACTIVE",
        )
        for item in memberships
    ]


@router.put(
    "/profile",
    response_model=ProfileOutput,
    dependencies=[Depends(require_csrf), Depends(rate_limit("profile-update", 20, 60))],
)
def update_profile(
    payload: ProfileInput,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileOutput:
    memberships = list(
        db.scalars(select(CourseMembership).where(CourseMembership.user_id == user.id))
    )
    owned_ids = {
        membership.course_id
        for membership in memberships
        if membership.enrollment_status == "ACTIVE"
    }
    requested_ids = set(payload.selected_course_ids)
    if not requested_ids.issubset(owned_ids):
        raise HTTPException(
            status_code=403, detail="A selected course is not available to this user"
        )
    for membership in memberships:
        membership.selected = membership.course_id in requested_ids
    profile = user.profile or UserProfile(user_id=user.id)
    profile.section = payload.section
    profile.lab_group = payload.lab_group
    profile.academic_level = payload.academic_level
    profile.program = payload.program
    profile.notification_preferences = payload.notification_preferences
    user.timezone = payload.timezone
    user.onboarding_state = OnboardingState.COMPLETE
    db.add(profile)
    db.commit()
    db.refresh(user)
    return _profile_output(user, db)


@router.delete(
    "/connection",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(require_recent_reauthentication),
        Depends(rate_limit("account-disconnect", 5, 3600)),
    ],
)
def disconnect_account(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.execute(delete(OAuthAccount).where(OAuthAccount.user_id == user.id))
    db.execute(delete(UserSession).where(UserSession.user_id == user.id))
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie("academic_csrf", path="/")


@router.delete(
    "/account",
    status_code=204,
    dependencies=[
        Depends(require_csrf),
        Depends(require_recent_reauthentication),
        Depends(rate_limit("account-delete", 3, 3600)),
    ],
)
def delete_account(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    db.delete(user)
    db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie("academic_csrf", path="/")
