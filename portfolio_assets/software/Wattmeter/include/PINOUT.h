#ifndef PINOUT_H
#define PINOUT_H

#include <Arduino.h>
#define ZMPT_PIN 32            // ZMPT101B voltage sensor pin
#define ACS_PIN 33             // ACS712 current sensor pin
#define SENSOR_OFFSET 2048.0   // Midpoint for ADC readings (2.5V
#define CALIBRATION_FACTOR 294 // Calibration factor for ZMPT101B
#define SENSITIVITY 0.185      // Sensitivity for ACS712-30A (66mV per amp)
#define VOLTAGE_OFFSET 2048.0  // Offset for ZMPT101B voltage sensor
#define CURRENT_OFFSET 2048.0  // Offset for ACS712 current sensor
// LCD: ST7920 128x64 via Software SPI
#define CLK 18
#define DATA 23
#define CS 5
#define RST 22

const float VREF = 3.3;
const int ADC_MAX = 4095;
const int SAMPLES = 5000;
//=============FUNCTIONS========================
float readACVoltage(void);
float readACCurrent(void);

#endif // PINOUT_H