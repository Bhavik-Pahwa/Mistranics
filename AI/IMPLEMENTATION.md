# Applied AI implementation

The shared architecture, changes and validation are documented in ../AI_SYSTEM_IMPLEMENTATION.md. This file describes the actual modules in AI.

- models.py: documents/chunks, troubleshooting sessions, durable message jobs, evidence snapshots, steps, feedback and notification outbox. All extend the existing backend Base and reference existing assets/incidents.
- schemas.py: strict session/message/feedback inputs and structured answer/citation/instruction/hypothesis outputs.
- provider.py: bounded-time HTTP calls to a configured Ollama-compatible chat/embedding provider, embedding validation and sanitized unavailable errors.
- rag.py: PDF extraction, explicit OCR boundary, section/page chunking, machine/model/version filtering, PostgreSQL vector storage, lexical/vector ranking and evidence metadata.
- context.py: question-based context selection, bounded latest/history/incidents/reports/approved configuration, staleness checks and server-rendered measured condition summary.
- reasoning.py: instructions separating untrusted retrieved/operator content from system rules, JSON-schema requests, citation/quote/prose/safety checks and one corrective attempt.
- service.py: durable message claims, bounded processing leases, conversation/evidence assembly, provider calls outside write transactions, response/step persistence and controlled errors.
- realtime.py: one in-process bounded WebSocket hub and durable outbox delivery with stable event IDs.
- api.py: mounted /api/v1 session/document/feedback/incident routes, shared role authentication and the WebSocket handshake.
- tests/: deterministic provider fixtures and integration/failure cases; these fakes are not part of the application.
- requirements.txt and .env.example: combined dependency installation and optional runtime configuration.

Telemetry, assets, detector evaluation, approved configuration and condition recovery remain outside the LLM's write authority. AI stores operator actions separately with operator_reported provenance and does not call incident resolution or limit-edit functions.

Messages are accepted before reasoning. A separate AI worker claims a pending message, persists processing state, gathers at most eight previous exchanges and twenty feedback reports, and selectively queries relevant sources. It retrieves at most six manual chunks only if question routing requests documentation. The latest prior questions are considered for short follow-ups. Structured output must cite actual retrieved evidence; instructions must be verbatim excerpts. The measured condition summary is constructed by the server from stored evidence so an LLM paraphrase cannot replace numerical telemetry facts.

Source snapshots are saved before generation, including when a provider later fails. A response and its recommended steps are saved atomically with the outbox response event. Resending an identical errored request requeues it without creating another user message. A request ID reused with changed text conflicts. Only one pending/processing message per session is accepted. An expired processing lease allows recovery after a crash.

The implementation deliberately uses a PostgreSQL-backed bounded vector scan instead of introducing another database, plugin framework or agent orchestration layer. Exact manual versions and applicability are required. Text/table extraction is evidence, not authoritative configuration. OCR needs an external Tesseract installation. Natural-language matching, source interpretation and the response safety checks are conservative prototype controls; semantic correctness and industrial safety require actual corpus evaluation and review.

Follow README.md for setup, troubleshooting and known deployment gaps; API_CONTRACT.md and WEBSOCKET_CONTRACT.md describe the frontend handoff.
