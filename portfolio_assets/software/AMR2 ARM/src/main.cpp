#include <Arduino.h>
#include "../lib/IR.cpp"
#include "../lib/Steppers.cpp"
#include "../lib/Gripper.cpp"
#include "../lib/PID.cpp"
#include "../lib/Arm.cpp"
#include <AccelStepper.h>

bool armEnabled = false; // Arm is disabled by default

void IRTask(void *pvParameters);

void setup()
{
  Serial.begin(9600);
  Serial.println("ARM ESP32 Booting...");
  gripper_Init(); // Initialize gripper
  initIRSensors();
  Serial.println("IR sensors initialized.");
  initSteppers();
  Serial.println("Steppers initialized.");
  Serial.println("Arm control initialized.");

  // Start IR reporting task
  xTaskCreate(IRTask, "IRTask", 2048, NULL, 1, NULL);
}

void loop()
{
  runAllSteppers(); // Always call this for smooth motion

  if (Serial.available())
  {
    char x = Serial.read();
    Serial.print("Serial input received: ");
    Serial.println(x);

    switch (x)
    {
    case 'z':
      armEnabled = true;
      enableMotors();
      Serial.println("Arm ENABLED.");
      break;
    case 'x':
      armEnabled = false;
      disableMotors();
      Serial.println("Arm DISABLED.");
      break;
    case 'w':
      if (armEnabled)
      {
        Serial.println("Manual: Base +100 steps");
        Base.move(100);
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 's':
      if (armEnabled)
      {
        Serial.println("Manual: Base -100 steps");
        Base.move(-100);
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 'a':
      if (armEnabled)
      {
        Serial.println("Manual: Shoulder +100 steps");
        Shoulder.move(100);
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 'd':
      if (armEnabled)
      {
        Serial.println("Manual: Shoulder -100 steps");
        Shoulder.move(-100);
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 'q':
      if (armEnabled)
      {
        Serial.println("Manual: Elbow +100 steps");
        Elbow.move(100);
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 'e':
      if (armEnabled)
      {
        Serial.println("Manual: Elbow -100 steps");
        Elbow.move(-100);
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 'i':
      if (armEnabled)
      {
        Serial.println("Manual: Gripper Open");
        gripper_Open();
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    case 'o':
      if (armEnabled)
      {
        Serial.println("Manual: Gripper Close");
        gripper_Close();
      }
      else
      {
        Serial.println("Arm is DISABLED.");
      }
      break;
    default:
      Serial.print("Unknown command: ");
      Serial.println(x);
      break;
    }
    runAllSteppers(); // Process moves after command
  }
}

// FreeRTOS task for IR correction reporting
void IRTask(void *pvParameters)
{
  const unsigned long irInterval = 1000; // ms
  for (;;)
  {
    float position = readLinePosition();   // Your IR.cpp function
    int correction = (int)round(position); // Or scale as needed

    // Only send if a line is detected (optional)
    // if (allSensorsHigh()) {
    //   // Optionally skip sending if all sensors are white
    // } else {
    Serial.print("CORRECTION:");
    Serial.println(correction);
    // }

    vTaskDelay(irInterval / portTICK_PERIOD_MS);
  }
}