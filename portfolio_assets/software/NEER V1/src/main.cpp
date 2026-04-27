#include <Arduino.h>
#include "../include/sensor_definitions.h"
#include "../lib/CommsManager/CommsManager.h"
#include "../lib/SensorManager/SensorManager.h"
#include <PubSubClient.h>

unsigned long lastSensorRead = 0;
unsigned long lastCommsSend = 0;

const unsigned long SENSOR_INTERVAL = 20000;
const unsigned long COMMS_INTERVAL = 30000;

void setup()
{
  initSensors();
  Serial.begin(9600);
  delay(2000);
  CommInit();
}

void loop()
{
  unsigned long now = millis();

  // Read sensors periodically
  if (now - lastSensorRead >= SENSOR_INTERVAL)
  {
    lastSensorRead = now;
    Serial.println("[Sensors] Reading all sensors...");
    // readAllSensors();
  }

  // Send comms periodically
  if (now - lastCommsSend >= COMMS_INTERVAL)
  {
    readAllSensors();
    lastCommsSend = now;
    Serial.println("[Comms] Sending sensor data...");
    comManager.loop(data);
  }

  // Let ESP breathe
  delay(10);
}
