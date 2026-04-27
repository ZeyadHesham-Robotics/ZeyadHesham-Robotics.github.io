#ifndef _SERVO_H
#define _SERVO_H

#pragma once

#define SERVO_PIN 5
#define PWM_CHANNEL 0
#define PWM_FREQ 50
#define PWM_RES_BITS 16

void gripper_Init();
void gripper_Open();
void gripper_Close();
void moveServo(int angle);

#endif
// Servo.h
