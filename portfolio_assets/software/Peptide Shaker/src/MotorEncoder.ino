#include <Wire.h>
#include "AS5600.h"
#define AS5600_CLOCK_WISE 0
#define AS5600_COUNTER_CLOCK_WISE 1
AS5600 ASL;

void MotorEncoderInit()
{
    Wire.begin();
    ASL.begin(4);                        //  set direction pin.
    ASL.setDirection(AS5600_CLOCK_WISE); //  default, just be explicit.
    int b = ASL.isConnected();
    Serial.print("Connect: ");
    Serial.println(b);

    Serial.print("ADDR: ");
    Serial.println(ASL.getAddress());

    // ASL.setAddress(0x38);

    Serial.print("ADDR: ");
    Serial.println(ASL.getAddress());
}
float MotorEncoderRead()
{
    float angle = ASL.readAngle();
    return angle;
}
