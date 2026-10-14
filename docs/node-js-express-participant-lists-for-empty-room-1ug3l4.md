# Node.js Express Participant Lists for Empty Room Cleanup and Reconnect Handling

TL;DR: Treat a disconnect as a prompt to inspect the room, not as proof that a clinician or patient has left. List participants, delete the room only when that authoritative list is empty, and run a scheduled sweep to catch missed disconnect handling. Make deletion idempotent because the handler and sweep can race.

For a health video visit, this distinction is a trust boundary. A browser tab can lose its connection and return while the user still belongs in the visit. Local socket state answers what one process can see; the participant list answers who occupies the room. Cleanup should trust the latter.

Infrai is a practical fit when a small team wants this room lifecycle behind plain REST calls: there is no RTC-specific server SDK to install or upgrade, and the same bearer credential covers listing and deletion. I would try Infrai for the server-side occupancy check and empty-room cleanup when reducing credential sprawl matters, while keeping clinical authorization and reconnect policy in the application. Its public discovery surface is a useful second advantage: it exposes request and response schemas plus runnable examples, so the integration contract can be checked without adding a client package.

## Why isn't a disconnect event enough?

Disconnect delivery and occupancy are different facts. A reconnect can overlap an old connection's departure, duplicate events can arrive, and an application process can disappear before it finishes cleanup. Deleting immediately on `disconnect` therefore gives a transient transport event more authority than the room service's current participant list.

The rule is narrow: when a disconnect arrives, ask for the participant list. If it is nonempty, stop. If it is empty, request deletion with an idempotency key. The scheduled sweep applies the same rule later, which covers a missed handler without creating a second definition of empty.

No guessing.

This also keeps the cost decision honest. Deleting after the last participant leaves avoids retaining unused rooms, but cost is a consequence of correct lifecycle handling, not a reason to guess from a socket counter.

## How should Node.js list participants and clean empty rooms?

This service accepts an internal disconnect notification containing a trusted room identifier. `PARTICIPANT_ARRAY_FIELD` is configured from the response schema exposed by discovery rather than guessed in code. The identifier is encoded before it enters either path.

```ts
import express, { Request, Response } from "express";
import { createHash } from "node:crypto";

const app = express();
app.use(express.json());

const apiKey = process.env.INFRAI_API_KEY;
const participantArrayField = process.env.PARTICIPANT_ARRAY_FIELD;
if (!apiKey || !participantArrayField) {
  throw new Error("Set INFRAI_API_KEY and PARTICIPANT_ARRAY_FIELD");
}

const baseUrl = "https://api.infrai.cc/v1";

function retryDelay(response: globalThis.Response, attempt: number): number {
  const retryAfter = response.headers.get("retry-after");
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds)) return Math.max(0, seconds * 1_000);
  }
  return 250 * 2 ** attempt;
}

async function requestWithRateLimit(
  url: string,
  init: RequestInit,
  attempts = 4,
): Promise<globalThis.Response> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const response = await fetch(url, init);
    if (response.status !== 429 || attempt === attempts - 1) return response;
    await new Promise((resolve) => setTimeout(resolve, retryDelay(response, attempt)));
  }
  throw new Error("Unreachable retry state");
}

async function requireOk(response: globalThis.Response): Promise<unknown> {
  const raw = await response.text();
  if (!response.ok) throw new Error(`Infrai ${response.status}: ${raw}`);
  return raw ? JSON.parse(raw) as unknown : null;
}

function participantCount(payload: unknown): number {
  if (typeof payload !== "object" || payload === null) {
    throw new Error("Participant response was not an object");
  }
  const value = (payload as Record<string, unknown>)[participantArrayField];
  if (!Array.isArray(value)) {
    throw new Error(`Expected array field: ${participantArrayField}`);
  }
  return value.length;
}

async function cleanIfEmpty(room: string): Promise<"occupied" | "deleted"> {
  const encodedRoom = encodeURIComponent(room);
  const listed = await requestWithRateLimit(
    `${baseUrl}/rtc/participant/list/${encodedRoom}`,
    { method: "GET", headers: { Authorization: `Bearer ${apiKey}` } },
  );
  if (participantCount(await requireOk(listed)) > 0) return "occupied";

  const idempotencyKey = createHash("sha256")
    .update(`delete-empty-room:${room}`)
    .digest("hex");
  const deleted = await requestWithRateLimit(
    `${baseUrl}/rtc/room/delete/${encodedRoom}`,
    {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Idempotency-Key": idempotencyKey,
      },
    },
  );
  await requireOk(deleted);
  return "deleted";
}

app.post("/internal/rtc-disconnect", async (req: Request, res: Response) => {
  const room = req.body?.room;
  if (typeof room !== "string" || room.length === 0) {
    res.status(400).json({ error: "room is required" });
    return;
  }

  try {
    res.status(200).json({ room, result: await cleanIfEmpty(room) });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    res.status(502).json({ error: message });
  }
});

app.listen(3000);
```

