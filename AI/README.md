# Applied AI (Part B)

This folder implements troubleshooting, conversation/feedback persistence, manufacturer-document RAG, a real Ollama-compatible HTTP provider, response validation, and WebSocket/outbox integration. It is mounted inside the existing backend; it is not a second service or MQTT consumer. Classical ML stays in ../ML.

## Run the integrated application

From the repository root, with Python 3.12+, an existing PostgreSQL database, and your MQTT broker:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r AI/requirements.txt
cp AI/.env.example AI/.env
# Edit database/broker credentials, three distinct tokens, reviewed configuration,
# and the LLM/embedding model names supported by your provider.
set -a
. AI/.env
set +a
backend/.venv/bin/python -m backend.app.manage migrate
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000
```

AI/.env contains shell-compatible assignments; quote values containing spaces and do not commit it. Existing backend-only startup from backend/ remains valid when ML_ENABLED and AI_ENABLED are false. The extensions require the canonical repository-root entry point so all modules use one shared SQLAlchemy metadata registry. Use one backend process/worker with a stable MQTT client ID. The existing backend Dockerfile packages only the legacy backend; the combined service uses this repository-root launch workflow. An integrated container deployment was not validated.

The existing migration sequence now includes additive 003/004 migrations. Existing assets, readings, results, decisions and alert identities are retained. AI does not own or duplicate telemetry, approved limits or detector findings.

Configure ML_LIMITS_FILE with reviewed ManufacturerLimitRecord objects. Approved runtime records require reviewer and timezone-aware approved_at attribution. No limits are configured by default. The file ML/examples/approved-limits.demo.json is **synthetic test data**, not manufacturer approval. ML_MODEL_FILE is optional; no existing artifact is silently activated or retrained. Sparse input without real extrema/peaks cannot satisfy the existing 22-feature model; unavailable/incomplete results are explicit.

ML_INCIDENT_POLICY_FILE defines provisional parameter correlation and recovery. The example defaults combine repeated observations over 120 seconds and require three reliable normal observations over six seconds, with no gap greater than 4.5 seconds. Review these for the actual machine. Legacy POLICY_FILE must be absent or have alerts_enabled=false while ML owns parameter-level incidents.

## Provider setup

AI_PROVIDER_URL defaults to http://localhost:11434. Set AI_LLM_MODEL and AI_EMBEDDING_MODEL to models your Ollama-compatible server actually serves. Optional AI_PROVIDER_TOKEN is sent only to this configured server. The adapter uses POST /api/chat with a JSON schema and POST /api/embed with a list of texts. There is no fake runtime provider or synthetic embedding fallback.

A server capable of chat may not support embeddings. A real local chat model was tested successfully during implementation, but the existing local server returned HTTP 501 for embeddings (“start it with --embeddings”). Its configuration was not changed. Use an embedding-capable endpoint/server before uploading manuals. No production manual, approved operational limits or production model approval was supplied.

## Typical workflow

1. Existing MQTT telemetry is canonicalized and persisted by the backend.
2. Optional ML processing evaluates each stored window once and updates parameter-level incidents.
3. New incidents create empty troubleshooting sessions when AI_ENABLED is true.
4. Upload an applicable manufacturer PDF through POST /api/v1/documents (operator token).
5. Select its exact document ID/version when creating a session or through the session manual PATCH route.
6. POST a message with a stable request_id. It returns 202; retrieve state through session APIs or subscribe to WebSocket events.
7. The AI worker selectively collects evidence, retrieves relevant manual passages if needed, requests structured reasoning and validates sources/quotes.
8. Operator feedback is stored as operator-reported, unverified evidence. Completing a step does not resolve an incident.

An operator can also start a session without an incident. Unknown machine/incident/manual references are rejected. Existing backend APIs supply readings and detector/decision history. API details: [API_CONTRACT.md](API_CONTRACT.md); real-time details: [WEBSOCKET_CONTRACT.md](WEBSOCKET_CONTRACT.md).

## Documents and retrieval

Upload PDFs up to 15 MiB and AI_MAX_PDF_PAGES (100 by default). Text, page numbers and section headings are preserved. Scanned pages require AI_OCR_ENABLED=true and an installed tesseract executable plus language data. Missing OCR is an explicit error, not an empty successful index. Technical tables remain source text; they never become approved numerical configuration.

Document identity is document_id plus version. Content/applicability conflicts under the same identity return 409. Retrieval requires an exact selected version and matching machine applicability; manufacturer/model registry metadata further restricts matching where configured. All passages retain chunk/document/version/page references.

Embeddings are persisted in the existing PostgreSQL database as JSONB arrays. Retrieval scans a bounded, metadata-filtered manual (at most AI_MAX_CHUNKS, default 1,000 chunks), combines cosine ranking and BM25-style lexical ranking with reciprocal rank fusion, and returns at most six passages. This avoids a new database service/extension for the prototype. It has no large-corpus latency guarantee, ANN index, or separate reranking model. Semantic candidate cutoff is the documented prototype constant 0.35; lexical matches also qualify. Relevance must be evaluated on actual manuals.

## Response and failure behavior

Generated instructions must exactly quote a retrieved manufacturer passage and cite its chunk/document/version/page; unsupported actions, references and generated numerical prose are rejected. Request-specific schemas restrict citations to the selected evidence (or empty sources/instructions when no passage exists). A failed schema/grounding check gets one corrective attempt including the actual validation error, then a persisted error. Safety warnings are added by the server. Confidence labels are hypotheses, not calibrated probabilities.

The displayed condition summary is rendered from authoritative stored measurements/configuration, overriding model paraphrases. Numeric observations are served separately in machine_context. Freshness is checked at response time; an MQTT disconnect or stale/future timestamp prevents a claim of current telemetry. Anomaly evidence does not establish a confirmed mechanical diagnosis.

Provider timeouts preserve the operator message with state=error. Resend the same request_id and identical text to explicitly retry. Unfinished work after process failure is reclaimed after a bounded processing lease. Database failures leave messages/outbox/checkpoints pending for safe retry. LLM work runs in a separate worker from the existing telemetry/classical worker.

## Tests

```bash
backend/.venv/bin/python -m pip install pytest
backend/.venv/bin/python -m pytest ML/tests -q
backend/.venv/bin/python -m pytest AI/tests -q
(cd backend && .venv/bin/python -m pytest tests -q)
```

For real PostgreSQL/MQTT integration, use disposable databases only; tests drop/recreate tables:

```bash
TEST_AI_DATABASE_URL=postgresql+psycopg://user:password@localhost/ai_test \
  backend/.venv/bin/python -m pytest AI/tests -q
