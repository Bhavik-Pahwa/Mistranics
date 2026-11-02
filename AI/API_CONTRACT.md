# Applied AI and incident API contract

Mounted in the existing FastAPI backend when AI_ENABLED=true (incident/limit reads also when ML_ENABLED=true). Base prefix /api/v1. Existing backend routes and IDs are reused. JSON request bodies reject unknown fields and nonfinite numbers.

Authentication follows backend roles: read endpoints require Bearer API_TOKEN when configured; mutations require Bearer OPERATOR_TOKEN. Internal detector submissions still use INTERNAL_TOKEN. These roles do not imply each other's permissions. Authorization is a shared prototype service role, not per-user/tenant authorization. WebSocket always requires a configured read token.

Errors retain the backend {"detail":...} format: 401 auth, 404 missing/cross-machine reference, 409 identity/state conflict, 422 invalid schema/document, 503 provider or database unavailable. Background message errors are returned as persisted message state, not a silently successful answer.

## Session creation and manual selection

POST /troubleshooting/sessions — 201:

```json
{
  "machine_id":"motor_001",
  "incident_id":null,
  "document_id":"motor-service-manual",
  "document_version":"revision-A"
}
```

machine_id required. Optional incident must exist and belong to the machine. document_id and document_version must both be supplied or both omitted; selected manual must already be indexed for this machine. A session linked to an incident is unique; a repeated start returns that existing session. Newly detected classical incidents automatically create a session when AI is enabled, without guessing a manual version.

Session object: id, asset_id, incident_id (nullable), document_id/document_version (nullable), state (ready/pending/processing/error), created_at. No session content is generated until a message is submitted.

PATCH /troubleshooting/sessions/{session_id}/manual uses the same body, with the session's exact unchanged machine_id and incident_id. It may select an indexed document/version or clear both fields. Changing selection while a message is pending/processing returns 409. Earlier evidence snapshots and instructions retain their original versions.

GET /troubleshooting/sessions?machine_id=...&limit=100&offset=0 returns a pagination object containing session records.

GET /troubleshooting/sessions/{session_id}?limit=100&offset=0 returns the Session plus independently paginated messages, steps and feedback collections, and incident (when linked). limit defaults to 100, allowed 1..1000; offset defaults to 0, allowed 0..1000000. Each collection uses {"items":[],"limit":100,"offset":0,"next_offset":null}. Follow next_offset to recover all persisted state.

## Message acceptance and retry

POST /troubleshooting/sessions/{session_id}/messages — 202:

```json
{"request_id":"operator-turn-001","text":"Why is pressure increasing, and what does the manual say to check?"}
```

request_id is a nonempty identifier (max 200, no whitespace); text length 1..8000. Identity is session plus request_id. Identical redelivery returns the same record. Changed text under that identity returns 409. Only one pending/processing message per session is accepted. Reposting an identical errored request explicitly requeues it; a successful response is not regenerated.

Message object:
- id, session_id, request_id, user_text.
- state: pending, processing, completed, error.
- attempts: processing attempts, including explicit retry/expired-lease recovery.
- response: structured object or null.
- error: controlled text or null.
- processing_at (nullable) and created_at.

The worker claims persisted messages, stores processing state and performs provider calls independently of classical detection. A process crash can reclaim processing work after a lease of three provider timeouts plus thirty seconds. Expired jobs may be processed again; response/steps commit atomically.

A completed response contains:
- session_id; response_type=TROUBLESHOOTING or INSUFFICIENT_EVIDENCE.
- condition_summary: server-rendered authoritative observations/configuration, with freshness caveat where needed.
- machine_context: selected context types, machine registry/configuration, reference IDs, limitations and whichever sources were relevant: latest_reading, recent_history, approved_limits, incidents, operator_reports, telemetry_stale/mqtt_connected.
- possible_causes: cause (hypothesis), supporting_evidence and contradicting_evidence reference arrays, confidence LOW or MEDIUM (not a calibrated probability).
- instructions: title, description, source_quote, source, requires_technician=true, kind diagnostic_check/corrective_action.
- missing_information and safety_warnings arrays.
- sources: {chunk_id,document_id,version,page} objects.

Every instruction description must equal source_quote and be a verbatim substring of its retrieved passage. Every source must have actually been retrieved for the request. Free generated prose cannot add numerical specifications; numbers in quoted source text remain documentation evidence and do not become approved configuration. Actual readings and approved bounds are served from authoritative structured context. Hypotheses require valid supporting reference IDs and never constitute verified failure. Condition summaries override model paraphrases to avoid replacing observed values with model assertions.

Context is bounded and selective: latest readings, up to fifty observations covering recent sixty-second history when needed, up to ten incidents, eight prior exchanges, twenty reports, and up to six retrieved passages. Exact values/counts are prototype bounds, not throughput guarantees. Stale or future-dated telemetry and MQTT disconnection cannot be described as a current-condition confirmation. Follow direct reading/incident APIs for more.

