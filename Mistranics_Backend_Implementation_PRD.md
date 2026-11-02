# Mistranics — Backend Implementation PRD

**Project:** Mistranics  
**System:** INDUX machine-health monitoring platform  
**Document type:** Product Requirements Document  
**Version:** 1.2 — aligned with Detector A/B contracts and Isolation Forest time-frame specification  
**Scope:** Backend only  
**Status:** Prototype implementation specification

---

## 1. Product definition

The backend is the central telemetry, persistence, integration, decision-management, and alert-lifecycle service for INDUX.

It receives machine telemetry through MQTT, validates and canonicalizes the messages, persists telemetry in PostgreSQL, and exposes historical and current data through REST APIs. It integrates with the external ML Engine by making telemetry available to detectors and accepting their structured results. It then runs the backend-owned Decision Layer and Alert Manager.

### 1.1 Core responsibilities

The backend shall:

1. Subscribe to configured MQTT topics.
2. validate incoming telemetry envelopes and timestamps.
3. Preserve original values and units, and store normalized values where an approved conversion exists.
4. Maintain machine, device, and sensor identity references.
5. Persist telemetry and provide bounded historical retrieval.
6. Make event-time-ordered telemetry available to external detectors.
7. Receive and validate Detector A and Detector B results.
8. Persist detector results separately from decisions.
9. Execute the Decision Layer using an approved, versioned policy.
10. Persist decisions and their source evidence.
11. Execute the Alert Manager and persist alert lifecycle events.
12. Expose REST APIs for assets, readings, detector results, decisions, alerts, and diagnostic context.
13. Handle duplicates, invalid data, delayed data, and processing failures without falsely reporting normal machine operation.

### 1.2 Explicit non-goals

The backend does **not** implement:

- Detector A algorithms: manufacturer-limit evaluation or statistical calculations.
- Detector B algorithms: feature engineering, Isolation Forest training, or inference.
- ML model evaluation, threshold selection, or model artifact management.
- LLM, RAG, technical-manual retrieval, or troubleshooting generation.
- Frontend functionality.
- IoT hardware, firmware, or MQTT broker implementation.
- Machine actuation, shutdown, or safety protection.
- SMS, email, WhatsApp, or push-notification delivery.

The backend integrates with these external components where required but does not implement them.

---

## 2. System architecture and boundaries

```text
Sensors / Gateway
       |
       | MQTT JSON (3-second telemetry windows)
       v
   MQTT Broker
       |
       v
+-------------------------- BACKEND ---------------------------+
|                                                               |
| MQTT Subscriber                                               |
|       |                                                       |
|       v                                                       |
| Envelope validation, deduplication, timestamp/unit handling  |
|       |                                                       |
|       v                                                       |
| PostgreSQL <------> Telemetry query/API                       |
|       |                         |                             |
|       |                         v                             |
|       |                  External ML Engine                   |
|       |                  - Detector A                         |
|       |                  - Detector B                         |
|       |                    * feature engineering              |
|       |                    * offline training                 |
|       |                    * inference                        |
|       |                         |                             |
|       |<---- structured detector findings -------------------|
|       |                                                       |
|       v                                                       |
| Detector-result validation and persistence                   |
|       |                                                       |
|       v                                                       |
| Decision Layer (backend-owned, policy-driven)                 |
|       |                                                       |
|       v                                                       |
| Alert Manager (backend-owned)                                 |
|       |                                                       |
|       v                                                       |
| PostgreSQL                                                   |
|                                                               |
| REST API: readings, detector results, decisions, alerts       |
+-------------------------------|-------------------------------+
                                v
                 Frontend / external diagnostic system
```

### 2.1 Ownership

| Capability | Owner |
|---|---|
| MQTT subscription and ingestion | Backend |
| Transport-envelope validation | Backend |
| Canonical telemetry persistence | Backend |
| Historical telemetry retrieval | Backend |
| Detector A preparation and algorithms | External ML Engine |
| Detector B feature engineering | External ML Engine |
| Isolation Forest training/inference | External ML Engine |
| Detector-result validation and storage | Backend |
| Detector-fusion policy | Backend Decision Layer |
| Incident lifecycle | Backend Alert Manager |
| LLM/RAG troubleshooting | External diagnostic subsystem |
| Safety shutdown/protection | Independent engineered protection system |

**Boundary clarification:** The supplied detector contract calls A1 “data preparation and validation.” The backend performs transport-level validation and canonical persistence preparation. Detector-side A1 remains responsible for any detector-specific validation or preparation required by the ML contract. The two stages must share definitions and must not contradict each other.

