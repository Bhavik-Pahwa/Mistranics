import json
import logging
import queue
import threading
import paho.mqtt.client as mqtt
from pydantic import ValidationError
from .services import ingest, DomainError

log = logging.getLogger(__name__)


def configure_client(client, settings):
    client.max_queued_messages_set(64)
    if settings.mqtt_username:
        client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
    if settings.mqtt_tls:
        client.tls_set(ca_certs=settings.mqtt_ca, certfile=settings.mqtt_cert, keyfile=settings.mqtt_key)
    client.reconnect_delay_set(1, settings.mqtt_reconnect_max)


class Subscriber:
    def __init__(self, settings, factory=None, *, consume=None, connection_changed=None):
        self.settings, self.factory = settings, factory
        self.consume = consume
        self.connection_changed = connection_changed or (lambda connected: None)
        self.stop_event = threading.Event()
        self.messages = queue.Queue(maxsize=256)
        self.reconnect_needed = threading.Event()
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            clean_session=consume is not None,
            manual_ack=True,
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect_fail = self.on_connect_fail
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        configure_client(self.client, settings)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(self.settings.mqtt_topic, qos=self.settings.mqtt_qos)
            log.info("MQTT connected and subscribed")
        else:
            self.connection_changed(False)
            log.error("MQTT connection rejected code=%s", reason_code)

    def on_subscribe(self, client, userdata, mid, reason_codes, properties):
        connected = bool(reason_codes) and all(code < 128 for code in reason_codes)
        self.connection_changed(connected)
        if not connected:
            log.error("MQTT subscription rejected")

    def on_disconnect(self, *args):
        self.connection_changed(False)
        log.warning("MQTT disconnected; automatic reconnect enabled")

    def on_connect_fail(self, *args):
        self.connection_changed(False)
        log.warning("MQTT broker unavailable; retrying")

    def on_message(self, client, userdata, message):
        if self.consume is not None and message.retain:
            log.warning("MQTT ignored retained live telemetry")
            client.ack(message.mid, message.qos)
            return
        if len(message.payload) > (8192 if self.consume is not None else 1_048_576):
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
                    if self.consume is not None:
                        self.consume(payload)
                        self.client.ack(message.mid, message.qos)
                        break
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
                ) as exc:
                    log.warning("MQTT rejected invalid telemetry: %s", exc)
                    self.client.ack(message.mid, message.qos)
                    break
                except Exception:
                    log.exception("MQTT processing failed; message remains unacknowledged")
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
