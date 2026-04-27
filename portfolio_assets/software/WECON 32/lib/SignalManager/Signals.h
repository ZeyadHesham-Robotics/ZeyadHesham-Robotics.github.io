#ifndef SIGNALS_H
#define SIGNALS_H

#include <Arduino.h>
#include <ModbusMaster.h>

extern uint16_t regs[256]; // decoded registers
extern uint16_t esc_pwm;   // ESC control value
extern uint16_t led1_pwm;  // LED1 control value
extern uint16_t led2_pwm;  // LED2 control value

extern bool Door_Light_Status;     // Door light status
extern bool Solenoid_Open_Status;  // Solenoid open status
extern bool Solenoid_Close_Status; // Solenoid close status
extern bool Heater_Status;         // Heater status

// Declare comm buffer variables so Signals.cpp can see them
extern byte buffer[256];
extern int bufIndex;
extern unsigned long lastByteTime;
extern unsigned long frameGap;
extern bool esc_pwm_activate; // ESC activation status

void ModbusInit();
void decodePLCFrame();
void ListenModbus();
void initPWM();
void pwmUpdate(uint8_t led1Val, uint8_t led2Val, uint8_t escVal);

#endif

/*
====================================================
 WECON PLC → ESP32 Register Map (Modbus RTU)
====================================================
Raw Example Frame (23 bytes):
02 10 00 01 00 08 10 00 64 00 32 00 00 00 42 00 00 00 00 00 00 00 00 7A C3
----------------------------------------------------
Frame Breakdown:
----------------------------------------------------
Field                  | Bytes      | Example     | Meaning
----------------------------------------------------
Slave ID               | 1          | 0x02        | Target device address
Function Code          | 1          | 0x10        | Write Multiple Registers
Start Address Hi/Lo    | 2          | 0x00 0x01   | First register = 0x0001
Register Count Hi/Lo   | 2          | 0x00 0x08   | Writing 8 registers
Byte Count             | 1          | 0x10        | 16 data bytes follow
----------------------------------------------------
Registers (8 total):
----------------------------------------------------
Reg Addr | Value (Hi Lo) | Decimal | Description
----------------------------------------------------
0x0001   | 00 64         | 100     | ESC Control Value (PWM / Hz)
0x0002   | 00 32         | 50      | LED2 PWM Value (0–255 or %)
0x0003   | 00 00         | 0       | Reserved
0x0004   | 00 42         | 66      | LED1 PWM Value (0–255 or %)
0x0005   | 00 00         | 0       | Reserved
0x0006   | 00 00         | 0       | Reserved
0x0007   | 00 00         | 0       | Reserved
0x0008   | 00 00         | 0       | Reserved
----------------------------------------------------
CRC16 (Lo Hi)          | 2          | 0x7A 0xC3   | Frame check (CRC-16 Modbus)
====================================================
*/