---

## 3. Technology and implementation constraints

| Area | Requirement |
|---|---|
| Architecture | Minimal modular monolith |
| Database | PostgreSQL |
| Ingestion | MQTT client subscribing to an existing broker |
| API | REST, versioned under `/api/v1` |
| Payload format | JSON |
| Internal contracts | Typed schemas; Pydantic if Python is selected |
| Time standard | UTC, timezone-aware timestamps |
| Flexible payload fields | JSONB where justified |
| Database evolution | Versioned migrations |
| Configuration | Environment variables |
| Logging | Basic structured application logs |
| Deployment | Simple prototype deployment |

The detector contract uses Python/Pydantic, Pandas, NumPy, Scikit-learn, and Joblib internally. Those dependencies belong to the ML Engine and are not automatically backend dependencies. If the backend is also Python, shared Pydantic contract definitions may be reused.

Do not introduce microservices, event-streaming platforms, complex orchestration, or production-scale abstractions without a demonstrated requirement.

---

## 4. Telemetry contract

### 4.1 Incoming MQTT envelope

The backend shall accept a JSON envelope with these logical fields:

| Field | Required | Meaning |
|---|---:|---|
| `schema_version` | Yes | Payload contract version |
| `machine_id` | Yes | Machine identity |
| `device_id` | Yes | Publishing device/gateway identity |
| `reading_id` | Yes | Stable unique message/window identity |
| `measured_at` | Yes | Observation time |
| `received_at` | No | Source/gateway receive time, if supplied |
| `operating_context` | No | Operating state, RPM, load, etc. |
| `readings` | Yes | One or more sensor measurements |

Illustrative message:

```json
{
  "schema_version": "1.0",
  "machine_id": "motor_001",
  "device_id": "esp32_001",
  "reading_id": "motor_001-20261102T091003Z-00017",
  "measured_at": "2026-11-02T09:10:03Z",
  "received_at": "2026-11-02T09:10:04Z",
  "operating_context": {
    "operating_state": "running",
    "rpm": 1450,
    "load_pct": 72
  },
  "readings": [
    {
      "sensor_id": "temp_01",
      "parameter": "motor_temperature",
      "value": 56.4,
      "unit": "degC"
    },
    {
      "sensor_id": "vib_01",
      "parameter": "vibration_velocity_rms",
      "value": 2.4,
      "unit": "mm/s"
    }
  ]
}
```

The exact sensor list and units are machine-configuration-dependent. This example is not an approved machine limit or hardware specification.

### 4.2 Three-second telemetry windows

The current design publishes telemetry summaries for successive 3-second windows. The backend shall support window-level messages and preserve:

- `window_id` or equivalent stable `reading_id`;
- `window_start` and `window_end`;
- `measured_at`;
- `received_at` and backend `ingested_at`;
- machine, device, sensor, and parameter identities;
- original value and unit;
- normalized value and canonical unit, when conversion is approved;
- quality state;
- operating context.

Do not assume that every MQTT message is an individual raw sensor sample. If the payload is a batch, each window record must retain the same semantic fields.

### 4.3 Canonical internal record

The backend shall convert accepted messages to a typed canonical representation. Conceptually:

```json
{
  "schema_version": "1.0",
  "machine_id": "motor_001",
  "window_id": "motor_001-20261102T091003Z-00017",
  "window_start": "2026-11-02T09:10:00Z",
  "window_end": "2026-11-02T09:10:03Z",
  "measured_at": "2026-11-02T09:10:03Z",
  "received_at": "2026-11-02T09:10:04Z",
  "ingested_at": "2026-11-02T09:10:04.200Z",
  "operating_context": {
    "operating_state": "running",
    "rpm": 1450,
    "load_pct": 72
  },
  "readings": [
    {
      "sensor_id": "temp_01",
      "parameter": "motor_temperature",
      "value_original": 56.4,
      "unit_original": "degC",
      "value_normalized": 56.4,
      "unit_normalized": "degC",
      "quality": "valid"
    }
  ]
}
```

### 4.4 Validation and quality

Validate required identifiers, schema version, timestamp format, numeric types, and reading structure. Reject NaN and infinity. Normalize timestamps to UTC. Do not encode missing measurements as zero. Preserve original values and units.

Supported quality states:

- `valid`
- `missing`
- `out_of_range`
- `suspect`

Quality describes measurement reliability, not mechanical condition. A data-quality issue is not automatically a machine-fault finding.

