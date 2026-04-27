#ifndef CONFIG_H
#define CONFIG_H

// =======================
// Pin Definitions
// =======================
#define RXD2 17
#define TXD2 16

// =======================
// PWM Parameters
// =======================
// For LEDs
#define LED_PWM_FREQ 5000    // 5 kHz
#define LED_PWM_RESOLUTION 8 // 8-bit resolution (0–255)

// For ESC
#define ESC_PWM_FREQ 50       // 50 Hz (20 ms period)
#define ESC_PWM_RESOLUTION 16 // 16-bit resolution (0–65535)

// ESC pulse width range (in microseconds)
#define ESC_MIN_PULSE_US 1000
#define ESC_MAX_PULSE_US 2000

#define LED1_CH 0
#define LED2_CH 1
#define ESC_CH 2

#define LED1_PIN 25
#define LED2_PIN 26
#define ESC_PIN 27

#define SOLENOID_OPEN_PIN 32
#define SOLENOID_CLOSE_PIN 33
#define DOOR_LIGHT_PIN 12
#define HEATER_PIN 14

// =======================
// Modbus Parameters
// =======================
#define MODBUS_SLAVE_ID 2

#endif
