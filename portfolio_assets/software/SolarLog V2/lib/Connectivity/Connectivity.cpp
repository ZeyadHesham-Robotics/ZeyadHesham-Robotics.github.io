#include "Connectivity.h"
#include <WiFi.h> // only for WiFi.status()
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

WiFiClientSecure tlsClient;
PubSubClient mqtt(tlsClient);
PanelReading r;

bool connectWiFi()
{
    // One-time Wi-Fi config (safe to call repeatedly)
    WiFi.mode(WIFI_STA);
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.printf("[WiFi] Already connected. IP: %s\n", WiFi.localIP().toString().c_str());
        return true;
    }

    uint32_t attempt = 0;
    for (;;)
    { // loop until connected
        attempt++;
        Serial.printf("\n[WiFi] Attempt %lu: connecting to SSID: %s\n",
                      (unsigned long)attempt, WIFI_SSID);

        WiFi.disconnect(true); // clear previous state
        delay(100);
        WiFi.begin(WIFI_SSID, WIFI_PASS); // start a new attempt

        unsigned long start = millis();
        while (WiFi.status() != WL_CONNECTED && millis() - start < 10000UL)
        {
            Serial.print('.');
            delay(500);
        }
        Serial.println();

        if (WiFi.status() == WL_CONNECTED)
        {
            Serial.printf("[WiFi] Connected. IP: %s\n", WiFi.localIP().toString().c_str());
            return true; // <-- only exits here
        }

        Serial.println("[WiFi] Failed. Retrying in 3s...");
        delay(3000); // backoff between attempts
    }
}

// Publish: solar/<device_id>/panel/<idx>
bool publishPanelPacket(uint8_t idx, const PanelReading &r, bool retained)
{
    if (!mqtt.connected())
        return false;

    char topic[64];
    snprintf(topic, sizeof(topic), "solar/%s/panel/%u", DEVICE_ID, idx);

    // Compact JSON (idx, v, i, t). Keep it small for PubSubClient.
    char payload[128];
    int n = snprintf(payload, sizeof(payload),
                     "{\"idx\":%u,\"v\":%.3f,\"i\":%.3f,\"t\":%.2f}",
                     idx, r.voltage, r.current, r.temperature);

    // Publish (QoS 0). Use the overload with retained flag if you want retained telemetry.
    return mqtt.publish(topic, (uint8_t *)payload, n, retained);
}

// Convenience: read a single panel and publish it
bool readAndPublishPanel(uint8_t idx, bool retained = false)
{
    if (!readPanelData(idx, r))
        return false;
    return publishPanelPacket(idx, r, retained);
}

// Read & publish all four panels as 4 separate MQTT messages
uint8_t publishAllPanels(bool retained = false)
{
    uint8_t sent = 0;
    for (uint8_t i = 0; i < 4; ++i)
    {
        if (readAndPublishPanel(i, retained))
        {
            ++sent;
            delay(10); // slight spacing between packets (optional)
        }
    }
    return sent;
}

bool mqtt_init()
{
    if (WiFi.status() != WL_CONNECTED)
        return false;

    tlsClient.setInsecure();              // TODO: replace with tlsClient.setCACert(ROOT_CA)
    mqtt.setServer(MQTT_HOST, MQTT_PORT); // 8883

    const char *id = DEVICE_ID;
    String statusTopic = String("solar/") + DEVICE_ID + "/status";

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
