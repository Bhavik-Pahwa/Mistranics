"""Server-owned port of Simulator.html, including ACS712 current and electrical faults.

Sensor generation runs once per backend process, independently of browser clients.
Temperature, current, acceleration, gyroscope, vibration and speed travel through MQTT.
"""
import asyncio
import json
import logging
import math
import random
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from statistics import fmean
from typing import Literal

import anyio
import paho.mqtt.client as mqtt
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field

from .mqtt import configure_client

log = logging.getLogger(__name__)
MODES = {
    "normal": ("Normal", "Healthy motor: small residual vibration at shaft frequency."),
    "imb": ("Imbalance", "Heavy rotor spot: 1x vibration increases with speed squared."),
    "mis": ("Misalignment", "Coupling offset: 2x harmonics, axial vibration and heating."),
    "brg": ("Bearing fault", "Periodic bearing impulses, ring-down and friction heating."),
    "loose": ("Loose mount", "Random knocks and a half-frequency rattle."),
    "heat": ("Overheating", "Reduced cooling increases the model's thermal target."),
    "over": ("Overload", "Excess shaft torque raises current and reduces speed."),
    "short": ("Winding short", "Shorted turns create high current and a 100 Hz hum."),
    "stall": ("Stall", "Locked rotor draws high current and heats rapidly."),
}
EXTRA = dict(normal=0, imb=6, mis=10, brg=25, loose=3, heat=45, over=30, short=35, stall=55)
EXTRA_I = dict(normal=0, imb=0.05, mis=0.15, brg=0.25, loose=0.03, heat=0.10, over=1.6, short=1.5, stall=4.5)
KEYS = ("ax", "ay", "az", "gx", "gy", "gz", "cur")


