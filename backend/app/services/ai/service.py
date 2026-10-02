import re
import dataclasses
from datetime import UTC, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models.entities import PersonalTask, User, UserProfile, UserTask
from app.schemas.assistant import (
    AssistantAction,
    AssistantItem,
    AssistantMessage,
    AssistantOutput,
    AssistantSource,
)
from app.services.ai.course_resolver import resolve_course_intent
from app.services.ai.gemini import GeminiError, GeminiStatus, summarize_with_gemini
from app.services.ai.personal_tasks import personal_task_records
from app.services.ai.planner import QueryPlan, plan_query
from app.services.ai.tools import (
    AcademicRecord,
    DateRangeArgs,
    ExamArgs,
    SearchArgs,
    UpcomingArgs,
    get_exams,
    get_tasks_by_date,
    get_upcoming_deadlines,
    last_successful_sync,
    search_academic_content,
)
from app.services.extraction.rules import (
    extract_target_values,
    normalize_lab_group,
    normalize_section,
)


def _execute(db: Session, user: User, plan: QueryPlan) -> list[AcademicRecord]:
    if plan.tool == "get_tasks_by_date":
        assert isinstance(plan.args, DateRangeArgs)
        return get_tasks_by_date(db, user.id, user.timezone, plan.args)
    if plan.tool == "get_upcoming_deadlines":
        assert isinstance(plan.args, UpcomingArgs)
        return get_upcoming_deadlines(db, user.id, plan.args)
    if plan.tool == "get_exams":
        assert isinstance(plan.args, ExamArgs)
        return get_exams(db, user.id, plan.args)
    assert isinstance(plan.args, SearchArgs)
    return search_academic_content(db, user.id, plan.args)


def _display_title(title: str) -> str:
    lines = [line.strip(" -\t") for line in title.splitlines() if line.strip()]
    return lines[0][:180] if lines else "Classroom item"

def _local_answer(
    records: list[AcademicRecord], tool: str, timezone_name: str, synced_at: datetime | None
) -> str:
    if not records:
        descriptions = {
            "get_tasks_by_date": "tasks for that date range",
            "get_upcoming_deadlines": "upcoming deadlines",
            "get_exams": "upcoming exams",
            "search_academic_content": "matching academic content",
        }
        if synced_at is None:
            return (
                "No successful Classroom synchronization is available yet. "
                "Synchronize Classroom, then ask again."
            )
        synced = synced_at.astimezone(ZoneInfo(timezone_name)).strftime("%b %d, %Y %I:%M %p %Z")
        return (
            f"I could not find {descriptions[tool]} in your synchronized Classroom data. "
            f"The last successful sync was {synced}."
        )
    timezone = ZoneInfo(timezone_name)
    label = "result" if len(records) == 1 else "results"
    lines = [f"I found {len(records)} {label} in your synchronized data:"]
    if tool == "search_academic_content":
        for index, record in enumerate(records[:5], start=1):
            heading = _display_title(record.title)
            raw = (record.body or "").strip()
            content_lines = [line.strip(" -\t") for line in raw.splitlines() if line.strip()]
            details = (
                content_lines[1:]
                if content_lines and content_lines[0] == heading
                else content_lines
            )
            lines.append(f"{index}. Course: {record.course_name}")
            state = " (completed)" if record.completed else " (not completed)"
            lines.append(f"   Item title: {heading}{state}")
            if record.personal:
                lines.append("   Source: Added by you")
            for detail in details[:10]:
                lines.append(f"   Relevant details: {detail[:300]}")
        if len(records) > 5:
            lines.append(f"…and {len(records) - 5} more matching items.")
        return "\n".join(lines)
    for index, record in enumerate(records[:10], start=1):
        when = record.due_at or record.starts_at
        timing = (
            f" — {when.astimezone(timezone).strftime('%a, %b %d, %Y %I:%M %p %Z')}" if when else ""
        )
        state = " (completed)" if record.completed else ""
        lines.append(f"{index}. Course: {record.course_name}")
        lines.append(f"   Item title: {_display_title(record.title)}{state}")
        if record.personal:
            lines.append("   Source: Added by you")
        lines.append(f"   Date/time:{timing.removeprefix(' —') if timing else ' Not specified'}")
    if len(records) > 10:
        lines.append(f"…and {len(records) - 10} more matching items.")
    return "\n".join(lines)


