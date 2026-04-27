#include <Arduino.h>
#include "header.h"
#include <EEPROM.h>
#include <U8g2lib.h>
#include <AccelStepper.h>
#include "MotorEncoder.ino"
#include "Stepper.ino"
#include "Push_Button.ino"

U8G2_ST7920_128X64_F_SW_SPI u8g2(U8G2_R0, 23, 17, 16);
AccelStepper stepper(1, stepPin, dirPin); // (Typeof driver, STEP, DIR)

void setup()
{
  Serial.begin(9600);
  delay(50);

  GLCD_Setup();
  Encoder_Setup();
  Stepper_Setup();
  PButton_Setup();
  MotorEncoderInit();

  pinMode(Buzz, OUTPUT);

  if (EEPROM.get(rpm_speed, RPM_Speed) > 0)
    RPM_Speed = EEPROM.get(rpm_speed, RPM_Speed);
  else
    EEPROM.put(rpm_speed, 0);
  if (EEPROM.get(angle, Angle) > 0)
    Angle = EEPROM.get(angle, Angle);
  else
    EEPROM.put(angle, 0);
  if (EEPROM.get(timer, Timer) > 0)
    Timer = EEPROM.get(timer, Timer);
  else
    EEPROM.put(timer, 0);

  SMode = 0;
}

void loop()
{ /*
   digitalWrite(enPin,LOW);
   stepper.setMaxSpeed(1000000);
   stepper.setSpeed(20000);
   stepper.runSpeed();
 */
  // Main Functions Loops
  GLCD_Loop();
  Encoder_Loop();
  Stepper_Loop();
  PButton_Loop();
  MotorEncoderRead();

  // Serial Print
  /*
    if(millis()-S_I > 1000){
     Serial.print("Speed : " ); Serial.print(EEPROM.read(rpm_speed)); Serial.print(" RPM | " ); Serial.print(RPM_Speed); Serial.print(" | " );Serial.println(Stepper_SPS_Speed);
     Serial.print("Angle : " ); Serial.print(EEPROM.read(angle)); Serial.print(" deg | " ); Serial.println(Angle);
     Serial.print("Timer : " ); Serial.print(EEPROM.read(timer)); Serial.print(" Min | " ); Serial.println(Timer);
     Serial.print("Timer Millis : " ); Serial.print(Stepper_timex ); Serial.println(" msec" );
     Serial.print("Push Button State : "); Serial.print(digitalRead(PButton)); Serial.print(" | "); Serial.print("Mode : "); Serial.println(Mode);
     Serial.println();

     S_I = millis() ;
    }
  */
}

void Encoder_Setup()
{
  b.begin(BUTTON_PIN);
  b.setTapHandler(click);
  b.setLongClickHandler(resetPosition);
  b.setDoubleClickHandler(DoubleClick);
  // b.setLongClickTime(1000);

  r.begin(ROTARY_PIN1, ROTARY_PIN2, CLICKS_PER_STEP, MIN_POS, MAX_POS, START_POS, INCREMENT);
  r.setChangedHandler(rotate);
  r.setLeftRotationHandler(showDirection);
  r.setRightRotationHandler(showDirection);
}

void Encoder_Loop()
{
  r.loop();
  b.loop();
}

/////////////////////////////////////////////////////////////////

// on change
void rotate(Rotary &r)
{
  // Serial.println(r.getPosition());
  if (Mode == 2 || Mode == 0)
  {
  }
}

// on left or right rotation
void showDirection(Rotary &r)
{
  // Serial.println(r.directionToString(r.getDirection()));
  if (Mode == 2 || Mode == 0)
  {

    if (r.directionToString(r.getDirection()) == "RIGHT")
    {
      if (ECs == 1)
      {
        RPM_Speed += 10;
      }
      if (ECs == 2)
      {
        Angle += 15;
        if (Angle > 360)
          Angle = 360;
      }
      if (ECs == 3)
      {
        Timer += 1;
      }
    }
    else
    {
      if (ECs == 1)
      {
        RPM_Speed -= 10;
        if (RPM_Speed < 0)
          RPM_Speed = 0;
      }
      if (ECs == 2)
      {
        Angle -= 15;
        if (Angle < 0)
          Angle = 0;
      }
      if (ECs == 3)
      {
        Timer -= 1;
        if (Timer < 0)
          Timer = 0;
      }
    }
    digitalWrite(Buzz, HIGH);
    delay(10);
    digitalWrite(Buzz, LOW);

    GLCDRC = 0; // Refresh GLCD
    EFRC1 = EFRC2 = EFRC3 = 0;
  }
}

