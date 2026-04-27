#include "../../include/config.h"
#include "CommsManager.h"
#include <WiFi.h>
#include <ArduinoHttpClient.h> // Changed from HTTPClient.h

ComManager comManager;
const char apn[] = "internet.vodafone.net";
const char user[] = "";
const char pass[] = "";

const char serverHost[] = "webhook.site";
const int serverPort = 80;
const char serverPath[] = "/67eb3adb-f7c0-40f6-9e10-037c60945654";

HardwareSerial gsmSerial(1);
TinyGsm modem(gsmSerial);
TinyGsmClient client(modem);
HttpClient http(client, serverHost, serverPort);

ComManager::ComManager()
    : lastHttpSend(0),
      myPhoneNumber("+201098877930"),
      serverUrl("https://webhook.site/67eb3adb-f7c0-40f6-9e10-037c60945654"),
      wifiSSID("ZAD LAB"), wifiPassword("#Z2A0D#L2A4B#")

{
    Serial.println("ComManager constructor called");
    Serial.println("wifiSSID initialized as: " + wifiSSID);
    Serial.println("serverUrl initialized as: " + serverUrl);
}

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
        return true;
    }
    else
    {
        Serial.println("WiFi connection failed.");
        return false;
    }
}
void ComManager::loop(const SensorData &data)
{
    static enum { WIFI_SEND,
                  GSM_SEND } state = WIFI_SEND;

    switch (state)
    {
    case WIFI_SEND:
        if (WiFi.status() == WL_CONNECTED)
        {
            Serial.println("Preparing WiFi send...");
            if (streamSensorDataHTTP(data))
            {
                Serial.println("WiFi send OK");
                state = WIFI_SEND; // Stay in Wi-Fi mode
            }
            else
            {
                Serial.println("WiFi failed, switching to GSM");
                state = GSM_SEND;
            }
        }
        else
        {
            Serial.println("WiFi not available, switching to GSM");
            state = GSM_SEND;
        }
        break;

    case GSM_SEND:
        Serial.println("Preparing GSM send...");
        if (streamSensorDataGSM(data))
        {
            Serial.println("GSM send OK");
        }
        else
        {
            Serial.println("GSM send failed");
        }
        state = WIFI_SEND; // Try Wi-Fi next time
        break;
    }
}

bool ComManager::streamSensorDataHTTP(const SensorData &data)
{
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("[HTTP] WiFi not connected.");
        return false;
    }

    WiFiClient wifiClient;
    HttpClient wifiHttp(wifiClient, serverHost, serverPort);

    String jsonPayload = buildJsonFromSensorData(data);

    Serial.println("[HTTP] Sending sensor data via WiFi...");
    wifiHttp.beginRequest();
    wifiHttp.post(serverPath);
    wifiHttp.sendHeader("Content-Type", "application/json");
    wifiHttp.sendHeader("Content-Length", jsonPayload.length());
    wifiHttp.beginBody();
    wifiHttp.print(jsonPayload);
    wifiHttp.endRequest();

    int statusCode = wifiHttp.responseStatusCode();
    String response = wifiHttp.responseBody();

    Serial.printf("[HTTP] WiFi POST returned: %d\n", statusCode);
    Serial.println("Response: " + response);

    wifiHttp.stop();

    return (statusCode >= 200 && statusCode < 300);
}

bool ComManager::streamSensorDataGSM(const SensorData &data)
{

    modem.restart();
    Serial.println("Modem restarted, waiting for network...");

    while (!modem.isNetworkConnected())
    {
        Serial.print(".");
        delay(1000);
    }
    Serial.println("\nNetwork connected!");

    if (!modem.gprsConnect(apn, user, pass))
    {
        Serial.println("GPRS connection failed");
        while (true)
            delay(1000);
    }
    Serial.println("GPRS connected");

    String jsonPayload = buildJsonFromSensorData(data);
    Serial.println("JSON payload:");
    Serial.println(jsonPayload);

    http.beginRequest();
    http.post(serverPath);
    http.sendHeader("Content-Type", "application/json");
    http.sendHeader("Content-Length", jsonPayload.length());
    http.beginBody();
    http.print(jsonPayload);
    http.endRequest();

    int statusCode = http.responseStatusCode();
    String response = http.responseBody();

    Serial.printf("GSM HTTP POST returned: %d\n", statusCode);
    Serial.println("Response: " + response);

// IMPORTANT: stop the HTTP client cleanly before disconnecting GPRS
// HttpClient has stop() method in ArduinoHttpClient; call it if available.
#if defined(ARDUINOHTTPCLIENT_H) || defined(ArduinoHttpClient_h)
    // try to stop/close the connection
    http.stop(); // safe even if not strictly necessary
#endif

    // small delay to ensure modem has finished underlying socket ops
    delay(150);

    // disconnect GPRS only after we've stopped the HTTP client
    if (modem.isGprsConnected())
    {
        modem.gprsDisconnect();
        Serial.println("GPRS disconnected");
    }
    else
    {
        Serial.println("GPRS was not connected");
    }

    // return true on HTTP 2xx
    return (statusCode >= 200 && statusCode < 300);
}

void ComManager::sendStatusSMS(const SensorData &data, const String &phoneNumber)
{
    String message = "Sensor Status:\n";
    message += "Soil Temp: " + String(data.soilTempC, 1) + " C\n";
    message += "Air Temp: " + String(data.airTempC, 1) + " C\n";
    message += "Humidity: " + String(data.airHumidity, 1) + " %\n";
    message += "Soil pH: " + String(data.soilPH, 2) + "\n";
    message += "Soil Moisture: " + String(data.soilMoisture, 1) + " %\n";
    message += "Battery: " + String(data.batteryVoltage, 2) + " V\n";
    message += "Timestamp: " + data.timestamp;

    sendSMS(phoneNumber, message);
}

void ComManager::sendSMS(const String &phoneNumber, const String &message)
{
    if (modem.sendSMS(phoneNumber, message))
        Serial.println("SMS sent successfully");
    else
        Serial.println("SMS sending failed");
}

String ComManager::buildJsonFromSensorData(const SensorData &data)
{
    String json = "{";
    json += "\"soilTempC\":" + String(data.soilTempC, 2) + ",";
    json += "\"airTempC\":" + String(data.airTempC, 2) + ",";
    json += "\"airHumidity\":" + String(data.airHumidity, 2) + ",";
    json += "\"soilPH\":" + String(data.soilPH, 2) + ",";
    json += "\"soilMoisture\":" + String(data.soilMoisture, 2) + ",";
    json += "\"batteryVoltage\":" + String(data.batteryVoltage, 2) + ",";
    json += ",\"soilEC\":" + String(data.soilEC, 2) + ",";
    json += "\"nitrogen\":" + String(data.nitrogen, 2) + ",";
    json += "\"phosphorus\":" + String(data.phosphorus, 2) + ",";
    json += "\"potassium\":" + String(data.potassium, 2) + ",";
    json += "\"conductivity\":" + String(data.conductivity, 2);
    json += "\"timestamp\":\"" + data.timestamp + "\"";
    json += "}";

    return json;
}
