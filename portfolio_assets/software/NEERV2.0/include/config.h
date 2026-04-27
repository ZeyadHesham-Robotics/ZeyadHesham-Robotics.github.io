#ifndef CONFIG_H
#define CONFIG_H

#define RELAY_CH1 18
#define RELAY_CH2 19
#define DHT_PIN 26
#define DS18B20_PIN 25
#define RS485_RX 26
#define RS485_TX 4
#define SD_CS 5
#define SD_SCK 18
#define SD_MISO 19
#define SD_MOSI 23
#define DOOR_SWITCH 5
#define RTC_SDA 21
#define RTC_SCL 22
#define GSM_TX 17
#define GSM_RX 16
#define VOLTAGE_SENSOR_PIN 32
#define PH_E291C_PIN 39
#define VOLTAGE_DIVIDER_RATIO 3.8
#define ADC_RESOLUTION 4095.0
#define ADC_VREF 3.3
#define BUZZER_PIN 27

#define BUZZER_ON_TIME 500  // milliseconds ON
#define BUZZER_OFF_TIME 500 // milliseconds OFF

#define SENSOR_INTERVAL_MS 60000
#define UPLOAD_INTERVAL_MS 300000

#endif
