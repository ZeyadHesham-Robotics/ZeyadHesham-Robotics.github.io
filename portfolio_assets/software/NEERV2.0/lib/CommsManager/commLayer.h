#ifndef COMMLAYER_H
#define COMMLAYER_H

#include <Arduino.h>
#include "../../lib/SensorManager/SensorManager.h"
#include <PubSubClient.h>
#define TINY_GSM_MODEM_SIM800
#include <TinyGsmClient.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>

extern WiFiClientSecure wifiSecureClient;
extern PubSubClient wifiMqttClient;
extern HardwareSerial gsmSerial;

void CommInit();
void setup_wifi();
bool reconnect();
void mloop(const SensorData &data);
String buildJsonFromSensorData(const SensorData &data);
void publishSensorDataMQTT(PubSubClient &client, const SensorData &data);

#endif // COMMLAYER_H