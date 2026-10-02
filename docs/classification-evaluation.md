# Classification evaluation

## Dataset

The reproducible dataset at `backend/tests/fixtures/classification_cases.json` contains 12 synthetic Classroom posts covering:

- general notices;
- section-specific and mismatched-section work;
- lab-group-specific and mismatched-group work;
- assignments, exams, materials, notices, and unknown content;
- relative, explicit, provider-supplied, malformed, and absent deadlines;
- conflicting sections and groups that require review;
- HTML, script-URL text, and prompt-injection-style instructions.

The reference profile is section A, lab group 2, timezone Asia/Dhaka.

## Results

Run:

```powershell
cd backend
python -m scripts.evaluate_classification
```

Results on 2026-09-26:

| Metric | Correct | Accuracy |
|---|---:|---:|
| Event type | 12/12 | 100% |
| Deadline | 12/12 | 100% |
| Target group | 12/12 | 100% |
| Relevance | 12/12 | 100% |

There were no false positives or false negatives in this deliberately bounded synthetic set. These numbers are regression evidence, not a claim of real-world model accuracy.

## Known limitations

- The rule engine recognizes a small English keyword vocabulary and explicit `section`, `sec`, `group`, and `lab group` labels.
- Relative dates are limited to today and tomorrow; explicit text dates support ISO and common day-month-year forms.
- Time-only phrases, recurring schedules, attachments, images, and natural-language dates such as “next Friday” are not interpreted.
- Multiple section or group targets remain visible and are sent to review rather than guessed.
- Ambiguous content may be classified as `other`, and provider metadata takes precedence over conflicting text dates.
- Relevance quality depends on the user having configured the correct section and lab group.

Every corrected classification defect must add a labeled case to the JSON dataset and a corresponding regression assertion before the rule changes.
