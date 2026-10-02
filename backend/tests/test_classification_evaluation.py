import json
from datetime import datetime
from pathlib import Path

import pytest

from app.db.models.entities import EventType, SourceType
from app.services.extraction.pipeline import relevance
from app.services.extraction.rules import extract

CASES = json.loads((Path(__file__).parent / "fixtures" / "classification_cases.json").read_text())


class EvaluationProfile:
    section = "a"
    lab_group = "2"


def evaluate(case: dict):
    result = extract(
        title=case["title"],
        body=case["body"],
        source_type=SourceType(case["source_type"]),
        source_created_at=datetime.fromisoformat(case["created_at"].replace("Z", "+00:00")),
        provider_metadata=case["metadata"],
        timezone_name="Asia/Dhaka",
    )
    expected = case["expected"]
    due = result.due_at.isoformat().replace("+00:00", "Z") if result.due_at else None
    return {
        "event_type": result.event_type == EventType(expected["event_type"]),
        "deadline": due == expected["due_at"],
        "target": list(result.sections) == expected["sections"]
        and list(result.lab_groups) == expected["groups"]
        and result.review_required == expected["review"],
        "relevance": relevance(EvaluationProfile(), result) == expected["relevant"],
    }


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_synthetic_classification_case(case: dict) -> None:
    scores = evaluate(case)
    assert all(scores.values()), scores


def test_synthetic_evaluation_thresholds() -> None:
    results = [evaluate(case) for case in CASES]
    metrics = {name: sum(row[name] for row in results) / len(results) for name in results[0]}
    assert metrics == {"event_type": 1.0, "deadline": 1.0, "target": 1.0, "relevance": 1.0}
