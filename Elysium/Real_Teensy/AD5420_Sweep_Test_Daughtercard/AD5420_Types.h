// AD5420_Types.h — types used by AD5420_Sweep_Test.ino.
// They live in a header so they're defined before the function prototypes
// the Arduino IDE auto-generates at the top of the .ino.
#pragma once
#include <stdint.h>

enum Expect : uint8_t { EXP_LINEAR, EXP_EDGE, EXP_CLIP };

struct Point {
  float    target_mA;
  uint16_t code, rbData, status;
  Expect   expect;
  bool     dir_up;
  float    meas_mA;      // NAN if not measured
};
