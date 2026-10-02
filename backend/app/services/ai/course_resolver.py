import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.entities import Course, CourseMembership

_CODE = re.compile(r"\b([A-Z]{2,6})\s*[- ]?\s*(\d{2,5})\b", re.IGNORECASE)
_WORDS = re.compile(r"[A-Za-z]+")
_METADATA_WORDS = {
    "course",
    "fall",
    "spring",
    "summer",
    "winter",
    "theory",
    "lab",
    "laboratory",
    "section",
    "semester",
    "session",
}
_REFERENCE_TERMS = re.compile(
    r"\b(this|that|these|those|it|its|their|same)\b|\bwhat\s+about\b", re.IGNORECASE
)
_COURSE_NUMBER_ALIASES = {
    "3202": {"cn lab", "computer network lab", "computer networks lab"},
    "3208": {"ai", "artificial intelligence"},
    "3214": {"os lab", "operating system lab", "operating systems lab"},
}
_SEMESTER_PREFIXES = {"fall", "spring", "summer", "winter"}


@dataclass(frozen=True)
class CourseResolution:
    course_names: list[str]
    ambiguous_names: list[str]
    matched_from_context: bool = False

    @property
    def ambiguous(self) -> bool:
        return bool(self.ambiguous_names)


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _course_code(name: str) -> re.Match[str] | None:
    # Semester labels such as "Fall 2025" have the same shape as a course
    # code. Never let them replace the real code in names like
    # "CSE 3208 - Fall 2025".
    return next(
        (
            match
            for match in _CODE.finditer(name)
            if match.group(1).casefold() not in _SEMESTER_PREFIXES
        ),
        None,
    )


def _aliases(name: str, configured: list[str] | None = None) -> set[str]:
    aliases = {_normalize(name)}
    aliases.update(_normalize(alias) for alias in (configured or []) if alias)
    code = _course_code(name)
    if code:
        prefix, number = code.groups()
        aliases.update({f"{prefix.casefold()} {number}", f"{prefix.casefold()}{number}"})
        aliases.update(_COURSE_NUMBER_ALIASES.get(number, set()))
    code_prefix = code.group(1).casefold() if code else None
    aliases.update(
        token.casefold()
        for token in re.findall(r"\b[A-Z]{2,6}\b", name)
        if token.casefold() not in _METADATA_WORDS and token.casefold() != code_prefix
    )
    words = [
        word.casefold()
        for word in _WORDS.findall(_CODE.sub(" ", name))
        if word.casefold() not in _METADATA_WORDS
    ]
    if words:
        aliases.add(" ".join(words))
        if len(words) >= 2:
            aliases.add("".join(word[0] for word in words))
    return {alias for alias in aliases if len(alias) >= 2}


def _matches(course_names: list[str], text: str) -> list[str]:
    normalized = f" {_normalize(text)} "
    scored: list[tuple[str, int]] = []
    for name in course_names:
        scores = [len(alias.split()) for alias in _aliases(name) if f" {alias} " in normalized]
        if scores:
            scored.append((name, max(scores)))
    if not scored:
        return []
    strongest = max(score for _, score in scored)
    return [name for name, score in scored if score == strongest]


def resolve_course_names(
    course_names: list[str], message: str, context: str = ""
) -> CourseResolution:
    current = _matches(course_names, message)
    if len(current) == 1:
        return CourseResolution(current, [])
    if len(current) > 1:
        return CourseResolution([], current)
    if context and (_REFERENCE_TERMS.search(message) or len(_normalize(message).split()) <= 5):
        previous = _matches(course_names, context)
        if len(previous) == 1:
            return CourseResolution(previous, [], matched_from_context=True)
        if len(previous) > 1:
            return CourseResolution([], previous, matched_from_context=True)
    return CourseResolution([], [])


def resolve_course_intent(
    db: Session, user_id: UUID, message: str, context: str = ""
) -> CourseResolution:
    courses = list(
        db.scalars(
            select(Course)
            .join(
                CourseMembership,
                (CourseMembership.course_id == Course.id)
                & (CourseMembership.user_id == user_id)
                & CourseMembership.selected.is_(True)
                & (CourseMembership.enrollment_status == "ACTIVE"),
            )
            .where(Course.status == "ACTIVE")
            .order_by(Course.name)
        )
    )
    names = [course.name for course in courses]
    normalized_message = f" {_normalize(message)} "
    configured_matches = [
        course.name
        for course in courses
        if any(
            f" {_normalize(str(alias))} " in normalized_message
            for alias in (course.provider_metadata or {}).get("aliases", [])
            if isinstance(alias, str) and len(_normalize(alias)) >= 2
        )
    ]
    if len(configured_matches) == 1:
        return CourseResolution(configured_matches, [])
    if len(configured_matches) > 1:
        return CourseResolution([], configured_matches)
    return resolve_course_names(names, message, context)
