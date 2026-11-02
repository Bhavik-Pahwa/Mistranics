"""Single-process, bounded, database-free temperature evaluation pipeline."""
import asyncio
import logging
import threading
import time
import uuid
import anyio
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from statistics import fmean, pstdev
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, ConfigDict, Field, AwareDatetime, model_validator, field_validator

from .mqtt import Subscriber
from .simulator import MotorSimulator, register_simulator_routes

log = logging.getLogger(__name__)
Source = Literal["physical", "simulation"]


class Temperature(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    mean: float | None
    min: float | None
    max: float | None
    unit: Literal["degC"]
    sample_count: int = Field(ge=0, le=100)
    status: Literal["valid", "error", "disconnected"]

    @model_validator(mode="after")
    def features(self):
        if self.status == "valid":
            if self.sample_count == 0 or any(v is None for v in (self.min, self.mean, self.max)):
                raise ValueError("Valid windows require samples and numeric features")
            # DS18B20 acquisition range, NOT a motor operating/manufacturer limit.
            if not -55 <= self.min <= self.mean <= self.max <= 125:
                raise ValueError("Temperature features outside probe range or inconsistent")
        elif self.sample_count != 0 or any(v is not None for v in (self.min, self.mean, self.max)):
            raise ValueError("Sensor errors require null features and zero samples")
        return self


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: int = Field(strict=True, ge=1, le=1)
    device_id: str = Field(strict=True, min_length=1, max_length=64)
    source: Source
    sequence: int = Field(strict=True, ge=1, le=9_007_199_254_740_991)
    window_start: AwareDatetime
    window_end: AwareDatetime
    window_duration_seconds: float = Field(strict=True, ge=3, le=3)
    temperature: Temperature

    @field_validator("window_start", "window_end", mode="before")
    @classmethod
    def iso_timestamp(cls, value):
        if not isinstance(value, str):
            raise ValueError("Timestamp must be an ISO-8601 string with timezone")
        return value

    @model_validator(mode="after")
    def timestamps(self):
        if abs((self.window_end - self.window_start).total_seconds() - 3) > 0.01:
            raise ValueError("Expected one non-overlapping three-second window")
        return self


class SourceSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Source


class RollingZScore:
    def __init__(self, settings):
        if settings.anomaly_min_baseline_samples > settings.anomaly_baseline_size:
            raise ValueError("Minimum baseline samples must not exceed baseline size")
        self.settings = settings
        self.values = deque(maxlen=settings.anomaly_baseline_size)

    def evaluate(self, value):
        result = dict(status="WARMING_UP", method="STATISTICAL_Z_SCORE", value=value,
                      baseline_mean=None, baseline_std=None, z_score=None,
                      baseline_samples=len(self.values), threshold=self.settings.anomaly_z_threshold)
        if len(self.values) >= self.settings.anomaly_min_baseline_samples:
            mean = fmean(self.values)
            std = max(pstdev(self.values), self.settings.anomaly_std_floor)
            z = (value - mean) / std
            result.update(status="ANOMALY" if abs(z) >= self.settings.anomaly_z_threshold else "NORMAL",
                          baseline_mean=mean, baseline_std=std, z_score=z)
        self.values.append(value)  # Evaluate first; never train on the current value first.
        return result


class TelemetryState:
    def __init__(self, settings):
        self.settings = settings
        self.lock = threading.RLock()
        self.session_id = str(uuid.uuid4())
        self.revision = 0
        self.source = settings.iot_source
        self.mqtt_connected = False
        self.latest = None
        self.history = deque(maxlen=60)
        self.detector = RollingZScore(settings)
        self.last_received = None
        self.last_received_monotonic = None
        self.selected_at = datetime.now(timezone.utc)
        # Exactly two configured publishers: bounded dedup state survives source switches.
        self.publishers = {"physical": settings.iot_physical_device,
                           "simulation": settings.iot_simulation_device}
        self.sequences = {}
        self.window_ends = {}
        self.notify = lambda: None

    def connected(self, value):
        with self.lock:
            self.mqtt_connected = value
            self.revision += 1
            self.notify()

    def select(self, source):
        with self.lock:
            if source != self.source:
                self.source = source
                self.selected_at = datetime.now(timezone.utc)
                self.latest = None
                self.history.clear()
                self.detector.values.clear()
                self.last_received = self.last_received_monotonic = None
                self.revision += 1
                self.notify()
            return self.snapshot()

    def consume(self, payload):
        window = Window.model_validate(payload)
        now = datetime.now(timezone.utc)
        if window.device_id != self.publishers[window.source]:
            raise ValueError("Unexpected device for source")
        age = (now - window.window_end).total_seconds()
        if age > self.settings.telemetry_stale_after_seconds or age < -2:
            raise ValueError("Old/future telemetry; check publisher clock")
        key = (window.source, window.device_id)
        with self.lock:
            if window.sequence <= self.sequences.get(key, 0):
                log.info("MQTT duplicate/out-of-order sequence ignored source=%s", window.source)
                return
            previous_end = self.window_ends.get(key)
            if previous_end and window.window_start < previous_end:
                raise ValueError("Overlapping or out-of-order window")
            self.sequences[key] = window.sequence
            self.window_ends[key] = window.window_end
            if window.source != self.source or window.window_end <= self.selected_at:
                return
            temperature = window.temperature
            if temperature.status == "valid":
                anomaly = self.detector.evaluate(temperature.mean)
            else:
                anomaly = dict(status="SENSOR_ERROR", method="STATISTICAL_Z_SCORE", value=None,
                               baseline_mean=None, baseline_std=None, z_score=None,
                               baseline_samples=len(self.detector.values),
                               threshold=self.settings.anomaly_z_threshold)
            self.latest = dict(source=window.source, device_id=window.device_id,
                               sequence=window.sequence, timestamp=window.window_end.isoformat(),
                               window_start=window.window_start.isoformat(),
                               window_duration_seconds=3, temperature=temperature.mean,
                               unit=temperature.unit, sample_count=temperature.sample_count,
                               sensor_status=temperature.status, anomaly=anomaly)
            self.history.append(self.latest)
            self.last_received = now.isoformat()
            self.last_received_monotonic = time.monotonic()
            self.revision += 1
            self.notify()
            log.info("Telemetry source=%s sequence=%s temperature=%s status=%s",
                     window.source, window.sequence, temperature.mean, anomaly["status"])

    def snapshot(self):
        with self.lock:
            stale = self.last_received_monotonic is None or (
                time.monotonic() - self.last_received_monotonic > self.settings.telemetry_stale_after_seconds)
            if self.latest and (datetime.now(timezone.utc) - datetime.fromisoformat(
                    self.latest["timestamp"])).total_seconds() > self.settings.telemetry_stale_after_seconds:
                stale = True
            stream = "DISCONNECTED" if stale or not self.mqtt_connected else (
                "SENSOR_ERROR" if self.latest["sensor_status"] != "valid" else "LIVE")
            return dict(type="state", session_id=self.session_id, revision=self.revision,
                        source=self.source, mqtt_connected=self.mqtt_connected, stream_status=stream,
                        stale_after_seconds=self.settings.telemetry_stale_after_seconds,
                        last_received_at=self.last_received, latest=self.latest, history=list(self.history))


def create_iot_app(settings):
    state = TelemetryState(settings)
    listeners = set()
    motor = MotorSimulator(settings)

    def wake():
        for event in tuple(listeners):
            event.set()

    @asynccontextmanager
    async def lifespan(app):
        loop = asyncio.get_running_loop()
        state.notify = lambda: loop.call_soon_threadsafe(wake)
        mqtt_settings = settings.model_copy(update={"mqtt_topic": settings.iot_topic, "mqtt_qos": 1})
        subscriber = Subscriber(mqtt_settings, consume=state.consume, connection_changed=state.connected)
        app.state.mqtt_subscriber = subscriber
        if settings.mqtt_enabled:
            subscriber.start()
        motor.start()
        try:
            yield
        finally:
            await asyncio.to_thread(motor.stop)
            if settings.mqtt_enabled:
                await asyncio.to_thread(subscriber.stop)
            state.notify = lambda: None

    app = FastAPI(title="INDUX live temperature", lifespan=lifespan)
    app.state.telemetry = state
    app.state.simulator = motor
    register_simulator_routes(app, motor)

    @app.get("/simulator", response_class=HTMLResponse)
    async def simulator():
        # Reuse the supplied layout; replace browser physics with a server-state viewer.
        path = Path(__file__).resolve().parents[2] / "ESP32 + MPU6050 Motor Simulator.html"
        html = await asyncio.to_thread(path.read_text, encoding="utf-8")
        before, _, script = html.partition("<script>")
        _, _, after = script.partition("</script>")
        return before + '<script src="/api/simulation/frontend.js"></script>' + after

    @app.get("/api/simulation/frontend.js")
    async def simulation_frontend():
        return FileResponse(Path(__file__).resolve().parents[1] / "examples" / "simulator_frontend.js",
                            media_type="text/javascript")

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": "iot", "mqtt_enabled": settings.mqtt_enabled}

    @app.get("/api/source")
    @app.get("/api/status")
    @app.get("/api/telemetry/latest")
    async def snapshot():
        return state.snapshot()

    @app.post("/api/source")
    async def select(payload: SourceSelection):
        return state.select(payload.source)

    @app.websocket("/ws/telemetry")
    async def telemetry_socket(websocket: WebSocket):
        await websocket.accept()
        event = asyncio.Event()
        listeners.add(event)

        async def send():
            while True:
                event.clear()
                # Snapshots include bounded history; slow clients can safely coalesce updates.
                await asyncio.wait_for(websocket.send_json(state.snapshot()), timeout=5)
                try:
                    await asyncio.wait_for(event.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass  # Heartbeat also recomputes stale stream status.

        sender = asyncio.create_task(send())
        receiver = asyncio.create_task(websocket.receive_text())
        try:
            done, _ = await asyncio.wait((sender, receiver), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
            pass
        finally:
            listeners.discard(event)
            sender.cancel()
            receiver.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(sender, receiver, return_exceptions=True)
                try:
                    await websocket.close()
                except (RuntimeError, WebSocketDisconnect):
                    pass

    return app
