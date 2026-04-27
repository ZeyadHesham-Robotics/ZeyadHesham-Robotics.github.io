#include "SensorsManager.h"
#include "Connectivity.h"

void setup()
{
    Serial.begin(9600);
    Sensors_Initialize();
    calibrateZeroCurrent();
}

void loop()
{
    PanelReading reading;
    for (int x = 0; x < 4; ++x)
    {
        if (readPanelData(x, reading))
        {
            Serial.print("Panel 0 - Voltage: ");
            Serial.print(reading.voltage);
            Serial.print(" V, Current: ");
            Serial.print(reading.current);
            Serial.print(" A, Temperature: ");
            Serial.print(reading.temperature);
            Serial.println(" °C");
        }
        else
        {
            Serial.println("Failed to read panel data.");
        }
        delay(1000); // Wait for 5 seconds before next reading
    }
}