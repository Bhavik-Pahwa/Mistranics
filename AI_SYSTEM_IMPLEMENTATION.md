# AI system implementation — Parts A and B

## Existing system and reuse

Before changes, the backend already owned MQTT ingestion, typed canonical telemetry, PostgreSQL assets/readings/results/decisions/alerts, lifecycle events, configuration and bearer-role APIs. ML already implemented manufacturer/statistical detectors, the fixed Isolation Forest feature/model pipeline, offline training and tests. AI_SYSTEM_AUDIT.md records the audit before development and distinguishes inspected code from verified behavior.

The implementation retains that architecture. Classical code stays in ML; applied AI stays in AI. Necessary integration changes are confined to existing backend configuration/startup, one alert correlation column/index, acknowledgment behavior for new incident scopes, additive migrations, and migration-test fixture cleanup. No duplicate MQTT subscriber, telemetry table, asset table, detector-result table, incident table, standalone AI server, or frontend was created.

## Directory structure and changed files

- ML/: existing algorithms/models/shared utilities/trainer/CLI/artifacts; audited defect fixes in pipeline.py, models/limits.py, models/telemetry.py, detector_a/limits_engine.py, detector_b/feature_extractor.py and inference.py.
- ML/runtime.py and persistence.py: canonical-record adapter, checkpointing, finding normalization and parameter-level incidents.
- AI/: provider, RAG, context, reasoning, persisted conversations/steps/feedback/evidence, API routes and one real-time/outbox implementation.
- backend/app/config.py: optional ML/AI settings, with both disabled by default.
- backend/app/main.py: optional mounts, canonical import guard, use of the existing three-second classical worker, isolated AI worker and provider-independent startup.
- backend/app/db.py: incident_key on existing alerts; machine/parameter active uniqueness.
- backend/app/services.py: acknowledgment remains independent of condition recovery; the legacy manual resolve route cannot bypass new classical recovery.
- backend/migrations/003_parameter_incidents.sql and 004_ai_system.sql: forward-only extensions preserving legacy rows.
- backend/tests/conftest.py and test_integration.py: disposable-schema cleanup now includes migrated extension tables; migration count updated.
- AI_SYSTEM_AUDIT.md, ML/IMPLEMENTATION.md, ML/INTEGRATION_CONTRACT.md, AI/README.md, AI/API_CONTRACT.md, AI/WEBSOCKET_CONTRACT.md: explanation and cross-subsystem handoff.

Model artifact binaries/metadata and existing backend ingestion were not changed. Legacy backend APIs continue to work with the extensions disabled. New incident_key is an additive alert field.

## Classical processing and incidents

The existing backend polling worker processes persisted windows every three seconds when ML_ENABLED is true. Each window reconstructs bounded canonical event-time history, calls manufacturer/statistical/Isolation Forest evaluations independently, adapts results to the existing backend envelope and saves a decision/evidence snapshot. Missing approved limits, wrong units, unavailable models and insufficient features are explicit statuses, not normal readings. The richer existing 60-second feature context is preserved alongside 3/15 seconds.

A processed-window checkpoint is committed in the same transaction as results, decisions, observations, alerts, sessions and lifecycle notification records. No synchronous read API runs inference, no startup process retrains models, and no second telemetry loop was introduced. The runtime has no configured statistical rule set by default; existing standalone statistical persistence remains in-memory and is not claimed to survive restart.

Existing alert rows now support an exact parameter or explicitly configured group key. Each abnormal finding remains a separate anomaly event; repetition updates the same compatible incident. Unrelated parameters remain separate. Condition state ACTIVE/RECOVERING/RESOLVED/CLOSED is independent from acknowledgment. Reliable consecutive normal evidence over configured time is required for recovery. Late data, missing affected parameters, detector failures, or excessive observation gaps cannot manufacture recovery. Resolved conditions may reopen within the configured correlation interval; closed or uncorrelated conditions start a new incident. Source category is preserved rather than severity inferred from an anomaly score.

Legacy alerts keep incident_key=__machine__. Enabling the classical incident manager while a legacy decision policy still generates alerts is rejected at startup, avoiding competing lifecycle owners. The prototype policy is versioned/configurable and immutably registered; it is not represented as manufacturer approval. Consult ML/IMPLEMENTATION.md for exact default policy rationale and limitations.

