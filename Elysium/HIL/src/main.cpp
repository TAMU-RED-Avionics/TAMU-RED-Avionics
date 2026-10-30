#include <Arduino.h>
#include <string>
using namespace std;

/*
==============================================
VARIABLE DEFINITIONS
==============================================
*/

// Serial data string
String SERIALDATA;

// PWM output pins
int PT1_OUT = 0;                        // PWM output pin
int PT2_OUT = 0;                        // PWM output pin
int PT3_OUT = 0;                        // PWM output pin
int PT4_OUT = 0;                        // PWM output pin
int PT5_OUT = 0;                        // PWM output pin
int PT6_OUT = 0;                        // PWM output pin
int PT7_OUT = 0;                        // PWM output pin
int PT8_OUT = 0;                        // PWM output pin

// Variables to store pressure values
int P1, P2, P3, P4, P5, P6, P7, P8;

// Maximum and minimum pressure values
int MIN_PRESSURE = 0; // psi
int MAX_PRESSURE = 1000; // psi

// PWM value range
int PWM_range = 1023; // 10-bit resolution

// Pressure transducer calibration constants
const float PT_SLOPE[] = {585.9375, 585.9375, 585.9375, 585.9375, 585.9375, 585.9375, 390.625, 390.625}; // Placeholder values
const float PT_INTERCEPT[] = {-375, -375, -375, -375, -375, -375, -250, -250}; // Placeholder values

/*
==============================================
FUNCTION DECLARATIONS
==============================================
*/
int READ_DATA(String);

float PWM_VALUE(int);

float pressureCalculation(float analog, size_t id);

/*
==============================================
SETUP
==============================================
*/
void setup() {
  // Initiate serial communication
  Serial.begin(9600);

  // Define pin modes
  pinMode(PT1_OUT, OUTPUT);
  pinMode(PT2_OUT, OUTPUT);
  pinMode(PT3_OUT, OUTPUT);
  pinMode(PT4_OUT, OUTPUT);
  pinMode(PT5_OUT, OUTPUT);
  pinMode(PT6_OUT, OUTPUT);
  pinMode(PT7_OUT, OUTPUT);
  pinMode(PT8_OUT, OUTPUT);

  // Set pin write frequency
  analogWriteFrequency(PT1_OUT, 146484.38);   // Ideal frequency of 146484.38 Hz at 600 MHz CPU speed for 10-bit resolution
  analogWriteFrequency(PT2_OUT, 146484.38);
  analogWriteFrequency(PT3_OUT, 146484.38);
  analogWriteFrequency(PT4_OUT, 146484.38);
  analogWriteFrequency(PT5_OUT, 146484.38);
  analogWriteFrequency(PT6_OUT, 146484.38);
  analogWriteFrequency(PT7_OUT, 146484.38);
  analogWriteFrequency(PT8_OUT, 146484.38);

  // Set analog write resolution to 10-bit
  analogWriteResolution(10);  // analogWrite value 0 to 1023
}

/*
==============================================
MAIN LOOP
==============================================
*/
void loop() {
  // Check for serial input
    if (Serial.available() > 0) {
      SERIALDATA = Serial.readStringUntil('\n');
      SERIALDATA.trim(); // remove any extra space
      READ_DATA(SERIALDATA);
      
      // Obtain PWM values
      float P1_VALUE = PWM_VALUE(P1, 1);
      float P2_VALUE = PWM_VALUE(P2, 2);
      float P3_VALUE = PWM_VALUE(P3, 3);
      float P4_VALUE = PWM_VALUE(P4, 4);
      float P5_VALUE = PWM_VALUE(P5, 5);
      float P6_VALUE = PWM_VALUE(P6, 6);
      float P7_VALUE = PWM_VALUE(P7, 7);
      float P8_VALUE = PWM_VALUE(P8, 8);

      // Send PWM signal
      analogWrite(PT1_OUT, P1_VALUE);
      analogWrite(PT2_OUT, P2_VALUE);
      analogWrite(PT3_OUT, P3_VALUE);
      analogWrite(PT4_OUT, P4_VALUE);
      analogWrite(PT5_OUT, P5_VALUE);
      analogWrite(PT6_OUT, P6_VALUE);
      analogWrite(PT7_OUT, P7_VALUE);
      analogWrite(PT8_OUT, P8_VALUE);
  }
}

/*
==============================================
FUNCTION DEFINITIONS
==============================================
*/
int READ_DATA(String SERIALDATA) {
  // Reset all variables before parsing
  float P1 = P2 = P3 = P4 = P5 = P6 = P7 = P8 = 0;

  int i = 0;
  while (i < SERIALDATA.length()) {
    int colonIndex = SERIALDATA.indexOf(':', i);
    int commaIndex = SERIALDATA.indexOf(',', i);
    if (commaIndex == -1) commaIndex = SERIALDATA.length(); // Handle last key-value pair

    if (colonIndex != -1 && colonIndex < commaIndex) {
        String key = SERIALDATA.substring(i, colonIndex);
        float value = SERIALDATA.substring(colonIndex + 1, commaIndex).toFloat();

        // Assign values based on key
        if      (key == "P1") P1 = value;
        else if (key == "P2") P2 = value;
        else if (key == "P3") P3 = value;
        else if (key == "P4") P4 = value;
        else if (key == "P5") P5 = value;
        else if (key == "P6") P6 = value;
        else if (key == "P7") P7 = value;
        else if (key == "P8") P8 = value;
    }
    i = commaIndex + 1;
  }
}

float PWM_VALUE(int PRESSURE, int id) {
  float ANALOG_VALUE = (PRESSURE - PT_INTERCEPT[id-1]) / PT_SLOPE[id-1]; // Calculate analog pressure value from transducer parameters
  // float duty_cycle = (PRESSURE - MIN_PRESSURE) / (MAX_PRESSURE - MIN_PRESSURE); // Pressure duty cycle as a percentage of min/max pressures
  float duty_cycle = (ANALOG_VALUE - 0) / (3.3 - 0); // Calculate duty cycle as a percentage from min/max voltages
  int pwm_value = (duty_cycle * PWM_range); // Calculate the pwm value based on the percentage duty cycle
  return constrain(pwm_value, 0, PWM_range); // Ensure it's within valid range
}