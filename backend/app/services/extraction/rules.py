import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.db.models.entities import EventType, ItemSubtype, SourceType

RULE_VERSION = "rules-v6-item-subtype"
MAX_TEXT_LENGTH = 30_000
TARGET_VALUE_REGEX = r"[a-z0-9]+(?:-[a-z0-9]+)?"
SECTION_PATTERN = re.compile(rf"\b(?:section|sec)\s*[-:#]?\s*({TARGET_VALUE_REGEX})\b", re.I)
GROUP_PATTERN = re.compile(rf"\b(?:lab\s*)?group\s*[-:#]?\s*({TARGET_VALUE_REGEX})\b", re.I)
COMPACT_GROUP_PATTERN = re.compile(
    r"(?<![a-z0-9])\(?([a-z])\s*-?\s*([0-9]{1,2})\)?(?![a-z0-9])", re.I
)
PAREN_SECTION_PATTERN = re.compile(r"\(([a-z])\)", re.I)
COURSE_WIDE_PATTERN = re.compile(
    r"\b(?:all\s+(?:sections|groups|students)|everyone|entire\s+course|course[- ]wide)\b",
    re.I,
)
LEVEL_PATTERN = re.compile(
    r"\b(?:academic\s*)?(?:year|level)\s*[-:#]?\s*(first|second|third|fourth|[1-9])\b", re.I
)
PROGRAM_PATTERN = re.compile(r"\b(?:department|program)\s*[-:#]?\s*([a-z][a-z0-9]{1,15})\b", re.I)
ISO_DATE_PATTERN = re.compile(r"\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b")
DMY_DATE_PATTERN = re.compile(r"\b([0-2]?\d|3[01])[/.-](0?\d|1[0-2])[/.-](\d{2}|20\d{2})\b")
CLOCK_PATTERN = re.compile(
    r"\b(?:time\s*[:\-]?\s*)?(1[0-2]|0?[1-9])[:.]([0-5]\d)\s*(am|pm)\b", re.I
)
LEVEL_WORDS = {"first": "1", "second": "2", "third": "3", "fourth": "4"}
WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def normalize_section(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"^(?:section|sec)\s*[-:#]?\s*", "", value.strip(), flags=re.I)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    return cleaned or None


def normalize_lab_group(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"^(?:lab\s*)?group\s*[-:#]?\s*", "", value.strip(), flags=re.I)
    cleaned = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    return cleaned or None


