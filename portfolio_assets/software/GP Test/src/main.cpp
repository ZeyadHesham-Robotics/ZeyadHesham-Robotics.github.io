#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// PWM setup
const int pwmPin = 27;
const int pwmChannel = 0;
const int pwmFreq = 20000;
const int pwmResolution = 11;
int pwmValue = 0;
bool pwmActive = true;

// MAX471 pins
const int currentPin = 39; // Current sense pin
const int voltagePin = 36; // Voltage sense pin

// WiFi credentials
#define WIFI_SSID "Robotics"
#define WIFI_PASS "123456789"

// MQTT broker settings
#define MQTT_HOST "bd1b75c8082040e2bd0f255e73f81959.s1.eu.hivemq.cloud"
#define MQTT_PORT 8883
#define MQTT_USER "Hotwire"
#define MQTT_PASSWD "Hotwire1"
#define DEVICE_ID "esp32-hotwire"

// MQTT setup
WiFiClientSecure tlsClient;
PubSubClient mqtt(tlsClient);

// Set PWM value from MQTT
int pwmValueFromMQTT = 0;
bool pwmMQTTActive = false;
bool skipWiFi = false;

// ADC constants
const float ADC_REF = 3.3; // ESP32 ADC ref
const int ADC_MAX = 4095;  // 12-bit ADC

// Calibration factors (adjust with multimeter)
const float CURR_SCALE = 1.0;  // 1 V = 1 A for MAX471 (adjust if needed)
const float VOLT_SCALE = 12.0; // 1 Vout ≈ 12 V input (depends on module resistors)

float readCurrent()
{
  int raw = analogRead(currentPin);
  float vout = (raw * ADC_REF) / ADC_MAX;
  return vout / CURR_SCALE; // in Amps
}

float readVoltage()
{
  int raw = analogRead(voltagePin);
  float vout = (raw * ADC_REF) / ADC_MAX;
  return vout * VOLT_SCALE; // in Volts
}

void setupADC()
{
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db); // Full 0–3.3 V
}

// Connect to WiFi
void connectWiFi()
{
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting to WiFi (press 'x' to skip) ");
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(500);
    Serial.print(".");
    if (Serial.available() && Serial.read() == 'x')
    {
      skipWiFi = true;
      Serial.println("\nSkipping WiFi connection. Running in Serial-only mode.");
      return;
    }
  }
  Serial.println();
  Serial.print("Connected! IP address: ");
  Serial.println(WiFi.localIP());
}

// MQTT callback
void mqttCallback(char *topic, byte *payload, unsigned int length)
{
  if (strstr(topic, "hotwire/esp32-hotwire/set_pwm"))
  {
    char buf[16] = {0};
    memcpy(buf, payload, min(length, sizeof(buf) - 1));
    pwmValueFromMQTT = atoi(buf);
    pwmMQTTActive = true;
    Serial.print("Received PWM from MQTT: ");
    Serial.println(pwmValueFromMQTT);
  }
}

bool mqtt_init()
{
  if (skipWiFi)
    return false;

  tlsClient.setInsecure();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(mqttCallback);

  String statusTopic = String("hotwire/") + DEVICE_ID + "/status";
  bool ok = (strlen(MQTT_USER) == 0)
                ? mqtt.connect(DEVICE_ID, statusTopic.c_str(), 1, true, "offline")
                : mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWD, statusTopic.c_str(), 1, true, "offline");

  if (ok)
  {
    mqtt.publish(statusTopic.c_str(), "online", true);
    mqtt.subscribe("hotwire/esp32-hotwire/set_pwm");
  }
  return ok;
}

// Publish JSON {pwm, current, voltage, power}
void publishData(int pwmValue, float current, float voltage)
{
  if (skipWiFi || !mqtt.connected())
    return;

  char topic[64];
  snprintf(topic, sizeof(topic), "hotwire/%s/data", DEVICE_ID);

  float power = voltage * current;

  char payload[200];
  snprintf(payload, sizeof(payload),
           "{\"pwm\":%d,\"current\":%.3f,\"voltage\":%.2f,\"power\":%.2f}",
           pwmValue, current, voltage, power);

  mqtt.publish(topic, payload, true);
}

void setup()
{
  Serial.begin(9600);
  setupADC();
  pinMode(currentPin, INPUT);
  pinMode(voltagePin, INPUT);

  // Setup PWM on D27
  ledcSetup(pwmChannel, pwmFreq, pwmResolution);
  ledcAttachPin(pwmPin, pwmChannel);
  ledcWrite(pwmChannel, pwmValue);

  Serial.println("Hot Wire PWM Control Ready.");
  Serial.println("Send 'w' to increase, 's' to decrease, 'x' to stop.");
  Serial.println("Press 'x' during WiFi connect to skip WiFi/MQTT.");

  connectWiFi();
  if (!skipWiFi)
  {
    mqtt_init();
  }
}

void loop()
{
  // Local keyboard control
  if (Serial.available())
  {
    char cmd = Serial.read();
    if (cmd == 'w')
    {
      pwmValue = min(pwmValue + 1, 2048);
      pwmActive = true;
      pwmMQTTActive = false;
    }
    else if (cmd == 's')
    {
      pwmValue = max(pwmValue - 1, 0);
      pwmActive = true;
      pwmMQTTActive = false;
    }
    else if (cmd == 'x')
    {
      pwmValue = 0;
      pwmActive = false;
      pwmMQTTActive = false;
    }

    if (pwmActive)
    {
      ledcWrite(pwmChannel, pwmValue);
      Serial.print("PWM set to: ");
      Serial.println(pwmValue);
    }
    else
    {
      ledcWrite(pwmChannel, 0);
      Serial.println("PWM stopped.");
    }
  }

  // MQTT control
  if (pwmMQTTActive)
  {
    pwmValue = constrain(pwmValueFromMQTT, 0, 2048);
    ledcWrite(pwmChannel, pwmValue);
    Serial.print("PWM set by MQTT: ");
    Serial.println(pwmValue);
  }

  // Send data every 500 ms
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 500)
  {
    lastPrint = millis();
    float current = readCurrent();
    float voltage = readVoltage();

    publishData(pwmValue, current, voltage);

    Serial.print("Measured current: ");
    Serial.print(current, 3);
    Serial.println(" A");

    Serial.print("Measured voltage: ");
    Serial.print(voltage, 2);
    Serial.println(" V");

    Serial.print("Transmitted PWM: ");
    Serial.println(pwmValue);
  }

  if (!skipWiFi)
  {
    mqtt.loop();
  }
}
