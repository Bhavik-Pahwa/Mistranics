# Mistranics backend

Python 3.12+, FastAPI, SQLAlchemy, PostgreSQL, and an external MQTT broker. All implementation files live in this folder. No ML algorithms, frontend, notifications, firmware, or broker implementation are included.

## Run locally

Provide an existing PostgreSQL database and MQTT broker, then:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env
# Edit database URL, three tokens, broker settings and machine registry.
.venv/bin/python -m app.manage migrate
.venv/bin/uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

The startup checks database connectivity and seeds assets from REGISTRY_FILE. Migrations must run first. Use one application worker for this prototype (one MQTT client ID and one polling worker). API docs are at /docs; machine-readable request schemas are at /openapi.json. /health checks database availability; mqtt_enabled means configured, not connection readiness.

API_TOKEN protects read routes when configured. INTERNAL_TOKEN and OPERATOR_TOKEN are mandatory, distinct role credentials; use different random values. An empty API_TOKEN permits trusted local read access only. Configure it before exposing the service.

## Containers

```bash
cd backend
cp .env.example .env
# Set secrets, MQTT_HOST to your externally reachable broker hostname,
# and add POSTGRES_PASSWORD (URL-safe characters) to .env.
docker compose up --build
```

Compose supplies PostgreSQL 17 and runs migrations automatically. It does not start a broker. The API binds to localhost; the database is not published. Inside a container, localhost refers to that container. Docker Compose was not available in the implementation environment; the Python service, PostgreSQL migrations, and MQTT flow were validated directly instead.

## Policy and integration status

The default has no decision policy: telemetry and detector results persist, but no decisions or alerts are fabricated. To run the demonstration, set POLICY_FILE=examples/demo-policy.json and restart. This file is a **test fixture, not operational approval**. Demo results are mocked external findings, not machine diagnoses. The example machine/unit registry is also illustrative.

For actual integration, supply a reviewed policy with a new version and approved_by attribution. Versions are immutable once registered. Policy selection is configuration-based; there is no approval UI or identity provider. Required detectors, timeout, rule predicates, alert enablement, optional severity, and recovery permissions are explicit policy fields. The backend cannot verify organizational approval.

The additional normative Detector A/B and Isolation Forest appendices named in the PRD were not present in this repository. The implemented adapter follows the PRD common envelope with documented window/run correlation extensions; finding objects and source metadata remain preserved JSON. Confirm compatibility with the ML team before deployment. See [API_CONTRACT.md](API_CONTRACT.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Tests and demonstration

```bash
cd backend
.venv/bin/python -m pytest -q
# WARNING: TEST_DATABASE_URL must name a disposable database.
# Tests DROP and recreate backend tables there.
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost/test_db \
TEST_MQTT_PORT=1883 .venv/bin/python -m pytest -q

# With the running service, real broker, .env and demo policy:
.venv/bin/python -m examples.demo
```

Without external services, SQLite is used only for fast tests; PostgreSQL migration and MQTT integration tests skip. The real-service test covers malformed messages, duplicate delivery, reconnect, persistence, protected detector callbacks, decisions, evidence, and incidents. The demo publishes telemetry twice and supplies three explicit mocked detector outputs, including a critical manufacturer finding. It never calculates ML features or scores.

## Troubleshooting

- Startup fails: run migrations, check DATABASE_URL and mandatory tokens, and check registry/policy paths relative to backend/.
- No MQTT data: verify broker/topic/QoS, credentials, network access and TLS CA. QoS 1 and a persistent broker session are required for retry guarantees. QoS 0 is best effort; QoS 2 is deliberately unsupported.
- Unknown device/sensor: update the reviewed registry and restart. Unknown identities are rejected. Unknown units are stored as suspect with no normalized value.
- No decisions: policy is disabled, a required detector is missing before timeout, or processing has failed. Inspect logs. The polling worker retries every RETRY_SECONDS; default 5 seconds.
- No alerts: the decision may be indeterminate, the alert policy disabled, or no machine-condition rule matched.
- 401: use the correct role token in Authorization: Bearer TOKEN.
- 409: identity reused with different data, forbidden transition, or disabled policy.
- 422: malformed schema, naive timestamp, unsupported version, invalid quality/value, or query bounds.
- 503: database operation failed; MQTT leaves valid data unacknowledged and retries. Inspect server logs without exposing credentials.

Retention/backup, hardware and limit approvals, final late-data/reprocessing agreement, full detector appendix compatibility, organizational policy approval, and production identity management remain external decisions. TLS/authenticated-broker deployment and scale targets were not verified.

## Validation recorded during implementation

- 41 tests passed against a disposable PostgreSQL 16.15 database and Mosquitto 2.0.18 broker, including the real-service integration tests.
- Uvicorn started successfully, connected/subscribed to MQTT, and served health and OpenAPI requests.
- The standalone demo published duplicate real MQTT messages, submitted mocked detector results over HTTP, and verified a persisted anomaly decision and active alert.
- Python compilation and Ruff unused/undefined-name checks passed.
- One dependency deprecation warning remains: Starlette currently warns about its httpx TestClient compatibility path. Tests pass.
- Docker Compose deployment, authenticated/TLS broker operation, production detector integration, policy approval and scale benchmarking were not verified.
