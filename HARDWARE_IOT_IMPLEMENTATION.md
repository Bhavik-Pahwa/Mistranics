# INDUX hardware-to-frontend implementation

**Updated:** The simulator now runs on the server, and actual COM5 / GPIO 19 sensor readings have been verified through MQTT and the dashboard. See [SIMULATOR_SETUP.md](SIMULATOR_SETUP.md) for the current server controls, OpenAPI endpoints and USB serial setup.

## Scope and audit

The existing app is React 19 / TypeScript / Vite, entered through `frontend/src/main.tsx` and `App.tsx`. `Part1SensorTrends.tsx` uses custom SVG, not a chart package. Other dashboard cards, alerts, and chatbot content use prototype sample data; they remain intact and are labeled separately from live telemetry.

The backend entry point is `backend.app.main:create_app` (FastAPI). Its original `/api/v1` APIs, `backend/app/services.py`, database-backed MQTT ingestion, ML decision layer, and `AI/realtime.py` require persistence. Those implementations remain available with `IOT_ENABLED=false`. The new **opt-in mode** returns an in-memory application from the same entry point before any database connection, registry loading, ML runtime, or AI worker starts. It reuses `backend/app/mqtt.py` rather than introducing another subscriber or service.

The initial repository audit found the deterministic motor generator in `ML/cli.py`. Its temperature logic was extracted unchanged to `ML/simulation.py` and is used by a command-line publisher for repeatable demonstrations. During implementation, `ESP32 + MPU6050 Motor Simulator.html` appeared in the workspace. It contains the actual interactive motor simulation: temperature `S.T` follows an operating-condition/RPM/severity-dependent target with a thermal time constant. Its layout is reused at `/simulator`; its browser calculations are replaced by a server-state viewer. The full model is ported to `backend/app/simulator.py`. Its original controls, graphics, and vibration model remain intact. Only its temperature is exported to INDUX; neither its condition labels nor its local fault decisions are passed to the detector.

There was no ESP32 firmware or LAN broker configuration in the repository. Existing Paho and FastAPI dependencies are reused. No simulator runtime dependency was added; the optional physical USB bridge adds pyserial 3.5. Firmware adds OneWire 2.3.8, DallasTemperature 3.11.0, and ArduinoJson 7.4.2; it uses ESP-IDF's built-in asynchronous MQTT client. PlatformIO and Playwright are optional development tools.

## Data flow and behavior

```text
DS18B20 → ESP32 three-second windows ───────────────────┐
                                                     ↓
Server motor model → three-second window publisher → Mosquitto
CLI motor simulator → three-second windows ───────────┘
                                                     ↓
existing Paho subscriber → schema/source/dedup validation
                        → rolling Z-score → bounded memory
                        → /ws/telemetry → existing dashboard
```

The server simulator publishes through its own MQTT client; the frontend only controls and observes it. Acknowledgment means the broker acknowledged publication, not that the dashboard selected that source. Physical USB readings can also reach MQTT using `backend/examples/serial_sensor.py` without changing the working Arduino sketch.

- Both sources publish QoS 1, non-retained messages to `indux/device-01/telemetry` (`IOT_TOPIC`). MQTT host, port, authentication, TLS and reconnect settings reuse the existing `MQTT_*` configuration.
- Only `physical/device-01` and `simulation/simulation-01` are accepted by default. IDs are configurable with `IOT_PHYSICAL_DEVICE` and `IOT_SIMULATION_DEVICE`.
- One active source is authoritative across all connected dashboards. Changing it clears chart history, current reading, stream health and Z-score baseline. Selecting the same source is idempotent. Publisher duplicate tracking survives switches.
- Duplicate/out-of-order sequences and overlapping windows are ignored or rejected. Stale, future-dated, retained, malformed, non-finite or inconsistent records never become live chart data. UTC timestamps must include a timezone and represent a three-second interval. Future tolerance is two seconds; old-message tolerance is the configured stale interval.
- Supplied publishers seed sequence numbers from UTC epoch time to survive ordinary restarts. ESP32 waits for NTP before publishing. Rewinding a publisher clock is not supported; synchronize clocks before testing. Custom publishers must retain or correctly seed their sequence across restarts.
- History contains at most 60 processed windows, including error gaps; baseline contains at most 20 valid values by default. Deduplication is bounded to two configured publisher identities. Ingestion queues, outgoing MQTT queues and firmware outbox are bounded. Slow dashboard consumers receive a current snapshot including bounded history.
- One valid window produces one evaluation. There is no second aggregation in the backend. Explicit sensor errors have null temperature features and zero samples, produce `SENSOR_ERROR`, and do not update the baseline. Malformed messages are logged and dropped; they do not refresh stream health.
- MQTT connectivity and sensor health are separate. Streams become `DISCONNECTED` after 10 seconds without fresh telemetry, or when the broker is disconnected. WebSocket snapshots/heartbeats arrive every second and immediately on changes. The frontend detects missed heartbeats after five seconds and reconnects with capped backoff. Reconnection includes current state/history.
- Run **one backend worker**. This evaluation mode intentionally has no cross-process state, database, authentication, durable replay, RAG, or ML execution.

