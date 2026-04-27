#define F_CPU 16000000UL
#include <avr/io.h>
#include <avr/interrupt.h>
#include <util/delay.h>
#include <stdbool.h>
#include "config.h"
#include "uart.h"
#include "hx711.h"
#include "esc.h"
#include "pid.h"
#include "buttons.h"

// ================= STATE MACHINE =================
typedef enum
{
    STATE_IDLE,
    STATE_CALIBRATE,
    STATE_MANUAL,
    STATE_PID_CONTROL
} SystemState_t;

// ================= GLOBAL VARIABLES =================
static SystemState_t system_state = STATE_IDLE;
static PID_t thrust_pid;
static float target_force = 0.0f;  // Target thrust in grams
static float current_force = 0.0f; // Current measured force
static uint16_t esc_pulse_us = ESC_MIN_US;
static long hx711_zero_offset = 0;
static bool pid_enabled = false;
static uint8_t hx711_error_count = 0;

// ================= FUNCTION PROTOTYPES =================
static void system_init(void);
static float read_force_filtered(void);
static void calibrate_zero(void);
static void handle_buttons(void);
static void run_pid_control(void);
static void run_manual_control(void);
static void print_status(void);
static void wake_hx711(void);

// ================= MAIN =================
int main(void)
{
    system_init();

    uart_println("=== BLDC PID Controller Started ===");
    uart_println("BTN_UP: Increase | BTN_DOWN: Decrease");
    uart_println("BTN_SEL: Mode | BTN_MISC: Calibrate");

    // Initial calibration
    uart_println("Calibrating zero point...");
    calibrate_zero();
    uart_println("Calibration complete!");

    // Wake HX711 after calibration
    uart_println("Waking HX711...");
    wake_hx711();
    uart_println("Ready!");

    uint16_t loop_counter = 0;

    while (1)
    {
        // Wake HX711 if needed

        // Read current force
        current_force = read_force_filtered();

        // Handle button inputs
        handle_buttons();

        // State machine
        switch (system_state)
        {
        case STATE_IDLE:
            esc_set_us(ESC_MIN_US);
            break;

        case STATE_CALIBRATE:
            esc_set_us(ESC_MIN_US);
            calibrate_zero();
            wake_hx711();
            uart_println("Recalibrated!");
            system_state = STATE_IDLE;
            break;

        case STATE_MANUAL:
            run_manual_control();
            break;

        case STATE_PID_CONTROL:
            run_pid_control();
            break;
        }

        // Print status every ~500ms
        if (++loop_counter >= 50)
        {
            loop_counter = 0;
            print_status();
        }

        _delay_ms(10); // 100Hz loop
    }

    return 0;
}

// ================= SYSTEM INITIALIZATION =================
static void system_init(void)
{
    // Initialize peripherals
    uart_init(9600);
    buttons_init();
    hx711_init();
    esc_init();

    // Initialize PID controller
    // Parameters: Kp, Ki, Kd, out_min, out_max
    pid_init(&thrust_pid,
             10.0f,       // Kp - proportional gain
             0.5f,        // Ki - integral gain
             2.0f,        // Kd - derivative gain
             ESC_MIN_US,  // Min output
             ESC_MAX_US); // Max output

    // ESC arming sequence
    uart_println("Arming ESC...");
    esc_set_us(ESC_MIN_US);
    _delay_ms(2000);
    uart_println("ESC Armed!");

    // Enable interrupts if needed
    sei();
}

// ================= HX711 WAKE =================
static void wake_hx711(void)
{
    // Ensure SCK is LOW to wake/keep HX711 awake
    PORTC &= ~(1 << HX711_SCK);
    _delay_ms(1);

    // Wait for HX711 to be ready
    uint16_t timeout = 1000;
    while (!hx711_is_ready() && timeout > 0)
    {
        _delay_ms(1);
        timeout--;
    }

    if (timeout == 0)
    {
        uart_println("WARNING: HX711 not responding!");
    }
    else
    {
        // Do a dummy read to ensure it's working
        hx711_read();
        _delay_ms(10);
    }
}

// ================= LOAD CELL READING =================
static float read_force_filtered(void)
{
    long sum = 0;
    uint8_t valid_samples = 0;

    // Average multiple readings
    for (uint8_t i = 0; i < HX_AVG_SAMPLES; i++)
    {
        // Check if HX711 is ready before reading
        if (!hx711_is_ready())
        {
            _delay_ms(1); // Wait a bit
            if (!hx711_is_ready())
            {
                hx711_error_count++;
                continue; // Skip this sample
            }
        }

        long reading = hx711_read();

        // Check if reading is valid (non-zero or within expected range)
        if (reading != 0 || i == 0) // Accept first reading even if zero
        {
            sum += reading;
            valid_samples++;
            hx711_error_count = 0; // Reset error count on successful read
        }
        else
        {
            hx711_error_count++;
        }

        _delay_ms(1); // Small delay between samples
    }

    // // If no valid samples, return last known value
    // if (valid_samples == 0)
    // {
    //     uart_println("ERROR: No valid HX711 readings!");
    //     return current_force; // Return last known value
    // }

    long avg_raw = sum / valid_samples;

    // Apply zero offset and scale
    long calibrated = avg_raw - hx711_zero_offset;
    float force_g = (float)calibrated * HX711_SCALE;

    return force_g;
}

