#include "Connectivity.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

WiFiClientSecure tlsClient;
PubSubClient mqtt(tlsClient);
HotWireReading hwReading; // Renamed for hot wire system

// Set up ESP32 as Wi-Fi Access Point
bool setupAccessPoint()
{
    WiFi.mode(WIFI_AP);
    WiFi.softAP("Hotwire", "Hotwire1"); // Use your desired SSID and password

    IPAddress ip = WiFi.softAPIP();
    Serial.printf("[WiFi] Access Point started. IP: %s\n", ip.toString().c_str());
    return true;
}

// Publish: hotwire/<device_id>/status
bool publishHotWirePacket(const HotWireReading &hwReading, bool retained)
{
    if (!mqtt.connected())
        return false;

    char topic[64];
    snprintf(topic, sizeof(topic), "hotwire/%s/status", DEVICE_ID);

    // Compact JSON (temp, pwm). Keep it small for PubSubClient.
    char payload[128];
    int n = snprintf(payload, sizeof(payload),
                     "{\"temperature\":%.2f,\"pwm\":%d}",
                     hwReading.temperature, hwReading.pwmValue);

    // Publish (QoS 0). Use the overload with retained flag if you want retained telemetry.
    return mqtt.publish(topic, (uint8_t *)payload, n, retained);
}

// Convenience: read and publish hot wire status
bool readAndPublishHotWire(bool retained = false)
{
    if (!readHotWireData(hwReading))
        return false;
    return publishHotWirePacket(hwReading, retained);
}

bool mqtt_init()
{
    // For AP mode, WiFi.status() always returns WL_CONNECTED, so this check is still valid
    if (WiFi.status() != WL_CONNECTED && WiFi.getMode() != WIFI_AP)
        return false;

    tlsClient.setInsecure();              // TODO: replace with tlsClient.setCACert(ROOT_CA)
    mqtt.setServer(MQTT_HOST, MQTT_PORT); // 8883

    const char *id = DEVICE_ID;
    String statusTopic = String("hotwire/") + DEVICE_ID + "/status";

    bool ok = (strlen(MQTT_USER) == 0)
                  ? mqtt.connect(id, statusTopic.c_str(), 1, true, "offline")
                  : mqtt.connect(id, MQTT_USER, MQTT_PASSWD, statusTopic.c_str(), 1, true, "offline");

    if (ok)
        mqtt.publish(statusTopic.c_str(), "online", true); // retained
    return ok;
}

void mqtt_loop()
{
    if (mqtt.connected())
        mqtt.loop();
}

bool mqtt_publish(const char *topic, const char *payload, bool retained = false)
{
    if (!mqtt.connected())
        return false;
    return mqtt.publish(topic, (const uint8_t *)payload, strlen(payload), retained);
}