#ifndef HEADER_H
#define HEADER_H

#define U8G2_16BIT

// Stepper Motor ///////////////////////////////////////////////////////////////////////////

// #include <MobaTools.h>

#define stepPin 54
#define dirPin 55
#define enPin 38

// MoToStepper stepper( 1600, STEPDIR );

// Rotary Encoder //////////////////////////////////////////////////////////////////////////

#define ROTARY_PIN1 33
#define ROTARY_PIN2 31
#define BUTTON_PIN 35

#define CLICKS_PER_STEP 4 // this number depends on your rotary encoder
#define MIN_POS -10000
#define MAX_POS 10000
#define START_POS 0
#define INCREMENT 1 // this number is the counter increment on each step

// Buzzer & Switch///////////////////////////////////////////////////////////////////////////////////
#define Buzz 37
#define PButton 3

// Variables//////////////////
unsigned long Timerx = 0;
unsigned long GLCDR = 0;
unsigned long stepperx = 0;
unsigned long S_I = 0;    // Serial Interval
unsigned long LPPB_I = 0; // Long Press Push Button Interval
unsigned long frame_refresh = 0;
unsigned long frame_refreshX = 0;
unsigned long EM_I = 0; // Elapsed Minutes Interval
unsigned long Timer_Interval = 0;

float Stepper_Steps = 0;
float Stepper_SPS_Speed = 0; // Stepper Step/sec Speed
float Stepper_timex = 0;

int Timer = 0; // Timer Value - Min
int timer = 0; // EEPROM Timer Value Location

int Angle = 0;  // Angle Value - deg
int angle = 10; // EEPROM Angle Value Location

float RPM_Speed = 0; // Speed Value - RPM
int rpm_speed = 20;  // EEPROM Speed Value Location

int i = 0, j = 0;
int pos = 0;
int Mode = 0; // Stepper Motor Mode (Running / Paused / Stoped)
int rel = 0;
int GLCDRC = 0; // GLCD Refreshing Counter
int EFRC1 = 0;  // Edit Frame Refresh Counter 1
int EFRC2 = 0;  // Edit Frame Refresh Counter 2
int EFRC3 = 0;  // Edit Frame Refresh Counter 3
int ECs = 0;    // Encoder Clicks
int FR = 0;
int omo = 0;
int SMode = 0;
int ZP = 0;

#endif
