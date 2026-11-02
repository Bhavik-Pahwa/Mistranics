# Backend integration contract v1 (prototype adapter)

Base prefix: /api/v1. JSON, schema_version "1.0", timezone-aware ISO 8601 timestamps normalized to UTC. Unknown typed envelope fields are rejected. Machine, device, sensor, window and run identifiers are nonempty strings without whitespace, up to 200 characters. This contract is the implemented prototype adapter; final detector appendices were not supplied and must be reconciled before integration approval.

## Authentication and errors

Read routes: Authorization: Bearer API_TOKEN when configured; otherwise trusted-local read access. Detector submission: Bearer INTERNAL_TOKEN. Acknowledge/resolve: Bearer OPERATOR_TOKEN. The three roles do not implicitly grant each other access. /health, /docs and /openapi.json do not require tokens; deploy documentation behind your boundary if needed.

Errors use {"detail": "message"}; validation uses {"detail":[{"loc":[...],"msg":"...","type":"..."}]}. 401 unauthorized, 404 missing resource, 409 identity conflict or invalid transition/policy, 422 invalid payload/query, 503 database failure, generic 500 unexpected error. Successful submission means its transaction committed. Writes return 200 including idempotent submissions.

## MQTT telemetry

Subscribe topic defaults to mistranics/+/telemetry, configurable by MQTT_TOPIC. The envelope machine_id is authoritative for identity; topic text is routing only. Gateway permissions must be enforced at the broker. Use QoS 1, stable backend client ID and persistent broker sessions for recovery. QoS 0 is best effort, QoS 2 unsupported.

Payload: one object or array of 1..100 objects, maximum 1 MiB per message. Batch acceptance is all-or-nothing.

```json
{
  "schema_version":"1.0",
  "machine_id":"motor_001",
  "device_id":"esp32_001",
  "reading_id":"window-001",
  "measured_at":"2026-11-02T09:10:03Z",
  "window_start":"2026-11-02T09:10:00Z",
  "window_end":"2026-11-02T09:10:03Z",
  "received_at":"2026-11-02T09:10:04Z",
  "operating_context":{"operating_state":"running","rpm":1450},
  "readings":[{"sensor_id":"temp_01","parameter":"motor_temperature","value":56.4,"unit":"degC","quality":"valid"}]
}
```

Required: schema_version, machine_id, device_id, reading_id, measured_at, readings (1..500). window_start/window_end may both be omitted; adapter defaults to [measured_at−3s, measured_at]. If supplied, both are required, start < end, and start ≤ measured_at ≤ end. received_at is optional and preserved. operating_context defaults to {}. quality defaults to valid; allowed valid/missing/out_of_range/suspect. value is a finite JSON number, or null only with missing quality. No implicit zero filling.

Registry rejects unknown machine/device/sensor/parameter identities. Approved parameter-specific affine conversions produce canonical values. Unknown units preserve originals and produce null normalized fields plus suspect quality (missing stays missing). Duplicate identity = (machine_id, reading_id). Exact normalized-envelope redelivery is idempotent; changed content conflicts and is rejected. Late telemetry is stored with original event time only; external ML scheduling/reprocessing is not triggered.

Reading response object:
- id (UUID string), machine_id, device_id, window_id (incoming reading_id), schema_version.
- measured_at, window_start, window_end, received_at (nullable), ingested_at.
- operating_context object, quality_status valid or suspect.
- readings array: sensor_id, parameter, value_original (nullable), unit_original, value_normalized (nullable), unit_normalized (nullable), quality.

## External detector write callback

POST /internal/detector-results. Protected by internal token. The adapter adds mandatory window_id and run_id to the PRD common envelope.

```json
{
  "schema_version":"1.0",
  "detector":"isolation_forest",
  "machine_id":"motor_001",
  "window_id":"window-001",
  "run_id":"evaluation-001",
  "evaluated_at":"2026-11-02T09:10:05Z",
  "status":"completed",
  "findings":[],
  "data_quality":{"status":"valid","warnings":[]},
  "model_or_config_version":"model-1",
  "model_version":"model-1",
  "feature_schema_version":"features-1"
}
```

detector: manufacturer_limits, statistical or isolation_forest. status: completed, insufficient_data, invalid_input, model_unavailable, processing_error. Preserve these statuses exactly. findings defaults to [], max 500 objects, schema-specific contents preserved. data_quality required; status is a quality enum and warnings defaults to an array of strings. model_or_config_version required. Detector B requires model_version and feature_schema_version. Detector A requires config_version. Optional source_metadata object preserves manufacturer-limit provenance; other optional version fields default null. There are no backend detector algorithms.

The referenced machine/window must already exist. Identity = (machine_id, window_id, detector, run_id). A new evaluation, including changed model/configuration, must use a new run_id. Reusing a run ID with different validated content returns 409.

Response: {"result": RESULT_OBJECT, "duplicate": false}. RESULT_OBJECT: id, asset_id, window_id, run_id, detector, evaluated_at, received_at, status, schema_version, model_version/config_version/feature_schema_version (nullable), payload (entire validated envelope). Results are persisted independently of decisions; callback acceptance does not imply a decision or alert has already been created.

