#ifndef SENSORSMANAGER_H
#define SENSORSMANAGER_H

#include "../../include/Pinout.h"
#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ===== Constants =====
const float VREF = 3.3;
const int ADC_MAX = 4095;
const int SAMPLES = 1000;             // start here; adjust if needed
const float ACS_SENSITIVITY = 0.185f; // V/A for ACS712-5A; change if using 20A/30A

// Channel map
#define CH_V_P0 4
#define CH_V_P1 5
#define CH_V_P2 6
#define CH_V_P3 7
#define CH_I_P0 0
#define CH_I_P1 1
#define CH_I_P2 2
#define CH_I_P3 3

// ===== API =====
void Sensors_Initialize();
void MUX_Select(uint8_t ch);
float readVoltage();         // expects MUX on a voltage divider channel
float readCurrent();         // expects MUX on an ACS channel
void calibrateZeroCurrent(); // measures zero-current voltage

struct PanelReading
{
    float voltage;     // V (post-divider, real panel voltage)
    float current;     // A
    float temperature; // °C
};

bool readPanelData(uint8_t panelIndex, PanelReading &out);

// Expose the last measured zero current offset (in volts)
extern float g_zero_current_voltage;

// Panel temperature sensors (4 separate buses)
extern DallasTemperature ds18b200;
extern DallasTemperature ds18b201;
extern DallasTemperature ds18b202;
extern DallasTemperature ds18b203;

#endif // SENSORSMANAGER_H
