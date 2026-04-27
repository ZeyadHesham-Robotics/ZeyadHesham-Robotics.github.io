#include "Signals.h"
#include "../include/Config.h"

// Only defined here, declared extern elsewhere
byte buffer[256];
int bufIndex = 0;
int Time_Interval = 1000; // Time interval in milliseconds
unsigned long lastByteTime = 0;
unsigned long frameGap = 5; // Gap time to consider end of frame (in milliseconds)

void setup()
{
  ModbusInit();
  initPWM();
}

void loop()
{
  if (millis() - lastByteTime > Time_Interval)
  {
    ListenModbus();

    Serial.println("Received Frame:");
    for (int i = 0; i < bufIndex; i++)
    {
      Serial.print(buffer[i], HEX);
      Serial.print(" ");
    }
    Serial.println();
    if (bufIndex > 0 && millis() - lastByteTime > frameGap)
    {
      decodePLCFrame();
      pwmUpdate(led1_pwm, led2_pwm, esc_pwm);
      bufIndex = 0;
    }
    Serial.println("LED1 PWM: " + String(led1_pwm) + " | LED2 PWM: " + String(led2_pwm) + " | ESC PWM: " + String(esc_pwm));
  }
}

    ة, String()epwescesc_pwm    + String(" | Solenoid Close: ") + String(Solenoid_Close_Status) + String(" | Heater: ") + String(Heater_Status, String(esc_pwm_activate)));
    

    + String(" | Solenoid Close: ") + String(Solenoid_Close_Status) + String(" | Heater: ") + String(Heater_Status, String(esc_pwm));escpw"" |    + String(" | Solenoid Close: ") + String(Solenoid_Close_StatString(" | Heater: ") + String(Heater_Status, String(" | ESC Activate: ") + String(esc_pwm_activate)));) ""+