Finding contents are unmodified JSON. The provisional policy adapter recognizes mechanical findings only when kind equals machine_condition. The demo rule additionally matches verified=true and limit_category=critical. Findings with kind=data_quality cannot activate that rule. Unmapped findings and unreliable source telemetry cannot produce normal; they become indeterminate unless an explicit anomaly rule applies. Confirm these extensions with the ML team; do not relabel arbitrary findings just to force a decision.

## Read routes and pagination

All collection endpoints return {"items":[...],"limit":100,"offset":0,"next_offset":null}. limit defaults 100, allowed 1..1000. offset defaults 0, allowed 0..1000000. next_offset is the next page offset or null. Bounds start/end are inclusive UTC-aware timestamps. Readings/results/decision history default end=now and start=end−CONTEXT_SECONDS (120); maximum range MAX_QUERY_DAYS (31). Invalid or reversed ranges return 422. Pages are deterministic for unchanged data; concurrent insertion can shift offset pages.

| Method and path | Response and query |
|---|---|
| GET /assets | Paginated assets; ordered asset_id |
| GET /assets/{asset_id} | asset_id, name, metadata object (configured registry), created_at |
| GET /assets/{asset_id}/readings | start/end/limit/offset; measured_at then window_id ascending |
| GET /assets/{asset_id}/readings/latest | Single latest reading by measured_at/window_id descending; 404 if none |
| GET /assets/{asset_id}/detector-results | start/end on evaluated_at, limit/offset; evaluated_at/id ascending |
| GET /detector-results/{result_id} | Single RESULT_OBJECT |
| GET /assets/{asset_id}/anomalies | start/end on decided_at, limit/offset; decided_at/id ascending; includes all decision statuses |
| GET /anomalies/{decision_id} | Single decision |
| GET /alerts | Optional asset_id and status=active/acknowledged/resolved, limit/offset; created_at/id ascending |
| GET /alerts/{alert_id} | Alert plus paginated events; event_limit (100, 1..1000), event_offset (0..1000000) |
| GET /assets/{asset_id}/diagnostic-context | asset, from, as_of, readings, detector_results, decisions, active_alerts |

A 60-second ML history query is GET /assets/motor_001/readings?start=2026-11-02T09:09:03Z&end=2026-11-02T09:10:03Z&limit=1000. Page if necessary; windows are not filled or synthesized. Offline exports use the same bounded queries repeatedly. No separate export file endpoint or ML scheduling API exists.

Decision: id, asset_id, window_id, decided_at, final_status (normal/anomaly/indeterminate), policy_version, evidence (array of {result_id,payload}), decision_reason ({rule_id, optional missing detector list, policy snapshot}), alert_processed boolean. Retrieval never reruns detectors. No decision policy means no fabricated decision; missing evidence before timeout means pending (no decision yet). Completeness/timeout/late-result behavior is documented in IMPLEMENTATION.md and must be reviewed with the policy owner.

Alert: id, asset_id, decision_id (origin), created_at, status, severity (nullable), acknowledged_at/resolved_at (nullable), metadata (policy_version and latest_anomaly_at). The detail endpoint adds events as a pagination object containing id, alert_id, event_type, occurred_at, details. Event types: created/updated/acknowledged/resolved. Policy-generated events reference decision_id; operator events include actor=operator and reason.

Diagnostic context returns up to 100 items in each nested pagination object; follow the corresponding history endpoints for more. Readings use measured_at ≥ from; results use received_at ≥ from, decisions use decided_at ≥ from, and active_alerts includes active/acknowledged incidents. No troubleshooting explanation, manuals or root-cause inference is returned.

## Operator mutations

POST /alerts/{alert_id}/acknowledge and POST /alerts/{alert_id}/resolve require {"reason":"nonempty explanation"} (1..2000 characters). Return the updated Alert object. Acknowledge only active; resolve only active/acknowledged and only when configured policy permits manual_resolution. Repeated/forbidden transitions return 409. An unavailable or disabled alert policy disallows mutations. Incident grouping is provisionally machine-level. There is no notification delivery.

## Configuration handoff

All paths are relative to backend working directory. Configure DATABASE_URL (PostgreSQL), REGISTRY_FILE, POLICY_FILE (optional), API_TOKEN, INTERNAL_TOKEN, OPERATOR_TOKEN, MQTT_ENABLED/HOST/PORT/TOPIC/CLIENT_ID/USERNAME/PASSWORD/TLS/CA/CERT/KEY/QOS/RECONNECT_MAX, MAX_QUERY_DAYS, CONTEXT_SECONDS, RETRY_SECONDS. See .env.example.

Policy requires version, approved_by, nonempty unique required_detectors, positive timeout_seconds, rules (each id/detector/match/outcome); alerts_enabled/manual_resolution/resolve_on_normal default false; severity nullable. Rules reference required detectors, use exact, type-sensitive top-level finding-field equality, and outcome anomaly or indeterminate. The engine's fixed conservative fallback behavior and first-result/frozen-decision semantics are part of the reviewed adapter configuration, not claims of operational approval.