(cd backend && TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/backend_test \
  TEST_MQTT_PORT=1883 .venv/bin/python -m pytest tests -q)
```

The AI suite uses an explicitly test-only provider for deterministic document/response tests, plus real PostgreSQL when configured. Actual local LLM calls and the live MQTT→PostgreSQL→incident→session→LLM→feedback path were also exercised. Live embedding retrieval and actual OCR extraction remain environment-dependent and were not verified.

## Troubleshooting and limits

- Startup import error: launch backend.app.main from the repository root and install AI/requirements.txt.
- Database/unknown column: run the migration command against the same DATABASE_URL before starting.
- No incidents: check reviewed limits, units, quality, detector statuses and ML_ENABLED. Model absence does not stop manufacturer checks.
- No model result: the fixed model requires explicit real extrema/peaks and complete 15/60-second contexts; do not fabricate them.
- No manual evidence: select document_id and exact version, verify applicability, model name, provider embedding support and indexed chunks.
- OCR error: install Tesseract/language data or provide a text-based PDF; OCR is optional and not silently simulated.
- Error response: inspect message.error, fix provider/evidence configuration, then resubmit the same request identity.
- WebSocket disconnect: reconnect/authenticate and GET persisted session/incident state; sockets are notifications only.
- 401: read and operator credentials are separate; session/document/feedback mutations need operator authorization.
- 409: conflicting identities, an outstanding session request, wrong manual selection, or invalid incident state transition.

No frontend was added: the user requested ML and applied AI folders, and no existing frontend is present. Consumer contracts cover Part D integration. Production identity/tenant permissions, validated manufacturer corpus, limits/model approval, retention/backup, embedding-provider deployment, OCR installation, semantic evaluation, safety review and scale benchmarking remain deployment work.
