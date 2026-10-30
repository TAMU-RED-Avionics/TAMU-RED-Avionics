/*
-------------------------------------------------------------------
Ignition Test Teensy
-------------------------------------------------------------------
Simple program to power one ignition system and report the time of the signals.
*/

/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

// time variables
long unsigned sensor_update_last = 0;
long unsigned sensor_update_interval = 10000;    // sensor update interval (microsec)     <-- USER INPUT

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT


/*
VALVE SETUP
*/

// Igniter
const int Igniter_pin = 2;           // <-- USER INPUT
int igniter_on = 0;

/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  pinMode(Igniter_pin, OUTPUT);    // sets the digital pin as output for controlling Igniter MOSFET
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

    // send data to serial monitor 
    Serial.print("I1:"); Serial.print(igniter_on);         // print current ignition state
    Serial.println();
    delay(10);
  }

  // checks if user input is available to read
  if (Serial.available() > 0) {
    // read user input
    String input = Serial.readStringUntil('\n');

    if (input == "IGNITE:0\r") {
      igniter_on = 0;
      digitalWrite(Igniter_pin, LOW);
    } else if (input == "IGNITE:1\r") {
      igniter_on = 1;
      digitalWrite(Igniter_pin, HIGH);
    }
  }
}