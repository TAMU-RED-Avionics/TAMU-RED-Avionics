/*
-------------------------------------------------------------------
TIME AND COMMUNICATION SETUP
-------------------------------------------------------------------
*/

// time variables
long unsigned sensor_update_last = 0;
long unsigned connection_last = 0;
const long unsigned SENSOR_UPDATE_INTERVAL = 100;       // Time between remeasuring sensors (microsec)               <-- USER INPUT
const long unsigned CONNECTION_TIMEOUT = 200000;      // Time without comms before automated shutdown (microsec)   <-- USER INPUT
const long unsigned TIMEOUT_PRINT_INTERVAL = 500000;  // Time betweeen alerts when comms are out (microsec)        <-- USER INPUT

// BAUD rate 
const int BAUD = 115200;    // serial com in bits per second     <-- USER INPUT

/*
-------------------------------------------------------------------
VALVE & IGNITER SETUP
-------------------------------------------------------------------
*/

// Valve pins
const int NCS1_PIN = 7;           // <-- USER INPUT
const int NCS2_PIN = 10;          // <-- USER INPUT
const int NCS4_PIN = 9;          // <-- USER INPUT
const int LABV1_PIN = 5;          // <-- USER INPUT

// Igniter pins
const int IG1_PIN = 11;           // <-- USER INPUT
const int IG2_PIN = 12;           // <-- USER INPUT

// Function to get pin number from string
int get_pin(String id) {
  if (id == "NCS1") {
    return NCS1_PIN;
  } else if (id =="NCS2") {
    return NCS2_PIN;
  } else if (id =="NCS4") {
    return NCS4_PIN;
  } else if (id =="LA-BV1") {
    return LABV1_PIN;
  } else if (id == "IGNITE") {
    return IG1_PIN;
  }

  // Return -1 if no match was found
  return -1;
}

/*
-------------------------------------------------------------------
PRESSURE TRANSDUCER SET UP
-------------------------------------------------------------------
*/

// teensy pins to read signals
const int PT1_PIN = 15;                    // <-- USER INPUT
const int PT2_PIN = 16;                    // <-- USER INPUT

int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal

// Calibration constants
const float PT_SLOPES[] = {0.927016, 0.927016};     // <-- USER INPUT
const float PT_INTERCEPTS[] = {-68.75, -68.75};     // <-- USER INPUT

// Function to calculate pressure
float get_pressure(float analog_reading, size_t id) {
  // Convert Voltage reading to measurement in psi with the correct calibration factors
  // PTs are 1-indexed, the lists are 0-indexed
  return PT_SLOPES[id-1] * analog_reading + PT_INTERCEPTS[id-1];
}


void setup() {
  // Initialize serial communication as configured and start thermocouple library
  Serial.begin(BAUD);

  // VALVES & IGNITERS
  // Configure digital pins for actuating valves and igniteres as output only
  pinMode(NCS1_PIN, OUTPUT);
  pinMode(NCS2_PIN, OUTPUT);
  pinMode(NCS4_PIN, OUTPUT);
  pinMode(LABV1_PIN, OUTPUT);
}

void loop() {
  /*
  -------------------------------------------------------------------
  SENSOR READING
  -------------------------------------------------------------------
  */

  // Check how long it has been since the last measurement
  if ((micros() - sensor_update_last) > SENSOR_UPDATE_INTERVAL) {
    // Update the time of last reading
    sensor_update_last = micros();

    // Read Pressure Transducer analog data
    pt1_analog = analogRead(PT1_PIN);
    pt2_analog = analogRead(PT2_PIN);

    // Print sensor readings to the serial output
    // Convert pressures to psi
    Serial.print("P1:"); Serial.print(get_pressure(pt1_analog, 1));
    Serial.print(",P2:"); Serial.print(get_pressure(pt2_analog, 2));

    // End the line to signify the end of message
    Serial.println();
  }

  /*
  -------------------------------------------------------------------
  VALVE & IGNITER ACTUATION
  -------------------------------------------------------------------
  */

  if (Serial.available() > 0) {
    // Update the time since last communication
    connection_last = micros();

    // read communication until end of message
    String input = Serial.readStringUntil('\n');

    // nop is the no operation command, which is merely to confirm that the connection is active
    if (input == "nop\r") { return; }

    // Parse message into ID and value, convert to pin number and an int
    // If message cannot be split, it is meaningless
    int split_index = input.indexOf(':');
    if (-1 == split_index) { return; }

    // If the pin number cannot be resolved, it is meaningless
    int pin = get_pin(input.substring(0, split_index));
    if (-1 == pin) { return; }

    // Convert the second half of the string to the integer value
    int value = input.substring(split_index + 1).toInt();
  

    // Use the pin and value to actuate the specified valve
    switch (value) {
      case 0:
        digitalWrite(pin, LOW);   // Close Valve, Unpower Igniter

        // Two igniters from the same signal
        if (IG1_PIN == pin) {
          digitalWrite(IG2_PIN, LOW);
        }
        break;
      case 1:
        digitalWrite(pin, HIGH);  // Open Valve, Power Igniter

        // Two igniters from the same signal
        if (IG1_PIN == pin) {
          digitalWrite(IG2_PIN, HIGH);
        }
    }
  }

  /*
  -------------------------------------------------------------------
  COMMUNICATIONS LOSS CHECK
  -------------------------------------------------------------------
  */
  // Check if the time since last communication exceeds the allowable timeout
  if ((micros() - connection_last) > CONNECTION_TIMEOUT) {
    // Guarantee a return to a safe state by Opening NCS2
    digitalWrite(NCS2_PIN, HIGH);
    
    // And then closing all other valves, unpowering igniters
    digitalWrite(NCS1_PIN, LOW);
    digitalWrite(NCS4_PIN, LOW);
    digitalWrite(LABV1_PIN, LOW);
    digitalWrite(IG1_PIN, LOW);
    digitalWrite(IG2_PIN, LOW);

    // Enter a fixed loop until connection is reestablished and reinitiated
    bool connection_lost = true;
    long unsigned print_last = 0;
    while (connection_lost) {
      // Every TIMEOUT_PRINT_INTERAVAL, output the aborted message to alert the operator of the current state
      if ((micros() - print_last) > TIMEOUT_PRINT_INTERVAL) {
        print_last = micros();
        Serial.println("Aborted");
      }

      // Check for input from the operator
      if (Serial.available() > 0) {
        String input = Serial.readStringUntil('\n');
        Serial.println("New Input= " + input);

        // Only respond if the specific string is encountered
        if (input == "Start\r") {
          // Update timer
          connection_last = micros();

          // Exit the connection_lost loop
          connection_lost = false;
        }
      }
    }
  }
}
