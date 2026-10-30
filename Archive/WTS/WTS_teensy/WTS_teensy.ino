/*
-------------------------------------------------------------------
WTS TEENSY CODE
-------------------------------------------------------------------
Reads analog signals from pressure transducers from each pin and outputs pressure using calibration
Pressure transducer A is upstream pressure, uses pin 14
Pressure transducer B is downstream pressure, uses pin 15

Reads serial messages ('0','1','2', or '3') to control MOSFETs connected to Valve A and Valve B
Valve A is N2 to WTS Tank, uses pin 2
Valve B is WTS Tank to orface, uses pin 9
*/

/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

// time variables
long unsigned update_last = 0;
long unsigned update_interval = 100000;    // pt update interval (microsec)     <-- USER INPUT

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT

// teensy pins to read and send signals
const int ptA_pin = 15;                    // downstream pt pin                 <-- USER INPUT
const int ptB_pin = 14;                    // upstream pt pin                   <-- USER INPUT
const int valA_pin = 2;                    // valve A pin                       <-- USER INPUT
const int valB_pin = 9;                    // valve B pin                       <-- USER INPUT

// callibration parameters for the pts
const float ptA_ref1 = 14.754;                   // known pressure low                <-- USER INPUT
const float ptA_ref2 = 140.0 + ptA_ref1;             // known pressure high               <-- USER INPUT

const float ptB_ref1 = 14.754;
const float ptB_ref2 = 150.0 + ptB_ref1;

const int ptA_analog_ref1 = 150;         // analog at known pressure small    <-- USER INPUT
const int ptA_analog_ref2 = 426;         // analog at known pressure high     <-- USER INPUT
const int ptB_analog_ref1 = 175;         // analog at known pressure small    <-- USER INPUT
const int ptB_analog_ref2 = 645;         // analog at known pressure high     <-- USER INPUT

// analog and digital reading variables
int ptA_analog = 0;                        // analog reading from PT output signal
int ptB_analog = 0;                        // analog reading from PT ourput signal
float ptA_pressure = 0.0;                  // calculated pressure using calibration eq
float ptB_pressure = 0.0;                  // calculated pressure using calibration eq

/*
-------------------------------------------------------------------
SETUP
-------------------------------------------------------------------
*/
void setup() {
  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  pinMode(valA_pin, OUTPUT);    // sets the digital pin as output for controlling Valve A MOSFET
  pinMode(valB_pin, OUTPUT);    // sets the digital pin as output for controlling Valve B MOSFET
}
/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // check for last reading update
  if ((micros() - update_last) > update_interval);{
    update_last = micros();                               // update last time update

    // reading presure data
    ptA_analog = analogRead(14);                          // reads value from input pin and assigns to variable
    ptB_analog = analogRead(15);                          // reads value from input pin and assigns to variable.
    ptA_pressure = ptA_ref1 + (ptA_ref2 - ptA_ref1)/(ptA_analog_ref2 - ptA_analog_ref1)*(ptA_analog - ptA_analog_ref1);  // calculates pressure reading using calibration parameters
    ptB_pressure = ptB_ref1 + (ptB_ref2 - ptB_ref1)/(ptB_analog_ref2 - ptB_analog_ref1)*(ptB_analog - ptB_analog_ref1); // calculates pressure reading using calibration parameters
    
    // send data to serial monitor 
    Serial.print(update_last);                            // print time reading
    // Serial.print(","); Serial.print(ptA_analog);          // print analog reading (comment out when using GUI)
    // Serial.print(","); Serial.print(ptB_analog);          // print analog reading (comment out when using GUI)
    Serial.print(","); Serial.print(ptA_pressure);        // print pressure calculation
    Serial.print(","); Serial.print(ptB_pressure);        // print pressure calculation
    Serial.println();
    delay(10);
  }
  // checks if user input is available to read
  if (Serial.available() > 0) {
    // read user input
    char input = Serial.read();
    // convert input to corresponding state and actuate pins
    switch (input) {
      case '0':                                           // case 0 = valve A open
        digitalWrite(2, HIGH); break;
      case '1':                                           // case 1 = valve A close
        digitalWrite(2, LOW); break;

      // Valve 2 is normally open, so high signal closes the valve
      case '2':                                           // case 2 = valve B open
        digitalWrite(9, LOW); break;
      case '3':                                           // case 3 = valve B close
        digitalWrite(9, HIGH); break;
    }
  }
}