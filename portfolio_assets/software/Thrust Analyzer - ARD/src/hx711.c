#include <avr/io.h>
#include <util/delay.h>
#include "hx711.h"
#include "config.h"

void hx711_init(void)
{
    DDRB |= (1 << HX711_SCK);   // SCK output
    DDRB &= ~(1 << HX711_DOUT); // DOUT input
    PORTB &= ~(1 << HX711_SCK); // SCK low
}

uint8_t hx711_read(long *out)
{
    // Not ready → do nothing
    if (PINB & (1 << HX711_DOUT))
        return 0;

    long count = 0;

    for (uint8_t i = 0; i < 24; i++)
    {
        PORTB |= (1 << HX711_SCK);
        _delay_us(1);

        count <<= 1;

        PORTB &= ~(1 << HX711_SCK);
        _delay_us(1);

        if (PINB & (1 << HX711_DOUT))
            count++;
    }

    // Gain = 128
    PORTB |= (1 << HX711_SCK);
    _delay_us(1);
    PORTB &= ~(1 << HX711_SCK);

    // Sign extend
    if (count & 0x800000)
        count |= 0xFF000000;

    *out = count;
    return 1; // NEW DATA
}
