#include "../include/PINOUT.h"

float readACVoltage()
{
    long sumSq = 0;
    for (int i = 0; i < SAMPLES; i++)
    {
        int raw = analogRead(ZMPT_PIN);
        float voltage = (raw - 2048) * (VREF / ADC_MAX); // Convert ADC value to voltage
        sumSq += voltage * voltage;
    }
    float meanSq = sumSq / float(SAMPLES);
    float vrms = sqrt(meanSq);
    return vrms * CALIBRATION_FACTOR; // Apply calibration factor
}