#ifndef BUTTONS_H
#define BUTTONS_H

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdint.h>

    // Initialize button GPIOs
    void buttons_init(void);

    // Check if a button is pressed (active LOW)
    uint8_t button_pressed(uint8_t pin);

#ifdef __cplusplus
}
#endif

#endif
