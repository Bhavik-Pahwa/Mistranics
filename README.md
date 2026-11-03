# Mistranics — Industrial Predictive Maintenance & IoT Analytics

Mistranics is an industrial IoT and predictive maintenance platform featuring real-time motor simulation, hardware telemetry streaming (ESP32 DS18B20 / MPU6050), statistical anomaly detection, and offline-trained Machine Learning Isolation Forest models.

---

## Quickstart with Docker Compose

To build and run all services in containers, simply execute:

```bash
docker compose up
```

*(Add `-d` to run in the background: `docker compose up -d`)*

### Running Services

When Docker Compose starts, the following services are spun up:

| Service | Container Name | Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend** | `mistranics-frontend` | `http://localhost:5173` | React 19 + Vite SPA served via Nginx reverse proxy |
| **Backend** | `mistranics-backend` | `http://localhost:8000` | FastAPI IoT streaming, Isolation Forest ML evaluation & Simulator |
| **MQTT Broker** | `mistranics-mqtt` | `localhost:1883` | Eclipse Mosquitto 2.x message broker |
| **Serial Bridge** | `mistranics-serial-bridge` | Internal | USB-to-MQTT telemetry bridge (with automatic hardware detection & standby fallback) |
| **PostgreSQL** *(Optional)* | `mistranics-postgres` | `localhost:5432` | Relational database (activated with `docker compose --profile db up`) |

### Accessing the Platform

- **Dashboard UI**: [http://localhost:5173](http://localhost:5173) (or [http://localhost](http://localhost))
- **Interactive Simulator**: [http://localhost:5173/simulator](http://localhost:5173/simulator)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) (or [http://localhost:5173/docs](http://localhost:5173/docs))
- **Live WebSocket Telemetry**: `ws://localhost:5173/ws/telemetry`

---

## Stopping the Containers

```bash
docker compose down
```

To remove all volumes as well:

```bash
docker compose down -v
```

---

## Architecture Overview

```
                      +-----------------------------+
                      |       Web Browser           |
                      |  http://localhost:5173      |
                      +--------------+--------------+
                                     |
                                     | (HTTP & WS)
                                     v
                      +-----------------------------+
                      |   mistranics-frontend       |
                      |  (Nginx SPA + Reverse Proxy)|
                      +--------------+--------------+
                                     |
                                     | (Reverse Proxy /api, /ws, /simulator)
                                     v
                      +-----------------------------+
                      |   mistranics-backend        |
                      |  (FastAPI + ML Isolation)   |
                      +--------------+--------------+
                                     |
                                     | (MQTT Sub & Pub)
                                     v
                      +-----------------------------+
                      |   mistranics-mqtt           |
                      |  (Eclipse Mosquitto 2.x)    |
                      +--------------+--------------+
                                     ^
                                     | (MQTT Publish: indux/device-01/telemetry)
                      +--------------+--------------+
                      |   mistranics-serial-bridge  |
                      |  (USB Hardware / Standby)   |
                      +-----------------------------+
```

---

## Physical Hardware Connection (Optional)

When deploying with a physical ESP32 or DS18B20 sensor:
1. On Windows, install the Silicon Labs CP210x driver via [`driver_cp210x/CP210xVCPInstaller_x64.exe`](driver_cp210x/CP210xVCPInstaller_x64.exe).
2. On Linux / Docker hosts with hardware access, map your serial device in `docker-compose.yml`:
   ```yaml
   devices:
     - "/dev/ttyUSB0:/dev/ttyUSB0"
   ```
   The bridge will automatically detect and stream from the physical sensor.

