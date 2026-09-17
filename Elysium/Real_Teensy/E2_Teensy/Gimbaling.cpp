#include "Gimbaling.h"
#include <AccelStepper.h>
#include "Gimbal_Angles.h"

// ---- Drivetrain configuration ----------------------------------------------
// steps/degree = (motor full-steps/rev * microstepping * gear ratio) / 360
static const int    MOTOR_STEPS_PER_REV = 200;   // motor property: 1.8 deg/step = 200, 0.9 deg = 400
static const int    MICROSTEPS          = 1;      // TODO: read off the driver's DIP switches (e.g. 8/16/32)
static const double GEAR_RATIO          = 100.0;  // TODO: actual gearbox/linkage reduction

static const float stepsPerDegree =
    ((double)MOTOR_STEPS_PER_REV * MICROSTEPS * GEAR_RATIO) / 360.0;

// ---- Motor driver pins (STEP/DIR mode) -------------------------------------
// !!! PIN CONFLICT WARNING !!!
// E2_Teensy.ino already uses pin 16 = PT6 and pin 17 = PT5, and pin 14 =
// GIMBAL_ENABLE_PIN. The STEP/DIR pins below MUST come from FREE Teensy pins per
// the E2 pin map and must not collide with any PT/LC/valve/ignition pin. These
// are placeholders — verify against the real wiring before powering the driver.
static const int pDirPin  = 2;   // TODO: pitch direction
static const int pStepPin = 3;   // TODO: pitch step
static const int yDirPin  = 4;   // TODO: yaw direction
static const int yStepPin = 6;   // TODO: yaw step
static const int gimbalEnablePin = 14; // matches E2_Teensy GIMBAL_ENABLE_PIN (driver ENABLE)
static const int motorInterfaceType = 1; // 1 = STEP/DIR driver mode

static AccelStepper pStepper(motorInterfaceType, pStepPin, pDirPin); // (type, STEP, DIR)
static AccelStepper yStepper(motorInterfaceType, yStepPin, yDirPin);

// ---- Trajectory state ------------------------------------------------------
// Tables can be different lengths, so walk only as far as the SHORTER of the two.
static const size_t PITCH_POINTS =
    sizeof(stepper_pitch_angles) / sizeof(stepper_pitch_angles[0]);
static const size_t YAW_POINTS =
    sizeof(stepper_yaw_angles) / sizeof(stepper_yaw_angles[0]);
static const size_t TRAJECTORY_POINTS =
    (PITCH_POINTS < YAW_POINTS) ? PITCH_POINTS : YAW_POINTS;

static size_t gimbaling_angle_index = 0;
static bool   is_gimbaling          = false;

// Load the next trajectory waypoint as target positions (does NOT step).
static void commandWaypoint(size_t index) {
  pStepper.moveTo(round(stepper_pitch_angles[index] * stepsPerDegree));
  yStepper.moveTo(round(stepper_yaw_angles[index]   * stepsPerDegree));
}

void gimbalSetup() {
  pinMode(gimbalEnablePin, OUTPUT);
  digitalWrite(gimbalEnablePin, LOW); // start disabled/safe

  // TODO: speed/accel in steps/s and steps/s^2 — bench-tune so the motor does
  // not stall (a stall silently loses steps and the gimbal drifts).
  pStepper.setMaxSpeed(4000);
  pStepper.setAcceleration(2000);
  yStepper.setMaxSpeed(4000);
  yStepper.setAcceleration(2000);

  // FIXME: assumes current position == 0 deg (straight ahead). Replace with a
  // real home reference (limit switch / absolute encoder).
  pStepper.setCurrentPosition(0);
  yStepper.setCurrentPosition(0);
}

void beginGimbalingProgram() {
  gimbaling_angle_index = 0;
  is_gimbaling = true;
  digitalWrite(gimbalEnablePin, HIGH); // enable driver
}

void haltGimbalingProgram() {
  is_gimbaling = false;
  // Command both axes home; gimbalUpdate() drives them there non-blocking.
  pStepper.moveTo(0);
  yStepper.moveTo(0);
}

bool gimbalIsActive() { return is_gimbaling; }

void gimbalUpdate() {
  if (is_gimbaling) {
    // Advance only when BOTH motors have reached the current waypoint, so pitch
    // and yaw stay synchronised and the loop never blocks.
    if (pStepper.distanceToGo() == 0 && yStepper.distanceToGo() == 0) {
      if (gimbaling_angle_index >= TRAJECTORY_POINTS) {
        is_gimbaling = false;               // trajectory complete
        digitalWrite(gimbalEnablePin, LOW); // disable driver at rest
      } else {
        commandWaypoint(gimbaling_angle_index);
        gimbaling_angle_index++;
      }
    }
  }
  pStepper.run(); // must run every pass — non-blocking stepping
  yStepper.run();
}