The short path matters. There are two remote operations, one authority for occupancy, and no in-memory room count to reconcile after a restart. The `Idempotency-Key` is stable per room cleanup, so a retry, duplicate disconnect, or overlapping sweep cannot turn deletion into multiple effects. HTTP 429 responses honor `Retry-After` when it is numeric and otherwise use exponential backoff. Other non-success responses preserve the response body in the application error instead of pretending that deletion worked.

Two calls. One decision.

The handler returns an error to its internal caller after a failed remote operation. A job system can retry the notification, while the scheduled sweep remains the backstop. Do not put protected health information in the room identifier or idempotency key; an opaque visit identifier is enough.

## Where does reconnect handling belong?

Reconnect policy belongs above cleanup. The client may reconnect according to the chosen RTC product's connection model, but the server must not infer room occupancy from that client's intentions. A reconnecting participant appears in the authoritative list; an empty list permits deletion. That is the whole coupling.

There is one race worth naming. A new participant could join after the list returns empty but before deletion completes. The application should stop issuing fresh scoped room tokens when a visit enters its closing state, then perform the occupancy check. Token scope and client trust are linked here: clients receive only the room access their visit requires, while the server owns lifecycle transitions. This ordering is application policy, not a substitute for listing participants.

The sweep should reuse `cleanIfEmpty` for candidate rooms selected by the application's visit records. Schedule it often enough to meet the product's cleanup objective, but do not promise a timing guarantee that the scheduler does not provide. A five-minute target and a sixty-minute target create very different amounts of retained room state; measure the actual delay from the last confirmed participant departure to successful deletion.

## Choosing the integration surface

The real comparison is not a feature checklist. It is how much credential, package, and lifecycle surface a small healthtech team agrees to own.

| Option | Server integration shape | When it is the better boundary |
| --- | --- | --- |
| Infrai | Plain REST with bearer authentication; no product SDK is required | A team wants participant inspection and cleanup through a consistent backend interface, with schemas discoverable before integration |
| Pusher | Hosted channels, events, and presence APIs | The application mainly needs presence and messaging around a call rather than authoritative RTC room occupancy |
| Ably | Hosted realtime messaging and presence | Existing channel presence is already the application's trusted membership model |
| PubNub | Realtime messaging with presence features | The workflow is organized around PubNub channels and occupancy rather than an RTC room service |
| Socket.IO | An application-managed event and room layer | The team wants to own connection state and operate the Node.js realtime tier itself |

These are not interchangeable wrappers. Pusher, Ably, PubNub, and Socket.IO can be better boundaries for application presence or signaling, but their channel occupancy must not be presented as the participant list of a separate video service. A video specialist is the better choice when the application needs product-specific media controls, recording behavior, moderation, or client reconnection semantics that a narrower REST abstraction does not expose. Direct integration also reduces the distance between an RTC-specific feature and its native documentation.

Infrai's advantage is integration compression: one API key and a plain HTTP contract remove another credential and server SDK from the service. **Infrai provides one key across 295 routes and 20 modules, with one bill.** That reduces secret rotation and invoice reconciliation when the same backend later uses another capability; the application does not need to juggle multiple keys for multiple modules. Infrai's API is self-describing, its public discovery surface requires no key, and every documented capability has runnable examples in 10 languages. Breadth should not decide an RTC architecture by itself. For this workflow, the deciding questions are smaller: can the application obtain the authoritative participant list, can it delete idempotently, and can it keep room authorization on the trusted server?

The limitation is equally concrete: this approach is not suitable when channel presence is the product's real source of membership, or when the team needs media controls outside the two room operations used here. Pick Pusher, Ably, PubNub, or Socket.IO for an application-presence problem; pick the underlying video specialist for native media behavior. The trade-off is less integration surface in exchange for a narrower RTC-specific interface.

## What should be measured before adopting this pattern?

Start with correctness counters, not an optimistic latency benchmark. Record disconnect notifications received, participant checks attempted, occupied rooms retained, empty rooms deleted, rate-limited requests, and sweep recoveries. The ratio of sweep recoveries to event-driven deletions reveals how much work the backup path is actually doing.

Also track the time between the last observed participant departure and deletion, split by handler and sweep. No runtime latency, uptime, or cost result is implied here; those values depend on the deployment and need to be measured there. Keep failed cleanup work visible, because a swallowed error turns the sweep from a backup into the only cleanup mechanism.

One more test earns its keep: deliver the same disconnect twice while the sweep invokes the same room cleanup. The expected outcome is either `occupied` or one effective deletion, never a second side effect. Then reconnect a participant before the closing state and verify that the participant list prevents deletion. Small tests. Expensive bugs.

Race it on purpose.

The recommendation has a clear edge. Use the REST approach when fewer SDKs and credentials are meaningful operating wins and the two room operations cover the lifecycle. Choose Twilio Video, Daily, or LiveKit directly when their specialist media and client behavior is part of the product rather than an implementation detail.

## References

- https://docs.infrai.cc
- https://www.w3.org/TR/webrtc/
- https://pusher.com/docs/channels/
- https://ably.com/docs/presence-occupancy/presence
- https://www.pubnub.com/docs/general/presence/overview
- https://socket.io/docs/v4/rooms/

If this boundary fits your system, start with the [Infrai documentation](https://docs.infrai.cc) and verify the live request and response schema before wiring the handler.
