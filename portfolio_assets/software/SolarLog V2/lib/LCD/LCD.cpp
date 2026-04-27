#include "LCD.h"
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <math.h>

// We use a pointer so we can recreate the object if the address changes.
static LiquidCrystal_I2C *s_lcd = nullptr;
static uint8_t s_addr = 0x27;

static inline void ensureLcd(uint8_t addr)
{
    if (s_lcd && addr == s_addr)
        return;
    if (s_lcd)
    {
        delete s_lcd;
        s_lcd = nullptr;
    }
    s_addr = addr;
    s_lcd = new LiquidCrystal_I2C(s_addr, 16, 4);
}

bool readAllPanels(PanelReading out[4])
{
    bool ok = true;
    for (uint8_t i = 0; i < 4; ++i)
    {
        if (!readPanelData(i, out[i]))
            ok = false;
    }
    return ok;
}

void LCD_Begin(uint8_t i2c_addr)
{
    ensureLcd(i2c_addr);
    // Some LiquidCrystal_I2C variants use .init(), others .begin(16,4).
    // We call both defensively; the extra call is harmless in common libs.
    s_lcd->init();
    s_lcd->begin(16, 4);
    s_lcd->backlight();
    s_lcd->clear();

    s_lcd->setCursor(0, 0);
    s_lcd->print("ESP32 Solar Meter");
}

void LCD_ClearRow(uint8_t row)
{
    if (!s_lcd)
        return;
    if (row > 3)
        row = 3;
    s_lcd->setCursor(0, row);
    for (int i = 0; i < 16; ++i)
        s_lcd->print(' ');
}

void LCD_PrintRow(uint8_t row, const char *s)
{
    if (!s_lcd)
        return;
    LCD_ClearRow(row);
    s_lcd->setCursor(0, row);
    // Print up to 16 chars to avoid leftovers from previous longer text
    for (int i = 0; i < 16 && s[i]; ++i)
        s_lcd->print(s[i]);
}

bool LCD_ReadAllPanels(PanelReading out[4])
{
    bool ok = true;
    for (uint8_t i = 0; i < 4; ++i)
    {
        if (!readPanelData(i, out[i]))
            ok = false;
    }
    return ok;
}

void LCD_ShowPage_VI(const PanelReading p[4])
{
    if (!s_lcd)
        return;
    char line[17]; // 16 chars + NUL
    for (uint8_t i = 0; i < 4; ++i)
    {
        const float v = p[i].voltage;
        const float I = p[i].current;
        // "P1 18.7V 1.24A" fits in 16 columns
        snprintf(line, sizeof(line), "P%u %4.1fV %4.2fA", (unsigned)(i + 1), v, I);
        LCD_PrintRow(i, line);
    }
}

void LCD_ShowPage_PT(const PanelReading p[4])
{
    if (!s_lcd)
        return;
    char line[17];
    for (uint8_t i = 0; i < 4; ++i)
    {
        const float P = p[i].voltage * p[i].current;
        float T = p[i].temperature;
        if (!isfinite(T))
            T = 0.0f;
        // "P1 23.2W 34.1C" fits in 16 columns
        snprintf(line, sizeof(line), "P%u %4.1fW %5.1fC", (unsigned)(i + 1), P, T);
        LCD_PrintRow(i, line);
    }
}
