#include "SensorsManager.h"
#include "Connectivity.h"
#include "LCD.h"

void setup()
{
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  Serial.begin(9600);
  Sensors_Initialize();
  calibrateZeroCurrent();
  connectWiFi();
  mqtt_init();
  LCD_Begin(0x27); // change to 0x3F if needed
}

void loop()
{
  static unsigned long lastSwitch = 0;
  static bool showVI = true;

  mqtt_loop();
  publishAllPanels(true); // non-blocking; skips if not connected

  PanelReading panels[4];
  if (readAllPanels(panels))
  {
    if (showVI)
      LCD_ShowPage_VI(panels);
    else
      LCD_ShowPage_PT(panels);
  }

  // switch page every 2 seconds
  if (millis() - lastSwitch > 2000)
  {
    showVI = !showVI;
    lastSwitch = millis();
  }

  delay(200); // small pace; keep display responsive
}