Only convert units using an approved, parameter-specific conversion mapping. Unknown or ambiguous units must not be silently interpreted.

---

## 5. MQTT ingestion

### FR-01 — Subscriber

The backend shall connect to the configured broker and subscribe to the agreed topic pattern.

Configurable settings:

- broker host and port;
- client ID;
- topic pattern;
- credentials;
- TLS settings, where used;
- QoS;
- reconnect interval/backoff.

The subscriber must reconnect after disconnection, log connection state, and isolate malformed messages so one bad payload does not terminate the subscriber.

The backend does not host or implement the MQTT broker.

### FR-02 — Idempotency and duplicate handling

Use a stable identity such as `(machine_id, reading_id)` or `(machine_id, window_id)`. Enforce uniqueness in PostgreSQL.

A duplicate delivery must not create duplicate telemetry or trigger a second authoritative decision for the same observation and policy version. MQTT delivery can be repeated; application-level idempotency is required.

### FR-03 — Timestamp semantics

Keep these timestamps distinct:

| Timestamp | Meaning |
|---|---|
| `measured_at` | Observation time |
| `window_start`, `window_end` | Window boundaries |
| `received_at` | Source/gateway receive time, if supplied |
| `ingested_at` | Backend persistence/acceptance time |
| `evaluated_at` | Detector evaluation time |
| `decided_at` | Decision Layer output time |
| `created_at` | Alert creation time |

Do not substitute arrival time for event time.

### FR-04 — Out-of-order and late messages

The backend shall persist valid late-arriving telemetry with its original event time, subject to the agreed lateness/retention policy. Historical queries must sort by event time.

The backend must not silently rewrite event timestamps to make records appear ordered. Duplicate and late-arrival handling must be distinguishable.

The exact late-data policy—whether a late window causes detector reprocessing, is merely stored, or is excluded from a current inference cycle—must be agreed with the ML integration. Do not infer it.

---

## 6. PostgreSQL data model

PostgreSQL is the system of record for backend-managed data. Use relational columns for identity, timestamps, statuses, and relationships; use JSONB for variable sensor collections and preserved contract payloads where useful.

### 6.1 `assets`

Machine identity and metadata.

| Field | Type / constraint |
|---|---|
| `asset_id` | Primary key |
| `name` | Text |
| `metadata` | JSONB |
| `created_at` | Timestamp with time zone |

### 6.2 `devices` (if device registry is required)

| Field | Type / constraint |
|---|---|
| `device_id` | Primary key or unique identifier |
| `asset_id` | Foreign key |
| `metadata` | JSONB |
| `created_at` | Timestamp with time zone |

If the prototype has a fixed device mapping and no device-management requirement, this may be represented in asset configuration rather than a separate table.

### 6.3 `sensor_readings`

One row per telemetry window/message, with a JSONB collection of sensor readings.

| Field | Type / constraint |
|---|---|
| `id` | Primary key |
| `asset_id` | Foreign key |
| `device_id` | Text / optional foreign key |
| `window_id` | Text |
| `measured_at` | Timestamp with time zone |
| `window_start` | Timestamp with time zone |
| `window_end` | Timestamp with time zone |
| `received_at` | Timestamp with time zone, nullable |
| `ingested_at` | Timestamp with time zone |
| `operating_context` | JSONB |
| `readings` | JSONB |
| `schema_version` | Text |
| `quality_status` | Text |
| Unique key | `(asset_id, window_id)` |

Index at minimum on `(asset_id, measured_at DESC)` and the unique window identity. Add indexes only for demonstrated query patterns.

A JSONB collection is a practical prototype choice when the set of sensors varies by machine. If frequent per-parameter range queries or aggregations become necessary, introduce a normalized measurement table based on measured workload rather than pre-emptively overcomplicating the schema.

### 6.4 `detector_results`

Persist every accepted detector result independently.

| Field | Type / constraint |
|---|---|
| `id` | Primary key |
| `asset_id` | Foreign key |
| `window_id` | Text |
| `detector` | Text |
| `evaluated_at` | Timestamp with time zone |
| `status` | Text |
| `schema_version` | Text |
| `model_version` | Text, nullable |
| `feature_schema_version` | Text, nullable |
| `config_version` | Text, nullable |
| `payload` | JSONB |
| `received_at` | Timestamp with time zone |

Allowed detector identities include `manufacturer_limits`, `statistical`, and `isolation_forest`. Preserve the original structured payload and version fields. Do not turn a detector result directly into an authoritative decision.

