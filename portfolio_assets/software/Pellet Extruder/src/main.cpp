#include <Arduino.h>
#include <HardwareSerial.h>

#define TXD2 17
#define RXD2 16

void setup()
{

  // Initialize UART2 with a specific baud rate and the assigned pins
  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);
}

void loop()
{
  // Example: read from UART2 and print to Serial Monitor
  Serial2.println("Hello from UART2!");
  delay(1000);
}