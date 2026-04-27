#ifndef ARM_H
#define ARM_H

#pragma once

void pickSequence();
void rotateSequence();
void placeSequence();
void executePickRotatePlace();
void runAllJoints();
void moveJointTo(int jointIndex, long steps);

#endif // ARM_H
#pragma once
