#ifndef CONFIG_H
#define CONFIG_H

// #define F_CPU 16000000UL

// ================= ESC =================
#define ESC_MIN_US 1000
#define ESC_MAX_US 2000

// ================= HX711 =================
#define HX711_SCALE 0.001f  // adjust after calibration
#define HX711_OFFSET 830000 // adjust after zero-load read

// ================= PIN DEFINITIONS =================

// Buttons on PORTA
#define BTN_UP PD7   // D22
#define BTN_SEL PD6  // D23
#define BTN_DOWN PD5 // D24
#define BTN_MISC PD4 // D25

// HX711 (PORTB)
#define HX711_DOUT PC2
#define HX711_SCK PC1

// ESC (Timer1 OC1A)
#define ESC_PIN PB1

#endif
