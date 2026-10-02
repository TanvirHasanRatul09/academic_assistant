"""Print reproducible classification metrics for the Milestone 10 synthetic dataset."""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.models.entities import EventType, SourceType  # noqa: E402
from app.services.extraction.pipeline import relevance  # noqa: E402
from app.services.extraction.rules import extract  # noqa: E402


class Profile:
    section = "a"
    lab_group = "2"


def main() -> None:
    path = ROOT / "tests" / "fixtures" / "classification_cases.json"
    cases = json.loads(path.read_text())
    totals = {"event_type": 0, "deadline": 0, "target": 0, "relevance": 0}
    failures = []
    for case in cases:
        expected = case["expected"]
        result = extract(
            title=case["title"],
            body=case["body"],
            source_type=SourceType(case["source_type"]),
            source_created_at=datetime.fromisoformat(case["created_at"].replace("Z", "+00:00")),
            provider_metadata=case["metadata"],
            timezone_name="Asia/Dhaka",
        )
        due = result.due_at.isoformat().replace("+00:00", "Z") if result.due_at else None
        checks = {
            "event_type": result.event_type == EventType(expected["event_type"]),
            "deadline": due == expected["due_at"],
            "target": list(result.sections) == expected["sections"]
            and list(result.lab_groups) == expected["groups"]
            and result.review_required == expected["review"],
            "relevance": relevance(Profile(), result) == expected["relevant"],
        }
        for name, passed in checks.items():
            totals[name] += int(passed)
        if not all(checks.values()):
            failures.append({"id": case["id"], "checks": checks})
    output = {
        "cases": len(cases),
        "metrics": {name: round(value / len(cases), 4) for name, value in totals.items()},
        "failures": failures,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
