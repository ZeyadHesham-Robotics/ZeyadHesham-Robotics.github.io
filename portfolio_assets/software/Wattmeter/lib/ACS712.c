#include "PINOUT.h"

const float sensitivity = 0.066;         // ACS712-30A = 66mV per A
const float zero_current_voltage = 1.65; // Voltage at 0A (calibrate this)
float readACCurrent()
{
    long sum = 0;

    for (int i = 0; i < SAMPLES; i++)
    {
        int adc = analogRead(ACS_PIN);
        float voltage = (adc * VREF) / ADC_MAX;
        float centered = voltage - zero_current_voltage;
        sum += centered * centered;
        delayMicroseconds(100);
    }

    float vrms = sqrt(sum / float(SAMPLES));
    float current = (vrms / sensitivity) * 0.54;

    return current;
}
