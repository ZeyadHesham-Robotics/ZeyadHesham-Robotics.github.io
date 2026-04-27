#include "../include/IR.h"
#include <Arduino.h>

int activeCount;

const int sensorPins[5] = {
    IR0_PIN, IR1_PIN, IR2_PIN, IR3_PIN, IR4_PIN};

void initIRSensors()
{
    for (int i = 0; i < 5; i++)
    {
        pinMode(sensorPins[i], INPUT);
    }
}

float readLinePosition()
{
    int weights[5] = {-2, -1, 0, 1, 2}; // Left to right
    int positionSum = 0;
    activeCount = 0;

    Serial.print("Sensor States: ");

    for (int i = 0; i < 5; i++)
    {
        int reading = digitalRead(sensorPins[i]) == HIGH ? 1 : 0; // ACTIVE HIGH
        Serial.print("IR");
        Serial.print(i);
        Serial.print(":");
        Serial.print(reading);
        Serial.print("  ");

        positionSum += weights[i] * reading;
        activeCount += reading;
    }

    if (activeCount == 0)
    {
        Serial.println("-> NO LINE (return 0)");
        return 0.0;
    }

    float position = (float)positionSum / activeCount;
    Serial.print("-> Calculated Position: ");
    Serial.println(position, 2); // 2 decimal places

    return position;
}

bool allSensorsHigh()
{
    return digitalRead(IR0_PIN) &&
           digitalRead(IR1_PIN) &&
           digitalRead(IR2_PIN) &&
           digitalRead(IR3_PIN) &&
           digitalRead(IR4_PIN);
}