## Files

Added:

- `.gitignore` — local environment, build and credential exclusions.
- `backend/.env.iot.example`, `backend/mosquitto.conf` — evaluation settings and LAN broker listener.
- `backend/app/telemetry.py` — schema, in-memory state, Z-score, REST/WebSocket routes and simulator relay.
- `backend/app/simulator.py`, `backend/examples/simulator_frontend.js` — server motor model, controls and viewer.
- `backend/examples/serial_sensor.py`, `backend/requirements-hardware.txt` — physical USB serial-to-MQTT bridge.
- `backend/tests/test_simulator.py`, `SIMULATOR_SETUP.md` — simulator/serial tests and updated setup instructions.
- `backend/examples/iot_simulator.py`, `ML/simulation.py` — deterministic MQTT publisher and extracted existing temperature function.
- `backend/tests/test_iot.py`, `backend/tests/test_iot_browser.py` — validation, real MQTT and browser coverage.
- `frontend/src/components/LiveTemperature.tsx` — source control, live SVG, readings, anomaly and connection states.
- `firmware/platformio.ini`, `firmware/include/indux_config.example.h`, `firmware/src/main.cpp` — reproducible ESP32 project.
- `HARDWARE_IOT_IMPLEMENTATION.md` — this guide.

Modified:

- `backend/app/config.py`, `backend/app/main.py`, `backend/app/mqtt.py` — optional IoT mode and reusable subscriber callbacks/configuration.
- `ML/cli.py` — use the extracted temperature function; original ML simulation remains available.
- `frontend/src/components/Part1SensorTrends.tsx` — default live view and retained demo chart toggle.
- `frontend/src/App.tsx` — sample-data clarification and small-screen scrolling.
- `frontend/vite.config.ts` — same-origin API/WebSocket/simulator proxies for dev and preview.
- `frontend/package.json` — lint source files rather than generated bundles.
- `frontend/dist/` — regenerated existing tracked build output.

The user-supplied PRD and simulator HTML were not rewritten.

## Start the application (Windows PowerShell)

