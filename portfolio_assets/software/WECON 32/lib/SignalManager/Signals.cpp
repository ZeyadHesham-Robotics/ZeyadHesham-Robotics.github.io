#include "Signals.h"
#include "../../include/Config.h"

#define RXD2 17
#define TXD2 16
#define PWM_FREQ 5000
#define PWM_RESOLUTION 8 // 8-bit (0–255)

// Define the global variables declared in Signals.h
uint16_t esc_pwm;                   // ESC control value
uint16_t led1_pwm;                  // LED1 control value
uint16_t led2_pwm;                  // LED2 control value
uint16_t regs[256];                 // Array to hold register values
bool Door_Light_Status = false;     // Door light status
bool Solenoid_Open_Status = false;  // Solenoid open status
bool Solenoid_Close_Status = false; // Solenoid close status
bool Heater_Status = false;         // Heater status
bool esc_pwm_activate = false;      // Heater status
// =======================
// PWM Channel Assignments
// =======================

// ModbusMaster node instance

// Initialize Modbus communication
void ModbusInit()
{
    Serial.begin(9600);
    Serial2.begin(9600, SERIAL_8N1, RXD2, TXD2); // RS485 UART
    Serial.println("Modbus Master Initialized");
}

// Function to initialize PWM channels
void initPWM()
{

    // LED1
    ledcSetup(LED1_CH, PWM_FREQ, PWM_RESOLUTION);
    ledcAttachPin(LED1_PIN, LED1_CH);

    // LED2
    ledcSetup(LED2_CH, PWM_FREQ, PWM_RESOLUTION);
    ledcAttachPin(LED2_PIN, LED2_CH);

    // ESC (you may want 50Hz for servo/ESC style control)
    ledcSetup(ESC_CH, 50, 8); // 50Hz, 16-bit resolution (servo/ESC control)
    ledcAttachPin(ESC_PIN, ESC_CH);

    Serial.println("PWM Initialized ");
    ledcWrite(LED1_CH, 0);
    ledcWrite(LED2_CH, 0);
    ledcWrite(ESC_CH, 0);

    pinMode(DOOR_LIGHT_PIN, OUTPUT);
    pinMode(SOLENOID_OPEN_PIN, OUTPUT);
    pinMode(SOLENOID_CLOSE_PIN, OUTPUT);
    pinMode(HEATER_PIN, OUTPUT);
}
// Decode a Modbus-like PLC frame
void decodePLCFrame()
{
    if (bufIndex > 0 && (millis() - lastByteTime > frameGap))
    {
        // Check function code
        byte slave = buffer[0];
        byte func = buffer[1];
        Serial.println("Decoding Frame - Slave: " + String(slave) + " | Function: " + String(func));

        // Function 0x10 (Write Multiple Registers) → contains values we need
        if (func == 0x10 && bufIndex > 9 & slave == MODBUS_SLAVE_ID)
        {
            // Values start at buffer[7]
            esc_pwm = (buffer[21] << 8) | buffer[22];        // 100w
            esc_pwm_activate = (buffer[7] << 8) | buffer[8]; // 100w
            led2_pwm = (buffer[9] << 8) | buffer[10];        // 50
            led1_pwm = (buffer[13] << 8) | buffer[14];
            Door_Light_Status = (buffer[19] << 8) | buffer[20];
            Solenoid_Open_Status = (buffer[11] << 8) | buffer[12];
            Solenoid_Close_Status = (buffer[15] << 8) | buffer[16];
            Heater_Status = (buffer[17] << 8) | buffer[18];
        }

        // Reset buffer for next packet
        bufIndex = 0;
    }
}

// Listen to Modbus data from Serial2
void ListenModbus()
{
    while (Serial2.available())
    {
        buffer[bufIndex++] = Serial2.read();
        lastByteTime = millis();

        if (bufIndex >= sizeof(buffer))
            bufIndex = 0; // prevent overflow
    }
}

// Update PWM values (called in loop)
void pwmUpdate(uint8_t led1Val, uint8_t led2Val, uint8_t escVal)
{

    ledcWrite(LED1_CH, map(led1Val, 0, 100, 0, 255));
    ledcWrite(LED2_CH, map(led2Val, 0, 100, 0, 255));
    if (esc_pwm_activate)
        ledcWrite(ESC_CH, map(escVal, 0, 100, 0, 255));
    else
        ledcWrite(ESC_CH, 0);
}