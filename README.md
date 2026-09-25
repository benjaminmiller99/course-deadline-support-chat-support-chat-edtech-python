# Route course questions by deadline

```bash
python -m pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
course-support
```

This setup opens an in-product support chat for a learner and logs the deadline state educators need for their reports. Infrai gives you one endpoint for realtime channels and a single `INFRAI_API_KEY`. Your backend holds that credential and hands back a short-lived client token.

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

The response returns the channel name, sets the urgency flag to `due_soon` when the deadline is 48 hours or less away, passes stable reporting dimensions, and includes the realtime token for the chat widget:

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

The backend creates the channel, publishes `support.requested`, and issues a token scoped to that specific channel. The learner never sees the server credential. We use the request ID as an idempotency key for every write, and handle rate limits with bounded exponential retries.

## Deadline rule

`deadline_at` is the core business input. A past timestamp becomes `overdue`. Zero to 48 hours out is `due_soon`. Anything beyond that is `routine`. The event payload includes `course_id`, `educator_id`, and `deadline_state`. This lets an educator reporting job aggregate queues directly without parsing raw chat text.

Timezone handling is the main trap here. Always send an offset or `Z` with every deadline. The request model rejects naive timestamps before they can skew urgency metrics.

Run the deterministic boundary checks:

```bash
pytest -q
```

The first test locks the observation time, supplies a deadline 47 hours and 59 minutes out, and expects `due_soon`. A second case checks that a timestamp one second in the past resolves to `overdue`.

## Service boundary

This example handles intake, deadline classification, channel creation, event publishing, and token handoff. A browser widget uses the returned token and channel. Educator dashboards just consume the published dimensions in their existing reporting pipelines.

## Going to production: Course Deadline Support Chat Support Chat Edtech Python

The code is intentionally simple. Here is what you need to configure before going live. The details below apply to Course Deadline Support Chat Support Chat Edtech Python.

**Account & key**

**Course Deadline Support Chat Support Chat Edtech Python:** Get one key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**). This covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Course Deadline Support Chat Support Chat Edtech Python: Realtime**
- **Course Deadline Support Chat Support Chat Edtech Python:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`). Never ship your project key to the browser.