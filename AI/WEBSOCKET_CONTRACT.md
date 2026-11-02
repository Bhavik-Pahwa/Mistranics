# WebSocket and durable event handoff

One WebSocket infrastructure is mounted when AI_ENABLED=true. The prior backend had none. REST/database records remain authoritative.

Connect to /api/v1/ws, then send this first JSON frame within five seconds:

```json
{"authorization":"Bearer YOUR_API_TOKEN"}
```

A configured read token is required even if trusted-local REST reads are otherwise anonymous. The token is sent in the first frame instead of a URL query parameter. Invalid/missing authentication closes with code 1008. Subsequent client text frames may be used as keepalives; there are no socket-side state mutations.

## Event envelope

```json
{
  "event_id":"OUTBOX_UUID",
  "event_type":"troubleshooting.response",
  "machine_id":"motor_001",
  "occurred_at":"2026-11-02T12:30:00+00:00",
  "payload":{"session_id":"SESSION_UUID","message_id":"MESSAGE_UUID","state":"completed"}
}
```

event_id is stable across publication retry; deduplicate it. Timestamps are timezone-aware. The stream includes authorized project-wide machine events, matching the prototype's shared role model.

| Event type | Payload |
|---|---|
| anomaly.detected | incident_id, decision_id, state=ACTIVE, parameter (correlation key) |
| incident.updated | incident_id, state; decision_id/parameter when a finding changes state |
| incident.resolved | incident_id, state=RESOLVED |
| troubleshooting.started | session_id, incident_id (nullable for operator-initiated session) |
| troubleshooting.processing | session_id, message_id |
| troubleshooting.response | session_id, message_id, state=completed/error; error text on failure |
| troubleshooting.step_updated | session_id, step_id (nullable), feedback_id, provenance=operator_reported |
| troubleshooting.resolution_updated | incident_id, state (RECOVERING/RESOLVED) |

Repeated ACTIVE findings retain normalized observations and counts but do not produce another anomaly.detected notification. Recovery persistence and source evidence remain available through incident APIs. An old out-of-correlation historical anomaly may emit incident.updated with state=CLOSED, without pretending the current condition changed.

## Persistence and retry

Each event is inserted into ai_event_outbox in the same transaction as its state change. An asynchronous publication pump, independent of provider latency, reads up to 100 undelivered records at a time. Failed publication leaves them pending. Delivery is at least once to the in-process hub; a crash after publishing but before marking delivered can produce duplicate event IDs.

Outbox delivered means published to the hub, not acknowledged by a frontend. When no clients are connected, events may be marked delivered; reconnect always requires an API state refresh. Multiple application workers are not supported by this in-process prototype hub; run one backend process. With AI disabled, outbox records may remain queued until the hub is enabled.

Each client queue is bounded to 64 events. A slow client receives {"event_type":"resync_required"} and closes with code 1013; this control frame has no outbox identity and instructs immediate reconnect/API resynchronization.

On reconnect, retrieve session state via GET /api/v1/troubleshooting/sessions/{id}, page messages/steps/feedback, GET the evidence collection, and GET the linked incident. There is no replay cursor, socket-based source of truth, token streaming, or durable client delivery acknowledgment.