class SimulationControl(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    mode: Literal["normal", "imb", "mis", "brg", "loose", "heat", "over", "short", "stall"] | None = None
    rpm: float | None = Field(default=None, ge=0, le=3000)
    severity: float | None = Field(default=None, ge=0, le=100)
    paused: bool | None = None
    publisher_enabled: bool | None = None


class MotorModel:
    """Original formulas, using fixed 20 ms frames and 1 ms sensor samples."""
    def __init__(self, seed=None):
        self.random = random.Random(seed)
        self.rpm, self.severity, self.mode = 1500.0, 60.0, "normal"
        self.temperature, self.rms = 28.0, 0.0
        self.current = self.sample_time = 0.0
        self.phase = self.bearing_phase = self.impulse = self.impulse_time = 0.0
        self.rotation = self.accumulator = self.history_time = self.serial_time = 0.0
        self.paused = False
        self.buffers = {key: deque([1.0 if key == "az" else 0.0] * 400, maxlen=400) for key in KEYS}
        self.history = deque(maxlen=120)
        self.lines = deque(["Server MPU6050 simulation initialized; 8G / 500dps"], maxlen=40)

    def noise(self, sd):
        return (sum(self.random.random() for _ in range(3)) - 1.5) * 2 * sd

    def sample(self):
        severity = self.severity / 100
        effective_rpm = self.rpm * (1 - {"over": 0.12, "stall": 0.95}.get(self.mode, 0) * severity)
        f, scale = effective_rpm / 60, (effective_rpm / 1500) ** 2
        self.sample_time += 0.001
        self.phase = (self.phase + 2 * math.pi * f * 0.001) % (4 * math.pi)
        vx = vy = vz = 0.0
        di = 0.0
        if self.rpm > 0:
            vx = 0.025 * scale * math.sin(self.phase)
            vy = 0.02 * scale * math.cos(self.phase)
            di = 0.02 * scale * math.sin(self.phase + 1)
            if self.mode == "imb":
                vx += 0.45 * severity * scale * math.sin(self.phase)
                vy += 0.45 * severity * scale * math.cos(self.phase)
                di += 0.05 * severity * scale * math.sin(self.phase + 0.5)
            elif self.mode == "mis":
                vx += 0.3 * severity * scale * math.sin(2 * self.phase)
                vy += 0.12 * severity * scale * math.sin(self.phase + 1)
                vz += 0.3 * severity * scale * math.sin(2 * self.phase + 1)
                di += 0.08 * severity * scale * math.sin(2 * self.phase)
            elif self.mode == "brg":
                self.bearing_phase += 3.57 * f * 0.001
                if self.bearing_phase >= 1:
                    self.bearing_phase -= 1
                    self.impulse = 1.1 * severity * (0.8 + self.random.random() * 0.4)
                    self.impulse_time = 0
                impulse = self.impulse * math.exp(-self.impulse_time / 0.004) * math.cos(2 * math.pi * 190 * self.impulse_time)
                self.impulse_time += 0.001
                vx += impulse
                vy += impulse * 0.5
                vz += impulse * 0.8
                di += 0.12 * impulse
            elif self.mode == "loose":
                if self.random.random() < 0.025 * severity:
                    self.impulse = (0.6 + self.random.random() * 1.6) * severity
                    self.impulse_time = 0
                impulse = self.impulse * math.exp(-self.impulse_time / 0.006) * math.cos(2 * math.pi * 160 * self.impulse_time)
                self.impulse_time += 0.001
                vx += impulse + 0.15 * severity * scale * math.sin(self.phase / 2)
                vz += impulse * 0.7
                di += 0.06 * impulse
            elif self.mode == "heat":
                vx += 0.04 * severity * math.sin(self.phase)
            elif self.mode == "over":
                vx += 0.05 * severity * scale * math.sin(self.phase)
                di += 0.05 * severity * math.sin(self.phase)
            elif self.mode == "short":
                hum = math.sin(2 * math.pi * 100 * self.sample_time)
                vx += 0.10 * severity * hum
                vy += 0.04 * severity * hum
                vz += 0.06 * severity * hum
                di += 0.35 * severity * math.sin(2 * math.pi * 100 * self.sample_time + 0.7)
        current = max(0, 0.6 + self.rpm / 1500 * (1 + EXTRA_I[self.mode] * severity) + di + self.noise(0.02)) if self.rpm > 0 else 0.0
        readings = (vx + self.noise(0.012), vy + self.noise(0.012), 1 + vz + self.noise(0.012),
                    vy * 70 + self.noise(0.6), -vx * 70 + self.noise(0.6), vx * 25 + self.noise(0.6), current)
        for key, value in zip(KEYS, readings):
            self.buffers[key].append(value)

    def step(self, dt=0.02):
        if self.paused:
            return
        self.accumulator += dt * 1000
        while self.accumulator >= 1:
            self.sample()
            self.accumulator -= 1
        target = 26 + 22 * self.rpm / 3000
        if self.rpm > 0 or self.mode == "heat":
            target += EXTRA[self.mode] * self.severity / 100
        self.temperature += (target - self.temperature) * dt / (6 if self.mode == "stall" else 12)
        self.current = self.current * 0.85 + fmean(list(self.buffers["cur"])[-200:]) * 0.15
        variance = 0
        for key in KEYS[:3]:
            values = list(self.buffers[key])[-200:]
            mean = fmean(values)
            variance += sum((value - mean) ** 2 for value in values) / 200
        self.rms = self.rms * 0.85 + math.sqrt(variance) * 0.15
        self.rotation = (self.rotation + 360 * self.rpm / 60 * dt * 0.1) % 360
        self.history_time += dt
        self.serial_time += dt
        if self.history_time >= 0.5:
            self.history_time -= 0.5
            self.history.append(self.temperature)
        if self.serial_time >= 3:
            self.serial_time -= 3
            self.lines.append(" ".join(f"{key}={self.buffers[key][-1]:.2f}" for key in ("ax", "ay", "az", "gz"))
                              + f" I={self.current:.2f} T={self.temperature + self.noise(0.05):.1f} rms={self.rms:.3f} {self.demo_status()}")

    def demo_status(self):
        ratio = self.current / (0.6 + self.rpm / 1500) if self.rpm > 0 else 0
        return "FAULT" if self.rms > 0.35 or self.temperature > 75 or ratio > 1.9 else (
            "WARNING" if self.rms > 0.15 or self.temperature > 60 or ratio > 1.35 else "NORMAL")

    def sensors(self):
        values = {key: self.buffers[key][-1] for key in KEYS if key != "cur"}
        values.update(current=self.current, vibration=self.rms, rpm=self.rpm)
        return values


class MotorSimulator:
    def __init__(self, settings):
        self.settings = settings
        self.model = MotorModel()
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.publisher_enabled = settings.simulator_publish_enabled
        self.connected = False
        self.revision = 0
        self.sequence = time.time_ns() // 1000
        self.window = None
        self.pending = {}
        self.last_window = self.last_acknowledged = None
        self.published_windows = self.dropped_windows = 0
        self.error = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                  client_id=settings.mqtt_client_id + "-motor-simulator")
        configure_client(self.client, settings)
        self.client.max_queued_messages_set(2)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect_fail = lambda *_: self.on_disconnect()
        self.client.on_publish = self.on_publish

    def on_connect(self, client, userdata, flags, reason, properties):
        with self.lock:
            self.connected = reason == 0
            self.error = None if self.connected else f"MQTT connection rejected: {reason}"
            self.revision += 1

    def on_disconnect(self, *_):
        with self.lock:
            self.connected = False
            self.error = "MQTT disconnected; reconnecting"
            self.revision += 1

    def on_publish(self, client, userdata, mid, reason, properties):
        with self.lock:
            record = self.pending.pop(mid, None)
            if record and reason == 0:
                self.last_acknowledged = {"sequence": record[0], "timestamp": datetime.now(timezone.utc).isoformat()}
                self.published_windows += 1
                self.error = None
                self.revision += 1

    def control(self, changes):
        with self.lock:
            for key, value in changes.model_dump(exclude_none=True).items():
                if key == "publisher_enabled":
                    if value != self.publisher_enabled:
                        self.window = None
                    self.publisher_enabled = value
                else:
                    if key == "mode" and value != self.model.mode:
                        self.model.impulse = self.model.impulse_time = self.model.bearing_phase = 0
                    if key == "paused" and value != self.model.paused:
                        self.window = None
                    setattr(self.model, key, value)
            self.revision += 1
            return self.snapshot()

    def cool_down(self):
        with self.lock:
            self.model.temperature = 28
            self.revision += 1
            return self.snapshot()

    def snapshot(self):
        with self.lock:
            model = self.model
            return dict(type="simulation_state", revision=self.revision,
                        timestamp=datetime.now(timezone.utc).isoformat(), modes=MODES,
                        rpm=model.rpm, severity=model.severity, mode=model.mode,
                        paused=model.paused, temperature=model.temperature, rms=model.rms, current=model.current,
                        demo_status=model.demo_status(), rotation_degrees=model.rotation,
                        waveforms={key: list(values) for key, values in model.buffers.items()},
                        temperature_history=list(model.history), serial=list(model.lines),
                        publisher_enabled=self.publisher_enabled, mqtt_connected=self.connected,
                        mqtt_topic=self.settings.iot_topic, device_id=self.settings.iot_simulation_device,
                        last_window=self.last_window, last_acknowledged=self.last_acknowledged,
                        published_windows=self.published_windows, dropped_windows=self.dropped_windows,
                        error=self.error)

    def collect(self, clock):
        if not self.publisher_enabled or self.model.paused:
            self.window = None
            return
        if self.window is None:
            self.window = {"clock": clock, "start": datetime.now(timezone.utc),
                           "samples": [self.model.temperature], "sensors": [self.model.sensors()], "next_sample": clock + 1}
            return
        window = self.window
        if clock - window["clock"] >= 3:
            values = window["samples"]
            self.sequence = max(self.sequence + 1, time.time_ns() // 1000)
            self.last_window = dict(schema_version=1, device_id=self.settings.iot_simulation_device,
                source="simulation", sequence=self.sequence, window_start=window["start"].isoformat(),
                window_end=(window["start"] + timedelta(seconds=3)).isoformat(), window_duration_seconds=3,
                temperature=dict(mean=fmean(values), min=min(values), max=max(values),
                                 sample_count=len(values), unit="degC", status="valid"))
            self.last_window["sensors"] = {
                key: dict(mean=fmean(row[key] for row in window["sensors"]),
                          min=min(row[key] for row in window["sensors"]),
                          max=max(row[key] for row in window["sensors"]),
                          sample_count=len(window["sensors"]), status="valid",
                          unit="A" if key == "current" else "rpm" if key == "rpm" else "deg/s" if key.startswith("g") else "g")
                for key in window["sensors"][0]
            }
            self.pending = {mid: item for mid, item in self.pending.items() if clock - item[1] < 10}
            if self.connected and len(self.pending) < 2:
                info = self.client.publish(self.settings.iot_topic, json.dumps(self.last_window), qos=1, retain=False)
                if info.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.pending[info.mid] = (self.sequence, clock)
                else:
                    self.dropped_windows += 1
                    self.error = "MQTT publish failed; next window will retry"
            else:
                self.dropped_windows += 1
                self.error = "Window dropped: MQTT offline or awaiting acknowledgments"
            self.window = None
            self.collect(clock)
        elif clock >= window["next_sample"]:
            window["samples"].append(self.model.temperature)
            window["sensors"].append(self.model.sensors())
            window["next_sample"] += 1

    def run(self):
        previous = time.monotonic()
        accumulated = 0
        while not self.stop_event.wait(0.01):
            clock = time.monotonic()
            elapsed = clock - previous
            previous = clock
            with self.lock:
                if elapsed > 0.25:
                    # A suspended host cannot supply actual wall-time samples for the missed window.
                    self.window = None
                accumulated += min(elapsed, 0.25)
                while accumulated >= 0.02:
                    self.model.step()
                    accumulated -= 0.02
                self.collect(clock)
                self.revision += 1

    def start(self):
        if self.settings.mqtt_enabled:
            self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=10)
            self.client.loop_start()
        self.thread = threading.Thread(target=self.run, name="motor-simulator", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
        if self.settings.mqtt_enabled:
            self.client.disconnect()
            self.client.loop_stop()


def register_simulator_routes(app, simulator):
    @app.get("/api/simulation", tags=["Motor simulator"], summary="Read server-generated sensor state")
    async def state():
        return simulator.snapshot()

    @app.patch("/api/simulation", tags=["Motor simulator"], summary="Set simulator controls and MQTT publishing")
    async def control(changes: SimulationControl):
        return simulator.control(changes)

    @app.post("/api/simulation/cool-down", tags=["Motor simulator"], summary="Reset model temperature to 28 degrees Celsius")
    async def cool_down():
        return simulator.cool_down()

    @app.websocket("/ws/simulation")
    async def stream(websocket: WebSocket):
        await websocket.accept()

        async def send():
            while True:
                await asyncio.wait_for(websocket.send_json(simulator.snapshot()), timeout=5)
                await asyncio.sleep(0.1)

        sender = asyncio.create_task(send())
        receiver = asyncio.create_task(websocket.receive_text())
        try:
            done, _ = await asyncio.wait((sender, receiver), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, RuntimeError, asyncio.TimeoutError):
            pass
        finally:
            sender.cancel()
            receiver.cancel()
            with anyio.CancelScope(shield=True):
                await asyncio.gather(sender, receiver, return_exceptions=True)
                try:
                    await websocket.close()
                except (WebSocketDisconnect, RuntimeError):
                    pass