Run from `D:\Work\Dev\Mistranics` unless a command changes directories. Python 3.14 and Node installed on this machine were used for verification.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
# First setup only; preserve an existing .env and merge these settings if present.
Copy-Item backend/.env.iot.example .env
```

Settings are loaded from `.env` in the current working directory. This is why backend and simulator commands below run from the repository root. Existing process environment variables take precedence. `MQTT_ENABLED=true` is needed as well as `IOT_ENABLED=true`.

Start Mosquitto in terminal 1:

```powershell
& 'C:\Program Files\Mosquitto\mosquitto.exe' -c backend/mosquitto.conf -v
```

If a broker already owns port 1883, use that broker if it accepts the required connections, or stop its service yourself before starting this listener. Alternatively, change the port in `backend/mosquitto.conf`, `.env`, and the firmware config together. The supplied listener binds LAN IPv4 for the ESP32. Permit inbound TCP on that port on the Windows private network and keep ESP32 and host on the same LAN. Anonymous access is for this local evaluation only; do not expose it to the internet. No existing broker service was reconfigured during implementation.

Optional Docker alternative, without Postgres or any additional services:

```powershell
docker run --rm --name indux-mqtt -p 1883:1883 --mount "type=bind,source=$((Resolve-Path backend/mosquitto.conf).Path),target=/mosquitto/config/mosquitto.conf,readonly" eclipse-mosquitto:2
```

Start the backend in terminal 2:

```powershell
.\.venv\Scripts\python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Start the frontend in terminal 3:

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:5173`. The live view starts empty until the selected publisher emits. No credentials are sent to frontend code. For another backend port, update both proxy targets in `frontend/vite.config.ts`. `npm run build` and `npm run preview` also work with the preview proxy. A separate static hosting deployment would need equivalent HTTP/WebSocket proxy rules.

## Demonstrate the interactive simulation

1. Select **Simulation** on the live card and wait for backend confirmation.
2. Click **Open motor simulator**, then **Start INDUX publisher**.
3. The server owns the simulation. You may hide or close the simulator page; generation and MQTT publication continue. Only Pause or Stop INDUX publisher stops outgoing windows.
4. Leave **Normal** running until the thermal model stabilizes and the baseline warms up. Five prior windows are required; startup heating itself can initially be statistically unusual.
5. Change **Overheating**, severity, RPM or use the existing cool-down button to produce a temperature change. Backend statistical status depends only on the measured window mean and prior baseline, never the chosen condition label.
6. Stop the publisher or pause the simulator. The dashboard becomes stale/disconnected. Resume and observe recovery without reloading.

The simulator's vibration graphs and fixed WARNING/FAULT thresholds are legacy demo content, not part of this sprint's detector or manufacturer-approved limits. The server viewer labels this distinction. Run only one simulation publisher at a time because the server and CLI share the configured simulation identity.

For a repeatable normal-to-unusual sequence, stop the browser publisher, switch Physical → Simulation to clear the baseline, then run in a fourth root terminal:

```powershell
.\.venv\Scripts\python -m backend.examples.iot_simulator --steps 10 --with-anomaly
# Continuous normal condition, stopped with Ctrl+C:
.\.venv\Scripts\python -m backend.examples.iot_simulator --steps 0
# Existing unusual condition from the first window:
.\.venv\Scripts\python -m backend.examples.iot_simulator --steps 10 --condition unusual
```

The CLI retains the original deterministic 52°C/82°C generator and is not a realistic thermal model. The ten-window scenario emits five warm-up windows, then normal values, then an initial anomaly at window eight. Later high values can become normal as the rolling baseline adapts; anomaly markers remain on the chart. Starting directly in the unusual condition does not guarantee an anomaly because that condition becomes the initial baseline.

## DS18B20 wiring and firmware

Use a powered three-wire DS18B20; parasite power is not supported by this asynchronous acquisition implementation.

| DS18B20 connection | ESP32 connection |
| --- | --- |
| VDD | 3.3V |
| GND | GND |
| DATA | GPIO 19, configurable as `ONE_WIRE_GPIO` |
| DATA pull-up | Typically **4.7 kΩ between DATA and 3.3V** |

Verify the probe's pinout; wire colors are not guaranteed. The DATA pin must use ESP32-safe 3.3V logic. Physically check whether the pull-up resistor is already present on a module; do not assume it is integrated. Do not pull DATA up to 5V.

```powershell
.\.venv\Scripts\python -m pip install platformio
Copy-Item firmware/include/indux_config.example.h firmware/include/indux_config.h
ipconfig
```

Edit the gitignored `firmware/include/indux_config.h` with Wi-Fi SSID/password, the host machine's **LAN IPv4** from `ipconfig`, MQTT port/optional credentials, and actual GPIO. Never put `localhost` or `127.0.0.1` in the ESP32 broker config. NTP must be reachable; `NTP_SERVER` is configurable.

```powershell
.\.venv\Scripts\python -m platformio run -d firmware
.\.venv\Scripts\python -m platformio device list
# Replace COM5 with the verified board's port before uploading.
.\.venv\Scripts\python -m platformio run -d firmware -t upload --upload-port COM5
.\.venv\Scripts\python -m platformio device monitor -d firmware --port COM5 --baud 115200
```

The default board is `esp32dev`. Choose the actual PlatformIO board if using a different ESP32 variant; Nano ESP32 pin names may differ. The user confirmed ESP32 Dev Module, GPIO 19, and a working 9600-baud sketch. Actual readings were received through COM5 and the USB-to-MQTT bridge. No firmware was flashed; direct Wi-Fi firmware upload remains untested.

Firmware requests asynchronous 12-bit conversions about once per second, checks readings after 750 ms, and emits non-overlapping UTC-aligned three-second summaries. Invalid/disconnected readings produce null features, never invented temperatures. Any failed acquisition in a window causes an explicit error window. The first window after clock synchronization may have fewer than three samples. Wi-Fi/MQTT reconnect asynchronously; offline windows are dropped and the outbox is bounded. A raw 85°C power-on sentinel is conservatively rejected, including an actual exactly-85°C reading; this is a documented evaluation limitation.

Physical demo: select **Physical Sensor**, upload configured firmware, confirm JSON `source: physical` in serial output and backend telemetry logs, and compare the probe's actual temperature with the live dashboard. Unplug the DATA wire to verify SENSOR ERROR; disconnect power to verify stale/disconnected. Gently change probe temperature and observe new window means. Real hardware acceptance is complete only after these measurements are observed.

## Payload and API

Illustrative valid message (timestamps must be current when actually publishing):

```json
{
  "schema_version": 1,
  "device_id": "device-01",
  "source": "physical",
  "sequence": 1,
  "window_start": "2026-11-03T00:00:00Z",
  "window_end": "2026-11-03T00:00:03Z",
  "window_duration_seconds": 3,
  "temperature": {
    "mean": 32.4, "min": 32.3, "max": 32.5,
    "unit": "degC", "sample_count": 3, "status": "valid"
  }
}
```

For sensor failures, set `status` to `error` or `disconnected`, `sample_count` to `0`, and `mean/min/max` to `null`. For simulation, set `source` to `simulation` and `device_id` to `simulation-01`. The probe acquisition range −55..125°C is validated; it is not a motor operating limit.

| Route | Behavior |
| --- | --- |
| `GET /health` | HTTP service health and active IoT mode |
| `GET /api/source`, `/api/status`, `/api/telemetry/latest` | Same complete state snapshot, including latest/history and connection state |
| `POST /api/source` | `{ "source": "physical" }` or `{ "source": "simulation" }`; returns confirmed snapshot |
| `WS /ws/telemetry` | Snapshot on connection, updates, one-second health heartbeat |
| `GET /simulator` | Supplied layout with a server-state viewer replacing browser calculations |
| `WS /ws/simulation` | Read-only server simulator snapshots at 10 Hz |
| `GET/PATCH /api/simulation` | Read state or update server controls/publication |
| `POST /api/simulation/cool-down` | Reset server temperature to 28°C |

Snapshots include a backend session ID and increasing revision. The frontend ignores older source/HTTP responses within a session. Reading events include source, device, sequence, original window timestamps, mean temperature, unit, sample count, sensor status, and anomaly metadata. No HTTP endpoint bypasses MQTT ingestion.

Manual API inspection:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/status
Invoke-RestMethod http://127.0.0.1:8000/api/source -Method Post -ContentType application/json -Body '{"source":"simulation"}'
& 'C:\Program Files\Mosquitto\mosquitto_sub.exe' -h 127.0.0.1 -p 1883 -t indux/device-01/telemetry -q 1 -v
```