// single click
void click(Button2 &btn)
{
  // Serial.println(b.getLongClickTime());
  if (Mode == 2 || Mode == 0)
  {
    GLCD_BE(); // Refresh GLCD

    EEPROM.put(rpm_speed, RPM_Speed);
    EEPROM.put(angle, Angle);
    EEPROM.put(timer, Timer);

    digitalWrite(Buzz, HIGH);
    delay(10);
    digitalWrite(Buzz, LOW);
    ECs++;

    Stepper_Steps = map(Angle, 0, 360, 0, 3200);
    Stepper_SPS_Speed = ((RPM_Speed * 3200) / 60);
    Stepper_timex = (Stepper_Steps / Stepper_SPS_Speed) * 1000; // Time in msec

    Serial.print("Speed : ");
    Serial.print(EEPROM.get(rpm_speed, RPM_Speed));
    Serial.print(" RPM | ");
    Serial.print(RPM_Speed);
    Serial.print(" | ");
    Serial.println(Stepper_SPS_Speed);
    Serial.print("Angle : ");
    Serial.print(EEPROM.get(angle, Angle));
    Serial.print(" deg | ");
    Serial.println(Angle);
    Serial.print("Timer : ");
    Serial.print(EEPROM.get(timer, Timer));
    Serial.print(" Min | ");
    Serial.println(Timer);
    Serial.print("Timer Millis : ");
    Serial.print(Stepper_timex);
    Serial.println(" msec");
  }
  if (ECs > 3)
  {
    EFRC1 = 0;
    EFRC2 = 0;
    EFRC3 = 0;
    ECs = 1;
  }
}

// long click

void resetPosition(Button2 &btn)
{
  // Serial.println(b.getType());
  if (Mode == 2 || Mode == 0)
  {
    // r.resetPosition();
    // GLCDRC = 0 ;
    ECs = 0;
    EFRC1 = EFRC2 = EFRC3 = 0;

    digitalWrite(Buzz, HIGH);
    delay(200);
    digitalWrite(Buzz, LOW);
    delay(200);
    digitalWrite(Buzz, HIGH);
    delay(200);
    digitalWrite(Buzz, LOW);
  }
}

/////////////////////////////////////////////////////////////////

