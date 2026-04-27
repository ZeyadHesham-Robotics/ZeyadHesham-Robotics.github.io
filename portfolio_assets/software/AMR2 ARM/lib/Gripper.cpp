#include "../include/Gripper.h"
#include <Arduino.h>

// variable to read the value from the analog pin

void moveServo(int angle)
{
    angle = constrain(angle, 0, 360);
    int minUs = 500;
    int maxUs = 2400;
    int pulseWidthUs = map(angle, 0, 360, minUs, maxUs);

    uint32_t duty = (pulseWidthUs * 65536UL) / 20000UL; // Convert µs to 16-bit PWM duty
    ledcWrite(PWM_CHANNEL, duty);
}

void gripper_Init()
{
    ledcSetup(PWM_CHANNEL, PWM_FREQ, PWM_RES_BITS);
    ledcAttachPin(SERVO_PIN, PWM_CHANNEL);
    Serial.println("Gripper initialized.");
}

void gripper_Open()
{
    moveServo(240); // Adjust as needed for open
    Serial.println("Gripper opened.");
}

void gripper_Close()
{
    moveServo(200); // Adjust as needed for closed
    Serial.println("Gripper closed.");
}