For a manually published fixture, use current UTC timestamps and increasing sequences, save it as a JSON file, then use `mosquitto_pub.exe -h 127.0.0.1 -p 1883 -t indux/device-01/telemetry -q 1 -f path/to/window.json`. The automated real-broker test constructs and publishes such fixtures; they test physical-source software handling and are not evidence of a real probe.

## Statistical calculation

For current window mean `x`, use the previous valid values only:

```text
baseline = last ANOMALY_BASELINE_SIZE valid means (default 20)
if fewer than ANOMALY_MIN_BASELINE_SAMPLES (default 5): WARMING_UP
else:
    mean = population mean(baseline)
    std = max(population standard deviation(baseline), ANOMALY_STD_FLOOR)
    z = (x - mean) / std
    status = ANOMALY if abs(z) >= ANOMALY_Z_THRESHOLD else NORMAL
append x to baseline after evaluation
```

Defaults: threshold 3.0 and standard deviation floor 0.1°C. Metadata includes baseline mean, effective standard deviation, prior sample count, Z-score and method `STATISTICAL_Z_SCORE`. Anomalous but valid values enter the baseline only **after** evaluation. A statistical anomaly is not a diagnosis of a mechanical fault. Existing Isolation Forest code and legacy decision behavior are retained but not instantiated in IoT mode.

## Verification commands and results

Actual verification on November 3, 2026:

| Check | Outcome |
| --- | --- |
| Backend suite with `RUN_MQTT_TESTS=1` | 70 passed; 4 skipped (3 PostgreSQL-only checks and the separately run browser test) |
| Existing ML and AI suites | 63 passed; 1 PostgreSQL-only test skipped |
| Running-stack Chrome browser test | 1 passed, including the actual browser simulator and mobile chart visibility |
| Frontend production build | Passed |
| Source lint | Passed with 2 pre-existing `ChatbotView.tsx` purity warnings |
| ESP32 PlatformIO build | Passed; 46,680 bytes RAM, 909,113 bytes flash; upstream OneWire warnings |
| Git whitespace check | Passed |
| Physical probe via USB → MQTT → dashboard | Actual COM5 readings around 29.6°C verified; existing sketch retained |
| Optional Wi-Fi firmware upload | Not performed |

