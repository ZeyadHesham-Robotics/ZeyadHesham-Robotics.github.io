#include "pid.h"

/* ================= PID INIT ================= */
void pid_init(PID_t *pid,
              float kp,
              float ki,
              float kd,
              float out_min,
              float out_max)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;

    pid->integral = 0.0f;
    pid->prev_error = 0.0f;

    pid->out_min = out_min;
    pid->out_max = out_max;
}

/* ================= PID COMPUTE ================= */
float pid_compute(PID_t *pid,
                  float setpoint,
                  float measurement,
                  float dt)
{
    float error = setpoint - measurement;

    // Integral term
    pid->integral += error * dt;

    // Derivative term
    float derivative = (error - pid->prev_error) / dt;

    // PID output
    float output = (pid->kp * error) +
                   (pid->ki * pid->integral) +
                   (pid->kd * derivative);

    pid->prev_error = error;

    // Output saturation
    if (output > pid->out_max)
        output = pid->out_max;
    else if (output < pid->out_min)
        output = pid->out_min;

    return output;
}