Define a stable idempotency key for detector submissions. It must distinguish legitimate reevaluations from duplicate delivery; a possible key includes machine, window, detector, model/configuration version, and evaluation/run identifier.

### 6.5 `anomaly_decisions`

| Field | Type / constraint |
|---|---|
| `id` | Primary key |
| `asset_id` | Foreign key |
| `window_id` | Text |
| `decided_at` | Timestamp with time zone |
| `final_status` | Text |
| `policy_version` | Text |
| `evidence` | JSONB |
| `decision_reason` | JSONB |

Decision evidence must reference the exact detector-result records used.

### 6.6 `alerts`

| Field | Type / constraint |
|---|---|
| `id` | Primary key |
| `asset_id` | Foreign key |
| `decision_id` | Foreign key |
| `created_at` | Timestamp with time zone |
| `status` | Text |
| `severity` | Text, nullable until policy defines it |
| `acknowledged_at` | Timestamp with time zone, nullable |
| `resolved_at` | Timestamp with time zone, nullable |
| `metadata` | JSONB |

### 6.7 `alert_events`

Append-only lifecycle history.

| Field | Type / constraint |
|---|---|
| `id` | Primary key |
| `alert_id` | Foreign key |
| `event_type` | Text |
| `occurred_at` | Timestamp with time zone |
| `details` | JSONB |

This records lifecycle events such as acknowledgment and resolution. It is not a notification queue.

### 6.8 Time-series scale and partitioning

At one feature/telemetry row every 3 seconds, a continuously operating machine produces 28,800 rows/day, approximately 201,600/week, and 864,000 per 30 days. Actual volume will be lower with downtime or missing windows.

Use PostgreSQL indexes and bounded queries first. Do not assume a time-series extension is required. Evaluate time-based partitioning only after measuring data volume, query latency, retention needs, and maintenance overhead. Define a retention and backup policy before production use.

---

## 7. Detector integration

### FR-05 — Result ingestion interface

The detector contracts define result structures but do not specify the transport. The prototype should use a documented internal HTTP endpoint/callback unless the ML team explicitly chooses another transport. This is an implementation recommendation, not an already-established contract.

The transport adapter must be separate from detector-result validation and business logic so the transport can change without rewriting the Decision Layer.

For each result:

1. Receive the payload.
2. Validate the schema and detector identity.
3. Validate machine and window references.
4. Validate timestamps and status.
5. Preserve model, feature-schema, or configuration versions.
6. Persist the result idempotently.
7. Determine whether the result set is eligible for decision evaluation.
8. Trigger the Decision Layer only when its input policy is satisfied.

### FR-06 — Common result envelope

The backend must support the common contract:

```json
{
  "schema_version": "1.0",
  "detector": "statistical",
  "machine_id": "motor_001",
  "evaluated_at": "2026-11-02T09:10:03Z",
  "status": "completed",
  "findings": [],
  "data_quality": {
    "status": "valid",
    "warnings": []
  },
  "model_or_config_version": "version_identifier"
}
```

Detector B must additionally preserve `model_version` and `feature_schema_version`. Detector A must preserve applicable configuration versions and source metadata for manufacturer limits.

### FR-07 — Detector statuses

Preserve these statuses exactly:

- `completed`
- `insufficient_data`
- `invalid_input`
- `model_unavailable`
- `processing_error`

`completed` with an empty findings list means evaluation completed with no finding. Any non-completed status is not equivalent to normal operation.

### FR-08 — Data-quality separation

Data-quality findings must remain distinguishable from machine-condition findings. The backend may expose them for sensor/system maintenance, but must not automatically convert them into mechanical-fault alerts.

---

## 8. Detector B: Isolation Forest timing and data-access requirements

The following timing design is the current prototype specification for the external Detector B. It creates backend storage and retrieval requirements; it does **not** move feature engineering or inference into the backend.

### 8.1 Inference cadence and windows

Detector B is intended to run once every 3 seconds per machine, when sufficient valid history is available. Each inference uses **one combined feature row** calculated by the external feature-engineering component from three overlapping event-time windows:

| Window | Coverage | Purpose |
|---|---|---|
| 3 seconds | Current telemetry window | Latest machine behaviour |
| 15 seconds | Current and recent short-term history | Short-term trends/fluctuations |
| 60 seconds | Current and recent longer-term history | Sustained changes and broader trend |

These are overlapping rolling windows, not three independent model inputs or batches. The model receives one engineered numerical feature row per inference.

Illustrative feature names include:

