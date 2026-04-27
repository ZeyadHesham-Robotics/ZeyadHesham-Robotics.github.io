#include "PIDController.h"

static float Kp = 0.0;

float computeCorrection(float currentPosition)
{
    float error = 0.0 - currentPosition; // Target is center (0.0)
    float output = Kp * error;
    return output;
}
