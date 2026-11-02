# Server simulator and physical ESP32 readings

## What runs where

The simulator is now a server process inside the existing FastAPI application. `backend/app/simulator.py` ports the equations from `ESP32 + MPU6050 Motor Simulator.html`: 1 kHz accelerometer/gyroscope samples, 400-sample waveforms, RMS, thermal response, and Normal / Imbalance / Misalignment / Bearing fault / Loose mount / Overheating modes. It uses fixed 20 ms frames and the original thermal target/time constant. The original browser's frame-dependent RMS smoothing is consequently evaluated at a consistent 50 Hz. Noise remains simulated.

The page at `/simulator` reuses the supplied HTML layout but replaces its original script with `backend/examples/simulator_frontend.js`. This script only displays server state and sends control requests; it does not generate sensor readings. All browser windows share one motor. Closing or hiding the page does not stop it, change controls, or stop MQTT publishing. Refreshing reconnects to the current state.

The motor runs when the backend starts; **MQTT publication initially stays off**. Start/stop the publisher independently of pausing/resuming the motor. Restarting the backend resets the model and stops publication. Run only one backend worker.

```text
Server motor model → 3-second temperature windows → MQTT QoS 1
                                                   ↓
DS18B20 → ESP32 working sketch → USB serial bridge → MQTT
                                                   ↓
backend MQTT subscriber → Z-score → dashboard WebSocket
```

The simulator has its own MQTT client. Neither its HTTP control endpoints nor its viewing WebSocket inject dashboard readings directly. Waveforms remain available on the simulator page and its API; only temperature is published to the existing INDUX topic. The original demo WARNING/FAULT labels remain clearly identified as illustrative, separate from the dashboard's statistical detector.

## Running preview

- Dashboard: `http://127.0.0.1:5173`
- Server simulator: `http://127.0.0.1:5173/simulator`
- Interactive API documentation: `http://127.0.0.1:8000/docs` (also proxied at `http://127.0.0.1:5173/docs`)
- Current local test broker: `127.0.0.1:18884`, topic `indux/device-01/telemetry`.

Select **Simulation** on the dashboard and click **Start INDUX publisher** on the simulator page. Change RPM, severity or mode, then return to the dashboard; publishing continues. The first five valid windows build the statistical baseline. Stop the publisher to demonstrate stale-stream detection. Do not run the separate CLI simulator at the same time because it shares the simulation publisher identity.

## Start from a fresh terminal

At `D:\Work\Dev\Mistranics`:

```powershell
.\.venv\Scripts\python -m pip install -r backend/requirements-hardware.txt
$env:IOT_ENABLED='true'
$env:MQTT_ENABLED='true'
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='18884' # Current preview broker; use 1883 for the supplied normal broker config.
.\.venv\Scripts\python -m uvicorn backend.app.main:create_app --factory --port 8000
```

In another terminal:

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1
```

For broker setup and the alternative ESP32 Wi-Fi firmware, see `HARDWARE_IOT_IMPLEMENTATION.md`. Start a new backend only after stopping any older instance on port 8000. No additional server runtime dependency is required for the simulator; the physical USB bridge adds `pyserial==3.5` in an optional hardware requirements file.

## Simulator HTTP/OpenAPI endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/simulation` | Current server-generated readings, waveforms, temperature history, controls, and MQTT status |
| `PATCH /api/simulation` | Change any subset of `mode`, `rpm` (0–3000), `severity` (0–100), `paused`, `publisher_enabled` |
| `POST /api/simulation/cool-down` | Reset temperature to 28°C, matching the original button |
| `WS /ws/simulation` | Read-only state stream at 10 updates/second; immediate snapshot on reconnect |
| `GET /api/status` | Processed active-source dashboard state, independent of simulator controls |
| `POST /api/source` | Select `physical` or `simulation` for the dashboard |

Mode values: `normal`, `imb`, `mis`, `brg`, `loose`, `heat`. Controls are server-authoritative and shared by all clients. Invalid values return HTTP 422. Full schema is in `/openapi.json`. These local evaluation APIs are unauthenticated; there is no public deployment.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/simulation
Invoke-RestMethod http://127.0.0.1:8000/api/simulation -Method Patch -ContentType application/json -Body '{"mode":"heat","rpm":2000,"severity":90,"publisher_enabled":true}'
Invoke-RestMethod http://127.0.0.1:8000/api/simulation -Method Patch -ContentType application/json -Body '{"paused":true}'
Invoke-RestMethod http://127.0.0.1:8000/api/simulation/cool-down -Method Post
Invoke-RestMethod http://127.0.0.1:8000/api/simulation -Method Patch -ContentType application/json -Body '{"paused":false,"publisher_enabled":false}'
```

## Physical readings using the working Arduino sketch

Confirmed user hardware: **ESP32 Dev Module**, DS18B20 DATA on **GPIO 19**, Arduino serial output at **9600 baud**. The existing sketch remains unchanged; no firmware was uploaded. Actual serial readings of **29.56–29.69°C** were received on **COM5**, forwarded through the real broker, and displayed on the dashboard as Physical Sensor / Live. A screenshot is in `.iot-test/real-ds18b20.png` (ignored local verification artifact).

Close Arduino Serial Monitor/Serial Plotter before starting the bridge; only one process can own COM5. Keep the board connected over USB:

```powershell
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='18884' # Match the backend/broker.
.\.venv\Scripts\python -m backend.examples.serial_sensor --port COM5 --baud 9600
```

Select **Physical Sensor** on the dashboard. Stop the bridge with Ctrl+C before reopening Arduino Serial Monitor. The bridge retries if USB is disconnected or temporarily busy. To run a bounded acquisition check, append `--duration 40`.

The user's sketch includes a five-second delay plus conversion time. The bridge timestamps each received measurement on the host and groups it into non-overlapping three-second windows. Most published windows therefore contain **one actual sample**; empty windows are omitted. It never copies the last value into empty windows or fabricates intermediate readings. Negative DS18B20 disconnect values such as −127°C produce an explicit error window; USB silence eventually makes the stream stale. Host receive timestamps are used because this sketch supplies no device timestamps. This route requires the USB host and bridge process; direct Wi-Fi publishing remains an optional, separately configured firmware route.

The optional firmware's GPIO default has also been corrected to **19**. Its upload and Wi-Fi behavior have not been hardware-tested. Wiring still requires ESP32-safe 3.3V DATA logic and the actual pull-up resistor (typically 4.7 kΩ to 3.3V).

## Validation

Latest results: **70 backend tests passed**, including real Mosquitto/server-simulator integration, with four optional checks skipped. The running-stack browser test passed, including controls, closed-viewer publication, reopening with preserved controls, pause/resume and reconnects. Frontend production build passed; lint has only two existing chatbot warnings. Actual COM5 measurements were verified separately from synthetic test fixtures.

```powershell
Set-Location backend
$env:RUN_MQTT_TESTS='1'
..\.venv\Scripts\python -m pytest tests -q
# With the local stack running and the physical serial bridge stopped:
$env:RUN_BROWSER_TESTS='1'
$env:MQTT_HOST='127.0.0.1'
$env:MQTT_PORT='18884'
..\.venv\Scripts\python -m pytest tests/test_iot_browser.py -q
```

The backend suite covers the thermal equation, all six modes, bounded/finite signals, validation, server controls, publishing with no viewers, broker reconnection, and serial aggregation without invented samples. Browser tests use synthetic physical-source fixtures: stop the real serial bridge before running them to avoid overlapping publishers. Those fixtures are separate from the actual COM5 acquisition described above.
