/*
-------------------------------------------------------------------
Example
-------------------------------------------------------------------
(Add text for what this program does)
*/

/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT


enum Components {
  NCS1, NCS2, NCS4,
  LABV1, LABV2,
  IG1, IG2, IG3,
  PT1, PT2, PT3, PT4, PT5, PT6,
  TC1, TC2,
  LC1, LC2, LC3
}

/*
VALVE SETUP
*/

// Valves
const int NCS1_pin = 0;           // <-- USER INPUT
const int NCS2_pin = 0;           // <-- USER INPUT
const int NCS3_pin = 0;           // <-- USER INPUT
const int NCS4_pin = 0;           // <-- USER INPUT
const int LABV1_pin = 0;           // <-- USER INPUT
const int LABV2_pin = 0;           // <-- USER INPUT

// Igniter
const int Igniter_pin = 0;           // <-- USER INPUT


/*
PRESSURE TRANSDUCER SET UP
----------------
*/

// teensy pins to read signals
const int pt1_pin = 0;                    // <-- USER INPUT
const int pt2_pin = 0;                    // <-- USER INPUT
const int pt3_pin = 0;                    // <-- USER INPUT
const int pt4_pin = 0;                    // <-- USER INPUT
const int pt5_pin = 0;                    // <-- USER INPUT


// callibration parameters for the pts
const float pt1_ref1 = 0;                       // known pressure low                <-- USER INPUT
const float pt1_ref2 = 0 + pt1_ref1;            // known pressure high               <-- USER INPUT
const float pt2_ref1 = 0;                       // known pressure low                <-- USER INPUT
const float pt2_ref2 = 0 + pt2_ref1;            // known pressure high               <-- USER INPUT
const float pt3_ref1 = 0;                       // known pressure low                <-- USER INPUT
const float pt3_ref2 = 0 + pt3_ref1;            // known pressure high               <-- USER INPUT
const float pt4_ref1 = 0;                       // known pressure low                <-- USER INPUT
const float pt4_ref2 = 0 + pt4_ref1;            // known pressure high               <-- USER INPUT
const float pt5_ref1 = 0;                       // known pressure low                <-- USER INPUT
const float pt5_ref2 = 0 + pt5_ref1;            // known pressure high               <-- USER INPUT

const int pt1_analog_ref1 = 0;         // analog at known pressure small    <-- USER INPUT
const int pt1_analog_ref2 = 0;         // analog at known pressure high     <-- USER INPUT
const int pt2_analog_ref1 = 0;         // analog at known pressure small    <-- USER INPUT
const int pt2_analog_ref2 = 0;         // analog at known pressure high     <-- USER INPUT
const int pt3_analog_ref1 = 0;         // analog at known pressure small    <-- USER INPUT
const int pt3_analog_ref2 = 0;         // analog at known pressure high     <-- USER INPUT
const int pt4_analog_ref1 = 0;         // analog at known pressure small    <-- USER INPUT
const int pt4_analog_ref2 = 0;         // analog at known pressure high     <-- USER INPUT
const int pt5_analog_ref1 = 0;         // analog at known pressure small    <-- USER INPUT
const int pt5_analog_ref2 = 0;         // analog at known pressure high     <-- USER INPUT

// analog and digital reading variables setup
int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal
int pt3_analog = 0;                        // analog reading from PT output signal
int pt4_analog = 0;                        // analog reading from PT output signal
int pt5_analog = 0;                        // analog reading from PT output signal
float pt1_pressure = 0.0;                  // calculated pressure using calibration eq
float pt2_pressure = 0.0;                  // calculated pressure using calibration eq
float pt3_pressure = 0.0;                  // calculated pressure using calibration eq
float pt4_pressure = 0.0;                  // calculated pressure using calibration eq
float pt5_pressure = 0.0;                  // calculated pressure using calibration eq


