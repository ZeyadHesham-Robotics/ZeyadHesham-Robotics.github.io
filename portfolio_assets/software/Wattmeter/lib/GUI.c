#include <U8g2lib.h>

void drawScreen(float voltage, float current, float power)
{
    // Thick frame (double borders)
    u8g2.drawFrame(0, 0, 128, 64);
    u8g2.drawFrame(1, 1, 126, 62);

    // Title (centered)
    const char *title = "POWER MONITOR";
    u8g2.setFont(u8g2_font_6x10_tf);
    int titleWidth = u8g2.getStrWidth(title);
    u8g2.setCursor((128 - titleWidth) / 2, 10);
    u8g2.print(title);

    // Power value (moved up center)
    char buf[10];
    dtostrf(power, 5, 1, buf);
    u8g2.setCursor(38, 22);
    u8g2.print("P:");
    u8g2.print(buf);
    u8g2.print("W");

    // Dials
    drawDial(voltage, 250.0, "V", 32, 44); // Voltage (left)
    drawDial(current, 30.0, "A", 96, 44);  // Current (right)
}

void drawDial(float value, float maxValue, const char *unit, int cx, int cy)
{
    // Draw thick arc (150° to 30°, clockwise — 0 on left)
    for (int r = 11; r <= 13; r++)
    { // Arc thickness
        for (int a = 150; a >= 30; a -= 2)
        {
            int x = cx + cos(radians(a)) * r;
            int y = cy - sin(radians(a)) * r;
            u8g2.drawPixel(x, y);
        }
    }

    // Needle calculation (reverse angle)
    float angle = map(value, 0, maxValue, 150, 30); // Left to right
    int nx = cx + cos(radians(angle)) * 10;
    int ny = cy - sin(radians(angle)) * 10;
    u8g2.drawLine(cx, cy, nx, ny);

    // Value label under the dial
    char buf[10];
    dtostrf(value, 4, 1, buf);
    strcat(buf, unit);
    u8g2.setFont(u8g2_font_5x8_tf);
    int tw = u8g2.getStrWidth(buf);
    u8g2.setCursor(cx - tw / 2, cy + 12);
    u8g2.print(buf);
}