- `motor_temp_mean_3s`
- `motor_temp_mean_15s`
- `motor_temp_mean_60s`
- `motor_temp_std_15s`
- `temperature_rate_60s`
- `vibration_rms_3s`
- `vibration_rms_mean_15s`
- `vibration_peak_3s`
- `current_mean_3s`
- `rpm_mean_3s`

The actual feature schema is machine-specific and owned by the ML Engine. The backend must not hardcode this illustrative list as a universal schema.

### 8.2 Backend requirements arising from these windows

The backend must:

1. Persist each accepted 3-second window with event-time boundaries.
2. Retrieve history for a specific machine over a requested event-time range.
3. Return records in deterministic ascending event-time order for feature construction.
4. Preserve gaps; do not manufacture missing windows or fill them with zero.
5. Expose quality flags and units with values.
6. Support bounded queries covering at least the recent 60-second history, with configurable margin for late arrival and integration needs.
7. Avoid using message arrival order as the rolling-window order.
8. Allow the ML Engine to determine whether enough valid history exists.
9. Avoid running Detector B inference inside ordinary REST API requests.
10. Avoid retraining the model for every incoming telemetry window.

The external feature-engineering component calculates rolling statistics and creates the exact ordered feature row expected by the trained model. The backend only supplies trustworthy source records.

### 8.3 Training data is separate

The 3-, 15-, and 60-second windows describe recent inference context. They are not the model's training-period duration.

The initial training-data collection target is approximately 1–2 weeks of representative, verified healthy operation where practical. This is a target, not a guaranteed minimum or a backend-enforced rule. The dataset should represent relevant modes such as startup, idle, low load, and high load. Suspected faulty periods must not be blindly labelled healthy.

The backend must make historical telemetry queryable/exportable for offline dataset preparation. Model training, chronological validation, model approval, artifact versioning, and deployment remain ML Engine responsibilities.

### 8.4 Observation volume

Assuming continuous operation and one row every 3 seconds:

| Duration | Rows per machine |
|---|---:|
| 1 minute | 20 |
| 1 hour | 1,200 |
| 24 hours | 28,800 |
| 7 days | 201,600 |
| 30 days | 864,000 |

These are feature/inference-row counts under continuous operation, not raw sensor sample counts. Missing windows reduce actual counts.

### 8.5 Vibration limitation

A 3-second RMS summary does not preserve the original high-frequency vibration waveform. If frequency-band energy or other waveform-derived features are required, those must be calculated upstream from sufficiently sampled raw waveform data. The backend must not claim that window summaries retain waveform information they do not contain.

### 8.6 Detector A relationship

Detector A may use the same validated telemetry source but is not required to use identical windows. Manufacturer-limit checks may evaluate current valid measurements; statistical checks may use their configured time windows. Detector A and Detector B produce independent findings for the shared Decision Layer.

### 8.7 Safety limitation

Three-second inference is a prototype monitoring cadence, not a safety-response guarantee. Critical protective functions must remain in independently engineered protection systems.

---

## 9. Decision Layer

### FR-09 — Responsibilities

The Decision Layer is backend-owned. It receives the separate results from manufacturer-limit checks, statistical checks, and Isolation Forest inference. It applies an explicit, versioned policy and produces a decision record.

It does not run detector algorithms, calculate feature rows, diagnose root causes, or reinterpret anomaly scores as probabilities.

### 9.1 Decision input

The logical input is grouped by machine and observation window and includes the relevant detector-result records, their statuses, findings, and versions.

### 9.2 Required behavior

The Decision Layer shall:

- distinguish completed evaluations from failed or unavailable evaluations;
- preserve detector identities and evidence provenance;
- apply only an approved policy version;
- record which detector-result records were considered;
- support an indeterminate outcome when evidence is insufficient;
- persist its output and decision rationale;
- never classify a failed evaluation as normal.

A verified critical manufacturer limit must not be vetoed by a normal Isolation Forest result. Preserve the source and limit category. An operating warning is not equivalent to a protective trip setting.

Do not add raw Isolation Forest scores to statistical scores. Do not interpret an Isolation Forest score as a probability of failure or severity. Detector agreement is evidence, not proof of severity.

### 9.3 Decision completeness and timing

The system must define when a detector-result set is complete enough for a decision. The supplied contracts do not specify a synchronization protocol, timeout, or late-result revision policy. These must be agreed with the ML integration and encoded in a versioned policy/configuration.

Until that policy is approved, implement the interface and persistence but do not invent a final fusion matrix or claim decisions are production-ready.

