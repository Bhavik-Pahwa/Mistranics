# Implementation explanation

## Architecture and layout

This is a minimal modular monolith. FastAPI serves synchronous REST handlers with short database sessions. Paho owns a separate MQTT network thread and a bounded ingestion worker. A small background thread periodically finds persisted telemetry without a decision for the configured policy, evaluates eligible evidence, and atomically saves decisions and incident changes. PostgreSQL is the system of record.

- app/config.py: environment settings and .env loading.
- app/schemas.py: strict Pydantic envelopes, timezone-aware timestamps, quality and policy schemas.
- app/db.py: six domain tables plus immutable policy_versions, foreign keys, JSONB and indexes.
- app/services.py: registry bootstrap, canonicalization, deduplication, detector persistence, versioned decision evaluation, incident transitions.
- app/mqtt.py: TLS/credential-capable external broker subscription, bounded queue, manual acknowledgment, reconnection and retries.
- app/main.py: application lifecycle, authentication, bounded REST queries and error handling.
- app/manage.py and migrations/: ordered transactional PostgreSQL migrations guarded by an advisory lock, plus optional registry seed command.
- examples/: explicitly illustrative registry, telemetry, demo-only policy, and executable end-to-end demonstration.
- tests/: schema, persistence, API, policy, lifecycle, failures, migrations and optional real MQTT integration.
- Dockerfile and compose.yaml: simple API plus PostgreSQL deployment; broker supplied externally.
- requirements*.txt: pinned direct dependencies. The optional demo and tests require development dependencies.

## Telemetry flow

Each accepted envelope identifies a machine, publishing device, reading/window, observation timestamp and sensor measurements. The file-backed registry defines allowed devices, sensor/parameter pairs, and parameter-specific affine conversions: normalized = original × scale + offset. The sample configuration approves only identity conversions for illustrative sensors, not machine thresholds. No conversion is guessed. Unknown units preserve originals, mark non-missing data suspect and leave normalized value/unit null.

NaN/infinity, booleans as measurements, numeric strings, malformed identifiers, naive timestamps, unsupported versions, duplicate sensor identities and invalid windows are rejected. Null is permitted only with quality missing. Arbitrary nested numeric JSON is checked for finiteness. Individual quality states are preserved; the envelope quality_status is valid only if every measurement is valid, otherwise suspect.

If both boundaries are omitted, the documented provisional adapter interprets measured_at as the end of a 3-second window. Supplied boundaries are preserved and measured_at must fall inside them. Received_at is never replaced by ingestion time. PostgreSQL sessions use UTC. Late/out-of-order valid data is stored unchanged and returned in event-time order. It is not automatically reprocessed by ML; detector scheduling is external.

Machine/window uniqueness is enforced by PostgreSQL. Locking the asset serializes related writes for a simple, safe prototype. Exact redelivery returns the original record; reuse with changed content is a conflict. A supplied batch (1..100 envelopes, total up to 1 MiB) is atomic: invalid members reject the whole batch. Normalized validated input is retained for conflict checking, while original measurement values and units remain in canonical records.

## MQTT and failure handling

The network callback only enqueues bounded messages; the consumer performs transactional ingestion. QoS 1 messages are acknowledged after commit, or explicitly rejected after validation failure. Transient database failures retain the message and retry; persistent broker sessions allow unacknowledged redelivery after process failure. Queue overflow initiates reconnect for redelivery. Keep the client ID stable and run one instance. Broker/session persistence is an external requirement. QoS 0 cannot provide redelivery guarantees; QoS 2 is rejected because its restart semantics need additional durable protocol state.

Malformed payloads never terminate the consumer. Rejected payload content is not retained or logged. Connection state, correlation IDs, duplicates and meaningful failures use lightweight Python logging with key/value context. No external notification or orchestration system is introduced.

## Detector integration and policy semantics

The protected HTTP adapter validates a common envelope, requires window_id and run_id extensions, and preserves findings, data quality and version/source metadata. Machine/window foreign keys prevent miscorrelation. A run ID uniquely identifies an evaluation per machine/window/detector; changed content under that identity conflicts. Legitimate reevaluations use new run IDs.