// ================= CALIBRATION =================
static void calibrate_zero(void)
{
    long sum = 0;
    uint8_t valid_readings = 0;

    uart_print("Zeroing");

    for (uint8_t i = 0; i < 20; i++)
    {
        // Wait for HX711 to be ready
        uint16_t timeout = 100;
        while (!hx711_is_ready() && timeout > 0)
        {
            _delay_ms(1);
            timeout--;
        }

        if (timeout > 0)
        {
            long reading = hx711_read();
            if (reading != 0 || i == 0) // Accept reading
            {
                sum += reading;
                valid_readings++;
                uart_print(".");
            }
            else
            {
                uart_print("x");
            }
        }
        else
        {
            uart_print("!");
        }

        _delay_ms(50);
    }
    uart_println("");

    if (valid_readings > 0)
    {
        hx711_zero_offset = sum / valid_readings;
        uart_print("Zero offset: ");
        uart_print_long(hx711_zero_offset);
        uart_print(" (");
        uart_print_long((long)valid_readings);
        uart_println(" samples)");
    }
    else
    {
        uart_println("ERROR: Calibration failed - no valid readings!");
        hx711_zero_offset = 0;
    }
}

// ================= BUTTON HANDLING =================
static void handle_buttons(void)
{
    static uint8_t btn_debounce[4] = {0};

    // BTN_SEL: Cycle through states
    if (button_pressed(BTN_SEL))
    {
        if (btn_debounce[0] == 0)
        {
            btn_debounce[0] = 20; // 200ms debounce

            switch (system_state)
            {
            case STATE_IDLE:
                system_state = STATE_MANUAL;
                uart_println(">>> MANUAL MODE");
                break;
            case STATE_MANUAL:
                system_state = STATE_PID_CONTROL;
                pid_enabled = true;
                target_force = 50.0f; // Start with 50g target
                uart_println(">>> PID MODE");
                break;
            case STATE_PID_CONTROL:
                system_state = STATE_IDLE;
                pid_enabled = false;
                uart_println(">>> IDLE MODE");
                break;
            default:
                system_state = STATE_IDLE;
                break;
            }
        }
    }

    // BTN_UP: Increase target or manual PWM
    if (button_pressed(BTN_UP))
    {
        if (btn_debounce[1] == 0)
        {
            btn_debounce[1] = 10;

            if (system_state == STATE_PID_CONTROL)
            {
                target_force += 10.0f; // Increase by 10g
                if (target_force > 500.0f)
                    target_force = 500.0f;
            }
            else if (system_state == STATE_MANUAL)
            {
                esc_pulse_us += ESC_STEP;
                if (esc_pulse_us > ESC_MAX_US)
                    esc_pulse_us = ESC_MAX_US;
            }
        }
    }

    // BTN_DOWN: Decrease target or manual PWM
    if (button_pressed(BTN_DOWN))
    {
        if (btn_debounce[2] == 0)
        {
            btn_debounce[2] = 10;

            if (system_state == STATE_PID_CONTROL)
            {
                target_force -= 10.0f; // Decrease by 10g
                if (target_force < 0.0f)
                    target_force = 0.0f;
            }
            else if (system_state == STATE_MANUAL)
            {
                esc_pulse_us -= ESC_STEP;
                if (esc_pulse_us < ESC_MIN_US)
                    esc_pulse_us = ESC_MIN_US;
            }
        }
    }

    // BTN_MISC: Recalibrate
    if (button_pressed(BTN_MISC))
    {
        if (btn_debounce[3] == 0)
        {
            btn_debounce[3] = 50; // 500ms debounce
            system_state = STATE_CALIBRATE;
        }
    }

    // Decrement debounce counters
    for (uint8_t i = 0; i < 4; i++)
    {
        if (btn_debounce[i] > 0)
            btn_debounce[i]--;
    }
}

// ================= PID CONTROL =================
static void run_pid_control(void)
{
    // Calculate dt (10ms loop time)
    float dt = 0.01f; // 10ms = 0.01s

    // Compute PID output
    float pid_output = pid_compute(&thrust_pid,
                                   target_force,
                                   current_force,
                                   dt);

    // Set ESC pulse
    esc_set_us((uint16_t)pid_output);
}

// ================= MANUAL CONTROL =================
static void run_manual_control(void)
{
    esc_set_us(esc_pulse_us);
}

// ================= STATUS PRINTING =================
static void print_status(void)
{
    uart_print("State: ");
    switch (system_state)
    {
    case STATE_IDLE:
        uart_print("IDLE");
        break;
    case STATE_MANUAL:
        uart_print("MANUAL");
        break;
    case STATE_PID_CONTROL:
        uart_print("PID");
        break;
    default:
        uart_print("UNKNOWN");
        break;
    }

    uart_print(" | Force: ");
    uart_print_float(current_force, 1);
    uart_print("g");

    if (system_state == STATE_PID_CONTROL)
    {
        uart_print(" | Target: ");
        uart_print_float(target_force, 1);
        uart_print("g");
    }

    if (system_state == STATE_MANUAL || system_state == STATE_PID_CONTROL)
    {
        uart_print(" | ESC: ");
        uart_print_long(esc_pulse_us);
        uart_print("us");
    }

    if (hx711_error_count > 0)
    {
        uart_print(" | Errors: ");
        uart_print_long(hx711_error_count);
    }

    uart_println("");
}