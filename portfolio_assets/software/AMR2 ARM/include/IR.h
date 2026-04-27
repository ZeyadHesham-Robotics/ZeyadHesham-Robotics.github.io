// IRLineSensor.h
#pragma once

// Sensor pins (customize as needed)
#define IR0_PIN 25
#define IR1_PIN 33
#define IR2_PIN 26
#define IR3_PIN 27
#define IR4_PIN 32

void initIRSensors();
float readLinePosition(); // Returns -2 to +2
bool allSensorsHigh();