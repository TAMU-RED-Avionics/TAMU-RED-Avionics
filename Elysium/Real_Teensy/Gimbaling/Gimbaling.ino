#include <Arduino.h>
#include <sstream>
#include <AccelStepper.h>
#include "Gimbal_Angles.h"


const int MOTOR_STEPS_PER_REV = 200;  // Steps per revolution for the base NEMA 23 motor (1.8 deg/step) 
const float GEAR_RATIO = 100.0;  // Gearbox reduction ratio 
int gimbaling_angle_index = 0; // Global variable: Stop from re-initiating druing the event loop
bool is_gimbaling = false; // The main state variable


const float stepsPerDegree = (MOTOR_STEPS_PER_REV * GEAR_RATIO) / 360.0;


const int pDirPin = 14;   // FIXME:  Direction pin for pitch stepper motor on Teensy <- USER INPUT
const int pStepPin = 16;  // FIXME: Step pin for pitch stepper motor on Teensy <- USER INPUT
const int yDirPin = 14;   // FIXME:  Direction pin for yaw stepper motor on Teensy <- USER INPUT
const int yStepPin = 16;  // FIXME: Step pin for yaw stepper motor on Teensy <- USER INPUT
const int motorInterfaceType  = 1; // Define the motor interface type (1 = Driver mode with STEP/DIR pins)

AccelStepper pStepper(motorInterfaceType, pDirPin, pStepPin); // Create an instance of the AccelStepper library
AccelStepper yStepper(motorInterfaceType, yDirPin, yStepPin); // Create an instance of the AccelStepper library


void setup() {
  // set known values for setter motor

  pStepper.setMaxSpeed(4000); // Set max speed of stepper motor -> CHANGE IF NESSECCARY
  pStepper.setAcceleration(2000); // Set acceleration of stepper motor -> CHANGE IF NESSECCARY  
  pStepper.setCurrentPosition(0); // FIXME: For now, just set the current position to 0 -> This should later be changed once the absolute encoder is integrated
  
  
  yStepper.setMaxSpeed(4000); // Set max speed of stepper motor -> CHANGE IF NESSECCARY
  yStepper.setAcceleration(2000); // Set acceleration of stepper motor -> CHANGE IF NESSECCARY  
  yStepper.setCurrentPosition(0); // FIXME: For now, just set the current position to 0 -> This should later be changed once the absolute encoder is integrated

  // values for testing
  Serial.begin(9600);
}

// Define motion when received the TRUE Packet from GUI
void RunGimbaling(const float& p_angle,const float& y_angle){
  
  long ptargetSteps = round(p_angle * stepsPerDegree);
  long ytargetSteps = round(y_angle * stepsPerDegree);

  pStepper.moveTo(ptargetSteps);
  yStepper.moveTo(ytargetSteps);

  pStepper.runToPosition();
  yStepper.runToPosition();

 
  std::stringstream oss;

  oss << "Gimbaled " << p_angle << " in the pitch axis and " << y_angle << " in the yaw axis!";

  Serial.println(oss.str().c_str());
}

void StopAndReturnGimbaling(){
  pStepper.moveTo(0);
  yStepper.moveTo(0);
  
  yStepper.runToPosition();
  pStepper.runToPosition();

  Serial.println("Stopped Gimbaling Pitch Stepper Motor");
}

void loop() {

  // Testing input using Serial (WIll implement udp later)
  if(Serial.available() > 0)
  {
    char ch = Serial.read();
    if(ch == 'f') {is_gimbaling = false;}
    else if(ch == 't') {is_gimbaling = true;}
  }

  // Define the bool onGimbal so that it can start implementing
  if(is_gimbaling)
  {
    RunGimbaling(stepper_pitch_angles[gimbaling_angle_index],stepper_yaw_angles[gimbaling_angle_index]);
    
    if(gimbaling_angle_index + 1 > 2901)
    {
      is_gimbaling = false;
    }
    else
    {
      gimbaling_angle_index++;
    }
  }
  else
  {
    StopAndReturnGimbaling();
    gimbaling_angle_index = 0;
  }
}