### 9.4 Decision output

Persist at least:

- decision ID;
- machine and window identity;
- decision timestamp;
- final status;
- policy version;
- references to source detector-result IDs;
- evidence snapshot or structured evidence;
- decision rationale/rule ID.

At minimum, the decision model must distinguish normal, anomaly, and indeterminate states. Exact enumerations should be finalized with the approved policy.

---

## 10. Alert Manager

### FR-10 — Alert generation and lifecycle

The Alert Manager receives authoritative decisions, not raw detector messages. It determines whether to create an alert, update an active incident, or resolve an incident under approved rules.

The prototype must support:

- alert creation;
- active status;
- acknowledgment;
- resolution;
- lifecycle event history;
- linkage to machine and originating decision;
- retrieval through REST APIs;
- prevention of duplicate active incidents for the same stable incident identity.

The precise incident grouping key, severity policy, recovery criteria, acknowledgment authorization, and allowed transitions require approval. A simple documented machine-level grouping approach may be used for a prototype if it is tested and clearly identified as provisional.

The Alert Manager does not send external notifications. It stores and serves alert records.

---

## 11. REST API requirements

All endpoints are versioned under `/api/v1`. Exact request/response schemas, pagination defaults, and authentication rules must be documented during implementation.

### 11.1 Assets

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/assets` | List assets |
| GET | `/api/v1/assets/{asset_id}` | Asset details |

### 11.2 Readings

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/assets/{asset_id}/readings` | Historical windows |
| GET | `/api/v1/assets/{asset_id}/readings/latest` | Latest stored window |

Historical queries must support `start`, `end`, pagination/limit, and deterministic event-time ordering. Enforce a maximum query range or result limit. The ML Engine's 60-second retrieval must be possible without requiring an unbounded API query.

### 11.3 Detector results

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/assets/{asset_id}/detector-results` | List detector results |
| GET | `/api/v1/detector-results/{result_id}` | One result |

### 11.4 Decisions

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/assets/{asset_id}/anomalies` | Decision history |
| GET | `/api/v1/anomalies/{decision_id}` | One decision |

These endpoints return persisted decisions; they do not rerun detectors.