The Python tests also emit an upstream Starlette/httpx TestClient deprecation warning. It does not fail the tests.

Backend regression + real MQTT test (Mosquitto must be on PATH; test starts an isolated ephemeral-port broker and restarts it):

```powershell
Set-Location backend
$env:RUN_MQTT_TESTS='1'
..\.venv\Scripts\python -m pytest tests -q
Set-Location ..
```

Browser test against the running application and broker; keep other publishers stopped. It intentionally changes active sources and sends synthetic physical-source packets:

```powershell
.\.venv\Scripts\python -m pip install playwright
# Chrome is used by default. Alternatively install Chromium and adapt PLAYWRIGHT_CHANNEL.
$env:RUN_BROWSER_TESTS='1'
$env:IOT_TEST_URL='http://127.0.0.1:5173'
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='1883'
Set-Location backend
..\.venv\Scripts\python -m pytest tests/test_iot_browser.py -q
Set-Location ..
```

Browser screenshots are saved to ignored `.iot-test/`. The test covers warm-up, normal and unusual values, red chart markers, stale status, explicit sensor errors, rejected source changes, history clearing, actual browser simulation publication, preserved simulator controls, pause/resume, WebSocket reconnection after network interruption, and mobile visibility. Every chart input traverses real MQTT; the browser's telemetry API is not mocked. Only the failed source-selection response is intentionally stubbed.

Frontend: `cd frontend; npm run build; npm run lint`. Firmware: `python -m platformio run -d firmware`. Source lint has two pre-existing purity warnings in `ChatbotView.tsx`; new live components are clean. Firmware compilation reports warnings in the upstream OneWire library, but builds successfully.

Implemented and tested: database-free startup, real broker ingestion, validation/deduplication, broker reconnection, deterministic CLI publication, browser simulation → MQTT → dashboard, Z-score states, source isolation, live frontend recovery, and ESP32 compilation.

Actual DS18B20 acquisition through the user's existing sketch and USB serial → MQTT → backend → dashboard was verified. Direct Wi-Fi firmware upload, behavior on the physical board, and physical unplug/reconnect testing remain unverified. The USB bridge uses host receipt timestamps and sparse one-sample windows because the existing sketch reads about every five seconds.

## Troubleshooting and limitations

- **Backend asks for database/tokens:** `IOT_ENABLED` is missing or false, or `.env` was loaded from the wrong directory. Start at repository root and check `/health` says `mode: iot`.
- **MQTT connected, no temperature:** select the correct source, start its publisher, check configured device ID and topic, then inspect validation warnings. Broker connectivity does not mean the sensor is healthy.
- **ESP32 cannot connect:** use host LAN IP, check private-network firewall, broker IPv4 LAN listener, Wi-Fi isolation and credentials. The implementation test broker used loopback-only port 18884; that is not reachable from ESP32.
- **No ESP32 windows:** check NTP synchronization, DS18B20 pinout, external pull-up, 3.3V logic, powered rather than parasite wiring, GPIO assignment and serial output.
- **Old/future or overlapping-window rejection:** synchronize publisher clocks and run only one simulation publisher. Do not reuse static example timestamps or reset custom publisher sequences during a session.
- **Simulator has no outgoing windows:** enable Start INDUX publisher and Resume, then check its MQTT status. Hidden or closed browser tabs no longer stop server publication.
- **Gradual heating not flagged:** warm-up/baseline adaptation can absorb slow changes. Stabilize the normal condition before changing it, or use the deterministic ten-window scenario. Z-score is a demonstration, not a validated industrial model.
- **Stale old value:** the last value/history remains visible for context, but the state becomes DISCONNECTED and is not labeled live. Source changes clear it entirely.
- **Refreshing clears nothing; backend restart clears everything:** state is intentionally in memory. There is no durable telemetry history. QoS 1 permits duplicates; deduplication is process-local. Old/offline backlog is deliberately rejected.
- **Legacy panels still show sample machines/alerts:** only the live temperature card is connected in this sprint. These panels are explicitly labeled; unrelated functionality remains unchanged.
- **Out of scope:** vibration ingestion, Isolation Forest execution, RAG, databases, manufacturer limits, OPC UA, additional sensors, production deployment, advanced authorization and motor control through the dashboard.

Implementation references: [Paho's asynchronous connection/network-loop API](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html), [DallasTemperature library](https://github.com/milesburton/Arduino-Temperature-Control-Library), and [ESP-MQTT](https://docs.espressif.com/projects/esp-idf/en/v4.4.8/esp32/api-reference/protocols/mqtt.html).
