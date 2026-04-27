#include "commLayer.h"
#include "../../include/config.h"

// ---------- GSM Config ----------
const char apn[] = "internet.vodafone.net";
const char gprsUser[] = "";
const char gprsPass[] = "";

// ---------- HiveMQ MQTT Config ----------
const char *mqtt_server = "023df8eba3dd4d669d18f1c8bf579ede.s1.eu.hivemq.cloud";
const int mqtt_port = 8883;
const char *mqtt_user = "zero0";
const char *mqtt_password = "xAVg@xEX7NG996w";
const char *mqtt_topic = "devices/ESP-mgm3u7it-D29DE4/data";
const char *mqtt_clientid = "68a323cabe3a5f1e60e2c699"; // Must be unique

const char *relay1Topic = "devices/ESP-mgm3u7it-D29DE4/command";
const char *relay2Topic = "devices/ESP-mgm3u7it-D29DE4/command";
const char *wifiSSID = "ZAD LAB";
const char *wifiPassword = "#Z2A0D#L2A4B#";

// const char *mqtt_server = "bd1b75c8082040e2bd0f255e73f81959.s1.eu.hivemq.cloud";
// const int mqtt_port = 8883;
// const char *mqtt_user = "SoilManager";
// const char *mqtt_password = "Soilmanager1";
// const char *mqtt_topic = "zeyad/soil";
// const char *mqtt_clientid = "soil_sensor_01"; // Must be unique

WiFiClientSecure wifiSecureClient;
PubSubClient wifiMqttClient(wifiSecureClient);

void callback(char *topic, byte *message, unsigned int length)
{
    // Convert payload to string
    String msg;
    for (int i = 0; i < length; i++)
    {
        msg += (char)message[i];
    }

    Serial.print("\n Message on topic [");
    Serial.print(topic);
    Serial.print("]: ");
    Serial.println(msg);

    // Allocate a JSON document (adjust capacity if message grows bigger)
    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, msg);
    if (error)
    {
        Serial.print("JSON parse failed: ");
        Serial.println(error.c_str());
        return;
    }

    // Extract fields
    const char *type = doc["type"];
    const char *outputId = doc["outputId"];
    bool state = doc["state"]; // true/false
    int value = doc["value"];  // optional

    // Check if it’s the right type
    if (strcmp(type, "OUTPUT_CONTROL") == 0)
    {
        if (strcmp(topic, relay1Topic) == 0 && strcmp(outputId, "output_1") == 0)
        {
            digitalWrite(RELAY_CH1, state ? LOW : HIGH);
            Serial.println(state ? " Relay 1 ON" : " Relay 1 OFF");
        }
        else if (strcmp(topic, relay2Topic) == 0 && strcmp(outputId, "output_2") == 0)
        {
            digitalWrite(RELAY_CH2, state ? LOW : HIGH);
            Serial.println(state ? " Relay 2 ON" : " Relay 2 OFF");
        }
    }
}

bool reconnect()
{
    while (!wifiMqttClient.connected())
    {
        Serial.print("Attempting MQTT connection...");
        // Try connecting with client ID, username, and password
        if (wifiMqttClient.connect(mqtt_clientid, mqtt_user, mqtt_password))
        {
            Serial.println("connected");
            wifiMqttClient.subscribe(relay1Topic);
            wifiMqttClient.subscribe(relay2Topic);
            Serial.print("Subscribed to: ");
            Serial.println(mqtt_topic);
            return true;
        }
        else
        {
            Serial.print("failed, rc=");
            Serial.print(wifiMqttClient.state());
            Serial.println(" retrying in 5 seconds");
            delay(5000);
            return false; // Return false if connection fails
        }
    }
}

void setup_wifi()
{
    delay(10);
    Serial.println();
    Serial.print("Connecting to ");
    Serial.println(wifiSSID);

    WiFi.begin(wifiSSID, wifiPassword);
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\nWiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
}

//======INITIALIZE COMMUNICATIONS========
void CommInit()
{
    Serial.begin(9600);
    Serial.println("Initializing Communications...");
    setup_wifi();
    wifiSecureClient.setInsecure(); // Disable SSL certificate verification for simplicity
    wifiMqttClient.setServer(mqtt_server, mqtt_port);
    wifiMqttClient.setCallback(callback);
    pinMode(RELAY_CH1, OUTPUT);
    pinMode(RELAY_CH2, OUTPUT);
    digitalWrite(RELAY_CH1, LOW); // start OFF
    digitalWrite(RELAY_CH2, LOW);

    // Link MQTT callback
}

void mloop(const SensorData &data)
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
                if (!reconnect())
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

        // GSM_SEND can be re-enabled if you want fallback
    }
}

void publishSensorDataMQTT(PubSubClient &client, const SensorData &data)
{
    // Safely format values into strings
    String soilTempStr = "{\"temperature\":" + String(data.soilTempC) + "}";
    String airTempStr = "{\"airtemperature\":" + String(data.airTempC) + "}";
    String airHumStr = "\"dht22_humidity\":" + String(data.airHumidity) + "}";
    String soilPhStr = "\"ph\":" + String(data.soilPH) + "}";
    String soilMoistStr = "\"soil_moisture\":" + String(data.soilMoisture) + "}";
    String soilECStr = "\"cwt_ec\":" + String(data.soilEC) + "}";
    String nitrogenStr = "\"cwt_nitrogen\":" + String(data.nitrogen) + "}";
    String phosphorusStr = "\"cwt_phosphorus\":" + String(data.phosphorus) + "}";
    String potassiumStr = "\"cwt_potassium\":" + String(data.potassium) + "}";
    String battVoltStr = "\"battery_voltage\":" + String(data.batteryVoltage) + "}";
    String timestampStr = "\"timestamp\":" + String(data.timestamp) + "}";
    String doorOpen = data.doorOpen ? "true" : "false";
    String doorOpenStr = "\"door_status\":" + doorOpen + "}";
    String PH_E291C = "\"PH_E291C\":" + String(data.PH_E291C) + "}";

    // Publish them safely
    wifiMqttClient.publish(mqtt_topic, soilTempStr.c_str());
    wifiMqttClient.publish(mqtt_topic, airTempStr.c_str());
    wifiMqttClient.publish(mqtt_topic, airHumStr.c_str());
    wifiMqttClient.publish(mqtt_topic, soilPhStr.c_str());
    wifiMqttClient.publish(mqtt_topic, soilMoistStr.c_str());
    wifiMqttClient.publish(mqtt_topic, soilECStr.c_str());
    wifiMqttClient.publish(mqtt_topic, nitrogenStr.c_str());
    wifiMqttClient.publish(mqtt_topic, phosphorusStr.c_str());
    wifiMqttClient.publish(mqtt_topic, potassiumStr.c_str());
    wifiMqttClient.publish(mqtt_topic, battVoltStr.c_str());
    wifiMqttClient.publish(mqtt_topic, timestampStr.c_str());
    wifiMqttClient.publish(mqtt_topic, doorOpenStr.c_str());
    Serial.println("Sensor mqtt_topic to MQTT.");
}

String buildJsonFromSensorData(const SensorData &data)
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
    json += "\"batteryVoltage\":" + String(data.batteryVoltage, 2) + ",";
    json += "\"doorOpen\":" + String(data.doorOpen ? "true" : "false") + ",";
    json += "\"timestamp\":\"" + data.timestamp + "\"";
    json += "}";
    return json;
}