const unsigned char REDS_bitmap[] PROGMEM =
    {
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x10,
        0x10,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x38,
        0x38,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFE,
        0x7F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x67,
        0xE6,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xC0,
        0x43,
        0xC2,
        0x03,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xE0,
        0xF0,
        0x0F,
        0x07,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x78,
        0x78,
        0x1E,
        0x0E,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x3C,
        0x1E,
        0x78,
        0x18,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xF8,
        0x0F,
        0xF0,
        0x3F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x30,
        0x02,
        0x40,
        0x0C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x20,
        0x02,
        0x40,
        0x04,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xF0,
        0x07,
        0xE0,
        0x0F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x38,
        0x0E,
        0x70,
        0x1C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x3C,
        0x3C,
        0x3C,
        0x0C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xF0,
        0xF0,
        0x0F,
        0x07,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xC0,
        0x61,
        0x86,
        0x03,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x80,
        0x43,
        0xE2,
        0x01,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFF,
        0xFF,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x3C,
        0x3C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x18,
        0x18,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xF8,
        0xFF,
        0x3F,
        0xF8,
        0xFF,
        0x1F,
        0xFC,
        0xFF,
        0x00,
        0xF8,
        0xFF,
        0x3F,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFC,
        0xFF,
        0x7F,
        0xFC,
        0xFF,
        0x1F,
        0xFE,
        0xFF,
        0x03,
        0xFC,
        0xFF,
        0x3F,
        0x00,
        0x00,
        0x00,
        0x00,
        0xFC,
        0xFF,
        0x7F,
        0xFC,
        0xFF,
        0x1F,
        0xFE,
        0xFF,
        0x0F,
        0xFE,
        0xFF,
        0x3F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x00,
        0x70,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x1F,
        0x0E,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x00,
        0x70,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x1C,
        0x0E,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x00,
        0x70,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x38,
        0x0E,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x00,
        0x70,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x38,
        0x0E,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x00,
        0x70,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x38,
        0x0E,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xFC,
        0x7F,
        0xFC,
        0xFF,
        0x1F,
        0x0E,
        0x00,
        0x38,
        0xFE,
        0xFF,
        0x0F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xFE,
        0x7F,
        0xFC,
        0xFF,
        0x1F,
        0x0E,
        0x00,
        0x38,
        0xFC,
        0xFF,
        0x1F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xFE,
        0x1F,
        0xFC,
        0xFF,
        0x1F,
        0x0E,
        0x00,
        0x38,
        0xF8,
        0xFF,
        0x3F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x1E,
        0x00,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x38,
        0x00,
        0x00,
        0x38,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x3E,
        0x00,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x38,
        0x00,
        0x00,
        0x38,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x7C,
        0x00,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x38,
        0x00,
        0x00,
        0x38,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xF8,
        0x00,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x1C,
        0x00,
        0x00,
        0x38,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xF0,
        0x01,
        0x1C,
        0x00,
        0x00,
        0x0E,
        0x00,
        0x1F,
        0x00,
        0x00,
        0x38,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xE0,
        0x03,
        0xFC,
        0xFF,
        0x1F,
        0xFE,
        0xFF,
        0x0F,
        0xFE,
        0xFF,
        0x3F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0xC0,
        0x07,
        0xFC,
        0xFF,
        0x1F,
        0xFE,
        0xFF,
        0x03,
        0xFE,
        0xFF,
        0x1F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x1C,
        0x80,
        0x0F,
        0xF8,
        0xFF,
        0x1F,
        0xFC,
        0xFF,
        0x00,
        0xFE,
        0xFF,
        0x0F,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x38,
        0x38,
        0x00,
        0x08,
        0x00,
        0x00,
        0x10,
        0x00,
        0x00,
        0x20,
        0x38,
        0x1C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x10,
        0x28,
        0x38,
        0x78,
        0x78,
        0x78,
        0x10,
        0x78,
        0xF0,
        0x00,
        0x28,
        0x04,
        0x00,
        0x00,
        0x00,
        0x00,
        0x10,
        0x38,
        0x08,
        0x48,
        0x48,
        0x48,
        0x10,
        0x48,
        0x90,
        0x20,
        0x38,
        0x1C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x10,
        0x08,
        0x08,
        0x48,
        0x48,
        0x48,
        0x10,
        0x48,
        0x90,
        0x20,
        0x08,
        0x10,
        0x00,
        0x00,
        0x00,
        0x00,
        0x10,
        0x38,
        0x38,
        0x48,
        0x48,
        0x78,
        0x30,
        0x78,
        0xF0,
        0x20,
        0x38,
        0x1C,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x80,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0xF0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
};

void GLCD_Setup(void)
{
  u8g2.begin();
  u8g2.clearBuffer();
  u8g2.setDrawColor(1);
  u8g2.drawXBMP(0, 0, 128, 64, REDS_bitmap);
  u8g2.sendBuffer();
  delay(5000);
}

void GLCD_BE()
{

  u8g2.clearBuffer();
  u8g2.setDrawColor(1);
  u8g2.setFont(u8g2_font_crox3hb_tf); // 12 Pixel
  u8g2.drawStr(2, 14, "Peptide Shaker");
  u8g2.drawBox(2, 20, 124, 2);

  u8g2.setFont(u8g2_font_profont11_tf); // 7 Pixel
  u8g2.drawStr(4, 31, "Speed :");
  u8g2.setCursor(60, 31);
  u8g2.print(RPM_Speed, 0);
  u8g2.drawStr(105, 31, "RPM");

  u8g2.drawStr(4, 41, "Angle :");
  u8g2.setCursor(60, 41);
  u8g2.print(Angle);
  u8g2.drawStr(105, 41, "deg");

  // u8g2.drawFrame(0,12,128,11);
  // u8g2.drawBox(0,12,128,1);
  u8g2.drawStr(4, 51, "Timer :");
  u8g2.setCursor(60, 51);
  u8g2.print(Timer);
  u8g2.drawStr(105, 51, "Min");
  u8g2.setFont(u8g2_font_baby_tf); // 5 Pixel - u8g2_font_tiny5_tr
  u8g2.drawStr(64, 61, "status ");
  if (Mode == 0)
    u8g2.drawStr(97, 61, "Stoped");
  if (Mode == 1)
    u8g2.drawStr(98, 61, "Runing");
  if (Mode == 2)
    u8g2.drawStr(96, 61, "Paused");
  u8g2.drawFrame(93, 53, 35, 11);
  u8g2.sendBuffer();
  // GLCDR = millis();
}
void GLCD_Loop(void)
{
  for (; GLCDRC < 1; GLCDRC++)
    GLCD_BE();
  if (ECs == 0)
    GLCD_BE();

  if (ECs == 1)
  {
    for (; EFRC1 < 1; EFRC1++)
    {
      u8g2.drawFrame(55, 22, 40, 11);
      u8g2.sendBuffer();
    }
  }

  if (ECs == 2)
  {
    for (; EFRC2 < 1; EFRC2++)
    {
      u8g2.drawFrame(55, 32, 40, 11);
      u8g2.sendBuffer();
    }
  }

  if (ECs == 3)
  {
    for (; EFRC3 < 1; EFRC3++)
    {
      u8g2.drawFrame(55, 42, 40, 11);
      u8g2.sendBuffer();
    }
  }
}

