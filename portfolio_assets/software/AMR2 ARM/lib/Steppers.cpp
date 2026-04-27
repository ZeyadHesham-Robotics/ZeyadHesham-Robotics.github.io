#include <Arduino.h>
#include "Steppers.h"
#include <AccelStepper.h>
#include "../include/Gripper.h"

AccelStepper Base(AccelStepper::DRIVER, BASE_STEP, BASE_DIR);
AccelStepper Shoulder(AccelStepper::DRIVER, SHOULDER_STEP, SHOULDER_DIR);
AccelStepper Elbow(AccelStepper::DRIVER, ELBOW_STEP, ELBOW_DIR);

void initSteppers()
{
    // Setup motion parameters
    Base.setMaxSpeed(MOTION_MAX_SPEED);
    Base.setAcceleration(MOTION_ACCELERATION);

    Shoulder.setMaxSpeed(MOTION_MAX_SPEED);
    Shoulder.setAcceleration(MOTION_ACCELERATION);

    Elbow.setMaxSpeed(MOTION_MAX_SPEED);
    Elbow.setAcceleration(MOTION_ACCELERATION);

    // Setup enable pins
    pinMode(BASE_ENABLE, OUTPUT);
    pinMode(SHOULDER_ENABLE, OUTPUT);
    pinMode(ELBOW_ENABLE, OUTPUT);
}

void enableMotors()
{
    digitalWrite(BASE_ENABLE, LOW);
    digitalWrite(SHOULDER_ENABLE, LOW);
    digitalWrite(ELBOW_ENABLE, LOW);
}

void disableMotors()
{
    digitalWrite(BASE_ENABLE, HIGH);
    digitalWrite(SHOULDER_ENABLE, HIGH);
    digitalWrite(ELBOW_ENABLE, HIGH);
}

void setAllSpeeds(float speed)
{
    Base.setSpeed(speed);
    Shoulder.setSpeed(speed);
    Elbow.setSpeed(speed);
}
void runAllSteppers()
{
    Base.run();
    Shoulder.run();
    Elbow.run();
}

// === Move joint by index (blocking) ===
void moveJointTo(int jointIndex, long targetSteps)
{
    switch (jointIndex)
    {
    case 0:
        Base.moveTo(targetSteps);
        while (Shoulder.distanceToGo() != 0)
            Base.run();
        break;
    case 1:
        Shoulder.moveTo(targetSteps);
        while (Shoulder.distanceToGo() != 0)
            Shoulder.run();
        break;
    case 2:
        Elbow.moveTo(targetSteps);
        while (Elbow.distanceToGo() != 0)
            Elbow.run();
        break;
    }
}

// === Pick object ===
void pickSequence()
{
    Serial.println("Executing PICK sequence...");
    moveJointTo(0, 500); // shoulder down
    moveJointTo(1, 400); // elbow extend
    moveJointTo(2, 100); // wrist down
    gripper_Close();     // close gripper
    delay(300);
}

// === Rotate object ===
void rotateSequence()
{
    Serial.println("Executing ROTATE sequence...");
    moveJointTo(2, 500); // wrist rotate
    delay(300);
}

// === Place object ===
void placeSequence()
{
    Serial.println("Executing PLACE sequence...");
    moveJointTo(0, 600); // shoulder up
    moveJointTo(1, 300); // elbow retract
    gripper_Open();      // release
    delay(300);
}

// === Full action ===
void executePickRotatePlace()
{
    pickSequence();
    rotateSequence();
    placeSequence();
}