## Feedback, steps and evidence

POST /troubleshooting/sessions/{session_id}/feedback — 201:

```json
{"kind":"step_completed","step_id":"STEP_UUID","text":"Operator reports the inspection step was completed"}
```

kind: step_completed, step_not_completed, issue_persists, improved, observation, maintenance. Step kinds require step_id. Any supplied step must belong to the session. text length 1..4000. The returned Feedback has id, session_id, incident_id, step_id, kind, text, provenance=operator_reported and created_at.

Step records contain id, session_id, message_id, instruction and state=recommended/step_completed/step_not_completed. Feedback can update the reported step state; it never resolves an incident, verifies a repair, or updates detector configuration. Feedback posts represent distinct reports and are not automatically deduplicated.

GET /troubleshooting/sessions/{session_id}/evidence?limit=100&offset=0 returns Evidence objects: id, message_id, chunk_id, snapshot. Snapshot preserves chunk_id/document_id/version/page/section/text/manufacturer/machine_model. Evidence is saved before generation, including failed attempts; it is not fabricated from LLM citations.

## PDF upload and retrieval metadata

POST /documents — multipart/form-data, 201:
- document_id, version, machine_id: nonempty identifiers without whitespace, up to 200 characters; manufacturer/machine_model: nonempty display strings up to 200 characters.
- file: PDF content, 1 byte..15 MiB; maximum AI_MAX_PDF_PAGES (default 100).

Returns {"document": DOCUMENT, "duplicate": false}. DOCUMENT includes id, document_id, version, asset_id, manufacturer, machine_model, sha256, embedding_model and created_at. Same document ID/version/content/applicability is idempotent; changed identity contents conflict with 409. Ingestion never overwrites an existing manual version.

Registry manufacturer/model values, where configured, must agree. Machine ID applicability is mandatory even when registry manufacturer/model metadata is unavailable. Scanned pages require explicitly enabled Tesseract OCR; missing OCR returns 422. Embedding-provider failure returns 503 and creates no partial successful document. Extraction and embedding are bounded; upload does not acquire a telemetry row write lock.

GET /documents?machine_id=...&limit=100&offset=0 returns indexed documents and metadata. Consumers select the exact document_id/version; versions are not interchangeable. There is no document/limit approval endpoint or automatic numerical limit extraction. Retrieval is internal to the message worker and strictly filtered by selected machine/document/version and current configured manufacturer/model applicability.

## Incidents and approved configuration

GET /assets/{asset_id}/approved-limits returns {machine_id,limits,available,authority:"reviewed_configuration",applicability:...}. Limits are the approved records in the active reviewed file, not LLM-extracted numbers. Review the recorded mode/unit/time-basis applicability; this read does not claim all records apply to the current observation.

GET /assets/{asset_id}/incidents?limit=100&offset=0 returns existing Alert records with incident_key and condition metadata. GET /incidents/{incident_id}?limit=100&offset=0 adds a paginated observations collection of normalized AnomalyEvent records.

The existing Alert shape remains id, asset_id, decision_id, incident_key, created_at, status, severity, acknowledged_at, resolved_at, metadata. metadata.condition_state is ACTIVE/RECOVERING/RESOLVED/CLOSED for classical incidents. status remains active/acknowledged/resolved for compatibility. metadata also records first/last detected timestamps, observation count, detector contributions, parameters, source-value trend and recovery policy/count. Severity preserves the latest chronological manufacturer limit category where available; no score-derived severity is generated.

Observation: id, result_id, incident_id, finding_key, parameter, observed_at, evidence (detector, finding, window_id). Exact detector result and decision history remain available through the existing backend routes. Repeated observations are retained while state-change notifications are deduplicated by semantics.

POST /incidents/{incident_id}/close accepts {"reason":"Reviewed recovery"} and requires condition_state=RESOLVED. It changes condition_state to CLOSED and records an operator lifecycle event. Existing /alerts/{id}/acknowledge remains the acknowledgment route. Existing /alerts/{id}/resolve refuses force-resolution of classical parameter incidents; recovery evidence owns that transition.

Correlation/grouping/hysteresis defaults and rationale are in ML/IMPLEMENTATION.md. Historical anomalies outside a newer incident's correlation range are preserved in a separate closed historical record; they cannot close/replace the newer active incident. Late evidence within a resolved condition's observation timeline cannot reopen it as a new current condition.

## Consumer guidance

Use accepted message/session IDs to correlate notifications. WebSocket events do not carry full responses or replace API retrieval. On reconnect or resync_required, GET current session/messages/evidence/steps/feedback and incident state. Read tokens and operator tokens are separate. No UI, streaming token renderer, safety actuation, notification delivery or production tenant identity system was added. See WEBSOCKET_CONTRACT.md for event delivery semantics.
