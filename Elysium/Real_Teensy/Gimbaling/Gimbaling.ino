#include <Arduino.h>
#include <AccelStepper.h>
#include "Gimbal_Angles.h"


const int MOTOR_STEPS_PER_REV = 200;  // Steps per revolution for the base NEMA 23 motor (1.8 deg/step) 
const double GEAR_RATIO = 100.0;  // Gearbox reduction ratio 


const float stepsPerDegree = (MOTOR_STEPS_PER_REV * GEAR_RATIO) / 360.0;


const int pDirPin = 14;   // FIXME:  Direction pin for pitch stepper motor on Teensy <- USER INPUT
const int pStepPin = 16;  // FIXME: Step pin for pitch stepper motor on Teensy <- USER INPUT
const int yDirPin = 14;   // FIXME:  Direction pin for yaw stepper motor on Teensy <- USER INPUT
const int yStepPin = 16;  // FIXME: Step pin for yaw stepper motor on Teensy <- USER INPUT
const int motorInterfaceType  = 1; // Define the motor interface type (1 = Driver mode with STEP/DIR pins)

AccelStepper pStepper(motorInterfaceType, pDirPin, pStepPin); // Create an instance of the AccelStepper library
AccelStepper yStepper(motorInterfaceType, yDirPin, yStepPin); // Create an instance of the AccelStepper libraryv




void setup() {
  // set known values for setter motor

  pStepper.setMaxSpeed(4000); // Set max speed of stepper motor -> CHANGE IF NESSECCARY
  pStepper.setAcceleration(2000); // Set acceleration of stepper motor -> CHANGE IF NESSECCARY  
  pStepper.setCurrentPosition(0); // FIXME: For now, just set the current position to 0 -> This should later be changed once the absolute encoder is integrated
  yStepper.setMaxSpeed(4000); // Set max speed of stepper motor -> CHANGE IF NESSECCARY
  yStepper.setAcceleration(2000); // Set acceleration of stepper motor -> CHANGE IF NESSECCARY  
  yStepper.setCurrentPosition(0); // FIXME: For now, just set the current position to 0 -> This should later be changed once the absolute encoder is integrated


}


// Convert from angles to steps
void pSetGimbalAngle(float& targetAngle) {
  long targetSteps = round(targetAngle * stepsPerDegree);
  yStepper.moveTo(targetSteps);
}

void ySetGimbalAngle(float& targetAngle) {
  long targetSteps = round(targetAngle * stepsPerDegree);
  pStepper.moveTo(targetSteps);
}

// Define motion when received the TRUE Packet from GUI
void pRunGimbaling(){
  for(float angle: stepper_pitch_angles){
    pSetGimbalAngle(angle);
    pStepper.runToPosition();
  }
}

void yRunGimbaling(){
  for(float angle: stepper_yaw_angles){
    ySetGimbalAngle(angle);
    yStepper.runToPosition();
  }
}

void pStopAndReturnGimbaling(){
  pStepper.moveTo(0);
  pStepper.runToPosition();
}

void yStopAndReturnGimbaling(){
  yStepper.moveTo(0);
  yStepper.runToPosition();
}


void loop() {


  // Define the bool onGimbal so that it can start implementing 
  if(true) // FIXME: ADD bool val here once All files are implemented into a main loop
  {
    do
    { 
      pRunGimbaling();
      yRunGimbaling();
    } while(false); // FIXME: ADD bool val here once All files are implemented into a main loop
  }
  else
  {
    pStopAndReturnGimbaling();
    yStopAndReturnGimbaling();
  }
}