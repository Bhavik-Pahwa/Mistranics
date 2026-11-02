#include <Arduino.h>
#include <WiFi.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>
#include <mqtt_client.h>
#include <sys/time.h>
#include <math.h>
#if __has_include("indux_config.h")
#include "indux_config.h"
#else
#include "indux_config.example.h"
#endif

OneWire oneWire(ONE_WIRE_GPIO);
DallasTemperature sensor(&oneWire);
DeviceAddress address;
bool found = false, converting = false, failed = false;
volatile bool mqttConnected = false;
esp_mqtt_client_handle_t mqttClient = nullptr;
uint32_t requestedAt = 0, lastWifiAttempt = 0;
time_t windowStart = 0;
uint64_t sequence = 0;
float total = 0, minimum = 0, maximum = 0;
unsigned samples = 0;

String isoTime(time_t value) {
  struct tm utc;
  gmtime_r(&value, &utc);
  char text[25];
  strftime(text, sizeof(text), "%Y-%m-%dT%H:%M:%SZ", &utc);
  return String(text);
}

void mqttEvent(void *, esp_event_base_t, int32_t id, void *) {
  if (id == MQTT_EVENT_CONNECTED) {
    mqttConnected = true;
    Serial.println("MQTT connected");
  } else if (id == MQTT_EVENT_DISCONNECTED) {
    mqttConnected = false;
    Serial.println("MQTT disconnected; reconnecting in background");
  }
}

void publishWindow() {
  // Epoch-microsecond seed survives ordinary reboots without writing flash per window.
  struct timeval now;
  gettimeofday(&now, nullptr);
  uint64_t clockSequence = uint64_t(now.tv_sec) * 1000000ULL + now.tv_usec;
  sequence = clockSequence > sequence ? clockSequence : sequence + 1;
  if (!mqttConnected || esp_mqtt_client_get_outbox_size(mqttClient) > 4096) {
    Serial.println("Window dropped: broker offline or outbox full");
    return;
  }
  JsonDocument doc;
  doc["schema_version"] = 1;
  doc["device_id"] = DEVICE_ID;
  doc["source"] = "physical";
  doc["sequence"] = sequence;
  doc["window_start"] = isoTime(windowStart);
  doc["window_end"] = isoTime(windowStart + 3);
  doc["window_duration_seconds"] = 3;
  JsonObject temperature = doc["temperature"].to<JsonObject>();
  bool valid = samples > 0 && !failed;
  if (valid) {
    temperature["mean"] = total / samples;
    temperature["min"] = minimum;
    temperature["max"] = maximum;
  } else {
    temperature["mean"] = nullptr;
    temperature["min"] = nullptr;
    temperature["max"] = nullptr;
  }
  temperature["unit"] = "degC";
  temperature["sample_count"] = valid ? samples : 0;
  temperature["status"] = valid ? "valid" : "disconnected";
  String message;
  serializeJson(doc, message);
  // QoS 1, retain=false. Enqueue is nonblocking; IDF handles acknowledgments/retries.
  int id = esp_mqtt_client_enqueue(mqttClient, MQTT_TOPIC, message.c_str(), message.length(), 1, 0, true);
  if (id >= 0) Serial.println(message);
  else Serial.println("MQTT enqueue failed");
}

void setup() {
  Serial.begin(115200);
  sensor.begin();
  found = sensor.getAddress(address, 0);
  sensor.setResolution(12);
  sensor.setWaitForConversion(false);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  configTime(0, 0, NTP_SERVER);
  esp_mqtt_client_config_t config = {};
  config.host = MQTT_HOST;
  config.port = MQTT_PORT;
  config.client_id = MQTT_CLIENT_ID;
  config.username = MQTT_USERNAME[0] ? MQTT_USERNAME : nullptr;
  config.password = MQTT_PASSWORD[0] ? MQTT_PASSWORD : nullptr;
  config.keepalive = 10;
  config.reconnect_timeout_ms = 2000;
  mqttClient = esp_mqtt_client_init(&config);
  esp_mqtt_client_register_event(mqttClient, MQTT_EVENT_ANY, mqttEvent, nullptr);
  esp_mqtt_client_start(mqttClient);
  Serial.printf("DS18B20 GPIO=%d; external DATA pull-up to 3.3V required\n", ONE_WIRE_GPIO);
}

void loop() {
  uint32_t ticks = millis();
  if (WiFi.status() != WL_CONNECTED && ticks - lastWifiAttempt >= 10000) {
    lastWifiAttempt = ticks;
    WiFi.reconnect();
  }
  time_t now = time(nullptr);
  if (now < 1704067200) {
    // Wait for actual UTC synchronization, never manufacture acquisition timestamps.
    yield();
    return;
  }
  time_t currentWindow = now - now % 3;
  if (windowStart != currentWindow) {
    if (windowStart && currentWindow == windowStart + 3) publishWindow();
    windowStart = currentWindow;
    samples = 0;
    total = 0;
    failed = false;
  }
  if (converting && ticks - requestedAt >= 750) {
    float value = sensor.getTempC(address);
    converting = false;
    // 85C is the probe power-on sentinel; conservatively reject it in this demo.
    if (isfinite(value) && value != DEVICE_DISCONNECTED_C && value != 85.0f && value >= -55 && value <= 125) {
      minimum = samples ? fminf(minimum, value) : value;
      maximum = samples ? fmaxf(maximum, value) : value;
      total += value;
      samples++;
    } else {
      failed = true;
      found = false;
    }
  }
  if (!converting && ticks - requestedAt >= 1000) {
    requestedAt = ticks;
    if (!found) {
      found = sensor.getAddress(address, 0);
      if (found) sensor.setResolution(address, 12);
    }
    if (found) {
      sensor.requestTemperaturesByAddress(address);
      converting = true;
    } else {
      failed = true;
    }
  }
  yield();
}
