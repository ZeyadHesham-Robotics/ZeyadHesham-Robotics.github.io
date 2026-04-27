#ifndef HX711_H
#define HX711_H

#include <stdint.h>

// Initialize HX711
void hx711_init(void);

// Read raw 24-bit value from HX711
long hx711_read(void);

// Check if HX711 is ready for reading
uint8_t hx711_is_ready(void);

#endif