# Classical ML / backend integration contract

Enable ML_ENABLED=true in the existing backend; run from repository root using backend.app.main:create_app. There is no new ML server, MQTT subscriber or HTTP telemetry ingestion endpoint.

## Inputs and configuration

Canonical input is the persisted backend Reading: asset_id, device_id, window_id, measured_at/window_start/window_end/received_at/ingested_at, operating_context, quality_status and canonical readings. The adapter maps asset_id to machine_id and load_pct to load_percentage. Canonical normalized values/units are preserved exactly; unknown/missing/suspect data is not silently rehabilitated by ML's standalone unit helpers.

ML_LIMITS_FILE: optional path to a JSON array of ManufacturerLimitRecord objects. Each record uses the existing schema: limit_id, machine_id, parameter, unit, lower_limit and/or upper_limit, status, source, config_version, and optional sensor/mode/RPM/load applicability. Only status=approved participates; runtime-approved records also require reviewer and timezone-aware approved_at attribution. source contains document, optional revision/page_or_section/candidate_id/extraction_method. Missing/unapproved/inapplicable configuration yields insufficient_data. The runtime uses a limits-sha256:<file hash prefix> configuration ID; each finding also preserves the record's config_version and approved bounds.

ML_MODEL_FILE: optional explicitly selected trusted Joblib file plus same-stem .json metadata. No automatic retraining or bundled-artifact activation. The existing 22-column features-1.0 order and 3/15/60-second contexts are retained. Missing real extrema/peaks, incomplete coverage, gaps and incompatible/nonfinite vectors prevent inference. The artifact has prototype-wide applicability; production machine-specific model dispatch requires a further contract.

ML_INCIDENT_POLICY_FILE: optional JSON with version, correlation_seconds (default 120), recovery_observations (3), recovery_seconds (6), max_observation_gap_seconds (4.5), and parameter_groups (object mapping exact parameter names to approved group IDs). Values are prototype configuration, not safety settings. A version is immutable after registration; change version when rules change. Unattributed multivariate findings use __multivariate__; ordinary parameters are not grouped with them.

## Persisted outputs

The existing detector callback/read envelope is reused. Result identity is machine/window/detector/run_id, where deployed runtime run_id = classical:<persisted reading ID>:<incident policy version>. Legitimate external evaluations may still use their own distinct run IDs. The runtime's own processed-window checkpoint prevents repeated evaluation or automatic historical replay.

Standalone DetectorResultEnvelope includes metrics and skipped_reasons. The backend adapter stores these as source_metadata.metrics and source_metadata.skipped_reasons to respect the backend's strict envelope. Unavailable versions are explicitly labelled unavailable. Existing model/config/schema/source fields and finding IDs are preserved.

One decision per processed window is stored as policy_version=classical:<version>. A completed detector's machine_condition finding makes final_status anomaly; completed evidence without findings is normal only if all required runtime evaluations completed and source quality is valid; otherwise indeterminate. This simple prototype finding-preservation rule never converts an Isolation Forest score to severity or confirmed failure. Source result IDs and payloads are stored in decision evidence.

Existing alerts represent incidents; incident_key adds parameter/group correlation. metadata.condition_state is ACTIVE/RECOVERING/RESOLVED/CLOSED; status remains active/acknowledged/resolved for legacy clients. acknowledgment is separate. Severity is the latest chronological manufacturer's limit category when present; multivariate score does not produce severity.

anomaly_events contain id, result_id, incident_id, finding_key, parameter, observed_at and evidence (detector/finding/window_id). alert_events preserve every observation and recovery count. Outbox events notify meaningful lifecycle changes. Incident observations are available through the new incident detail API.

## API and policy ownership

GET /api/v1/assets/{asset_id}/incidents and GET /api/v1/incidents/{incident_id} expose the existing alert records with normalized observations. POST /api/v1/incidents/{incident_id}/close requires an already RESOLVED condition and operator authorization. Existing /alerts/{id}/acknowledge remains the acknowledgment route. /alerts/{id}/resolve cannot force-resolution of classical parameter incidents; recovery evidence owns that transition.

If ML_ENABLED is true, a legacy backend policy with alerts_enabled=true is rejected at startup to avoid competing alert owners. Legacy backend policies and APIs otherwise remain supported. Applied AI feedback never calls detector configuration or incident recovery mutation.

The normalized troubleshooting handoff uses the same asset, incident, decision and result IDs. For event payloads and conversation endpoints see ../AI/API_CONTRACT.md and ../AI/WEBSOCKET_CONTRACT.md.
