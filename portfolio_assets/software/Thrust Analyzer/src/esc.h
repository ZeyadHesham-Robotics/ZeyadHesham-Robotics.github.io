#ifndef ESC_H
#define ESC_H
#ifdef __cplusplus
extern "C"
{
#endif

#include <stdint.h>

    // Initialize ESC PWM (Timer1)
    void esc_init(void);

    // Set ESC pulse width in microseconds
    void esc_set_us(uint16_t us);

#ifdef __cplusplus
}
#endif

#endif
