#ifndef UART_H
#define UART_H

#ifdef __cplusplus
extern "C"
{
#endif

    void uart_init(uint32_t baud);
    void uart_print(const char *s);
    void uart_println(const char *s);
    void uart_print_long(long val);
    void uart_print_float(float val, uint8_t digits);

#ifdef __cplusplus
}
#endif

#endif
