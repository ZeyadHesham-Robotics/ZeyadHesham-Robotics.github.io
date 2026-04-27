#include <avr/io.h>
#include "buttons.h"
#include "config.h"

/*
 * Buttons are ACTIVE-LOW
 * Connected to PORTA (D22–D25)
 */
void buttons_init(void)
{
    // Set pins as INPUT
    DDRD &= ~(
        (1 << BTN_UP) |
        (1 << BTN_SEL) |
        (1 << BTN_DOWN) |
        (1 << BTN_MISC));

    // Enable internal pull-ups
    PORTD |= ((1 << BTN_UP) |
              (1 << BTN_SEL) |
              (1 << BTN_DOWN) |
              (1 << BTN_MISC));
}

/*
 * Returns 1 when button is PRESSED
 * Active-LOW logic
 */
uint8_t button_pressed(uint8_t pin)
{
    return !(PIND & (1 << pin));
}
