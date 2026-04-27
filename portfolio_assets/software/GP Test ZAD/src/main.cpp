#include <Arduino.h>

void setup()
{
  // Initialize serial communication at 9600 bits per second:
  Serial.begin(9600);
}

void loop()
{
  float PH = analogRead(32);
  Serial.println(PH);
  delay(1000);
}