## Troubleshooting and selective context

A new incident can create a session automatically. Operators can independently select an existing machine and optionally an incident/manual version. Session, messages, evidence, recommended steps and unverified operator feedback are persisted in the same database.

A durable message is accepted before provider work. The AI worker is separate from detection so provider latency/timeouts do not stop telemetry or manufacturer checks. It selects latest readings, bounded history, approved configuration, incidents and prior reported actions according to question intent, considering recent questions for follow-ups. Original source types remain distinguishable. MQTT connection state and measurement age determine staleness, checked again at response time.

The structured response exposes observed readings and configurations in machine_context. Its condition summary is rendered from these authoritative records, overriding model paraphrases. Hypotheses are not confirmed faults; operator reports are not verified maintenance outcomes. Completing a step or reporting improvement does not change incident state.

## RAG and LLM reasoning

PDF upload preserves document identity/version, machine/manufacturer/model applicability, page, section and original extracted text. Scanned pages require explicitly enabled external OCR; missing OCR does not silently index empty pages. Tables remain source text and are never automatically promoted to approved limits.

The configured provider creates real embeddings. Chunk vectors persist in PostgreSQL JSONB with no new database service. Retrieval first filters the exact document version and applicability, then performs a bounded cosine plus BM25-style lexical search, fused by rank. Exact component identifiers and page references are retained. This is a prototype vector store, not an ANN/large-corpus design.

The real Ollama HTTP adapter receives selected history/context and retrieved passages with explicit untrusted-data instructions. Responses must match a strict JSON schema. Every citation must match a retrieved chunk/document/version/page. An instruction must equal an actual source excerpt, and hazardous bypass/energized-work requests are blocked conservatively. Free generated prose cannot introduce numeric specifications; actual measurements/configuration and quoted documentation remain separately attributable. A schema/grounding failure gets one corrective attempt, then an explicit persisted error. Provider timeouts retain conversation state for explicit retry.

Document ingestion and chatbot routes cannot edit limits, retrain models or resolve incidents. A local provider is configurable; no production provider credential or embedding fallback is hardcoded.

## API, WebSocket and frontend handoff

The new routes use the existing /api/v1 prefix and read/operator bearer roles. POST messages returns 202; session APIs and notifications expose pending/processing/completed/error state. request_id enables idempotent acceptance and explicit retry of errored messages. One outstanding request per session preserves conversation ordering.

A single new WebSocket hub was added because none existed. Persisted outbox events are written with state changes and retried until publication. Events are at-least-once notifications with stable IDs; delivery to a socket is not a durable client acknowledgment. Clients deduplicate event_id and retrieve state after reconnect or resync_required. Existing APIs/database remain authoritative.

No frontend was supplied or implemented: the explicit user scope is classical ML and applied AI. The consumer-facing route/schema/event contracts support later UI implementation without inventing an existing frontend architecture.

## Setup, validation and operation

Use AI/requirements.txt, AI/.env.example and the repository-root commands in AI/README.md. Migrations are run by the existing backend migration command before startup. Configure reviewed limits, a trusted selected model, applicable manual versions, and a provider supporting chat and embeddings. Run a single backend process. No additional broker or database service is required.

Validation covers the original backend and detector suites plus new database/API/RAG/reasoning/feedback/incident/outbox cases. The migration upgrade test reconstructs the original schema and verifies that an existing active alert and identity survive 003/004. Live MQTT and PostgreSQL ingestion produced an actual manufacturer finding, persisted incident and automatic troubleshooting session; a real local LLM completed a message and operator feedback persisted. Tests with an isolated provider cover the complete manual/citation/instruction path and failure behavior.

The available local server supported real chat but rejected embedding requests with HTTP 501. Live embedding retrieval therefore remains unverified; its real HTTP integration and explicit failure behavior exist. OCR installation/extraction, production manufacturer evidence/model approval, industrial semantic/safety evaluation, frontend rendering, deployment identity/tenant isolation, retention/backup and scale guarantees remain outside the validated prototype. Test fakes exist only in AI/tests. Synthetic manufacturer data is explicitly labelled under ML/examples and is not enabled by default.

Detailed executed results are recorded in AI/VALIDATION.md.
