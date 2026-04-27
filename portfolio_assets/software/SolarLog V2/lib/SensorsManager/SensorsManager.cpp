#include "SensorsManager.h"
#include <Wire.h>
#include <driver/adc.h>

/*
| Function Name                                        | Description                                                                                                 |
|------------------------------------------------------|-------------------------------------------------------------------------------------|
| adcToVolt(int adc)                                   | Converts a raw ADC value to voltage using the reference voltage and ADC resolution.                         |
| MUX_Select(uint8_t ch)                               | Sets the multiplexer to the specified channel by controlling S0-S3 pins and waits for signal to settle.     |
| Sensors_Initialize()                                 | Initializes Dallas temperature sensors, sets up MUX control pins, ADC input, and sets default MUX channel.  |
| readVoltage()                                        | Reads and averages analog samples from the voltage channel, converts to voltage, and applies divider scale. |
| readCurrent()                                        | Reads and averages analog samples from the current channel, converts to voltage, and calculates current.    |
| calibrateZeroCurrent()                               | Calibrates the zero-current voltage by averaging ADC readings when no current is flowing.                   |
| readTempC(uint8_t idx)                               | Reads temperature in Celsius from the Dallas sensor at the given index (0-3).                               |
| readPanelData(uint8_t panelIndex, PanelReading &out) | Reads voltage, current, and temperature for a given panel index and fills the output struct.                |
*/

// ===== OneWire & Dallas setup =====
OneWire DS18B20_Zero(DS18B20_0);
OneWire DS18B20_One(DS18B20_1);
OneWire DS18B20_Two(DS18B20_2);
OneWire DS18B20_Three(DS18B20_3);

DallasTemperature ds18b200(&DS18B20_Zero);
DallasTemperature ds18b201(&DS18B20_One);
DallasTemperature ds18b202(&DS18B20_Two);
DallasTemperature ds18b203(&DS18B20_Three);

float g_zero_current_voltage = 1.54; // will be updated by /calibrate
float g_zero_voltage_voltage = 0.5;  // will be updated by /calibrate

static inline float adcToVolt(int adc)
{
    return (adc * VREF) / ADC_MAX;
}

void MUX_Select(uint8_t ch)
{
    digitalWrite(MUX_S0, (ch >> 0) & 0x1);
    digitalWrite(MUX_S1, (ch >> 1) & 0x1);
    digitalWrite(MUX_S2, (ch >> 2) & 0x1);
    digitalWrite(MUX_S3, (ch >> 3) & 0x1);
    delayMicroseconds(50); // allow MUX & ADC input to settle
}

void Sensors_Initialize()
{
    // Dallas sensors
    ds18b200.begin();
    ds18b201.begin();
    ds18b202.begin();
    ds18b203.begin();

    // MUX select pins
    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    // ADC input
    pinMode(MUX_Signal, INPUT); // GPIO36 has no pullups/downs

    // default MUX = 0
    MUX_Select(0);
}
float readVoltage()
{
    // Average samples
    uint32_t sum = 0;
    for (int i = 0; i < SAMPLES; ++i)
    {
        sum += analogRead(MUX_Signal);
    }
    const float avg_adc = sum / (float)SAMPLES;

    // ADC node voltage (0..VREF), for thresholding/logging
    const float v_adc = adcToVolt((int)avg_adc);

    // Convert to real panel voltage using your existing scale (29.15 V full-scale)
    const float v_panel = (avg_adc / ADC_MAX) * 29.15f;

    Serial.print("Raw voltage Vadc: ");
    Serial.println(v_adc, 4);

    // Clamp small/offset voltages to zero (compare at the ADC node)
    if (v_adc <= g_zero_voltage_voltage)
    {
        return 0.0f; // <-- return the clamped value
    }

    return v_panel; // normal case
}

float readCurrent()
{
    uint32_t sum = 0;
    for (int i = 0; i < SAMPLES; ++i)
    {
        sum += analogRead(MUX_Signal);
    }

    const float avg_adc = sum / (float)SAMPLES;
    const float v = adcToVolt((int)avg_adc); // your adcToVolt(int) API
    Serial.print("Raw current V: ");
    Serial.println(v, 4);

    float current = (v - g_zero_current_voltage) / ACS_SENSITIVITY; // amps

    // Deadband: treat anything within ±0.20 A of zero as zero
    if (fabsf(current) < 0.20f)
        current = 0.0f;

    // Unipolar clamp (optional: keep if you never expect reverse current)
    if (current < 0.0f)
        current = 0.0f;

    return current * 2.22; // <-- always return
}

void calibrateZeroCurrent()
{
    // Ensure no current flows through ACS sensors during this call
    MUX_Select(CH_I_P0);
    uint32_t sum = 0;
    for (int i = 0; i < SAMPLES; ++i)
    {
        sum += analogRead(MUX_Signal);
        delayMicroseconds(200);
    }
    float v = adcToVolt(int(float(sum) / SAMPLES));
    g_zero_current_voltage = v;
}

static float readTempC(uint8_t idx)
{
    switch (idx)
    {
    case 0:
        ds18b200.requestTemperatures();
        return ds18b200.getTempCByIndex(0);
    case 1:
        ds18b201.requestTemperatures();
        return ds18b201.getTempCByIndex(0);
    case 2:
        ds18b202.requestTemperatures();
        return ds18b202.getTempCByIndex(0);
    case 3:
        ds18b203.requestTemperatures();
        return ds18b203.getTempCByIndex(0);
    default:
        return NAN;
    }
}

bool readPanelData(uint8_t panelIndex, PanelReading &out)
{
    if (panelIndex > 3)
        return false;

    // Select voltage channel for this panel
    const uint8_t vch[4] = {CH_V_P0, CH_V_P1, CH_V_P2, CH_V_P3};
    const uint8_t ich[4] = {CH_I_P0, CH_I_P1, CH_I_P2, CH_I_P3};

    MUX_Select(vch[panelIndex]);
    delayMicroseconds(50); // allow MUX & ADC input to settle
    out.voltage = readVoltage();

    MUX_Select(ich[panelIndex]);
    delayMicroseconds(50); // allow MUX & ADC input to settle
    out.current = readCurrent();

    out.temperature = readTempC(panelIndex);
    return true;
}
