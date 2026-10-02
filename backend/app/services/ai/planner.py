import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.db.models.entities import ItemSubtype
from app.services.ai.tools import DateRangeArgs, ExamArgs, SearchArgs, UpcomingArgs

ToolName = Literal[
    "get_tasks_by_date", "get_upcoming_deadlines", "get_exams", "search_academic_content"
]
QueryIntent = Literal[
    "schedule",
    "completion_status",
    "mark_as_completed",
    "mark_as_incomplete",
    "deadline",
    "question_pattern",
    "syllabus",
    "instructions",
    "marks_or_result",
    "attachments",
    "teacher_announcement",
    "general_information",
]
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
INFORMATIONAL_TERMS = (
    "question pattern",
    "pattern",
    "marks",
    "instructions",
    "detail",
    "syllabus",
    "room",
    "marks",
    "format",
    "topics",
    "announcement",
    "notice",
    "details",
    "instructions",
    "complete",
    "completed",
    "done",
)
SEARCH_STOP_WORDS = {
    "what",
    "when",
    "where",
    "which",
    "who",
    "how",
    "is",
    "are",
    "was",
    "were",
    "the",
    "a",
    "an",
    "of",
    "for",
    "to",
    "in",
    "on",
    "about",
    "my",
    "me",
    "this",
    "that",
    "it",
    "exam",
    "task",
    "classroom",
    "please",
    "tell",
    "show",
    "find",
    "search",
    "did",
    "teacher",
    "sir",
    "mam",
    "say",
    "said",
    "post",
    "posted",
    "upload",
    "uploaded",
    "available",
    "any",
    "there",
    "these",
    "those",
    "exams",
    "tasks",
    "marked",
    "complete",
    "completed",
    "done",
}

EVENT_TERMS = (
    "lab final",
    "class cancellation",
    "cancelled",
    "rescheduled",
    "midterm",
    "final",
    "exam",
    "quiz",
    "mid",
)


@dataclass(frozen=True)
class QueryPlan:
    tool: ToolName
    args: DateRangeArgs | UpcomingArgs | ExamArgs | SearchArgs
    intent: QueryIntent = "general_information"
    item_subtype: ItemSubtype | None = None
    include_past: bool = False


def _item_subtype(message: str) -> ItemSubtype | None:
    normalized = " ".join(message.casefold().split())
    patterns = (
        (r"\blab\s+final\b", ItemSubtype.LAB_FINAL),
        (r"\btheory\s+final\b", ItemSubtype.THEORY_FINAL),
        (r"\bquiz(?:zes)?\b", ItemSubtype.QUIZ),
        (r"\b(?:midterm|mid[- ]?term|mid\s+exam)\b", ItemSubtype.MIDTERM),
        (r"\b(?:online|assessment)\s*[-#]?\s*\d*\b", ItemSubtype.ONLINE_ASSESSMENT),
        (r"\b(?:assignment|homework|project)\b", ItemSubtype.ASSIGNMENT),
        (r"\blab\s+(?:task|assignment|work|\d+)\b", ItemSubtype.LAB_TASK),
        (r"\b(?:marks|results?|grades?|scores?)\b", ItemSubtype.MARKS_OR_RESULT),
        (r"\b(?:announcement|notice)\b", ItemSubtype.ANNOUNCEMENT),
        (r"\b(?:material|slides?|handout)\b", ItemSubtype.MATERIAL),
    )
    return next((subtype for pattern, subtype in patterns if re.search(pattern, normalized)), None)


def _intent(message: str) -> QueryIntent:
    normalized = message.casefold()
    if (
        re.search(
            r"\bmark\b.{0,120}\b(?:incomplete|incompleted|not\s+complete|not\s+completed|open)\b",
            normalized,
        )
        or re.search(r"\b(?:reopen|undo\s+completion)\b", normalized)
    ):
        return "mark_as_incomplete"
    if re.search(r"\bmark\b.{0,120}\b(?:complete|completed|done)\b", normalized):
        return "mark_as_completed"
    if any(
        term in normalized
        for term in ("marked complete", "marked completed", "is complete", "is completed", "done")
    ):
        return "completion_status"
    if any(term in normalized for term in ("marks", "result", "grade", "score")):
        return "marks_or_result"
    if any(term in normalized for term in ("question pattern", "format", "structure")):
        return "question_pattern"
    if any(term in normalized for term in ("syllabus", "topics", "chapters")):
        return "syllabus"
    if any(term in normalized for term in ("instruction", "guideline", "requirement")):
        return "instructions"
    if any(term in normalized for term in ("attachment", "file", "pdf")):
        return "attachments"
    if any(term in normalized for term in ("deadline", "due")):
        return "deadline"
    if any(
        term in normalized
        for term in ("when", "time", "date", "schedule", "where", "venue", "today", "tomorrow")
    ):
        return "schedule"
    if any(
        term in normalized for term in ("teacher say", "teacher said", "announcement", "notice")
    ):
        return "teacher_announcement"
    return "general_information"


