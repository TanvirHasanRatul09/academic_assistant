from datetime import UTC, datetime

from app.db.models.entities import EventType, ItemSubtype, SourceType
from app.services.extraction.pipeline import relevance
from app.services.extraction.rules import MAX_TEXT_LENGTH, extract


class Profile:
    section = "a"
    lab_group = "2"


def make(text: str, source_type: SourceType = SourceType.ANNOUNCEMENT):
    return extract(
        title=text,
        body=None,
        source_type=source_type,
        source_created_at=datetime(2026, 9, 25, 10, tzinfo=UTC),
        provider_metadata={},
        timezone_name="Asia/Dhaka",
    )


def test_general_notice_is_relevant_to_everyone() -> None:
    result = make("Important class notice")
    assert result.event_type == EventType.NOTICE
    assert relevance(Profile(), result)


def test_matching_and_different_section_relevance() -> None:
    assert relevance(Profile(), make("Assignment for section A due tomorrow"))
    assert not relevance(Profile(), make("Assignment for section B due tomorrow"))


def test_group_target_and_relative_date_use_user_timezone() -> None:
    result = make("Quiz for lab group 2 tomorrow")
    assert result.event_type == EventType.EXAM
    assert result.item_subtype == ItemSubtype.QUIZ
    assert result.lab_groups == ("2",)
    assert result.due_at == datetime(2026, 9, 26, 17, 59, tzinfo=UTC)


def test_multiple_explicit_sections_are_each_relevant() -> None:
    result = make("Section A and section B exam")
    assert not result.review_required
    assert relevance(Profile(), result)


def test_provider_due_date_has_priority() -> None:
    result = extract(
        title="Homework",
        body=None,
        source_type=SourceType.COURSEWORK,
        source_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        provider_metadata={"dueDate": {"year": 2026, "month": 10, "day": 2}},
        timezone_name="Asia/Dhaka",
    )
    assert result.due_at == datetime(2026, 10, 2, 17, 59, tzinfo=UTC)


def test_input_is_bounded() -> None:
    result = make("x" * (MAX_TEXT_LENGTH + 1000))
    assert result.metadata["input_length"] == MAX_TEXT_LENGTH


class A1Profile:
    section = "Section A"
    lab_group = "A-1"
    academic_level = "Third year"
    program = "CSE"


def test_target_variants_normalize_without_bare_letter_false_positive() -> None:
    assert relevance(A1Profile(), make("Quiz for Sec A and Group A1 tomorrow"))
    assert relevance(A1Profile(), make("Quiz for Section A and lab group A-1 tomorrow"))
    bare = make("Bring a calculator to room A tomorrow")
    assert bare.sections == ()
    assert bare.lab_groups == ()
    assert relevance(A1Profile(), bare)


def test_other_sections_and_groups_are_rejected() -> None:
    assert not relevance(A1Profile(), make("Quiz for Section B tomorrow"))
    assert not relevance(A1Profile(), make("Quiz for Group B1 tomorrow"))
    assert not relevance(A1Profile(), make("Quiz for Group C1 tomorrow"))


def test_year_program_and_conflicting_targets() -> None:
    assert relevance(A1Profile(), make("Exam for year 3, program CSE tomorrow"))
    assert not relevance(A1Profile(), make("Exam for year 1, program EEE tomorrow"))
    conflict = make("Exam for Section A and Group B1 tomorrow")
    assert conflict.review_required
    assert not relevance(A1Profile(), conflict)


def test_named_weekday_lab_final_is_extracted_in_user_timezone() -> None:
    result = extract(
        title="CSE 3208 lab final on Tuesday",
        body=None,
        source_type=SourceType.ANNOUNCEMENT,
        source_created_at=datetime(2026, 9, 27, 10, tzinfo=UTC),
        provider_metadata={},
        timezone_name="Asia/Dhaka",
    )
    assert result.event_type == EventType.EXAM
    assert result.item_subtype == ItemSubtype.LAB_FINAL
    assert result.due_at == datetime(2026, 9, 29, 17, 59, tzinfo=UTC)


def test_classroom_lab_final_short_year_time_and_section_rooms() -> None:
    result = extract(
        title="Lab Final",
        body="""Date: 29-09-26 (Tuesday)
Time: 4:20 pm
Room No:
Section A: 7A03
Section B: 7C06
Section C: 7C07""",
        source_type=SourceType.ANNOUNCEMENT,
        source_created_at=datetime(2026, 9, 4, 10, tzinfo=UTC),
        provider_metadata={},
        timezone_name="Asia/Dhaka",
    )
    assert result.event_type == EventType.EXAM
    assert result.due_at == datetime(2026, 9, 29, 10, 20, tzinfo=UTC)
    assert result.starts_at == result.due_at
    assert result.sections == ()
    assert result.lab_groups == ()
    assert result.metadata["targeting"]["explicit_course_wide"] is True
    assert not result.review_required
    assert relevance(A1Profile(), result)


def test_compact_parenthesized_lab_groups_are_strictly_targeted() -> None:
    own = make("Final Report (A1)", SourceType.COURSEWORK)
    assert own.lab_groups == ("a1",)
    assert relevance(A1Profile(), own)

    for target in ("A2", "B1", "B2", "C1", "C2", "A6", "B8", "C10"):
        result = make(f"Final Report ({target})", SourceType.COURSEWORK)
        assert result.lab_groups == (target.casefold(),)
        assert not relevance(A1Profile(), result)


def test_explicit_all_groups_and_all_sections_are_course_wide() -> None:
    for text in (
        "Final report instructions for all groups",
        "Notice for all sections",
        "Section A, Section B, Section C: common exam room notice",
    ):
        result = make(text)
        assert result.sections == ()
        assert result.lab_groups == ()
        assert result.metadata["targeting"]["explicit_course_wide"] is True
        assert relevance(A1Profile(), result)


def test_partial_target_lists_remain_restricted() -> None:
    result = make("Final Report for A2, B1 and C2", SourceType.COURSEWORK)
    assert result.lab_groups == ("a2", "b1", "c2")
    assert not relevance(A1Profile(), result)