def _outside_profile_target(db: Session, user: User, question: str) -> str | None:
    sections, groups, course_wide = extract_target_values(question)
    if course_wide or not (sections or groups):
        return None
    profile = db.get(UserProfile, user.id)
    profile_section = normalize_section(profile.section if profile else None)
    profile_group = normalize_lab_group(profile.lab_group if profile else None)
    if groups and profile_group not in groups:
        requested = ", ".join(value.upper() for value in groups)
        current = profile_group.upper() if profile_group else "not configured"
        return (
            f"That information is targeted to lab group {requested}. "
            f"Your profile lab group is {current}, so it is not available "
            "in your assistant results."
        )
    if sections and profile_section not in sections:
        requested = ", ".join(value.upper() for value in sections)
        current = profile_section.upper() if profile_section else "not configured"
        return (
            f"That information is targeted to section {requested}. "
            f"Your profile section is {current}, so it is not available in your assistant results."
        )
    return None


def answer_question(
    db: Session,
    user: User,
    question: str,
    settings: Settings,
    history: list[AssistantMessage] | None = None,
) -> AssistantOutput:
    today = datetime.now(UTC).astimezone(ZoneInfo(user.timezone)).date()
    # Use the latest substantive user question as context. Repeated commands
    # such as "mark it as incomplete" do not identify an academic item, so
    # skip them and retain the earlier course/item question they refer to.
    user_messages = [
        message.content for message in history or [] if message.role == "user"
    ]
    context = user_messages[-1] if user_messages else ""
    for candidate in reversed(user_messages):
        normalized_candidate = " ".join(candidate.casefold().split())
        context_only_action = (
            len(normalized_candidate.split()) <= 12
            and re.search(r"\b(?:mark|reopen|undo)\b", normalized_candidate)
            and re.search(r"\b(?:it|that|this|them|those|same)\b", normalized_candidate)
        )
        if not context_only_action:
            context = candidate
            break
    resolution = resolve_course_intent(db, user.id, question, context)
    plan = plan_query(
        question,
        today,
        context=context,
        resolved_course_terms=resolution.course_names,
    )
    synced_at = last_successful_sync(db, user.id)
    if resolution.ambiguous:
        choices = ", ".join(resolution.ambiguous_names)
        return AssistantOutput(
            answer=f"Which course do you mean: {choices}?",
            mode="local",
            gemini_status="configured" if settings.gemini_api_key else "not_configured",
            tool=plan.tool,
            sources=[],
            last_sync_at=synced_at,
            data_available=False,
            answer_status="ambiguous_course",
            intent=plan.intent,
        )
    boundary_answer = _outside_profile_target(db, user, question)
    if boundary_answer:
        return AssistantOutput(
            answer=boundary_answer,
            mode="local",
            gemini_status="configured" if settings.gemini_api_key else "not_configured",
            tool=plan.tool,
            sources=[],
            last_sync_at=synced_at,
            data_available=False,
            answer_status="no_exact_match",
            intent=plan.intent,
        )
    personal_records = personal_task_records(db, user, plan) if db is not None else []
    records = [*_execute(db, user, plan), *personal_records]
    completion_intent = plan.intent == "completion_status"
    mark_as_completed_intent = plan.intent == "mark_as_completed"
    mark_as_incomplete_intent = plan.intent == "mark_as_incomplete"
    mutation_intent = mark_as_completed_intent or mark_as_incomplete_intent
    if completion_intent or mutation_intent:
        informational_titles = (
            "question pattern",
            "question format",
            "syllabus",
            "guideline",
            "instructions",
        )
        records = [
            record
            for record in records
            if not any(term in record.title.casefold() for term in informational_titles)
        ]
    records.sort(
        key=lambda item: (
            0
            if plan.item_subtype
            and plan.item_subtype.value.replace("_", " ") in item.title.casefold()
            else 1,
            0
            if (mark_as_completed_intent and not item.completed)
            or (mark_as_incomplete_intent and item.completed)
            else 1,
            item.due_at or item.starts_at or datetime.max.replace(tzinfo=UTC),
            -item.priority,
        )
    )
    records = records[:25]
    if mutation_intent and len(records) > 1:
        choices = ", ".join(
            f'"{_display_title(record.title)}" in {record.course_name}' for record in records[:5]
        )
        target_state = "completed" if mark_as_completed_intent else "incomplete"
        answer = (
            f"I found multiple matching items: {choices}. "
            f"Tell me the exact item title so I can mark only the intended one as {target_state}."
        )
    elif (completion_intent or mutation_intent) and records:
        record = records[0]
        display_title = _display_title(record.title)
        if mutation_intent:
            desired_state = mark_as_completed_intent
            updated = record.completed == desired_state
            if not updated and record.task_id and db is not None:
                task = db.get(UserTask, record.task_id)
                if task and task.user_id == user.id:
                    task.completed = desired_state
                    db.commit()
                    records[0] = dataclasses.replace(record, completed=desired_state)
                    updated = True
            elif not updated and record.personal_task_id and db is not None:
                task = db.get(PersonalTask, record.personal_task_id)
                if task and task.user_id == user.id:
                    task.completed = desired_state
                    db.commit()
                    records[0] = dataclasses.replace(record, completed=desired_state)
                    updated = True
            if record.completed == desired_state:
                state = "completed" if desired_state else "incomplete"
                answer = f"{display_title} in {record.course_name} was already marked {state}."
            elif updated:
                state = "completed" if desired_state else "incomplete"
                answer = f"I marked {display_title} in {record.course_name} as {state}."
            else:
                answer = (
                    f"I found {display_title} in {record.course_name}, but could not update it. "
                    "Please refresh and try again."
                )
        else:
            state = "Yes" if record.completed else "No"
            status = "completed" if record.completed else "not marked completed"
            when = record.due_at or record.starts_at
            timing = (
                when.astimezone(ZoneInfo(user.timezone)).strftime("%a, %b %d, %Y %I:%M %p %Z")
                if when
                else "date not specified"
            )
            answer = (
                f"{state} — {display_title} in {record.course_name} is {status}. Date/time: {timing}."
            )
    elif not records and plan.item_subtype and resolution.course_names:
        label = plan.item_subtype.value.replace("_", " ")
        answer = (
            f"I could not find a synchronized {resolution.course_names[0]} item identified as "
            f"{label}. I will not substitute a different assessment."
        )
    else:
        answer = _local_answer(records, plan.tool, user.timezone, synced_at)
    mode: Literal["gemini", "local"] = "local"
    gemini_status: GeminiStatus = "configured" if settings.gemini_api_key else "not_configured"
    if (
        records
        and settings.gemini_api_key
        and plan.tool == "search_academic_content"
        and plan.intent not in {"completion_status", "marks_or_result", "mark_as_completed", "mark_as_incomplete"}
    ):
        try:
            answer = summarize_with_gemini(
                settings.gemini_api_key, settings.gemini_model, question, records
            )
            mode = "gemini"
            gemini_status = "reachable"
        except GeminiError as error:
            gemini_status = error.status
    attachment_intent = any(
        term in question.casefold() for term in ("marks", "mark sheet", "result", "score", "grade")
    )
    if attachment_intent:
        attachment_notes: list[str] = []
        for item in records[:25]:
            if any(attachment.is_pdf for attachment in item.attachments):
                continue
            if item.attachments:
                attachment_notes.append(
                    f"No PDF was attached for {item.title}; an alternative attachment is available."
                )
            else:
                attachment_notes.append(
                    f"No marks document was attached for {item.title}; "
                    "the Classroom post is available."
                )
        if attachment_notes:
            answer = f"{answer}\n\n" + "\n".join(attachment_notes)

    def actions_for(item: AcademicRecord) -> list[AssistantAction]:
        if not attachment_intent:
            return []
        pdfs = [attachment for attachment in item.attachments if attachment.is_pdf]
        if pdfs:
            return [
                AssistantAction(label="Open marks PDF", url=attachment.url, kind="pdf")
                for attachment in pdfs[:5]
            ]
        if item.attachments:
            attachment = item.attachments[0]
            return [
                AssistantAction(
                    label=f"Open {attachment.title}", url=attachment.url, kind="attachment"
                )
            ]
        if item.source_url:
            return [
                AssistantAction(label="Open Classroom post", url=item.source_url, kind="classroom")
            ]
        return []

    return AssistantOutput(
        answer=answer,
        mode=mode,
        gemini_status=gemini_status,
        tool=plan.tool,
        sources=[
            AssistantSource(
                title=item.title,
                course_name=item.course_name,
                source_url=item.source_url,
                event_type=item.event_type,
                item_subtype=item.item_subtype,
                completed=item.completed,
                starts_at=item.starts_at,
                due_at=item.due_at,
                actions=actions_for(item),
            )
            for item in records[:25]
        ],
        last_sync_at=synced_at,
        data_available=bool(records),
        answer_status=(
            "exact_match"
            if len(records) == 1
            else "multiple_matches"
            if records
            else "no_exact_match"
        ),
        intent=plan.intent,
        item=(
            AssistantItem(
                title=_display_title(records[0].title),
                course_name=records[0].course_name,
                item_subtype=records[0].item_subtype,
                completed=records[0].completed,
                starts_at=records[0].starts_at,
                due_at=records[0].due_at,
                source_kind="manual" if records[0].personal else "classroom",
                source_url=records[0].source_url,
            )
            if len(records) == 1
            else None
        ),
    )
