#ifndef CONNECTIVITY_H
#define CONNECTIVITY_H
#include <PubSubClient.h>

extern PubSubClient mqtt; // MQTT client instance

#include "SensorsManager.h"
#include <WiFi.h>
#include <Arduino.h>
#include <PubSubClient.h>

extern PanelReading r; // reusable reading struct

// ---- Wi-Fi ----
#define WIFI_SSID "Kareem"
#define WIFI_PASS "AhmedKem00Box"

// ---- MQTT broker ----
#define MQTT_HOST "830e6d9f89504070a296bc58ca55abda.s1.eu.hivemq.cloud"
#define MQTT_PORT 8883              // 8883 if you use TLS with WiFiClientSecure
#define MQTT_USER "SolarLog"        // leave "" if no auth
#define MQTT_PASSWD "SolarLogPass1" // leave "" if no auth

// Device/base topics
#define DEVICE_ID "esp32-solar" // optional; auto-ID also used

//===== Function Prototypes =====
bool connectWiFi();
bool publishPanelPacket(uint8_t idx, const PanelReading &r, bool retained);
bool readAndPublishPanel(uint8_t idx, bool retained);
uint8_t publishAllPanels(bool retained);
bool mqtt_init();
void mqtt_loop();
bool mqtt_publish(const char *topic, const char *payload, bool retained);

#endif
