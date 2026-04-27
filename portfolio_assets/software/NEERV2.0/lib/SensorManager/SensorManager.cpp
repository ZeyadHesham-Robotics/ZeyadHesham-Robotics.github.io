#include <Arduino.h>
#include <SPI.h>
#include "SensorManager.h"
#include "../../include/sensor_definitions.h"
#include "../../include/config.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <SoftwareSerial.h>
#include <Wire.h>
#include "RTClib.h"

// ==== RS485 Serial ====
// Objects
SoftwareSerial mySerial(RS485_RX, RS485_TX); // RX, TX
OneWire oneWire(DS18B20_PIN);
DallasTemperature ds18b20(&oneWire);
DHT dht(DHT_PIN, DHT22);
SensorData data;
RTC_DS3231 rtc; // or RTC_DS1307 rtc;

// Global readings
static float voltage = NAN;
bool buzzerActive = false;
bool buzzerState = false;
unsigned long lastBuzzMillis = 0;

// ===== Initialization =====
void initSensors()
{
  ds18b20.begin();
  mySerial.begin(4800);
  Serial.begin(9600);
  dht.begin();
  setupRTC();
  pinMode(DOOR_SWITCH, INPUT);
  pinMode(VOLTAGE_SENSOR_PIN, INPUT);
  pinMode(RELAY_CH1, OUTPUT);
  pinMode(RELAY_CH2, OUTPUT);
  pinMode(PH_E291C_PIN, INPUT);
  digitalWrite(RELAY_CH1, HIGH);
  digitalWrite(RELAY_CH2, HIGH);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
}

// ===== All Sensor Read =====
void readAllSensors()
{
}

// ===== High-level CWT-5 Read =====
bool readCWT5Sensor()
{
  data.PH_E291C = analogRead(PH_E291C_PIN) * (3.3 / 4095.0) * 3.5; // Assuming a voltage divider ratio of 3.5
  ds18b20.requestTemperatures();
  data.airTempC = ds18b20.getTempCByIndex(0);
  // data.airHumidity = dht.readHumidity();
  data.batteryVoltage = readBatteryVoltage();
  data.doorOpen = (digitalRead(DOOR_SWITCH));
  Buzz(data.doorOpen);
  // data.timestamp = getTimestamp();
  byte queryData[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x07, 0x04, 0x08};
  byte receivedData[19];

  mySerial.write(queryData, sizeof(queryData));
  delay(1000);

  if (mySerial.available() >= sizeof(receivedData))
  {
    mySerial.readBytes(receivedData, sizeof(receivedData));

    // Parse and print the received data in decimal format
    unsigned int soilHumidity = (receivedData[3] << 8) | receivedData[4];
    unsigned int soilTemperature = (receivedData[5] << 8) | receivedData[6];
    unsigned int soilConductivity = (receivedData[7] << 8) | receivedData[8];
    unsigned int soilPH = (receivedData[9] << 8) | receivedData[10];
    unsigned int nitrogen = (receivedData[11] << 8) | receivedData[12];
    unsigned int phosphorus = (receivedData[13] << 8) | receivedData[14];
    unsigned int potassium = (receivedData[15] << 8) | receivedData[16];

    data.soilMoisture = float(soilHumidity) / 10.0;
    data.soilTempC = float(soilTemperature) / 10.0;
    data.soilEC = soilConductivity;
    data.soilPH = float(soilPH) / 10.0;
    data.nitrogen = nitrogen;
    data.phosphorus = phosphorus;
    data.potassium = potassium;
    data.timestamp = getTimestamp();
    data.batteryVoltage = voltage;

    Serial.println("CWT-5 Sensor Readings:");
    Serial.print("Soil Moisture: ");
    Serial.print(data.soilMoisture);
    Serial.println(" %");
    Serial.print("Soil Temperature: ");
    Serial.print(data.soilTempC);
    Serial.println(" °C");
    Serial.print("Soil EC: ");
    Serial.print(data.soilEC);
    Serial.println(" µS/cm");
    Serial.print("Soil pH: ");
    Serial.println(data.soilPH);
    Serial.print("Nitrogen: ");
    Serial.print(data.nitrogen);
    Serial.println(" mg/kg");
    Serial.print("Phosphorus: ");
    Serial.print(data.phosphorus);
    Serial.println(" mg/kg");
    Serial.print("Potassium: ");
    Serial.print(data.potassium);
    Serial.println(" mg/kg");
    Serial.print("Air Temperature: ");
    Serial.print(data.airTempC);
    Serial.println(" °C");
    Serial.print("Battery Voltage: ");
    Serial.print(data.batteryVoltage);
    Serial.println(" V");
    Serial.print("Door Open: ");
    Serial.println(data.doorOpen ? "Yes" : "No");
    Serial.print("pH E291C: ");
    Serial.println(data.PH_E291C);
    Serial.print("Timestamp: ");
    Serial.println(data.timestamp);
    Serial.println("-----------------------");

    return true;
  }
  else
  {
    Serial.println("Not enough data received from CWT-5");
    return false;
  }
}

void Buzz(bool enable)
{
  if (enable && !buzzerActive)
  {
    buzzerActive = true;
    buzzerState = true;
    digitalWrite(BUZZER_PIN, HIGH);
    lastBuzzMillis = millis();
  }

  if (buzzerActive)
  {
    unsigned long currentMillis = millis();

    if (buzzerState && (currentMillis - lastBuzzMillis >= BUZZER_ON_TIME))
    {
      buzzerState = false;
      digitalWrite(BUZZER_PIN, LOW);
      lastBuzzMillis = currentMillis;
    }
    else if (!buzzerState && (currentMillis - lastBuzzMillis >= BUZZER_OFF_TIME))
    {
      // Stop buzzing after one full cycle
      buzzerActive = false;
      buzzerState = false;
      digitalWrite(BUZZER_PIN, LOW);
    }
  }
}

// ===== Voltage Sensor =====
float readBatteryVoltage()
{
  long sum = 0;
  const int samples = 10;
  for (int i = 0; i < samples; i++)
  {
    sum += analogRead(VOLTAGE_SENSOR_PIN);
    delay(5);
  }
  float avgRaw = sum / (float)samples;
  return (avgRaw / ADC_RESOLUTION) * ADC_VREF * VOLTAGE_DIVIDER_RATIO;
}

void setupRTC()
{
  if (!rtc.begin())
  {
    Serial.println("Couldn't find RTC");
    while (1)
      ;
  }

  if (rtc.lostPower())
  {
    Serial.println("RTC lost power, setting time to compile time");
    rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
}

String getTimestamp()
{
  DateTime now = rtc.now();

  // Format: YYYY-MM-DD HH:MM:SS
  char buffer[25];
  sprintf(buffer, "%04d-%02d-%02d %02d:%02d:%02d",
          now.year(), now.month(), now.day(),
          now.hour(), now.minute(), now.second());

  return String(buffer);
}