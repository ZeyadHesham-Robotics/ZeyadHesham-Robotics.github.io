#ifndef HX711_H
#define HX711_H
#ifdef __cplusplus
extern "C"
{
#endif

    void hx711_init(void);

    /*
     * Non-blocking read
     * Returns 1 if new data available
     * Returns 0 if no new data
     */
    uint8_t hx711_read(long *out);

#ifdef __cplusplus
}
#endif

#endif
