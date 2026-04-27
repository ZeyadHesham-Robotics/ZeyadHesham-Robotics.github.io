#ifndef STEPPERS_H
#define STEPPERS_H

#define MOTION_SPEED 5000.0     // Speed for the motion base motors
#define MOTION_MAX_SPEED 500.0  // Maximum speed for the motion base motors
#define MOTION_ACCELERATION 200 // Acceleration for the motion base motors

#define BASE_STEP 12
#define BASE_DIR 14
#define BASE_ENABLE 19 // Enable pin for back left stepper

#define SHOULDER_STEP 15
#define SHOULDER_DIR 13
#define SHOULDER_ENABLE 18 // Enable pin for back right stepper

#define ELBOW_STEP 2
#define ELBOW_DIR 4
#define ELBOW_ENABLE 21 // Enable pin for front left stepper

void initSteppers(void);
void enableMotors(void);
void disableMotors(void);
void setAllSpeeds(float speed);
void runAllSteppers(void);

#endif
