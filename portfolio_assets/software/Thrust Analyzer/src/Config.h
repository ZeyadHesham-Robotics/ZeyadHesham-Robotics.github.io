#ifndef CONFIG_H
#define CONFIG_H

// ================= ESC =================
#define ESC_MIN_US 1100
#define ESC_MAX_US 1200
#define ESC_STEP 10

// ================= HX711 =================
#define HX711_SCALE 0.001f // adjust after calibration
#define HX711_OFFSET 0     // adjust after zero-load read
#define HX_AVG_SAMPLES 10

// ================= PIN DEFINITIONS =================
// Buttons on PORTD
#define BTN_UP PD7
#define BTN_SEL PD6
#define BTN_DOWN PD5
#define BTN_MISC PD4

// HX711 (PORTC)
#define HX711_DOUT PC1
#define HX711_SCK PC2

// ESC (Timer1 OC1A)
#define ESC_PIN PB1

// I2C for OLED (PORTC)
// SDA = PC4
// SCL = PC5

#endif