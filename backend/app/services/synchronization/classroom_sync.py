import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.db.models.entities import (
    ClassroomItem,
    Course,
    CourseMembership,
    OAuthAccount,
    SourceType,
    SyncRun,
    SyncStatus,
)
from app.db.session import SessionLocal
from app.services.classroom.client import ClassroomClient, ClassroomError
from app.services.classroom.tokens import access_token
from app.services.extraction.pipeline import process_user

logger = logging.getLogger(__name__)
_locks: dict[UUID, threading.Lock] = {}
_locks_guard = threading.Lock()
INITIAL_PAGE_LIMIT = 2
INCREMENTAL_PAGE_LIMIT = 3
COURSE_CONCURRENCY = 5
STALE_AFTER = timedelta(minutes=2)
WORKER_LEASE = timedelta(minutes=2)
MAX_JOB_ATTEMPTS = 3
QUICK_SYNC_DEADLINE = 15.0
COURSE_DEADLINE = 8.0
RECENT_SUBMISSION_WINDOW = timedelta(days=14)


def _lock_for(user_id: UUID) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(user_id, threading.Lock())


def _text(value: object, limit: int) -> str:
    return str(value or "").replace("\x00", "").strip()[:limit]


def _url(value: object) -> str:
    url = _text(value, 2048)
    parsed = urlparse(url)
    return url if parsed.scheme == "https" and parsed.netloc else "https://classroom.google.com/"


def _optional_url(value: object) -> str | None:
    url = _text(value, 2048)
    parsed = urlparse(url)
    return url if parsed.scheme == "https" and parsed.netloc else None


def _attachment_metadata(materials: object, synchronized_at: datetime) -> list[dict[str, object]]:
    if not isinstance(materials, list):
        return []
    attachments: list[dict[str, object]] = []
    for material in materials[:25]:
        if not isinstance(material, dict):
            continue
        kind = ""
        provider_id = ""
        title = "Attachment"
        url: str | None = None
        drive = material.get("driveFile")
        if isinstance(drive, dict) and isinstance(drive.get("driveFile"), dict):
            file = drive["driveFile"]
            kind = "drive_file"
            provider_id = _text(file.get("id"), 256)
            title = _text(file.get("title"), 500) or title
            url = _optional_url(file.get("alternateLink"))
        elif isinstance(material.get("link"), dict):
            link = material["link"]
            kind = "link"
            title = _text(link.get("title"), 500) or title
            url = _optional_url(link.get("url"))
        elif isinstance(material.get("form"), dict):
            form = material["form"]
            kind = "form"
            title = _text(form.get("title"), 500) or "Google Form"
            url = _optional_url(form.get("formUrl"))
        elif isinstance(material.get("youtubeVideo"), dict):
            video = material["youtubeVideo"]
            kind = "youtube"
            provider_id = _text(video.get("id"), 256)
            title = _text(video.get("title"), 500) or "YouTube video"
            url = _optional_url(video.get("alternateLink"))
        if not kind or not url:
            continue
        attachments.append(
            {
                "kind": kind,
                "provider_id": provider_id,
                "title": title,
                "url": url,
                "is_pdf": title.casefold().endswith(".pdf"),
                "synchronized_at": synchronized_at.isoformat(),
            }
        )
    return attachments


def _timestamp(value: object) -> datetime:
    parsed = _optional_timestamp(value)
    return parsed or datetime.now(UTC)


