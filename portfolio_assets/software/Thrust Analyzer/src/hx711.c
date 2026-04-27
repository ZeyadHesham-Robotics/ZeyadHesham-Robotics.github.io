#define F_CPU 16000000UL
#include <avr/io.h>
#include <util/delay.h>
#include <stdint.h>
#include "hx711.h"
#include "config.h"

/*
  HX711 basic driver
  Gain = 128 (Channel A)
*/

// ================= INIT =================
void hx711_init(void)
{
    // SCK = output, DOUT = input
    DDRC |= (1 << HX711_SCK);
    DDRC &= ~(1 << HX711_DOUT);
    // Ensure SCK LOW
    PORTC &= ~(1 << HX711_SCK);

    // Give HX711 time to stabilize
    _delay_ms(100);
}

// ================= READ RAW =================
long hx711_read(void)
{
    long count = 0;
    uint32_t timeout = 0;

    // Wait for HX711 ready (DOUT goes LOW) with timeout
    while (PINC & (1 << HX711_DOUT))
    {
        _delay_us(1);
        if (++timeout > 100000) // ~100ms timeout
        {
            return 0; // Return 0 if timeout (HX711 not responding)
        }
    }

    // Read 24 bits
    for (uint8_t i = 0; i < 24; i++)
    {
        PORTC |= (1 << HX711_SCK);
        _delay_us(1);
        count <<= 1;
        PORTC &= ~(1 << HX711_SCK);
        _delay_us(1);
        if (PINC & (1 << HX711_DOUT))
            count++;
    }

    // 25th pulse -> set gain = 128 (Channel A)
    PORTC |= (1 << HX711_SCK);
    _delay_us(1);
    PORTC &= ~(1 << HX711_SCK);
    _delay_us(1);

    // Sign extend 24-bit value to 32-bit
    if (count & 0x800000)
        count |= 0xFF000000;

    return count;
}

// ================= CHECK IF READY =================
uint8_t hx711_is_ready(void)
{
    return !(PINC & (1 << HX711_DOUT));
}