def normalize_level(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().casefold()
    match = re.search(r"\b(first|second|third|fourth|[1-9])\b", cleaned)
    return LEVEL_WORDS.get(match[1], match[1]) if match else re.sub(r"\s+", " ", cleaned)


def normalize_program(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"^(?:department|program)\s*[-:#]?\s*", "", value.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]", "", cleaned.casefold()) or None


def extract_target_values(text: str) -> tuple[tuple[str, ...], tuple[str, ...], bool]:
    course_wide = bool(COURSE_WIDE_PATTERN.search(text))
    sections = {value for raw in SECTION_PATTERN.findall(text) if (value := normalize_section(raw))}
    sections.update(
        value for raw in PAREN_SECTION_PATTERN.findall(text) if (value := normalize_section(raw))
    )
    groups = {value for raw in GROUP_PATTERN.findall(text) if (value := normalize_lab_group(raw))}
    groups.update(
        value
        for raw in ("".join(raw) for raw in COMPACT_GROUP_PATTERN.findall(text))
        if (value := normalize_lab_group(raw))
    )
    course_wide = course_wide or sections.issuperset({"a", "b", "c"})
    if course_wide:
        return (), (), True
    return tuple(sorted(sections)), tuple(sorted(groups)), False


@dataclass(frozen=True)
class Extraction:
    event_type: EventType
    item_subtype: ItemSubtype
    starts_at: datetime | None
    due_at: datetime | None
    priority: int
    action_required: bool
    confidence: float
    sections: tuple[str, ...]
    lab_groups: tuple[str, ...]
    academic_levels: tuple[str, ...]
    programs: tuple[str, ...]
    review_required: bool
    metadata: dict[str, Any]


def _provider_due(metadata: dict[str, Any], timezone: ZoneInfo) -> datetime | None:
    value = metadata.get("dueDate")
    if not isinstance(value, dict):
        return None
    try:
        raw_time = metadata.get("dueTime")
        due_time = raw_time if isinstance(raw_time, dict) else {}
        local = datetime(
            int(value["year"]),
            int(value["month"]),
            int(value["day"]),
            int(due_time.get("hours", 23)),
            int(due_time.get("minutes", 59)),
            tzinfo=timezone,
        )
        return local.astimezone(ZoneInfo("UTC"))
    except (KeyError, TypeError, ValueError):
        return None


def _text_due(text: str, created_at: datetime, timezone: ZoneInfo) -> datetime | None:
    local_created = created_at.astimezone(timezone)
    lowered = text.casefold()
    date_value = None
    weekday = next(
        (value for name, value in WEEKDAYS.items() if re.search(rf"\b{name}\b", lowered)),
        None,
    )
    match = ISO_DATE_PATTERN.search(text)
    if match:
        try:
            date_value = datetime(int(match[1]), int(match[2]), int(match[3])).date()
        except ValueError:
            return None
    else:
        match = DMY_DATE_PATTERN.search(text)
        if match:
            try:
                year = int(match[3])
                year = 2000 + year if year < 100 else year
                date_value = datetime(year, int(match[2]), int(match[1])).date()
            except ValueError:
                return None
        elif "tomorrow" in lowered:
            date_value = local_created.date() + timedelta(days=1)
        elif "today" in lowered:
            date_value = local_created.date()
        elif weekday is not None:
            date_value = local_created.date() + timedelta(
                days=(weekday - local_created.weekday()) % 7
            )
    if not date_value:
        return None
    clock = CLOCK_PATTERN.search(text)
    event_time = time(23, 59)
    if clock:
        hour = int(clock[1]) % 12 + (12 if clock[3].casefold() == "pm" else 0)
        event_time = time(hour, int(clock[2]))
    return datetime.combine(date_value, event_time, timezone).astimezone(ZoneInfo("UTC"))


def classify_item_subtype(text: str, source_type: SourceType) -> ItemSubtype:
    lowered = text.casefold()
    if re.search(r"\blab\s+final\b", lowered):
        return ItemSubtype.LAB_FINAL
    if re.search(r"\b(?:theory\s+)?final(?:\s+(?:exam|test))?\b", lowered):
        return ItemSubtype.THEORY_FINAL
    if re.search(r"\bquiz(?:zes)?(?:\s*[-#]?\s*\d+)?\b", lowered):
        return ItemSubtype.QUIZ
    if re.search(r"\b(?:midterm|mid[- ]?term|mid\s+exam)\b", lowered):
        return ItemSubtype.MIDTERM
    if re.search(r"\b(?:online|assessment)\s*[-#]?\s*\d*\b", lowered):
        return ItemSubtype.ONLINE_ASSESSMENT
    if re.search(r"\b(?:marks?|results?|grades?|scores?)\b", lowered):
        return ItemSubtype.MARKS_OR_RESULT
    if re.search(r"\b(?:lab\s+(?:task|assignment|work)|lab\s*[-#]?\s*\d+)\b", lowered):
        return ItemSubtype.LAB_TASK
    if re.search(r"\b(?:assignment|homework|project)\b", lowered):
        return ItemSubtype.ASSIGNMENT
    if source_type == SourceType.MATERIAL:
        return ItemSubtype.MATERIAL
    if re.search(r"\b(?:class|lecture|session)\b", lowered):
        return ItemSubtype.CLASS
    if source_type == SourceType.ANNOUNCEMENT:
        return ItemSubtype.ANNOUNCEMENT
    return ItemSubtype.OTHER


def extract(
    *,
    title: str,
    body: str | None,
    source_type: SourceType,
    source_created_at: datetime,
    provider_metadata: dict[str, Any],
    timezone_name: str,
) -> Extraction:
    text = f"{title}\n{body or ''}"[:MAX_TEXT_LENGTH]
    lowered = text.casefold()
    timezone = ZoneInfo(timezone_name)
    item_subtype = classify_item_subtype(text, source_type)
    if any(word in lowered for word in ("exam", "midterm", "final test", "lab final", "quiz")):
        event_type = EventType.EXAM
    elif any(word in lowered for word in ("assignment", "homework", "project", "submit")):
        event_type = EventType.ASSIGNMENT
    elif source_type == SourceType.MATERIAL or any(
        word in lowered for word in ("lecture slide", "reading material", "handout")
    ):
        event_type = EventType.MATERIAL
    elif source_type == SourceType.ANNOUNCEMENT or any(
        word in lowered for word in ("notice", "cancelled", "rescheduled")
    ):
        event_type = EventType.NOTICE
    else:
        event_type = EventType.OTHER
    due_at = _provider_due(provider_metadata, timezone) or _text_due(
        text, source_created_at, timezone
    )
    action_required = event_type in {EventType.ASSIGNMENT, EventType.EXAM} or any(
        word in lowered for word in ("submit", "complete", "attend", "bring")
    )
    priority = 3 if event_type == EventType.EXAM else 2 if action_required else 1
    if any(word in lowered for word in ("urgent", "important", "tomorrow")):
        priority = 3
    sections, groups, explicit_course_wide = extract_target_values(text)
    levels = tuple(
        sorted({value for raw in LEVEL_PATTERN.findall(text) if (value := normalize_level(raw))})
    )
    programs = tuple(
        sorted(
            {value for raw in PROGRAM_PATTERN.findall(text) if (value := normalize_program(raw))}
        )
    )
    group_prefixes = {
        re.match(r"[a-z]+", value).group() for value in groups if re.match(r"[a-z]+", value)
    }
    conflict = (
        len(levels) > 1
        or len(programs) > 1
        or bool(sections and group_prefixes and not group_prefixes.intersection(sections))
    )
    confidence = 0.95 if provider_metadata.get("dueDate") else 0.8
    if event_type == EventType.OTHER:
        confidence -= 0.25
    if conflict:
        confidence -= 0.2
    metadata = {
        "rule_version": RULE_VERSION,
        "item_subtype": item_subtype.value,
        "input_length": len(text),
        "targeting": {
            "sections": sections,
            "lab_groups": groups,
            "academic_levels": levels,
            "programs": programs,
            "ambiguous": conflict,
            "explicit_course_wide": explicit_course_wide,
        },
    }
    return Extraction(
        event_type,
        item_subtype,
        due_at if event_type == EventType.EXAM else None,
        due_at,
        priority,
        action_required,
        max(0.0, min(1.0, confidence)),
        sections,
        groups,
        levels,
        programs,
        conflict,
        metadata,
    )
