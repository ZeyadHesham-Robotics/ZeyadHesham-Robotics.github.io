#include "../../include/config.h"
#include "CommsManager.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <TinyGsmClient.h>

ComManager comManager;

// ---------- GSM Config ----------
const char apn[] = "internet.vodafone.net";
const char gprsUser[] = "";
const char gprsPass[] = "";

// ---------- HiveMQ MQTT Config ----------
const char *mqtt_server = "bd1b75c8082040e2bd0f255e73f81959.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char *mqtt_user = "SoilManager";
const char *mqtt_password = "Soilmanager1";
const char *mqtt_topic = "zeyad/soil";
const char *mqtt_clientid = "soil_sensor_01"; // Must be unique

// ---------- WiFi + GSM Clients ----------
WiFiClientSecure wifiSecureClient;
PubSubClient wifiMqttClient(wifiSecureClient);
HardwareSerial gsmSerial(1);
TinyGsm modem(gsmSerial);
TinyGsmClientSecure gsmSecureClient(modem);
PubSubClient gsmMqttClient(gsmSecureClient);

ComManager::ComManager()
    : lastHttpSend(0),
      myPhoneNumber("+201098877930"),
      wifiSSID("ZAD LAB"), wifiPassword("#Z2A0D#L2A4B#")
{
    Serial.println("ComManager constructor called");
}

// ---------- Init ----------
void CommInit()
{
    Serial.begin(9600);
    delay(1000);
    Serial.println("Initializing CommsManager...");
    comManager.begin(9600);
    comManager.connectWiFi();
    Serial.println("CommsManager initialized");
}

void ComManager::begin(long gsmBaudRate)
{
    gsmSerial.begin(gsmBaudRate, SERIAL_8N1, GSM_RX, GSM_TX);
    delay(1000);
    modem.restart();
    Serial.println("GSM modem Initialized with baud rate: " + String(gsmBaudRate));
    while (!modem.isNetworkConnected())
    {
        Serial.print(".");
        delay(1000);
    }
    Serial.println("\nNetwork connected!");
}

bool ComManager::connectWiFi()
{
    if (WiFi.status() == WL_CONNECTED)
        return true;

    Serial.printf("Connecting to WiFi SSID: %s\n", wifiSSID.c_str());
    WiFi.begin(wifiSSID.c_str(), wifiPassword.c_str());

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 10000)
    {
        Serial.print(".");
        delay(500);
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED)
    {
        Serial.println("WiFi connected.");
        wifiSecureClient.setInsecure();
        wifiMqttClient.setServer(mqtt_server, mqtt_port);
        return true;
    }
    else
    {
        Serial.println("WiFi connection failed.");
        return false;
    }
}

// bool ComManager::connectGSM()
// {
//     Serial.println("Connecting GSM to GPRS...");
//     if (!modem.gprsConnect(apn, gprsUser, gprsPass))
//     {
//         Serial.println("GPRS connection failed.");
//         return false;
//     }
//     Serial.println("GPRS connected.");
//     gsmSecureClient.setInsecure();
//     gsmMqttClient.setServer(mqtt_server, mqtt_port);
//     return true;
// }

bool mqttReconnect(PubSubClient &client)
{
    while (!client.connected())
    {
        Serial.print("Attempting MQTT connection...");
        if (client.connect(mqtt_clientid, mqtt_user, mqtt_password))
        {
            Serial.println("connected");
            return true;
        }
        else
        {
            Serial.print("failed, rc=");
            Serial.print(client.state());
            Serial.println(" try again in 5 seconds");
            delay(5000);
        }
    }
    return false;
}

// ---------- Main loop ----------
void ComManager::loop(const SensorData &data)
{
    static enum { WIFI_SEND,
                  GSM_SEND } state = WIFI_SEND;

    switch (state)
    {
    case WIFI_SEND:
        if (WiFi.status() == WL_CONNECTED)
        {
            wifiMqttClient.loop();
            if (!wifiMqttClient.connected())
            {
                if (!mqttReconnect(wifiMqttClient))
                {
                    Serial.println("WiFi MQTT failed, switching to GSM");
                    state = GSM_SEND;
                    break;
                }
            }
            publishSensorDataMQTT(wifiMqttClient, data);
            state = WIFI_SEND; // stay in WiFi mode
        }
        else
        {
            Serial.println("WiFi not available, switching to GSM");
            state = GSM_SEND;
        }
        break;
    }

    // case GSM_SEND:
    //     if (!modem.isNetworkConnected() || !modem.isGprsConnected())
    //     {
    //         if (!connectGSM())
    //         {
    //             Serial.println("GSM connection failed");
    //             return;
    //         }
    //     }
    //     gsmMqttClient.loop();
    //     if (!gsmMqttClient.connected())
    //     {
    //         if (!mqttReconnect(gsmMqttClient))
    //         {
    //             Serial.println("GSM MQTT failed");
    //             state = WIFI_SEND;
    //             break;
    //         }
    //     }
    //     publishSensorDataMQTT(gsmMqttClient, data);
    //     state = WIFI_SEND; // try WiFi next
    //     break;
    // }
}

