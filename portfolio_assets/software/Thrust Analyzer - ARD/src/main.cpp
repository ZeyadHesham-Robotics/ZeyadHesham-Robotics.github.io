#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>

// Create OLED object (I2C, full buffer)
U8G2_SSD1306_128X64_NONAME_F_HW_I2C u8g2(
    U8G2_R0,
    U8X8_PIN_NONE);

int main(void)
{
    // Arduino core init
    init();

    // I2C init
    Wire.begin();

    // OLED init
    u8g2.begin();

    // Draw once
    u8g2.clearBuffer();
    u8g2.setFont(u8g2_font_6x12_tf);

    u8g2.drawStr(0, 15, "OLED TEST");
    u8g2.drawStr(0, 30, "Arduino UNO");
    u8g2.drawStr(0, 45, "SSD1306 OK");

    u8g2.sendBuffer();

    // Infinite loop (do nothing)
    while (1)
    {
        // keep MCU alive
    }
}
