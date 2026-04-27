#pragma once
#include <Arduino.h>
#include "SensorsManager.h"
#include <LiquidCrystal_I2C.h>

extern
    // Simple I2C LCD driver for a 16x4 display with a PCF8574 backpack (e.g., 0x27 or 0x3F)

    // Initialize LCD. Pass I2C address (0x27 default; some boards use 0x3F).
    void
    LCD_Begin(uint8_t i2c_addr = 0x27);

// Clear a single row (0..3)
void LCD_ClearRow(uint8_t row);

// Print a string at row start (clears row first)
void LCD_PrintRow(uint8_t row, const char *s);

// Convenience: read all 4 panels via your readPanelData()
bool LCD_ReadAllPanels(PanelReading out[4]);

// Show page A: "P1 18.7V 1.24A" for rows 0..3
void LCD_ShowPage_VI(const PanelReading panels[4]);

// Show page B: "P1 23.2W 34.1C" for rows 0..3
void LCD_ShowPage_PT(const PanelReading panels[4]);

bool readAllPanels(PanelReading out[4]);