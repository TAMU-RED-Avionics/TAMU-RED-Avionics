#include <Arduino.h>
#include <AccelStepper.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
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

// Define all the hard-coded angles for stepper motor -> Warning this is a BIG array




// TODO: Implement the Ethernet library

unsigned int PORT = 8888; 
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED}; // USER INPUT -> ADD THE MAC ADDRESS
IPAddress REMOTE(192, 168, 1, 175); 
IPAddress LOCAL(192, 168, 1, 174);

char packetBuffer[UDP_TX_PACKET_MAX_SIZE];




void setup() {
  // set known values for setter motor

  // Conection setup
  Ethernet.begin(MAC_ADDRESS,REMOTE);


  // Check for Ethernet hardware present
  while(Ethernet.hardwareStatus() == EthernetNoHardware)
  {
    Serial.println("Ethernet Shield Not Connected!");
  }
  while (Ethernet.linkStatus() == LinkOFF) 
  {
    Serial.println("Ethernet cable is not connected.");
  }

  udp.begin(LOCAL);

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
    setGimbalAngle(angle);
    pStepper.runToPosition();
  }
}

void yRunGimbaling(){
  for(float angle: stepper_yaw_angles){
    setGimbalAngle(angle);
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

  int packetSize = Udp.parsePacket();

  if(packetSize && sizeof(packetSize) == 1)
  {
    
    if(bool(packetSize)) // TODO: Implement Ethernet First
    {
      pRunGimbaling();
      yRunGimbaling();
    }
    else
    {
      pStopAndReturnGimbaling();
      yStopAndReturnGimbaling();
    }
  }

}