void Stepper_Setup()
{
  pinMode(enPin, OUTPUT);
}

void Stepper_Loop()
{

  if (Mode == 0 || Stepper_Steps <= 0)
  {
    digitalWrite(enPin, HIGH);
  } // Stoping
  else
  {
    digitalWrite(enPin, LOW);
    stepper.setMaxSpeed(100000000);
  }

  if (Mode == 1 && Timer > 0 && millis() - Timer_Interval <= (Timer * 60000))
  { // Running With Timer

    if (millis() - EM_I >= 60000)
    {
      Timer -= 1;
      GLCDRC = 0;
      EM_I = millis();
    }

    if (Angle < 360)
    {
      for (; ZP < 1; ZP++)
        stepper.setCurrentPosition(0);

      if (i == 0)
      {

        // by Step
        stepper.moveTo(Stepper_Steps);
        stepper.setSpeed(Stepper_SPS_Speed);
        stepper.runSpeedToPosition();
        if (stepper.distanceToGo() == 0)
        {
          i = 1;
        }

        // by Time
        /*
        if(millis() - stepperx <= Stepper_timex){
          stepper.setSpeed(Stepper_SPS_Speed);
          stepper.runSpeed();
        }else {stepperx = millis() ; i = 1; }
        */
      }

      if (i == 1)
      {

        // by Step
        stepper.moveTo(0);
        stepper.setSpeed(Stepper_SPS_Speed);
        stepper.runSpeedToPosition();
        if (stepper.distanceToGo() == 0)
        {
          i = 0;
        }

        // by Time
        /*
        if(millis() - stepperx <= Stepper_timex){
          stepper.setSpeed(-Stepper_SPS_Speed);
          stepper.runSpeed();
        }else {stepperx = millis() ; i = 0; }
        */
      }
    }
    else
    {
      stepper.setMaxSpeed(1000000);
      stepper.setSpeed(Stepper_SPS_Speed);
      stepper.runSpeed();
      ZP = 0;
    }
  }
  else
  {
    Timer_Interval = millis();
    EM_I = millis();
    for (; SMode < 1; SMode++)
      Mode = 0;
  }

  if (Mode == 2 && Timer > 0)
  { // Pausing
    stepper.stop();
    for (; omo < 1; omo++)
    { /*Timer = 0;*/
      GLCDRC = 0;
    }
  }
  else
    omo = 0;

  if (Mode == 1 && Timer == 0)
  { // Finished
    Mode = 0;
    GLCDRC = 0;
    digitalWrite(Buzz, HIGH);
    delay(200);
    digitalWrite(Buzz, LOW);
    delay(200);
    digitalWrite(Buzz, HIGH);
    delay(200);
    digitalWrite(Buzz, LOW);
    delay(200);
    digitalWrite(Buzz, HIGH);
    delay(200);
    digitalWrite(Buzz, LOW);
  }
}

void PButton_Setup()
{
  pinMode(PButton, INPUT_PULLUP);
}

void PButton_Loop()
{

  if (!digitalRead(PButton))
  {
    if (millis() - LPPB_I > 2000)
    {
      Mode = ECs = 0;
      Angle = RPM_Speed = Timer = 0;
      EEPROM.put(angle, Angle);
      EEPROM.put(rpm_speed, RPM_Speed);
      EEPROM.put(timer, Timer);
    }
    for (; j < 1; j++)
    {
      Mode++;
      digitalWrite(Buzz, HIGH);
      delay(20);
      digitalWrite(Buzz, LOW);
    }
    if (Mode > 2)
      Mode = 1;
    GLCDRC = 0;
  }
  else
  {
    j = 0;
    LPPB_I = millis();
  }
}