void ComManager::publishSensorDataMQTT(PubSubClient &client, const SensorData &data)
{
    Serial.println("Publishing sensor data to MQTT...");
    Serial.println("Soil Temp: " + String(data.soilTempC, 2));
    Serial.println("Air Temp: " + String(data.airTempC, 2));
    Serial.println("Air Humidity: " + String(data.airHumidity, 2));
    Serial.println("Soil pH: " + String(data.soilPH, 2));
    Serial.println("Soil Moisture: " + String(data.soilMoisture, 2));
    Serial.println("Soil EC: " + String(data.soilEC, 2));
    Serial.println("Nitrogen: " + String(data.nitrogen, 2));
    Serial.println("Phosphorus: " + String(data.phosphorus, 2));
    Serial.println("Potassium: " + String(data.potassium, 2));
    Serial.println("Conductivity: " + String(data.conductivity, 2));
    Serial.println("Battery Voltage: " + String(data.batteryVoltage, 2));
    Serial.println("Timestamp: " + data.timestamp);
    Serial.println("Publishing to MQTT topic: " + String(mqtt_topic));

    client.publish((String(mqtt_topic) + "/data").c_str(), buildJsonFromSensorData(data).c_str());
    Serial.println("Published JSON payload to MQTT topic: " + String(mqtt_topic) + "/data");
    // Publish each sensor reading to its own topic
    client.publish((String(mqtt_topic) + "/soilTempC").c_str(), String(data.soilTempC, 2).c_str());
    client.publish((String(mqtt_topic) + "/airTempC").c_str(), String(data.airTempC, 2).c_str());
    client.publish((String(mqtt_topic) + "/airHumidity").c_str(), String(data.airHumidity, 2).c_str());
    client.publish((String(mqtt_topic) + "/soilPH").c_str(), String(data.soilPH, 2).c_str());
    client.publish((String(mqtt_topic) + "/soilMoisture").c_str(), String(data.soilMoisture, 2).c_str());
    client.publish((String(mqtt_topic) + "/soilEC").c_str(), String(data.soilEC, 2).c_str());
    client.publish((String(mqtt_topic) + "/nitrogen").c_str(), String(data.nitrogen, 2).c_str());
    client.publish((String(mqtt_topic) + "/phosphorus").c_str(), String(data.phosphorus, 2).c_str());
    client.publish((String(mqtt_topic) + "/potassium").c_str(), String(data.potassium, 2).c_str());
    client.publish((String(mqtt_topic) + "/conductivity").c_str(), String(data.conductivity, 2).c_str());
    client.publish((String(mqtt_topic) + "/batteryVoltage").c_str(), String(data.batteryVoltage, 2).c_str());
    client.publish((String(mqtt_topic) + "/timestamp").c_str(), data.timestamp.c_str());

    Serial.println("Published each sensor reading to its own MQTT topic.");
}

String ComManager::buildJsonFromSensorData(const SensorData &data)
{
    String json = "{";
    json += "\"soilTempC\":" + String(data.soilTempC, 2) + ",";
    json += "\"airTempC\":" + String(data.airTempC, 2) + ",";
    json += "\"airHumidity\":" + String(data.airHumidity, 2) + ",";
    json += "\"soilPH\":" + String(data.soilPH, 2) + ",";
    json += "\"soilMoisture\":" + String(data.soilMoisture, 2) + ",";
    json += "\"soilEC\":" + String(data.soilEC, 2) + ",";
    json += "\"nitrogen\":" + String(data.nitrogen, 2) + ",";
    json += "\"phosphorus\":" + String(data.phosphorus, 2) + ",";
    json += "\"potassium\":" + String(data.potassium, 2) + ",";
    json += "\"conductivity\":" + String(data.conductivity, 2) + ",";
    json += "\"batteryVoltage\":" + String(data.batteryVoltage, 2) + ",";
    json += "\"timestamp\":\"" + data.timestamp + "\"";
    json += "}";
    return json;
}
