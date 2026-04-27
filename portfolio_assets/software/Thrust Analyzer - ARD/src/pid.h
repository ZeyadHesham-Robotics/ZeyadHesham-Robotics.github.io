#ifndef PID_H
#define PID_H

typedef struct
{
    float kp;
    float ki;
    float kd;
    float prev_error;
    float integral;
} PID_t;

// Initialize PID controller
void pid_init(PID_t *pid, float kp, float ki, float kd);

// Compute PID output
float pid_compute(PID_t *pid, float setpoint, float measurement);

#endif