### 11.5 Alerts

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/alerts` | List/filter alerts |
| GET | `/api/v1/alerts/{alert_id}` | Alert details and history |
| POST | `/api/v1/alerts/{alert_id}/acknowledge` | Acknowledge |
| POST | `/api/v1/alerts/{alert_id}/resolve` | Resolve, if policy permits |

Mutating endpoints require authorization and valid state transitions.

### 11.6 Diagnostic context

Proposed endpoint:

`GET /api/v1/assets/{asset_id}/diagnostic-context`

Return machine identity, bounded recent readings, relevant detector findings, decisions, timestamps, and active alert information. Do not generate troubleshooting explanations or retrieve manuals in this endpoint.

### 11.7 Detector-result write interface

If HTTP callbacks are selected, define a protected endpoint such as:

`POST /api/v1/internal/detector-results`

This is a proposed transport adapter, not a field or route mandated by the detector contracts. Authenticate internal callers, validate payloads, and enforce idempotency.

---

## 12. Data consistency and processing guarantees

The logical workflow is:

1. Receive MQTT message.
2. Validate envelope and measurements.
3. Deduplicate.
4. Persist accepted telemetry.
5. Make telemetry available to external detectors.
6. External Detector A and Detector B process independently.
7. Receive detector results.
8. Validate and persist each result.
9. Check decision eligibility/completeness.
10. Execute the Decision Layer under an approved policy.
11. Persist the decision and evidence references.
12. Execute the Alert Manager.
13. Persist alert and lifecycle events.
14. Serve persisted information through REST APIs.

A message must not be reported as successfully persisted before the database transaction commits. Detector results must reference the correct machine/window. Decisions must reference the exact evidence used. Alerts must reference an authoritative decision.

Use idempotent operations at each boundary. Database transactions should protect related writes. If a multi-step workflow can fail after an earlier step commits, persist enough state to retry safely rather than relying on in-memory execution alone.

Do not introduce a distributed message broker or elaborate workflow engine for the prototype unless testing demonstrates the need.

---

## 13. Error handling

| Failure | Required behavior |
|---|---|
| MQTT broker unavailable | Retry with bounded backoff; log state |
| Malformed telemetry | Reject and log; subscriber continues |
| Duplicate telemetry | No duplicate persistence or downstream trigger |
| Unknown machine/device | Reject or quarantine according to configured policy |
| Unknown/ambiguous unit | Do not silently convert; mark/reject by policy |
| Database unavailable | Do not report persistence success; recover safely |
| Late telemetry | Preserve event time; apply agreed late-data policy |
| Invalid detector result | Reject and log |
| Duplicate detector result | Idempotent handling |
| `insufficient_data` | Preserve status; not normal |
| `model_unavailable` | Preserve status; not normal |
| Detector timeout/missing result | Track incomplete evaluation; do not invent normal |
| Decision policy unavailable | No fabricated decision |
| Alert policy unavailable | No fabricated alert |
| Invalid API request | Appropriate 4xx response |
| Missing resource | 404 response |
| Unexpected internal failure | Log details internally; return generic 5xx |

A dedicated dead-letter queue is not required for the first prototype. If rejected payloads need later investigation, store a bounded, access-controlled rejection record without retaining secrets.

---

## 14. Logging and security

### 14.1 Logging

Log application startup/shutdown, MQTT connection changes, validation failures, duplicate deliveries, persistence errors, detector-result acceptance/rejection, decision failures, alert lifecycle transitions, and API errors.

Include relevant correlation identifiers such as machine ID, window ID, detector-result ID, decision ID, and alert ID. Never log credentials or tokens.

Heavy observability infrastructure is not required for the prototype.

### 14.2 Security

- Keep secrets in environment variables or an appropriate secret store.
- Restrict database access to the backend.
- Use parameterized queries/ORM-safe operations.
- Authenticate internal detector-result submissions.
- Use authenticated MQTT connections and TLS where supported.
- Do not expose stack traces, credentials, or internal configuration through public APIs.
- Apply API authentication and authorization before deployment outside a trusted development environment.
- Restrict acknowledgment/resolution actions to authorized users or systems.

The exact identity provider and authorization model remain to be selected.

---

## 15. Performance and operational requirements

The intended telemetry cadence is one window per machine every 3 seconds. The backend must keep ingestion independent of slow API requests and avoid loading unbounded history into memory.

Requirements:

- MQTT callback/consumer work must be bounded.
- Database writes must be efficient and transactional.
- Historical reads must be indexed and bounded.
- APIs must paginate potentially large result sets.
- The backend must not run ML inference synchronously in ordinary API retrieval.
- The backend must support retrieval of at least the recent 60-second event-time history, plus any configured lateness margin.
- Processing must preserve machine/window correlation end to end.

No guaranteed throughput, latency, device count, or availability target is established by this PRD. Benchmark using the actual payload size, machine count, database configuration, and expected query patterns before making scale claims.

---

## 16. Testing requirements

### 16.1 Unit tests

Test:

- schema and required-field validation;
- UTC parsing and timestamp semantics;
- unit conversion and unknown-unit handling;
- NaN/infinity rejection;
- quality-state handling;
- deduplication;
- event-time ordering;
- detector envelope validation;
- detector status handling;
- decision policy behavior;
- alert state transitions;
- API validation and pagination.

### 16.2 Integration tests

Test:

- MQTT to PostgreSQL ingestion;
- duplicate MQTT delivery;
- PostgreSQL historical retrieval in event-time order;
- 60-second bounded history retrieval;
- detector-result ingestion and persistence;
- detector-result idempotency;
- decision evidence linkage;
- decision persistence;
- alert creation and lifecycle persistence;
- REST retrieval of readings, results, decisions, and alerts.

### 16.3 Failure tests

Test malformed payloads, missing values, invalid units, NaN/infinity, duplicate IDs, out-of-order and late timestamps, broker disconnection, database failure, unknown assets, invalid detector results, insufficient-data status, model-unavailable status, missing detector output, unavailable decision policy, and unavailable alert policy.

### 16.4 End-to-end backend demonstration

Use real MQTT telemetry and PostgreSQL, with Detector A and Detector B mocked initially if their implementation is outside this backend task. Demonstrate the full ingestion-to-alert path without implementing ML algorithms.

---

## 17. Acceptance criteria

The backend prototype is accepted when:

- [ ] It connects and subscribes to the configured MQTT broker.
- [ ] It accepts the agreed 3-second window payload.
- [ ] It validates identifiers, schema, timestamps, and measurement types.
- [ ] It preserves original and normalized values/units.
- [ ] It supports explicit quality flags and missing values.
- [ ] It persists telemetry in PostgreSQL.
- [ ] It handles duplicate delivery idempotently.
- [ ] It preserves and queries event-time ordering.
- [ ] It handles late/out-of-order records according to an agreed policy.
- [ ] It can retrieve bounded machine history covering the 60-second Detector B window.
- [ ] It exposes current and historical readings through REST.
- [ ] It provides the required telemetry to the external ML Engine.
- [ ] It ingests and persists Detector A and Detector B results.
- [ ] It preserves detector statuses and version metadata.
- [ ] It distinguishes data-quality findings from machine-condition findings.
- [ ] It does not treat failed detector evaluations as normal.
- [ ] It executes only an approved, versioned Decision Layer policy.
- [ ] It persists decisions with evidence references.
- [ ] It executes the approved Alert Manager lifecycle.
- [ ] It prevents duplicate active incidents under the agreed incident identity.
- [ ] It exposes alert state and history through REST.
- [ ] It has basic operational logging and security controls.
- [ ] Unit and integration tests pass.
- [ ] It contains no ML algorithms, LLM/RAG, frontend, or IoT firmware implementation.

---

## 18. Minimal implementation structure

Keep the repository small and readable. One suitable logical layout is:

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── mqtt/
│   │   ├── subscriber.py
│   │   └── ingestion.py
│   ├── schemas/
│   │   ├── telemetry.py
│   │   ├── detector_results.py
│   │   ├── decisions.py
│   │   └── alerts.py
│   ├── services/
│   │   ├── telemetry.py
│   │   ├── detector_integration.py
│   │   ├── decision_layer.py
│   │   └── alert_manager.py
│   ├── db/
│   │   ├── models.py
│   │   ├── repository.py
│   │   └── migrations/
│   └── api/
│       ├── assets.py
│       ├── readings.py
│       ├── detector_results.py
│       ├── decisions.py
│       └── alerts.py
├── tests/
├── .env.example
├── requirements.txt
└── README.md
```