Detector acceptance commits independently of policy processing. The polling worker derives pending work from persisted readings and results, so a crash between acceptance and evaluation does not lose work. It handles up to 100 pending windows per transaction. It also retries persisted decisions whose alert processing remains pending.

No policy is enabled by default. Configuring a reviewed policy explicitly opts into these adapter semantics:
1. The first accepted evaluation for each required detector is used, ordered by received_at and result ID.
2. Once all required detectors exist, or the configured timeout since backend ingestion expires, one decision per machine/window/policy is frozen.
3. Missing/failed evaluations yield indeterminate. Completed empty findings with valid detector data quality and reliable source telemetry yield normal.
4. Explicit predicates can map machine_condition findings to anomaly or indeterminate. An anomaly rule takes precedence. Unmapped findings or unreliable data quality cannot yield normal.
5. Raw numerical scores are never combined, thresholded or interpreted as probabilities.
6. Later results and reevaluations are retained but do not revise the frozen decision. A new policy version may evaluate stored windows again; enabling such a policy can replay historical incidents.
7. Evidence snapshots contain exact detector result IDs and original payloads; the reason includes the selected rule and full policy snapshot.

The demo policy gives a verified critical manufacturer machine-condition finding priority even if Isolation Forest is normal or unavailable. Data-quality findings never create a mechanical incident under this rule. Its synchronization, timeout, field vocabulary and fusion behavior are test-only proposals requiring ML/policy-owner review. The engine provides a bounded declarative rule interface, not an arbitrary policy programming language. Policy versions cannot be silently edited after registration. approved_by is attribution, not an approval mechanism.

## Alert lifecycle

Alert processing is atomic with decision creation when enabled. The documented provisional grouping key is machine ID, enforced with a partial unique index covering active and acknowledged states. Anomaly decisions create or update the active incident; updates append events referencing each new decision. Indeterminate decisions never resolve incidents. Optional normal recovery requires policy permission and an event timestamp newer than the latest anomalous observation, preventing late normal windows from resolving newer anomalies.

Authorized operator actions acknowledge active incidents and, when allowed by policy, resolve active/acknowledged incidents. Invalid repeated transitions return 409. Lifecycle events are append-only through application interfaces. Originating decision links remain unchanged. Severity is nullable and assigned only by configuration, never derived from Isolation Forest scores. Shared operator tokens are a prototype authorization model, with actor recorded as operator; per-user attribution requires an external identity provider.

## Retrieval and security

Historical readings use inclusive measured_at bounds, ascending measured_at/window_id ordering, pagination and a maximum time range. Missing windows are never synthesized. The ML Engine can page a 60-second query or longer offline dataset ranges. Read handlers never run inference. Detector histories use evaluated_at and decisions use decided_at. Diagnostic context combines bounded records without troubleshooting generation.

Read, detector-write and operator-write credentials are separate bearer tokens. No secret is hardcoded; startup requires write credentials. Read authentication is optional for trusted local development. Public errors omit SQL and stack traces. Deploy behind an authenticated TLS boundary, configure read auth and broker TLS, and restrict database access before external exposure.

## Trade-offs, limitations and approvals

The registry is configuration-backed rather than a management subsystem. JSONB stores variable sensor collections and findings. Offset pagination is simple and bounded but not a snapshot during concurrent insertion; clients preparing offline data should query stable ranges and deduplicate identities. Per-machine locks limit throughput but simplify correctness; no performance guarantees have been established. History is indexed, not partitioned.

There are no ML algorithms, engineered feature rows, model training/artifacts, waveform reconstruction, LLM/RAG, notifications or protective controls. Only external detector outputs are mocked in demos. The backend uses real MQTT and PostgreSQL.

Unresolved operational inputs remain explicit: actual broker/topic/QoS credentials, final payload and registry approvals, conversion mappings, detector appendices and transport/run-ID agreement, lateness/reprocessing policy, completeness/fusion approval, severity/recovery/incident policy, identity provider, retention and backups. No production policy approval is claimed. Runtime/demo and validation commands are in README.md; the exact implemented handoff is API_CONTRACT.md.
