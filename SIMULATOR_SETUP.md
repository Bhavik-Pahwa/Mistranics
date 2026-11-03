# Mistranics prototype: Industrial and Hands-on workspaces

## Run locally

The entry screen at http://127.0.0.1:5173 always asks which workspace to open. Industrial Mode shows simulated operations; Hands-on Mode shows only physical-source telemetry and anomaly detection. The Workspaces action returns to the entry screen. Choosing a workspace never changes another browser's data source.

Install Python dependencies in the repository virtual environment and frontend dependencies:

```powershell
.\.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
```

Start Mosquitto (installed separately). The supplied local configuration listens on port 1883:

```powershell
& 'C:\Program Files\Mosquitto\mosquitto.exe' -c backend/mosquitto.conf
```

In another terminal, from the repository root:

```powershell
$env:IOT_ENABLED='true'
$env:MQTT_ENABLED='true'
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='1883'
$env:SIMULATOR_PUBLISH_ENABLED='true'
.\.venv\Scripts\python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Then start the frontend:

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1
```

Run **one backend worker**, because the simulation and bounded telemetry histories belong to that process. This prototype profile does not require PostgreSQL or an LLM. The original database/AI application remains available with `IOT_ENABLED=false`.

Use the same MQTT host and port for the backend and physical publisher. The normal local broker uses **1883**; **18884** is a separate test broker. Publishing to 18884 while the backend listens on 1883 will leave the physical graph empty. Do not run a second simulation publisher with the same `simulation-01` device ID.

## Live ESP32 readings over USB

The working sketch sends `Temperature: ...` lines on **COM5 at 9600 baud**. Serial output needs the USB-to-MQTT bridge before it can reach the frontend. Start the backend, broker and frontend as above, then run this from the repository root in another terminal:

```powershell
.\Start-LiveReadings.ps1
```

Keep that terminal running and open **Hands-on Mode** at http://127.0.0.1:5173. Close Arduino Serial Monitor before opening the bridge because only one program can own COM5. The bridge reads actual sensor measurements and publishes physical-source windows through MQTT; it does not flash or change the ESP32 firmware.

For a different port or broker, pass the settings explicitly and use the same broker settings for the backend:

```powershell
.\Start-LiveReadings.ps1 -SerialPort COM5 -Baud 9600 -BrokerHost 127.0.0.1 -BrokerPort 1883
```

The bridge logs the broker, port, topic, actual serial temperatures and published windows. The backend's `/api/status?source=physical` should report `stream_status: LIVE`, and the graph should match the serial temperature. With the current sketch, a measurement arrives approximately every 5.5 seconds.

## Workspaces

- **Industrial:** preserves the fleet dashboard layout, with a server-connected Prototype motor and clearly marked illustrative fleet datasets. Temperature, current, vibration, RPM, all three acceleration axes, and all three gyroscope axes can be selected in the motor graph. Open machine analytics to inspect readings with their actual units.
- **Investigations:** searchable alert cards, open/resolved filters, and keyboard-accessible dialogs with anomaly evidence and troubleshooting steps. Simulator anomalies are added while the workspace is open. The latest 300 records and resolutions are saved in this browser.
- **Knowledge manuals:** machine illustrations and readable prototype inspection guides. These are not supplied OEM manuals.
- **Admin:** use `admin@mistranics.com` / `admin123`. Onboard machines and edit names, codes, location, type, and configured sensors. Changes persist locally and appear throughout the workspace. Sensor configuration controls the motor graph tabs; it does not provision hardware or change the server's validated publisher identities. This is a dummy login, not production authentication.
- **Chat:** centered composer, selected machine and machine-specific conversation history. Conversations persist in this browser. Replies summarize workspace data; no new LLM/RAG connection is claimed.
- **Hands-on:** a single page with the physical sensor graph, red anomaly points, and detection cards containing time, device, sequence, observed value, baseline, z-score, threshold, and sample count. No chatbot or diagnostic AI. All sensors supplied by the hardware publisher are displayed; existing temperature-only firmware remains compatible. Stream errors and disconnects are distinct from normal readings.

Machine onboarding does not synthesize readings. A newly registered machine remains awaiting data until an acquisition integration is provided. Illustrative fleet machines remain static samples; only the Prototype motor is driven by the server simulator.

## Simulator server

Open http://127.0.0.1:5173/simulator to control the model. The server reuses **Simulator.html** as a viewer and replaces its browser-side generator with `backend/examples/simulator_frontend.js`. Physics continues if the viewer closes.

