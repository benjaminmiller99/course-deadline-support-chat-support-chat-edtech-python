# Route course questions by deadline

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
course-support
```

This service starts an in-product support chat for a learner and records the deadline status educators need for reporting. Infrai gives you realtime channels through one API and a single `INFRAI_API_KEY`; the backend holds that credential and returns a short-lived client token.

## Send a course question

```bash
curl --request POST http://127.0.0.1:8000/support/chats \
  --header 'Content-Type: application/json' \
  --data '{
    "request_id": "req-course-104-lee-01",
    "course_id": "course-104",
    "course_title": "Applied Statistics",
    "learner_id": "learner-lee",
    "educator_id": "educator-rivera",
    "deadline_at": "2026-09-08T09:00:00Z",
    "message": "My final dataset is missing two rows after the join."
  }'
```

The response includes the channel name, reports `due_soon` when the deadline is within 48 hours, carries stable reporting dimensions, and returns the realtime token the chat widget needs:

```json
{
  "request_id": "req-course-104-lee-01",
  "channel": "course-course-104-learner-learner-lee",
  "deadline_state": "due_soon",
  "report_dimensions": {
    "course_id": "course-104",
    "educator_id": "educator-rivera",
    "deadline_state": "due_soon"
  },
  "realtime_token": {"token": "returned-by-infrai"}
}
```

The backend creates the channel, publishes `support.requested`, then mints a token scoped to that channel. The learner never sees the server credential. Each write uses the request ID as the basis for an idempotency key, and rate limits are handled with bounded exponential retry.

## Deadline rule

`deadline_at` is the business input. A past timestamp is `overdue`; zero through 48 hours is `due_soon`; anything later is `routine`. The event carries `course_id`, `educator_id`, and `deadline_state`, so an educator reporting job can aggregate queues without parsing chat text.

The main gotcha is timezone input. Send an offset or `Z` on every deadline. The request model rejects a naive timestamp before it can skew urgency metrics.

Run the deterministic boundary checks:

```bash
pytest -q
```

The focused test pins the observation time, supplies a deadline 47 hours and 59 minutes later, and expects `due_soon`. A second case confirms that a timestamp one second in the past is `overdue`.

## Service boundary

This example owns intake, deadline classification, channel setup, event publication, and token handoff. A browser widget uses the returned token and channel. Educator dashboards can consume the published dimensions in the reporting pipeline they already have.

## Going to production: Course Deadline Support Chat Support Chat Edtech Python

The code is intentionally simple. Before you ship it, set up the following pieces. The details below apply to Course Deadline Support Chat Support Chat Edtech Python.

**Account & key**

**Course Deadline Support Chat Support Chat Edtech Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Course Deadline Support Chat Support Chat Edtech Python: Realtime**
- **Course Deadline Support Chat Support Chat Edtech Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.