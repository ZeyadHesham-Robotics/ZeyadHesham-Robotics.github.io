#ifndef COMMSMANAGER_H
#define COMMSMANAGER_H

#include <Arduino.h>
#include "../../lib/SensorManager/SensorManager.h"

// MQTT library
#include <PubSubClient.h>

// GSM module definition (SIM800 in this case)
#define TINY_GSM_MODEM_SIM800
#include <TinyGsmClient.h>

// Initializes the communications module
void CommInit();

class ComManager
{
public:
    ComManager();

    // Initialize GSM modem with baud rate and APN credentials
    void begin(long gsmBaudRate);

    // Main loop: decide whether to send over WiFi or GSM
    void loop(const SensorData &data);

    // WiFi helpers
    bool connectWiFi();
    bool connectGSM();

    // MQTT helper (public so main.cpp can also call directly if needed)
    void publishSensorDataMQTT(PubSubClient &client, const SensorData &data);

private:
    // SMS helpers
    void sendStatusSMS(const SensorData &data, const String &phoneNumber);
    void sendSMS(const String &phoneNumber, const String &message);

    // HTTP helpers
    bool streamSensorDataHTTP(const SensorData &data);
    bool streamSensorDataGSM(const SensorData &data);

    // JSON builder
    String buildJsonFromSensorData(const SensorData &data);

    // Timing for HTTP sending
    unsigned long lastHttpSend;
    const unsigned long httpInterval = 60000; // 60 seconds

    // Internal settings
    String myPhoneNumber;
    String serverUrl;
    String wifiSSID;
    String wifiPassword;
};

extern ComManager comManager;

#endif
