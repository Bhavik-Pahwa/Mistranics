#pragma once
// Copy to indux_config.h (gitignored) before upload. Example values do not connect.
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
// Host computer's LAN IPv4 from ipconfig. NEVER localhost or 127.0.0.1 here.
#define MQTT_HOST "192.168.1.100"
#define MQTT_PORT 1883
#define MQTT_USERNAME ""
#define MQTT_PASSWORD ""
#define MQTT_CLIENT_ID "indux-esp32-device-01"
#define DEVICE_ID "device-01"
#define MQTT_TOPIC "indux/device-01/telemetry"
#define ONE_WIRE_GPIO 19
#define NTP_SERVER "pool.ntp.org"
