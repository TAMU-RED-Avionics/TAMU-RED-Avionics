/*
-------------------------------------------------------------------
PT Calibration
-------------------------------------------------------------------
Outputs the analog pressure readings so that they can be used to calibrate the PTs.
*/

/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

// time variables
long unsigned sensor_update_last = 0;
long unsigned sensor_update_interval = 0;    // sensor update interval (microsec)     <-- USER INPUT

long unsigned start_time = 0;
long unsigned num_reads = 0;

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT

/*
PRESSURE TRANSDUCER SET UP
----------------
*/

// teensy pins to read signals
const int pt1_pin = 14;                    // <-- USER INPUT
const int pt2_pin = 15;                    // <-- USER INPUT
const int pt3_pin = -1;                    // <-- USER INPUT
const int pt4_pin = -1;                    // <-- USER INPUT
const int pt5_pin = -1;                    // <-- USER INPUT
const int pt6_pin = -1;                    // <-- USER INPUT

// analog and digital reading variables setup
int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal
int pt3_analog = 0;                        // analog reading from PT output signal
int pt4_analog = 0;                        // analog reading from PT output signal
int pt5_analog = 0;                        // analog reading from PT output signal
int pt6_analog = 0;                        // analog reading from PT output signal

/*
-------------------------------------------------------------------
SETUP Function
-------------------------------------------------------------------
*/
void setup() {
  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  start_time = micros();
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
    pt6_analog = analogRead(pt6_pin);

    // send data to serial monitor 
    Serial.print("t:"); Serial.print(sensor_update_last);        // print time reading

    // If the PT has been defined, print its analog pressure reading
    if (pt1_pin >= 0) {
        Serial.print(",P1:"); Serial.print(pt1_analog);
    } if (pt2_pin >= 0) {
        Serial.print(",P2:"); Serial.print(pt2_analog);
    } if (pt3_pin >= 0) {
        Serial.print(",P3:"); Serial.print(pt3_analog);
    } if (pt4_pin >= 0) {
        Serial.print(",P4:"); Serial.print(pt4_analog);
    } if (pt5_pin >= 0) {
        Serial.print(",P5:"); Serial.print(pt5_analog);
    } if (pt6_pin >= 0) {
        Serial.print(",P6:"); Serial.print(pt6_analog);
    }

    // Prints the sample rate for the current duration of the test
    double seconds_elapsed = (sensor_update_last - start_time) / 1000000.0;
    Serial.print(",SR:"); Serial.print(++num_reads / seconds_elapsed);
    // Serial.print(",smp:"); Serial.print(num_reads);
    // Serial.print(",tim:"); Serial.print(seconds_elapsed);

    // Newline and delay (not sure the reason for the delay, currently commented out)
    Serial.println();
    // delay(10);
  }
}