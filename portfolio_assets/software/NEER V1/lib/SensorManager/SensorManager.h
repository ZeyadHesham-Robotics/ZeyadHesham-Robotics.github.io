#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

// Data structure to hold all sensor readings
struct SensorData
{
    unsigned int soilTempC;
    float airTempC = NAN;
    float airHumidity = NAN;
    unsigned int soilPH;
    unsigned int soilMoisture;
    float batteryVoltage = NAN;
    unsigned int soilEC;
    unsigned int nitrogen;
    unsigned int phosphorus;
    unsigned int potassium;
    unsigned int conductivity;
    String timestamp = "";
};

// SensorManager.h
void initSensors();
void readAllSensors();
float readBatteryVoltage();
bool readModbusFrame(const byte *request, byte expectedBytes);
bool readCWT5Sensor(SensorData &data);

extern SensorData data;

#endif
