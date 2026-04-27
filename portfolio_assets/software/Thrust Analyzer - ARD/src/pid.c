#include "pid.h"

void pid_init(PID_t *pid, float kp, float ki, float kd)
{
    pid->kp = kp;
    pid->ki = ki;
    pid->kd = kd;
    pid->prev_error = 0;
    pid->integral = 0;
}

float pid_compute(PID_t *pid, float setpoint, float measurement)
{
    float error = setpoint - measurement;
    pid->integral += error;
    float derivative = error - pid->prev_error;

    pid->prev_error = error;

    return pid->kp * error + pid->ki * pid->integral + pid->kd * derivative;
}