`backend/app/simulator.py` ports the source's fixed 1 ms sensor sampling, 400-sample buffers, 20 ms model frames, thermal response, current model, and all nine fault modes:

`normal`, `imb`, `mis`, `brg`, `loose`, `heat`, `over`, `short`, `stall`.

Current uses the original speed/load relationship, fault-specific increases and ripple, and smoothing. Stall uses the faster thermal time constant. The model's illustrative WARNING/FAULT labels are separate from the statistical detector.

Publishing starts automatically. Set `SIMULATOR_PUBLISH_ENABLED=false` to opt out. Pause and publisher controls are available in the simulator viewer; there are no reading-source toggles inside either frontend workspace.

```text
Simulator.html equations -> Python motor model -> 3-second sensor windows
                                                        |
                                                        v
Hardware firmware / serial bridge ------------------> MQTT broker
                                                        |
                                                        v
                                    validation + duplicate detection
                                                        |
                                     independent source / sensor baselines
                                                        |
                                                        v
                              source-scoped WebSocket -> graphs + anomalies
```

All dashboard readings pass through MQTT QoS 1. Simulator control HTTP responses and `/ws/simulation` are viewer state only and do not inject data into dashboard histories. Each source keeps at most 60 windows in memory. A broker interruption triggers reconnects; stale readings remain visible as history with an unavailable stream status. Histories and baselines reset on backend restart.

## API and payload

| Endpoint | Purpose |
| --- | --- |
| `GET /api/simulation` | Model state, all sensor waveforms, current, controls, publisher counters |
| `PATCH /api/simulation` | Mode, RPM 0–3000, severity 0–100, paused, publisher_enabled |
| `POST /api/simulation/cool-down` | Reset modeled temperature to 28 °C |
| `WS /ws/simulation` | Server viewer updates |
| `GET /api/status?source=simulation` | Processed Industrial stream |
| `GET /api/status?source=physical` | Processed Hands-on stream |
| `WS /ws/telemetry?source=simulation` | Industrial telemetry subscription |
| `WS /ws/telemetry?source=physical` | Hands-on telemetry subscription |

`/api/telemetry/latest` supports the same source query. The legacy `/api/source` selection affects only endpoints without a source query; the new workspaces do not call it.

The existing schema-version-1 envelope and required `temperature` object are unchanged. Optional `sensors` carries `current`, `vibration`, `rpm`, `ax`, `ay`, `az`, `gx`, `gy`, `gz`. Each sensor has `mean`, `min`, `max`, `sample_count`, `unit`, and `status`:

```json
"sensors": {
  "current": {"mean": 1.6, "min": 1.58, "max": 1.62, "sample_count": 3, "unit": "A", "status": "valid"},
  "vibration": {"mean": 0.025, "min": 0.023, "max": 0.027, "sample_count": 3, "unit": "g", "status": "valid"}
}
```

Units: temperature `degC`, current `A`, acceleration/vibration `g`, gyroscope `deg/s`, speed `rpm`. Acceleration is not mislabeled as velocity in mm/s. Invalid values, non-finite numbers, inconsistent min/mean/max, incorrect units, overlapping windows, unexpected device identities, and stale/future packets are rejected. Error/disconnected sensors require null features and zero samples.

Each sensor gets an independent rolling z-score detector. It evaluates against previous values, begins after 5 valid baseline windows, and flags absolute z-scores of at least 3 by default. This detects deviations; it is not a manufacturer-limit or fault-diagnosis model. Legacy top-level temperature fields remain available, while `latest.readings` contains every sensor's statistics and detector result.

## Validation

```powershell
npm --prefix frontend run build
npm --prefix frontend run lint
Set-Location backend
..\.venv\Scripts\python -m pytest -q
$env:RUN_MQTT_TESTS='1'
..\.venv\Scripts\python -m pytest tests/test_iot.py tests/test_simulator.py tests/test_revamp.py -q
```

Optional browser tests require Playwright, Chrome, and the running local stack:

```powershell
$env:RUN_BROWSER_TESTS='1'
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='18884'
..\.venv\Scripts\python -m pytest tests/test_iot_browser.py -q
```

Browser tests publish synthetic physical-source fixtures to verify anomaly presentation; they do not verify a physical sensor. Screenshots are saved under `.iot-test/`. The real-MQTT test starts its own isolated broker and exercises duplicates, malformed packets, reconnects, and server publishing.
