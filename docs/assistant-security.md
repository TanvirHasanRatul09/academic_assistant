# Milestone 9: Assistant security and privacy

## Data boundary

The assistant can read only records returned by four backend-owned tools:

- `get_tasks_by_date` (maximum 31-day range, 50 results)
- `get_upcoming_deadlines` (maximum 60 days, 50 results)
- `get_exams` (maximum 180 days, 50 results)
- `search_academic_content` (120-character query, 25 results)

Every query receives the authenticated user ID from the backend. The request and model cannot provide or override that ID. Queries also require a selected course membership for that same user. Tools are read-only.

## Model boundary

A deterministic backend planner selects the tool and validates its arguments. Gemini never chooses a tool or authorization scope. If `GEMINI_API_KEY` is configured, Gemini receives only the question and a bounded projection of authorized query results: title, course, event type, dates, priority, completion state, and a short content excerpt. It does not receive user IDs, email addresses, OAuth tokens, secrets, configuration, source URLs, or records belonging to another user.

Classroom text and user questions are treated as untrusted content. The model is explicitly instructed not to follow embedded instructions. Its response must match the structured `{ "answer": string }` schema and is validated before display. The provider request has an eight-second timeout. Any timeout, provider error, malformed response, or missing key silently falls back to the deterministic local formatter.

## Retention and limits

The server does not save conversation text. The browser keeps at most 12 messages in component memory and clears them when the page is reloaded or **Clear chat** is selected. The API accepts at most six history messages, but history is not sent to Gemini in this first release.

The endpoint requires the authenticated session and CSRF token. It permits 20 requests per IP per minute and 100 successful requests per authenticated user per UTC day. Audit events record only tool name, answer mode, and result count—not prompts or academic content.

## Offline behavior

When the network request fails, the frontend uses only the signed-in user's IndexedDB dashboard snapshot. It supports today, tomorrow, week, deadlines, exams, and text search. The answer displays the snapshot's last successful sync time. If no snapshot or matching record exists, it says that data is unavailable instead of guessing.

## Configuration

`GEMINI_API_KEY` is optional. Without it, the assistant remains fully usable through deterministic database answers. `GEMINI_MODEL` defaults to `gemini-2.5-flash-lite`. Keep the API key only in `backend/.env` or the deployment secret store; never commit it.
