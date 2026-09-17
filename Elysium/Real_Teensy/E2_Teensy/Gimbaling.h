#pragma once
#include <Arduino.h>

// ============================================================================
// Gimbaling module — comms-aligned, NON-BLOCKING
// ----------------------------------------------------------------------------
// Drives the pitch/yaw gimbal steppers through the precomputed trajectory in
// Gimbal_Angles.h. Designed to run inside the E2_Teensy EGCP comms loop, which
// enforces CONNECTION_TIMEOUT (5 s). Nothing here blocks: gimbalUpdate() issues
// at most one step per motor per call, so the comms loop is never starved.
//
// Wiring into E2_Teensy.ino:
//   setup():            gimbalSetup();
//   PKT_BGP handler:    beginGimbalingProgram();
//   PKT_HGP handler:    haltGimbalingProgram();
//   trigger_shutdown(): haltGimbalingProgram();
//   loop() every pass:  gimbalUpdate();
// ============================================================================

void gimbalSetup();              // configure steppers + enable pin (call from setup)
void beginGimbalingProgram();    // PKT_BGP: start the trajectory from the beginning
void haltGimbalingProgram();     // PKT_HGP / shutdown: stop and return toward home
void gimbalUpdate();             // call EVERY loop() pass — non-blocking stepping
bool gimbalIsActive();           // true while a trajectory is running