This is a suggested organization, not a requirement to create every file as a separate abstraction. Combine related modules when that keeps the prototype simpler. Do not introduce microservices or unnecessary layers.

---

## 19. Unresolved dependencies and decisions

These must be explicitly confirmed; the implementation agent must not invent them.

| Item | Current status |
|---|---|
| Backend language/framework | To confirm |
| MQTT broker, topic pattern, QoS | To confirm |
| Final 3-second window payload schema | To confirm |
| Machine/sensor registry source | To confirm |
| Approved unit conversion map | Machine-specific |
| Detector-result transport | HTTP callback recommended; approval required |
| Detector-result run/evaluation identity | To define |
| Late-arrival and reprocessing policy | To define with ML team |
| Detector synchronization/completeness timeout | To define |
| Decision fusion policy and version | Requires approval |
| Alert severity policy | Requires approval |
| Incident grouping identity | Requires approval |
| Recovery conditions | Requires approval |
| Acknowledgment/resolution authorization | To define |
| API authentication | To define |
| Retention and backup policy | To define |
| Partitioning strategy | Measurement-dependent |

Implement stable interfaces and persistence without pretending these policies are already known.

---

## 20. Final scope statement

The INDUX backend is a centralized telemetry, persistence, detector-integration, decision, and alert-management service.

It consumes 3-second windowed MQTT telemetry, validates and stores it in PostgreSQL, and exposes event-time-ordered historical data. That data supports Detector B's external feature-engineering process, which calculates a single feature row per inference from overlapping 3-, 15-, and 60-second windows. The backend does not calculate those features or run Isolation Forest.

The backend receives structured findings from Detector A and Detector B, preserves their statuses and provenance, applies an approved backend-owned Decision Layer policy, and manages resulting incidents through the Alert Manager.

It does not implement ML algorithms, model training/inference, LLM/RAG, frontend functionality, IoT firmware, or independent safety protection.

**Implementation principle:** Build the smallest reliable backend that honors the telemetry and detector contracts, preserves evidence and event time, and does not invent machine-specific thresholds, detector behavior, decision rules, or alert policies.

---

## Appendix A — Contract and implementation references

The following supplied specifications are normative inputs to this PRD:

1. **INDUX — Detector A and Detector B Input/Output Data Contracts.**
2. **INDUX — Isolation Forest Time-Frame Structure.**

Implementation references:

- PostgreSQL documentation: https://www.postgresql.org/docs/
- MQTT specifications: https://mqtt.org/mqtt-specification/
- Pydantic documentation: https://docs.pydantic.dev/
- Pandas documentation: https://pandas.pydata.org/docs/
- Scikit-learn Isolation Forest API: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html

Pandas and Scikit-learn are ML Engine references, not mandatory backend dependencies.
