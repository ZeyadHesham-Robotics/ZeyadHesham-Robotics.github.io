#include "../include/sensor_definitions.h"
#include "../lib/CommsManager/commLayer.h"

void setup()
{
  initSensors();
  CommInit();
}

void loop()
{
  readCWT5Sensor();
  publishSensorDataMQTT(wifiMqttClient, data);
  if (!wifiMqttClient.connected())
  {
    reconnect();
  }
  wifiMqttClient.loop();
  delay(100);
}