def _optional_timestamp(value: object) -> datetime | None:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _hash(item: dict[str, Any]) -> str:
    encoded = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class ClassroomSynchronizer:
    def __init__(self, db: Session, user_id: UUID, worker_id: str | None = None) -> None:
        self.db = db
        self.user_id = user_id
        self.worker_id = worker_id

    @staticmethod
    def claim_run(db: Session, worker_id: str, run_id: UUID | None = None) -> SyncRun | None:
        now = db.scalar(select(func.now())) or datetime.now(UTC)
        query = (
            select(SyncRun)
            .where(
                SyncRun.status == SyncStatus.RUNNING,
                SyncRun.attempt_count < MAX_JOB_ATTEMPTS,
                (SyncRun.lease_expires_at.is_(None)) | (SyncRun.lease_expires_at <= now),
            )
            .order_by(SyncRun.started_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run_id is not None:
            query = query.where(SyncRun.id == run_id)
        run = db.scalar(query)
        if not run:
            db.rollback()
            return None
        run.worker_id = worker_id
        run.lease_expires_at = now + WORKER_LEASE
        run.heartbeat_at = now
        run.attempt_count += 1
        if run.attempt_count > 1:
            run.courses_processed = 0
            run.courses_total = 0
            run.items_seen = 0
            run.items_changed = 0
            run.failed_courses = []
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def release_crashed_run(db: Session, run_id: UUID, worker_id: str) -> None:
        db.rollback()
        run = db.get(SyncRun, run_id)
        if not run or run.status != SyncStatus.RUNNING or run.worker_id != worker_id:
            return
        now = db.scalar(select(func.now())) or datetime.now(UTC)
        if run.attempt_count >= MAX_JOB_ATTEMPTS:
            run.status = SyncStatus.FAILED
            run.current_phase = "complete"
            run.safe_error_code = "sync_worker_failed"
            run.finished_at = now
            run.checkpoint = now.isoformat()
        else:
            run.current_phase = "queued"
            run.safe_error_code = "sync_worker_retry"
        run.worker_id = None
        run.lease_expires_at = None
        run.heartbeat_at = now
        db.commit()

    @staticmethod
    def recover_stalled(db: Session, run: SyncRun) -> bool:
        if run.status != SyncStatus.RUNNING:
            return False
        now = db.scalar(select(func.now())) or datetime.now(UTC)
        if run.current_phase == "queued":
            return False
        if run.worker_id and run.lease_expires_at and run.lease_expires_at <= now:
            run.worker_id = None
            run.lease_expires_at = None
            run.current_phase = "queued"
            run.safe_error_code = "sync_worker_retry"
            run.heartbeat_at = now
            db.commit()
            return False
        reference = run.heartbeat_at or run.started_at
        if reference > now - STALE_AFTER:
            return False
        run.status = SyncStatus.FAILED
        run.current_phase = "complete"
        run.safe_error_code = "sync_stalled"
        run.finished_at = now
        run.checkpoint = now.isoformat()
        db.commit()
        return True

    @staticmethod
    def fail_crashed_run(db: Session, run_id: UUID) -> None:
        db.rollback()
        run = db.get(SyncRun, run_id)
        if not run or run.status != SyncStatus.RUNNING:
            return
        run.status = SyncStatus.FAILED
        run.current_phase = "complete"
        run.safe_error_code = "sync_worker_failed"
        run.finished_at = db.scalar(select(func.now())) or datetime.now(UTC)
        run.checkpoint = run.finished_at.isoformat()
        db.commit()

    def start(self, *, cooldown_seconds: int = 30) -> SyncRun:
        latest = self.db.scalar(
            select(SyncRun)
            .where(SyncRun.user_id == self.user_id)
            .order_by(SyncRun.started_at.desc())
            .limit(1)
        )
        now = self.db.scalar(select(func.now())) or datetime.now(UTC)
        if latest and latest.status == SyncStatus.RUNNING:
            if not self.recover_stalled(self.db, latest):
                raise ClassroomError("sync_already_running")
            now = self.db.scalar(select(func.now())) or datetime.now(UTC)
        if latest and latest.started_at > now - timedelta(seconds=cooldown_seconds):
            raise ClassroomError("sync_cooldown")
        run = SyncRun(
            user_id=self.user_id,
            status=SyncStatus.RUNNING,
            current_phase="queued",
            heartbeat_at=now,
            failed_courses=[],
        )
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ClassroomError("sync_already_running") from exc
        self.db.refresh(run)
        return run

    def run(self, *, cooldown_seconds: int = 60) -> SyncRun:
        lock = _lock_for(self.user_id)
        if not lock.acquire(blocking=False):
            raise ClassroomError("sync_already_running")
        try:
            run = self.start(cooldown_seconds=cooldown_seconds)
            return self._execute(run)
        finally:
            lock.release()

    def run_existing(self, run_id: UUID) -> SyncRun:
        lock = _lock_for(self.user_id)
        if not lock.acquire(blocking=False):
            raise ClassroomError("sync_already_running")
        try:
            run = self.db.get(SyncRun, run_id)
            if not run or run.user_id != self.user_id:
                raise ClassroomError("sync_run_not_found")
            if self.worker_id and run.worker_id != self.worker_id:
                raise ClassroomError("sync_lease_lost")
            if run.status != SyncStatus.RUNNING:
                return run
            return self._execute(run)
        finally:
            lock.release()

    def _execute(self, run: SyncRun) -> SyncRun:
        run.current_phase = "authorizing"
        self._persist_progress(run)
        account = self.db.scalar(
            select(OAuthAccount).where(
                OAuthAccount.user_id == self.user_id, OAuthAccount.provider == "google"
            )
        )
        if not account:
            return self._finish(run, SyncStatus.FAILED, "reauthorization_required")
        started = perf_counter()
        metrics: dict[str, float | int] = {}
        try:
            provider_token = access_token(account, self.db)
            quick_started = perf_counter()
            quick_deadline = quick_started + QUICK_SYNC_DEADLINE
            client = ClassroomClient(provider_token, deadline=quick_deadline)
            sync_started = perf_counter()
            changed, seen, partial, changed_ids = self._sync_all(
                client, run, provider_token, quick=True, deadline=quick_deadline
            )
            metrics["classroom_api_and_database_ms"] = round(
                (perf_counter() - sync_started) * 1000, 2
            )
            metrics["google_api_ms"] = round(client.request_seconds * 1000, 2)
            metrics["google_api_requests"] = client.request_count
            metrics["pages_fetched"] = client.page_count
            metrics["database_and_reconciliation_ms"] = round(
                max(0.0, metrics["classroom_api_and_database_ms"] - metrics["google_api_ms"]), 2
            )
            run.items_changed = changed
            run.items_seen = seen
            # The visible quick job ends after current Classroom data is committed.
            # Extraction, notifications, and historical rule upgrades belong to maintenance.
            metrics["quick_sync_ms"] = round((perf_counter() - quick_started) * 1000, 2)
            metrics["total_ms"] = metrics["quick_sync_ms"]
            run.timing_metrics = metrics
            logger.info(
                "sync_complete user_id=%s status=%s metrics=%s",
                self.user_id,
                "partial" if partial else "succeeded",
                metrics,
            )
            return self._finish(run, SyncStatus.PARTIAL if partial else SyncStatus.SUCCEEDED, None)
        except ClassroomError as exc:
            self.db.rollback()
            if exc.code in {"authorization_revoked", "reauthorization_required"}:
                refreshed = self.db.get(OAuthAccount, account.id)
                if refreshed:
                    refreshed.encrypted_access_token = None
                    refreshed.encrypted_refresh_token = None
            run = self.db.get(SyncRun, run.id) or run
            run.timing_metrics = {"total_ms": round((perf_counter() - started) * 1000, 2)}
            logger.warning("sync_failed user_id=%s code=%s", self.user_id, exc.code)
            return self._finish(run, SyncStatus.FAILED, exc.code)

    def run_maintenance(self, run_id: UUID) -> None:
        """Reprocess historical extraction in a separate, low-priority job."""
        run = self.db.get(SyncRun, run_id)
        if not run or run.user_id != self.user_id:
            return
        started = perf_counter()
        run.current_phase = "historical_maintenance"
        self._persist_progress(run)
        try:
            result = process_user(self.db, self.user_id)
            metrics = dict(run.timing_metrics or {})
            metrics.update(
                {
                    "maintenance_ms": round((perf_counter() - started) * 1000, 2),
                    "maintenance_events_processed": result["processed"],
                }
            )
            run.timing_metrics = metrics
            run.current_phase = "complete"
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception("classroom_maintenance_failed user_id=%s", self.user_id)

    def _persist_progress(self, run: SyncRun) -> None:
        if self.worker_id:
            lease_owner = self.db.scalar(select(SyncRun.worker_id).where(SyncRun.id == run.id))
            if lease_owner != self.worker_id:
                self.db.rollback()
                raise ClassroomError("sync_lease_lost")
        run.heartbeat_at = self.db.scalar(select(func.now())) or datetime.now(UTC)
        if self.worker_id:
            run.lease_expires_at = run.heartbeat_at + WORKER_LEASE
        run.checkpoint = f"{run.current_phase}:{run.courses_processed}/{run.courses_total}"
        self.db.add(run)
        self.db.commit()

    def _finish(self, run: SyncRun, status: SyncStatus, code: str | None) -> SyncRun:
        run.status = status
        run.safe_error_code = code
        run.current_phase = "complete"
        run.finished_at = self.db.scalar(select(func.now())) or datetime.now(UTC)
        run.heartbeat_at = run.finished_at
        run.checkpoint = run.finished_at.isoformat()
        run.lease_expires_at = None
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _sync_all(
        self,
        client: ClassroomClient,
        run: SyncRun,
        provider_token: str,
        *,
        quick: bool = True,
        deadline: float | None = None,
    ) -> tuple[int, int, bool, set[UUID]]:
        changed = seen = 0
        partial = False
        changed_ids: set[UUID] = set()
        provider_course_ids: set[str] = set()
        run.current_phase = "discovering_courses"
        self._persist_progress(run)
        memberships = {
            membership.course.classroom_course_id: membership
            for membership in self.db.scalars(
                select(CourseMembership)
                .join(Course)
                .where(CourseMembership.user_id == self.user_id, Course.provider == "google")
                .options(joinedload(CourseMembership.course))
            )
        }
        discovered: list[tuple[Course, CourseMembership]] = []
        fields = "nextPageToken,courses(id,name,courseState,alternateLink,updateTime)"
        for page in client.pages(
            "/courses", "courses", {"studentId": "me", "courseStates": ["ACTIVE"], "fields": fields}
        ):
            for raw in page:
                provider_id = _text(raw.get("id"), 128)
                if not provider_id:
                    continue
                provider_course_ids.add(provider_id)
                membership = memberships.get(provider_id)
                course = (
                    membership.course
                    if membership
                    else self.db.scalar(
                        select(Course).where(
                            Course.provider == "google", Course.classroom_course_id == provider_id
                        )
                    )
                )
                if not course:
                    course = Course(
                        provider="google",
                        classroom_course_id=provider_id,
                        name="",
                        status="ACTIVE",
                        provider_metadata={},
                    )
                    self.db.add(course)
                    self.db.flush()
                    changed += 1
                before = (course.name, course.status, course.provider_metadata)
                course.name = _text(raw.get("name"), 255) or "Untitled course"
                course.status = "ACTIVE"
                course.provider_metadata = {
                    "alternateLink": _url(raw.get("alternateLink")),
                    "updateTime": raw.get("updateTime"),
                }
                if before != (course.name, course.status, course.provider_metadata):
                    changed += 1
                if not membership:
                    membership = CourseMembership(
                        user_id=self.user_id,
                        course_id=course.id,
                        selected=False,
                        enrollment_status="ACTIVE",
                        sync_checkpoint={},
                    )
                    self.db.add(membership)
                    memberships[provider_id] = membership
                    changed += 1
                membership.enrollment_status = "ACTIVE"
                if membership.selected:
                    discovered.append((course, membership))
        run.courses_total = len(discovered)
        run.current_phase = "syncing_courses"
        self._persist_progress(run)
        failed_courses: list[dict[str, str]] = []
        futures = {}
        with ThreadPoolExecutor(
            max_workers=min(COURSE_CONCURRENCY, max(1, len(discovered))),
            thread_name_prefix="classroom-sync",
        ) as executor:
            for course, membership in discovered:
                future = executor.submit(
                    self._sync_course_isolated,
                    provider_token,
                    course.id,
                    membership.id,
                    quick,
                    deadline,
                )
                futures[future] = (course.name, course.id)
            for future in as_completed(futures):
                course_name, _course_id = futures[future]
                try:
                    item_changed, item_seen, item_ids, request_count, request_seconds, pages = (
                        future.result()
                    )
                    changed += item_changed
                    seen += item_seen
                    changed_ids.update(item_ids)
                    client.request_count += request_count
                    client.request_seconds += request_seconds
                    client.page_count += pages
                except ClassroomError as exc:
                    if exc.code == "authorization_revoked":
                        for pending in futures:
                            pending.cancel()
                        raise
                    partial = True
                    failed_courses.append({"course": course_name, "code": exc.code})
                except Exception:
                    logger.exception(
                        "course_sync_failed user_id=%s course=%s", self.user_id, course_name
                    )
                    partial = True
                    failed_courses.append({"course": course_name, "code": "course_sync_failed"})
                run.courses_processed += 1
                run.items_changed = changed
                run.items_seen = seen
                run.failed_courses = failed_courses
        self._persist_progress(run)
        for provider_id, membership in memberships.items():
            if provider_id not in provider_course_ids:
                membership.selected = False
                membership.enrollment_status = "INACTIVE"
        self.db.commit()
        return changed, seen, partial, changed_ids

    def _sync_course_isolated(
        self,
        provider_token: str,
        course_id: UUID,
        membership_id: UUID,
        quick: bool = True,
        deadline: float | None = None,
    ) -> tuple[int, int, set[UUID], int, float, int]:
        with SessionLocal() as worker_db:
            course = worker_db.get(Course, course_id)
            membership = worker_db.get(CourseMembership, membership_id)
            if not course or not membership:
                raise ClassroomError("course_unavailable")
            worker_client = ClassroomClient(provider_token, deadline=deadline)
            worker = ClassroomSynchronizer(worker_db, self.user_id)
            try:
                changed, seen, changed_ids = worker._sync_course(
                    worker_client, course, membership, quick=quick, deadline=deadline
                )
                worker_db.commit()
                return (
                    changed,
                    seen,
                    changed_ids,
                    worker_client.request_count,
                    worker_client.request_seconds,
                    worker_client.page_count,
                )
            except Exception:
                worker_db.rollback()
                raise

    def _sync_course(
        self,
        client: ClassroomClient,
        course: Course,
        membership: CourseMembership,
        *,
        quick: bool = True,
        deadline: float | None = None,
    ) -> tuple[int, int, set[UUID]]:
        checkpoint = dict(membership.sync_checkpoint or {})
        course_deadline = (
            min(deadline, perf_counter() + COURSE_DEADLINE)
            if deadline
            else perf_counter() + COURSE_DEADLINE
        )
        incremental = bool(checkpoint)
        max_pages = INCREMENTAL_PAGE_LIMIT if incremental else INITIAL_PAGE_LIMIT
        submissions: dict[str, dict[str, Any]] = {}
        submission_cutoff = _optional_timestamp(checkpoint.get("submissions"))
        newest_submission = submission_cutoff
        try:
            if perf_counter() >= course_deadline:
                raise ClassroomError("quick_sync_deadline", retryable=True)
            path = f"/courses/{course.classroom_course_id}/courseWork/-/studentSubmissions"
            should_fetch_submissions = not (
                quick
                and not any(
                    item.source_type == SourceType.COURSEWORK
                    and (item.provider_metadata or {}).get("state") not in {"CLOSED", "ARCHIVED"}
                    for item in self.db.scalars(
                        select(ClassroomItem).where(ClassroomItem.course_id == course.id)
                    )
                )
            )
            if should_fetch_submissions:
                fields = (
                    "nextPageToken,studentSubmissions("
                    "id,courseWorkId,state,late,updateTime,alternateLink)"
                )
                for page in client.pages(
                    path,
                    "studentSubmissions",
                    {"userId": "me", "fields": fields},
                    max_pages=max_pages,
                ):
                    reached_checkpoint = False
                    for raw in page:
                        updated = _optional_timestamp(raw.get("updateTime"))
                        if submission_cutoff and updated and updated <= submission_cutoff:
                            reached_checkpoint = True
                        if updated and (newest_submission is None or updated > newest_submission):
                            newest_submission = updated
                        key = _text(raw.get("courseWorkId"), 128)
                        if key:
                            submissions[key] = {
                                "id": _text(raw.get("id"), 128),
                                "state": _text(raw.get("state"), 32),
                                "late": bool(raw.get("late", False)),
                                "updateTime": raw.get("updateTime"),
                                "alternateLink": _url(raw.get("alternateLink")),
                            }
                    if reached_checkpoint:
                        break
        except ClassroomError as exc:
            if exc.code == "authorization_revoked":
                raise
        if newest_submission:
            checkpoint["submissions"] = newest_submission.isoformat()

        definitions = (
            (
                SourceType.ANNOUNCEMENT,
                "announcements",
                "announcements",
                "id,text,alternateLink,creationTime,updateTime,state,materials",
            ),
            (
                SourceType.COURSEWORK,
                "courseWork",
                "courseWork",
                "id,title,description,alternateLink,creationTime,updateTime,state,dueDate,dueTime,materials",
            ),
            (
                SourceType.MATERIAL,
                "courseWorkMaterials",
                "courseWorkMaterial",
                "id,title,description,alternateLink,creationTime,updateTime,state,materials",
            ),
        )
        changed = seen = 0
        changed_ids: set[UUID] = set()
        for source_type, path_name, collection, resource_fields in definitions:
            if perf_counter() >= course_deadline:
                raise ClassroomError("quick_sync_deadline", retryable=True)
            key_name = source_type.value
            cutoff = _optional_timestamp(checkpoint.get(key_name))
            newest = cutoff
            existing = {
                item.source_id: item
                for item in self.db.scalars(
                    select(ClassroomItem).where(
                        ClassroomItem.course_id == course.id,
                        ClassroomItem.source_type == source_type,
                    )
                )
            }
            fields = f"nextPageToken,{collection}({resource_fields})"
            path = f"/courses/{course.classroom_course_id}/{path_name}"
            for page in client.pages(
                path,
                collection,
                {"fields": fields, "orderBy": "updateTime desc"},
                max_pages=max_pages,
            ):
                reached_checkpoint = False
                for raw in page:
                    source_id = _text(raw.get("id"), 128)
                    if not source_id:
                        continue
                    updated = _optional_timestamp(raw.get("updateTime"))
                    if cutoff and updated and updated <= cutoff:
                        reached_checkpoint = True
                    if updated and (newest is None or updated > newest):
                        newest = updated
                    item = existing.get(source_id)
                    submission = (
                        submissions.get(source_id) if source_type == SourceType.COURSEWORK else None
                    )
                    digest = _hash({"resource": raw, "submission": submission})
                    if item and item.content_hash == digest:
                        seen += 1
                        continue
                    if not item:
                        item = ClassroomItem(
                            course_id=course.id,
                            source_type=source_type,
                            source_id=source_id,
                        )
                        self.db.add(item)
                    item.title = _text(raw.get("title") or raw.get("text"), 500) or "Untitled"
                    item.body = _text(raw.get("description") or raw.get("text"), 30000) or None
                    item.source_url = _url(raw.get("alternateLink"))
                    item.source_created_at = _timestamp(raw.get("creationTime"))
                    item.source_updated_at = _timestamp(raw.get("updateTime"))
                    item.content_hash = digest
                    item.provider_metadata = {
                        "state": _text(raw.get("state"), 32),
                        "dueDate": raw.get("dueDate"),
                        "dueTime": raw.get("dueTime"),
                        "studentSubmission": submission,
                        "attachments": _attachment_metadata(
                            raw.get("materials"), datetime.now(UTC)
                        ),
                    }
                    self.db.flush()
                    changed_ids.add(item.id)
                    changed += 1
                    seen += 1
                if reached_checkpoint:
                    break
            if newest:
                checkpoint[key_name] = newest.isoformat()
        checkpoint["last_successful_sync_at"] = datetime.now(UTC).isoformat()
        membership.sync_checkpoint = checkpoint
        return changed, seen, changed_ids
