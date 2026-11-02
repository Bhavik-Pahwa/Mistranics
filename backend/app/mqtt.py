import json
import logging
import queue
import threading
import paho.mqtt.client as mqtt
from pydantic import ValidationError
from .services import ingest, DomainError

log = logging.getLogger(__name__)


class Subscriber:
    def __init__(self, settings, factory):
        self.settings, self.factory = settings, factory
        self.stop_event = threading.Event()
        self.messages = queue.Queue(maxsize=256)
        self.reconnect_needed = threading.Event()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            clean_session=False,
            manual_ack=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = lambda *args: log.warning("MQTT disconnected")
        self.client.on_message = self.on_message
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            self.client.tls_set(
                ca_certs=settings.mqtt_ca,
                certfile=settings.mqtt_cert,
                keyfile=settings.mqtt_key,
            )
        self.client.reconnect_delay_set(1, settings.mqtt_reconnect_max)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(self.settings.mqtt_topic, qos=self.settings.mqtt_qos)
            log.info("MQTT connected and subscribed")
        else:
            log.error("MQTT connection rejected code=%s", reason_code)

    def on_message(self, client, userdata, message):
        if len(message.payload) > 1_048_576:
            log.warning("MQTT rejected oversized payload")
            client.ack(message.mid, message.qos)
            return
        try:
            self.messages.put_nowait(message)
        except queue.Full:
            log.warning("MQTT ingestion queue full; reconnect for redelivery")
            self.reconnect_needed.set()

    def run(self):
        while not self.stop_event.is_set():
            if self.reconnect_needed.is_set():
                try:
                    self.client.disconnect()
                    self.client.loop_stop()
                    self.client.reconnect()
                    self.client.loop_start()
                    self.reconnect_needed.clear()
                except OSError:
                    self.stop_event.wait(self.settings.retry_seconds)
            try:
                message = self.messages.get(timeout=0.5)
            except queue.Empty:
                continue
            while not self.stop_event.is_set():
                try:
                    payload = json.loads(message.payload)
                    # A batch is atomic and bounded; no partial acknowledgment.
                    batch = payload if isinstance(payload, list) else [payload]
                    if not 1 <= len(batch) <= 100:
                        raise DomainError("Batch must contain 1..100 windows")
                    with self.factory.begin() as session:
                        for record in batch:
                            ingest(session, record)
                    self.client.ack(message.mid, message.qos)
                    break
                except (
                    ValueError,
                    ValidationError,
                    DomainError,
                    TypeError,
                    RecursionError,
                ):
                    log.warning("MQTT rejected invalid telemetry")
                    self.client.ack(message.mid, message.qos)
                    break
                except Exception:
                    log.error("MQTT persistence failed; message remains unacknowledged")
                    self.stop_event.wait(self.settings.retry_seconds)
            self.messages.task_done()

    def start(self):
        if self.settings.mqtt_qos not in (0, 1):
            raise ValueError(
                "Prototype supports MQTT QoS 0 or 1; use 1 for retry guarantees"
            )
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port)
        self.client.loop_start()

    def stop(self):
        self.stop_event.set()
        self.client.disconnect()
        self.client.loop_stop()
        self.thread.join(timeout=5)
