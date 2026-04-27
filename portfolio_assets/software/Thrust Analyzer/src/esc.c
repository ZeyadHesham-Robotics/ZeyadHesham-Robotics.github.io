#include <avr/io.h>
#include "esc.h"
#include "config.h"

void esc_init(void)
{
    DDRB |= (1 << ESC_PIN);

    // Timer1 Fast PWM, TOP = ICR1
    TCCR1A = (1 << COM1A1) | (1 << WGM11);
    TCCR1B = (1 << WGM13) | (1 << WGM12) | (1 << CS11); // prescaler 8

    ICR1 = 40000; // 50 Hz (16MHz / 8 = 2MHz → 20ms)
}

void esc_set_us(uint16_t us)
{
    if (us < ESC_MIN_US)
        us = ESC_MIN_US;
    if (us > ESC_MAX_US)
        us = ESC_MAX_US;

    OCR1A = us * 2; // 0.5us per tick
}
