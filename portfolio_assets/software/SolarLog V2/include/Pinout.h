#ifndef PINOUT_H
#define PINOUT_H

//=====MUX PINOUTS=====
#define MUX_S0 25
#define MUX_S1 26
#define MUX_S2 14
#define MUX_S3 13

//=====DS18B20 PINOUTS (each on its own 1-Wire bus)=====
#define DS18B20_0 27
#define DS18B20_1 4
#define DS18B20_2 17
#define DS18B20_3 16

//=====I2C LCD PINOUTS=====
#define LCD_SDA 21
#define LCD_SCL 22

//=====MUX ANALOG OUTPUT (to ESP32 ADC)=====
#define MUX_Signal 36 // ADC1_CH0

#endif // PINOUT_H
