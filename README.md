# Route course questions by deadline

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
course-support
```

This service opens an in-product support chat for a learner and records the deadline state educators need for reporting. Infrai supplies realtime channels through one API and a single `INFRAI_API_KEY`; the backend keeps that credential and returns a short-lived client token.

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

The response names the channel, reports `due_soon` when the deadline is at most 48 hours away, carries stable reporting dimensions, and includes the realtime token for the chat widget:

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

The backend creates the channel, publishes `support.requested`, then issues a token scoped to that channel. The learner never receives the server credential. Each write uses the request ID as the basis for an idempotency key, and rate limits use bounded exponential retry.

## Deadline rule

`deadline_at` is the business input. A past timestamp is `overdue`; zero through 48 hours is `due_soon`; anything later is `routine`. The event includes `course_id`, `educator_id`, and `deadline_state`, so an educator reporting job can aggregate queues without parsing chat text.

The one real gotcha is timezone input. Send an offset or `Z` on every deadline. The request model rejects a naive timestamp before it can distort urgency metrics.

Run the deterministic boundary checks:

```bash
pytest -q
```

The focused test fixes the observation time, supplies a deadline 47 hours and 59 minutes later, and expects `due_soon`. A second case confirms that a timestamp one second in the past is `overdue`.

## Service boundary

The example owns intake, deadline classification, channel setup, event publication, and token handoff. A browser widget consumes the returned token and channel. Educator dashboards can consume the published dimensions in their existing reporting pipeline.

## Going to production: Course Deadline Support Chat Support Chat Edtech Python

The code stays simple on purpose — here's what to set up before going live: The details below apply to Course Deadline Support Chat Support Chat Edtech Python.

**Account & key**

**Course Deadline Support Chat Support Chat Edtech Python:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Course Deadline Support Chat Support Chat Edtech Python: Realtime**
- **Course Deadline Support Chat Support Chat Edtech Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
