#include <Arduino.h>
#include <SPI.h>
#include "SensorManager.h"
#include "../../include/sensor_definitions.h"
#include "../../include/config.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <DHT.h>
#include <SoftwareSerial.h>

// ==== RS485 Serial ====
// Objects
SoftwareSerial mySerial(26, 4); // RX, TX
OneWire oneWire(DS18B20_PIN);
DallasTemperature ds18b20(&oneWire);
DHT dht(DHT_PIN, DHT22);
SensorData data;

// Global readings
static float voltage = NAN;
static bool doorOpen = false;

// ===== Initialization =====
void initSensors()
{
  // DS18B20
  ds18b20.begin();
  mySerial.begin(4800); // Initialize SoftwareSerial with the same baud rate
  // DHT22
  dht.begin();
  // Door Switch & Battery Voltage
  pinMode(DOOR_SWITCH, INPUT_PULLDOWN);
  pinMode(VOLTAGE_SENSOR_PIN, INPUT);
}

// ===== All Sensor Read =====
void readAllSensors()
{
  readCWT5Sensor(data);
  // Soil Temperature
  ds18b20.requestTemperatures();
  data.soilTempC = ds18b20.getTempCByIndex(0);
  // Air Temp & Humidity (DHT22)
  data.airTempC = dht.readTemperature();
  data.airHumidity = dht.readHumidity();
  // Battery Voltage
  // data.batteryVoltage = readBatteryVoltage();
  // Door Switch
  doorOpen = (digitalRead(DOOR_SWITCH) == HIGH);
  // Optional timestamp if available
  // data.timestamp = getTimestamp();
}

// ===== High-level CWT-5 Read =====
bool readCWT5Sensor(SensorData &data)
{
  byte queryData[] = {0x01, 0x03, 0x00, 0x00, 0x00, 0x07, 0x04, 0x08};
  byte receivedData[19];
  mySerial.write(queryData, sizeof(queryData)); // Send the query data to the NPK sensor
  delay(1000);                                  // Wait for 1 second
  if (mySerial.available() >= sizeof(receivedData))
  {                                                         // Check if there are enough bytes available to read
    mySerial.readBytes(receivedData, sizeof(receivedData)); // Read the received data into the receivedData array
                                                            // Parse
    unsigned int soilHumidity = (receivedData[3] << 8) | receivedData[4];
    unsigned int soilTemperature = (receivedData[5] << 8) | receivedData[6];
    unsigned int soilConductivity = (receivedData[7] << 8) | receivedData[8];
    unsigned int soilPH = (receivedData[9] << 8) | receivedData[10];
    unsigned int nitrogen = (receivedData[11] << 8) | receivedData[12];
    unsigned int phosphorus = (receivedData[13] << 8) | receivedData[14];
    unsigned int potassium = (receivedData[15] << 8) | receivedData[16];

    data.soilMoisture = (float)soilHumidity / 10.0; // Convert to percentage
    data.soilTempC = (float)soilTemperature / 10.0; // Convert to Celsius
    data.soilEC = soilConductivity;                 // Soil EC in mS/cm
    data.soilPH = float(soilPH) / 10;               // Soil pH
    data.nitrogen = nitrogen;                       // Nitrogen in ppm
    data.phosphorus = phosphorus;                   // Phosphorus in ppm
    data.potassium = potassium;                     // Potassium in ppm
    data.timestamp = String(millis());              // Use millis() as a simple timestamp
    // Print to Serial for debugging

    Serial.print("Soil Humidity: ");
    Serial.println((float)soilHumidity / 10.0);
    Serial.print("Soil Temperature: ");
    Serial.println((float)soilTemperature / 10.0);
    Serial.print("Soil Conductivity: ");
    Serial.println(soilConductivity);
    Serial.print("Soil pH: ");
    Serial.println((float)soilPH / 10.0);
    Serial.print("Nitrogen: ");
    Serial.println(nitrogen);
    Serial.print("Phosphorus: ");
    Serial.println(phosphorus);
    Serial.print("Potassium: ");
    Serial.println(potassium);
    return true;
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