def _search_terms(message: str) -> list[str]:
    normalized = " ".join(message.casefold().split())
    terms: list[str] = []
    course = re.search(r"\b[a-z]{2,6}\s*[- ]?\s*\d{3,5}\b", normalized)
    if course:
        terms.append(re.sub(r"\s+", " ", course.group()).upper())
    for term in EVENT_TERMS:
        if term in normalized and not any(term in existing for existing in terms):
            terms.append(term)
    return terms[:4]


def _course_terms(terms: list[str]) -> list[str]:
    return [term for term in terms if re.fullmatch(r"[A-Z]{2,6}\s*[- ]?\s*\d{3,5}", term)]


def _day_of_month(message: str, today: date) -> date | None:
    match = re.search(r"\b(?:on|of)\s+(?:the\s+)?([0-3]?\d)(?:st|nd|rd|th)?\b", message)
    if not match:
        return None
    day = int(match[1])
    year, month = today.year, today.month
    if day < today.day:
        month += 1
        if month == 13:
            month = 1
            year += 1
    if day < 1 or day > calendar.monthrange(year, month)[1]:
        return None
    return date(year, month, day)


def _content_query(message: str) -> str:
    normalized = message.casefold()
    intent_aliases = {
        "pattern": ("pattern", "format", "structure", "question type"),
        "syllabus": ("syllabus", "topics", "chapters", "contents", "coverage"),
        "marks": ("marks", "score", "points", "weight"),
        "room": ("room", "venue", "location", "where"),
        "instructions": ("instructions", "instruction", "guidelines", "rules", "requirements"),
    }
    intent_terms = [
        canonical
        for canonical, aliases in intent_aliases.items()
        if any(alias in normalized for alias in aliases)
    ]
    words = re.findall(r"[a-z0-9*+-]+", normalized)
    meaningful = [word for word in words if word not in SEARCH_STOP_WORDS and len(word) >= 3]
    query = " ".join(dict.fromkeys([*meaningful, *intent_terms]))
    return query[:120] if len(query) >= 2 else "academic notice"


