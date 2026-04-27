#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

// Data structure to hold all sensor readings
struct SensorData
{
    float soilTempC;            // CWRT-5
    float soilPH;               // CWT-5
    float soilMoisture;         // CWT-5
    float soilEC;               // CWT-5
    float nitrogen;             // CWT-5
    float phosphorus;           // CWT-5
    float potassium;            // CWT-5
    float airTempC = NAN;       // DS18B20;
    float airHumidity = NAN;    // DHT22
    float batteryVoltage = NAN; // Voltage Sensor
    bool doorOpen = false;      // Door Switch
    float PH_E291C;             // Door Switch
    String timestamp = "";
};

// SensorManager.h
void initSensors();
void readAllSensors();
float readBatteryVoltage();
bool readModbusFrame(const byte *request, byte expectedBytes);
bool readCWT5Sensor();
String getTimestamp();
void setupRTC();
void Buzz(bool enable);



extern SensorData data;

#endif
