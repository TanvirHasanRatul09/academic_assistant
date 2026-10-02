# i4 assistant correctness trace

Date: 2026-09-27

## CSE 3208 lab-final failure path

1. Classroom synchronization preserved the source title/body and source URL correctly.
2. Extraction did not recognize `lab final` as an exam and did not convert named weekdays such as `Tuesday` into a timezone-aware event date.
3. The assistant planner did not resolve weekday names and could not combine course code, event phrase, and date constraints.
4. Consequently, the deterministic query selected either an unfiltered date search, a broad exam search, or text search with no usable event date. Gemini could not repair the missing deterministic record.

## Resolution

- `lab final`, quiz, mid/midterm, final, exam, cancellations, and rescheduling wording are recognized by deterministic extraction/planning.
- Named weekdays resolve to the next matching local calendar day using the user's timezone.
- Date, deadline, and exam tools accept bounded course/event terms and require each term to match the title, body, or course.
- Factual date/exam/deadline answers remain local and deterministic even when Gemini is configured. Gemini is limited to explanatory free-text searches over records already returned by the database.
- Local answers render dates in the user's timezone and include course and event details.
- Sources now include title, course, event type, start/due date, and Classroom URL; responses include last successful sync time.
- Empty results distinguish no successful synchronization from no matching synchronized record and never treat Gemini failure as evidence that an event does not exist.

## Verification

A synthetic SQLite regression creates an active selected CSE 3208 course, a relevant Tuesday lab-final exam, a successful sync record, and a Classroom source URL. The real `answer_question` path returns a deterministic local answer, the exam source, the CSE 3208 course, and the date. Backend suite, focused Ruff, frontend tests, TypeScript, ESLint, and production build pass.