def plan_query(
    message: str, today: date, context: str = "", resolved_course_terms: list[str] | None = None
) -> QueryPlan:
    normalized = " ".join(message.lower().split())
    direct_item_subtype = _item_subtype(normalized)
    direct_intent = _intent(normalized)
    # A short course/alias reply usually answers a clarification and should
    # continue the previous academic question instead of starting a generic
    # search for the course code alone.
    is_course_reply = bool(
        context
        and resolved_course_terms
        and len(normalized.split()) <= 4
        and direct_intent == "general_information"
        and direct_item_subtype is None
    )
    intent = _intent(context) if is_course_reply else direct_intent
    contextual_follow_up = bool(
        context
        and intent in ("completion_status", "mark_as_completed", "mark_as_incomplete")
        and re.search(r"\b(?:it|that|this|them|those)\b", normalized)
    )
    item_subtype = direct_item_subtype
    if item_subtype is None and (is_course_reply or intent in ("completion_status", "mark_as_completed", "mark_as_incomplete")):
        item_subtype = _item_subtype(context)
    include_past = intent in {"completion_status", "marks_or_result", "mark_as_completed", "mark_as_incomplete"}
    terms = _search_terms(normalized)
    context_terms = _search_terms(context)
    course_terms = resolved_course_terms or _course_terms(terms) or _course_terms(context_terms)
    if contextual_follow_up:
        contextual_terms = [
            *course_terms,
            *(term for term in context_terms if term not in course_terms),
        ][:4]
        if "tomorrow" in context:
            target = today + timedelta(days=1)
            return QueryPlan(
                "get_tasks_by_date",
                DateRangeArgs(
                    start_date=target,
                    end_date=target,
                    terms=contextual_terms,
                    item_subtype=item_subtype,
                ),
                intent,
                item_subtype,
            )
        if "today" in context:
            return QueryPlan(
                "get_tasks_by_date",
                DateRangeArgs(
                    start_date=today,
                    end_date=today,
                    terms=contextual_terms,
                    item_subtype=item_subtype,
                ),
                intent,
                item_subtype,
            )
        if any(term in context for term in ("this week", "next 7 days", "next week")):
            return QueryPlan(
                "get_tasks_by_date",
                DateRangeArgs(
                    start_date=today,
                    end_date=today + timedelta(days=7),
                    terms=contextual_terms,
                    item_subtype=item_subtype,
                ),
                intent,
                item_subtype,
            )
    if intent in ("completion_status", "mark_as_completed", "mark_as_incomplete") and item_subtype is not None:
        return QueryPlan(
            "search_academic_content",
            SearchArgs(
                query=item_subtype.value.replace("_", " "),
                course_terms=course_terms,
                item_subtype=item_subtype,
            ),
            intent,
            item_subtype,
            include_past,
        )
    if intent in ("completion_status", "mark_as_completed", "mark_as_incomplete") and any(
        term in (context if contextual_follow_up else normalized)
        for term in ("exam", "test", "final", "midterm", "mid")
    ):
        return QueryPlan(
            "get_exams",
            ExamArgs(terms=course_terms, item_subtype=item_subtype, include_past=True),
            intent,
            item_subtype,
            True,
        )
    if contextual_follow_up:
        return QueryPlan(
            "search_academic_content",
            SearchArgs(
                query=_content_query(context),
                course_terms=course_terms,
                item_subtype=item_subtype,
            ),
            intent,
            item_subtype,
            include_past,
        )
    if any(term in normalized for term in INFORMATIONAL_TERMS):
        return QueryPlan(
            "search_academic_content",
            SearchArgs(
                query=_content_query(normalized),
                course_terms=course_terms,
                item_subtype=item_subtype,
            ),
            intent,
            item_subtype,
            include_past,
        )
    if "tomorrow" in normalized:
        target = today + timedelta(days=1)
        return QueryPlan(
            "get_tasks_by_date",
            DateRangeArgs(
                start_date=target, end_date=target, terms=terms, item_subtype=item_subtype
            ),
            intent,
            item_subtype,
        )
    if "today" in normalized:
        return QueryPlan(
            "get_tasks_by_date",
            DateRangeArgs(start_date=today, end_date=today, terms=terms, item_subtype=item_subtype),
            intent,
            item_subtype,
        )
    weekday = next(
        (value for name, value in WEEKDAYS.items() if re.search(rf"\b{name}\b", normalized)), None
    )
    if weekday is not None:
        target = today + timedelta(days=(weekday - today.weekday()) % 7)
        return QueryPlan(
            "get_tasks_by_date",
            DateRangeArgs(
                start_date=target, end_date=target, terms=terms, item_subtype=item_subtype
            ),
            intent,
            item_subtype,
        )
    numbered_day = _day_of_month(normalized, today)
    if numbered_day is not None:
        return QueryPlan(
            "get_tasks_by_date",
            DateRangeArgs(
                start_date=numbered_day,
                end_date=numbered_day,
                terms=_course_terms(terms),
                item_subtype=item_subtype,
            ),
            intent,
            item_subtype,
        )
    if any(term in normalized for term in ("this week", "next 7 days", "next week")):
        return QueryPlan(
            "get_tasks_by_date",
            DateRangeArgs(
                start_date=today,
                end_date=today + timedelta(days=7),
                terms=terms,
                item_subtype=item_subtype,
            ),
            intent,
            item_subtype,
        )
    if any(term in normalized for term in ("exam", "quiz", "test", "final", "midterm", "mid")):
        return QueryPlan(
            "get_exams",
            ExamArgs(
                terms=_course_terms(terms), item_subtype=item_subtype, include_past=include_past
            ),
            intent,
            item_subtype,
            include_past,
        )
    if any(term in normalized for term in ("deadline", "due", "upcoming")):
        return QueryPlan(
            "get_upcoming_deadlines",
            UpcomingArgs(terms=_course_terms(terms), item_subtype=item_subtype),
            intent,
            item_subtype,
        )
    return QueryPlan(
        "search_academic_content",
        SearchArgs(
            query=_content_query(normalized), course_terms=course_terms, item_subtype=item_subtype
        ),
        intent,
        item_subtype,
        include_past,
    )
