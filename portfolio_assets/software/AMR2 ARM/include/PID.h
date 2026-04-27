#pragma once

void initPID(float kp);               // Initialize controller
float computeCorrection(float input); // Returns P-only correction