/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  Serial.begin(BAUD);           // initializes serial communication at set baud rate

  /*
  VALVE SET UP
  -----------------------
  */

  pinMode(NCS1_pin, OUTPUT);
  pinMode(NCS2_pin, OUTPUT);
  pinMode(NCS3_pin, OUTPUT);
  pinMode(NCS4_pin, OUTPUT);
  pinMode(LABV1_pin, OUTPUT);
  pinMode(LABV2_pin, OUTPUT);
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // check for last reading update
  if ((micros() - sensor_update_last) > sensor_update_interval) {
    sensor_update_last = micros();                               // update last time update

    // read pressure data
    pt1_analog = analogRead(pt1_pin);                          // reads value from input pin and assigns to variable
    pt2_analog = analogRead(pt2_pin);                          // reads value from input pin and assigns to variable.
    pt3_analog = analogRead(pt3_pin);
    pt4_analog = analogRead(pt4_pin);
    pt5_analog = analogRead(pt5_pin);

    // Calculate pressure value
    pt1_pressure = pt1_ref1 + (pt1_ref2 - pt1_ref1)/(pt1_analog_ref2 - pt1_analog_ref1)*(pt1_analog - pt1_analog_ref1); // calculates pressure reading using calibration parameters
    pt2_pressure = pt2_ref1 + (pt2_ref2 - pt2_ref1)/(pt2_analog_ref2 - pt2_analog_ref1)*(pt2_analog - pt2_analog_ref1); // calculates pressure reading using calibration parameters
    pt3_pressure = pt3_ref1 + (pt3_ref2 - pt3_ref1)/(pt3_analog_ref2 - pt3_analog_ref1)*(pt3_analog - pt3_analog_ref1); // calculates pressure reading using calibration parameters
    pt4_pressure = pt4_ref1 + (pt4_ref2 - pt4_ref1)/(pt4_analog_ref2 - pt4_analog_ref1)*(pt4_analog - pt4_analog_ref1); // calculates pressure reading using calibration parameters
    pt5_pressure = pt5_ref1 + (pt5_ref2 - pt5_ref1)/(pt5_analog_ref2 - pt5_analog_ref1)*(pt5_analog - pt5_analog_ref1); // calculates pressure reading using calibration parameters

  
    // send data to serial monitor 
    Serial.print("t:"); Serial.print(sensor_update_last);                                  // print time reading
    // Serial.print(","); Serial.print(pt1_analog);             // print analog pressure reading (comment out when using GUI)
    // Serial.print(","); Serial.print(pt2_analog);             // print analog pressure reading (comment out when using GUI)
    Serial.print(",P1:"); Serial.print(pt1_pressure);             // print pressure calculation in psi
    Serial.print(",P2:"); Serial.print(pt2_pressure);              // print pressure calculation in psi
    Serial.print(",P3:"); Serial.print(pt2_pressure);              // print pressure calculation in psi
    Serial.print(",P4:"); Serial.print(pt2_pressure);              // print pressure calculation in psi
    Serial.print(",P5:"); Serial.print(pt2_pressure);              // print pressure calculation in psi
    Serial.print(",T1:"); Serial.print(mcp.readThermocouple());    // print thermocouple temperature in C
    Serial.print(",T2:"); Serial.print(mcp2.readThermocouple());    // print thermocouple temperature in C
    Serial.print(",L1:"); Serial.print(weight1);                   // print load cell 1 in kg
    Serial.print(",L2:"); Serial.print(weight2);                   // print load cell 2 in kg
    Serial.print(",Ax:"); Serial.print(accx);                      // print acceleration in x direction  <-- determine what direction x is in relation to engine
    Serial.print(",Ay:"); Serial.print(accy);                      // print acceleration in y direction  <-- determine what direction y is in relation to engine
    Serial.print(",Az:"); Serial.print(accz);                      // print acceleration in z direction  <-- determine what direction z is in relation to engine
    Serial.println();
    delay(10);
  }

  // checks if user input is available to read
  if (Serial.available() > 0) {
    // read user input
    String input = Serial.read();

    // update last time of communication variable
    last_update_time = micros();

    // convert input to corresponding state, actuate pins, and set valve control state

    // Normally closed solenoid valve 1
    if (input == "NCS1:0\r\n") {
      digitalWrite(NCS1_pin, HIGH); // Open
    }
    if (input == "NCS1:1\r\n") {
      digitalWrite(NCS1_pin, LOW);  // Closed
    }

    // Normally closed solenoid valve 2
    if (input == "NCS2:0\r\n") {
      digitalWrite(NCS2_pin, HIGH);
    }
    if (input == "NCS2:1\r\n") {
      digitalWrite(NCS2_pin, LOW);
    }

    // Normally closed solenoid valve 3
    if (input == "NCS3:0\r\n") {
      digitalWrite(NCS3_pin, HIGH);
    }
    if (input == "NCS3:1\r\n") {
      digitalWrite(NCS3_pin, LOW);
    }

    // Normally closed solenoid valve 4
    if (input == "NCS4:0\r\n") {
      digitalWrite(NCS4_pin, HIGH);
    }
    if (input == "NCS4:1\r\n") {
      digitalWrite(NCS4_pin, LOW);
    }

    // Linearly Actuated Ball Valve 1
    if (input == "LA-BV 1:0\r\n") {
      digitalWrite(LABV1_pin, HIGH);
    }
    if (input == "LA-BV 1:1\r\n") {
      digitalWrite(LABV1_pin, LOW);
    }

    // Linearly Actuated Ball Valve 2
    if (input == "LA-BV 2:0\r\n") {
      digitalWrite(LABV2_pin, HIGH);
    }
    if (input == "LA-BV 2:1\r\n") {
      digitalWrite(LABV2_pin, LOW);
    }

    // Igniter
    if (input == "IGNITE:1\r\n") {
      digitalWrite(Igniter_pin, HIGH);
    }
  }

  // Shutdown engine if teensy is not communicating with computer
  if ((micros() - last_update_time) > shutdown_time) {
    // Shutdown engine

    // Open NCS2 & NCS3
    digitalWrite(NCS2_pin, HIGH);
    digitalWrite(NCS3_pin, HIGH);

    // Close ball valves & NCS1
    digitalWrite(NCS1_pin, LOW);
    digitalWrite(LABV1_pin, LOW);
    digitalWrite(LABV2_pin, LOW);

    // Open NCS4 for 3 seconds
    digitalWrite(NCS4_pin, HIGH);
    delay(3000);
    digitalWrite(NCS4_pin, LOW);

    // End program
    abort(); // maybe break command? Maybe while?
    while(1);
  }
}}
}