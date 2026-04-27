
#include <avr/io.h>
#include <util/delay.h>
#include <stdlib.h>
#include "uart.h"

void uart_init(uint32_t baud)
{
    uint16_t ubrr = (F_CPU / 16 / baud) - 1;

    UBRR0H = (ubrr >> 8);
    UBRR0L = ubrr;

    UCSR0B = (1 << TXEN0);
    UCSR0C = (1 << UCSZ01) | (1 << UCSZ00);
}

void uart_print(const char *s)
{
    while (*s)
    {
        while (!(UCSR0A & (1 << UDRE0)))
            ;
        UDR0 = *s++;
    }
}

void uart_println(const char *s)
{
    uart_print(s);
    uart_print("\r\n");
}

void uart_print_long(long val)
{
    char buf[16];
    ltoa(val, buf, 10);
    uart_print(buf);
}

void uart_print_float(float val, uint8_t digits)
{
    char buf[16];
    dtostrf(val, 0, digits, buf);
    uart_print(buf);
}
