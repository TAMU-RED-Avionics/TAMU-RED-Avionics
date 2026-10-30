/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

#include <Arduino.h>

// time variables
long unsigned LAST_SENSOR_UPDATE = 0;                     // Timestamp of last sensor reading (microsec)
const long unsigned SENSOR_UPDATE_INTERVAL = 1000;        // sensor update interval (microsec)              <-- USER INPUT

long unsigned LAST_LC_UPDATE = 0;                         // Timestamp of last Load Cell reading (microsec)
const long unsigned LC_UPDATE_INTERVAL = 100000;          // Load Cell update interval (microsec)           <-- USER INPUT

long unsigned LAST_COMMUNICATION_TIME = 0;                // Timestamp of last communication of any type (microsec)
const long unsigned CONNECTION_TIMEOUT = 200000;          // automated shutdown timeout for complete comms failure (microsec)           <-- USER INPUT

long unsigned LAST_HUMAN_UPDATE = 0;                      // Timestamp of last human communication(microsec)
const long unsigned HUMAN_CONNECTION_TIMEOUT = 300000000; // automated shutdown timeout for human comms failure (microsec)              <-- USER INPUT

long unsigned ABORT_TIME_TRACKING = 0;
const long unsigned ABORTED_TIME_INTERVAL = 500000;       // microsec between printing "aborted" (when aborted)
const long unsigned SHUTDOWN_PURGE_TIME = 2000;           // duration of purge for shutdown, in milliseconds

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT

// LABV 1 state variable
bool is_LABV1_open = false;

/*
VALVE SETUP
*/

// Valves
const int NCS1_PIN = 7;           // <-- USER INPUT
const int NCS2_PIN = 8;           // <-- USER INPUT
const int NCS4_PIN = 11;           // <-- USER INPUT
const int LABV1_PIN = 5;          // <-- USER INPUT
const int LABV2_PIN = 6;          // <-- USER INPUT

// Igniter
const int IGN1_PIN = 10;          // <-- USER INPUT
const int IGN2_PIN = 9;          // <-- USER INPUT

// serial input variables
String IDENTIFIER = "";
int CONTROL_STATE = 0;

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
  } else if (id =="LA-BV2") {
    return LABV2_PIN;
  } else if (id =="IG1") {
    return IGN1_PIN;
  } else if (id =="IG2") {
    return IGN2_PIN;
  }

  // Return -1 if no match was found
  return -1;
}

#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

unsigned int PORT = 8888;
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];  // buffer to hold incoming packet,
// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
IPAddress REMOTE(192, 168, 1, 175);
IPAddress LOCAL(192, 168, 1, 174);

void output_string(unsigned int port, const char *to_write) {
  udp.beginPacket(REMOTE, port);
  udp.write(to_write);
  udp.endPacket();
}

void output_float(unsigned int port, float to_write) {
  char buf[100]; // *slaps roof* yeah that'll do nicely
  constexpr unsigned long PRECISION = 5;
  dtostrf(to_write, 1, PRECISION, buf);
  udp.beginPacket(REMOTE, port);
  udp.write(buf);
  udp.endPacket();
}

String input_until(char stop_character) {
  String ret = "";
  char c = udp.read();
  while (c != stop_character) {
    ret += c;
    c = udp.read();
  }
  return ret;
}

bool init_comms(byte* mac, unsigned int port) {
  EthernetUDP ret;
  IPAddress GATEWAY(192, 168, 1, 1);   // there is no router, so this is meaningless 
  IPAddress SUBNET(255, 255, 255, 0);  // could be almost anything else tbh
  Ethernet.begin(mac, LOCAL, GATEWAY, SUBNET);
  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("ERR: No Ethernet board detected");
    return false;
  } else if (Ethernet.linkStatus() == LinkOFF) {
    Serial.println("ERR: Ethernet cable disconnected");
    return false;
  }
  udp.begin(port);
  return true;
}

/*
LOAD CELL SET UP
----------------
*/

// import library
#include "HX711.h"

// define data and clock pins for each loadcell
const int LC1_D_OUT_PIN = 28;            // <-- USER INPUT
const int LC1_CLK_PIN = 29;              // <-- USER INPUT
const int LC2_D_OUT_PIN2 = 26;           // <-- USER INPUT
const int LC2_CLK_PIN2 = 27;             // <-- USER INPUT
const int LC3_D_OUT_PIN3 = 24;           // <-- USER INPUT
const int LC3_CLK_PIN3 = 25;             // <-- USER INPUT

// measurement set up
float weight1 = 0;
float weight2 = 0;
float weight3 = 0;
HX711 scale, scale2, scale3;



/*
THERMOCOUPLE SET UP
----------------
*/

// Thermocouple libraries
#include <Wire.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_I2CRegister.h>
#include <Adafruit_MCP9600.h>

// Thermocouple I2C addresses
#define I2C_ADDRESS1 (0x67)
//#define I2C_ADDRESS2 (0x66)

// Thermocouple mcp identifier
Adafruit_MCP9600 mcp;
//Adafruit_MCP9600 mcp2;


/*
PRESSURE TRANSDUCER SET UP
--------------------------------
*/

// teensy pins to read signals
const int PT1_PIN = 23;                    // <-- USER INPUT
const int PT2_PIN = 22;                    // <-- USER INPUT
const int PT3_PIN = 21;                    // <-- USER INPUT
const int PT4_PIN = 20;                    // <-- USER INPUT
const int PT5_PIN = 17;                    // <-- USER INPUT
const int PT6_PIN = 16;                    // <-- USER INPUT
 

// analog and digital reading variables setup
int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal
int pt3_analog = 0;                        // analog reading from PT output signal
int pt4_analog = 0;                        // analog reading from PT output signal
int pt5_analog = 0;                        // analog reading from PT output signal
int pt6_analog = 0;                        // analog reading from PT output signal

// Calibration constants
const float pt_slope[] = {1.22983871, 1.22983871, 1.22983871, 1.22983871, 1.22983871, 1.22983871};
const float pt_intercept[] = {-111.9733871, -105.8241935, -109.5137097, -111.9733871, -108.283871, -113.2032258};

// Calibration constants for pure analog readings
//const float pt_slope[] = {1, 1, 1, 1, 1, 1};
//const float pt_intercept[] = {0, 0, 0, 0, 0, 0};

// Function to calculate pressure
float pressureCalculation(float analog, size_t id) {
    // Calculate pressure based on analog input
    return pt_slope[id-1] * analog + pt_intercept[id-1];
}

/*
ACCELEROMETER SET UP
----------------
*/

// import libraries
#include "IMU.h"
#include "LSM6DSL.h"
#include "LIS3MDL.h"

// measurement variable setup
byte buff[6];
int accRaw[3];
float accx, accy, accz;
const float accoffset = 4180;

/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  // Serial.begin(BAUD);           // initializes serial communication at set baud rate
  init_comms(MAC_ADDRESS, PORT);  // does what it says on the tin
  Wire.begin();

  /*
  VALVE SET UP
  -----------------------
  */
  output_string(PORT, "test1");
  // Serial.println("test1");

  pinMode(NCS1_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 1 MOSFET
  pinMode(NCS2_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 2 MOSFET
  pinMode(NCS4_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 4 MOSFET
  pinMode(LABV1_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 5 MOSFET
  pinMode(LABV2_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 6 MOSFET
  pinMode(IGN1_PIN, OUTPUT);
  pinMode(IGN2_PIN, OUTPUT);

  // Serial.println("test2_Pins");
  output_string(PORT, "test2_Pins");

  /*
  THERMOCOUPLE SET UP
  -----------------------
  */

  // Initialize MCP9600 sensors
  mcp.begin(I2C_ADDRESS1);
  //mcp2.begin(I2C_ADDRESS2);

  // Configure both sensors
  mcp.setADCresolution(MCP9600_ADCRESOLUTION_18);
  mcp.setThermocoupleType(MCP9600_TYPE_K);
  mcp.setFilterCoefficient(3);
  mcp.enable(true);

  //mcp2.setADCresolution(MCP9600_ADCRESOLUTION_18);
  //mcp2.setThermocoupleType(MCP9600_TYPE_K);
  //mcp2.setFilterCoefficient(3);
  //mcp2.enable(true);

  // Serial.println("test3_TC");
  output_string(PORT, "test3_TC");

  /*
  LOAD CELL SET UP
  -----------------------
  */

  // load cell setup
  scale.begin(LC1_D_OUT_PIN, LC1_CLK_PIN);
  scale2.begin(LC2_D_OUT_PIN2, LC2_CLK_PIN2);
  scale3.begin(LC3_D_OUT_PIN3, LC3_CLK_PIN3);

  // scale and tare load cells
  scale.set_scale(-3980.f);  // Set the scale factor for conversion to pounds
  scale.tare();             // Reset the scale to zero

  scale2.set_scale(-3880.f); // Set the scale factor for conversion to pounds
  scale2.tare();            // Reset the scale to zero

  scale3.set_scale(-3780.f); // Set the scale factor for conversion to pounds
  scale3.tare();            // Reset the scale to zero
  
  // Serial.println("test4_LC");
  output_string(PORT, "test4_LC");
  /*
  ACCELEROMETER SET UP
  -----------------------
  */

  // detect and enable IMU
  // detectIMU();
  // enableIMU();
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // checks if user input is available to read
  udp.parsePacket();
  if (udp.available() > 0) {
    // read communication
    String input = input_until('\n');
    LAST_COMMUNICATION_TIME = micros();

    // no operation command to confirm connection
    if (input != "nop\r") {
      LAST_HUMAN_UPDATE = micros();
    } else {
      return;
    }

    // break string into identifier and control state
    int delimiterIndex = input.indexOf(':');
    if (delimiterIndex != -1) {
      IDENTIFIER = input.substring(0, delimiterIndex);
      CONTROL_STATE = input.substring(delimiterIndex + 1).toInt();
    }
    else { return; }

    int pin = get_pin(IDENTIFIER);
    if (pin == -1) {
      return;
    }
    switch (CONTROL_STATE) {
      case 0:
        digitalWrite(pin, LOW);   // Close Valve
        if (IDENTIFIER == "LA-BV1") {
          if (is_LABV1_open) {
            digitalWrite(NCS2_PIN, HIGH);
          }
          is_LABV1_open = false;
        }
        break;
      case 1:
        digitalWrite(pin, HIGH);  // Open Valve
        if (IDENTIFIER == "LA-BV1") {
          is_LABV1_open = true;
        }
        break;
    }
  }

  // check for last reading update
  if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
    LAST_SENSOR_UPDATE = micros();                               // update time

    // read pressure data
    pt1_analog = analogRead(PT1_PIN);                          // reads value from input pin and assigns to variable
    pt2_analog = analogRead(PT2_PIN);                          // reads value from input pin and assigns to variable.
    pt3_analog = analogRead(PT3_PIN);
    pt4_analog = analogRead(PT4_PIN);
    pt5_analog = analogRead(PT5_PIN);
    pt6_analog = analogRead(PT6_PIN);

    // read acceleration
    // readACC(buff);
    // accRaw[0] = (int16_t)(buff[0] | (buff[1] << 8)); 
    // accRaw[1] = (int16_t)(buff[2] | (buff[3] << 8));
    // accRaw[2] = (int16_t)(buff[4] | (buff[5] << 8));
    // accx = accRaw[0]/accoffset;
    // accy = accRaw[1]/accoffset;
    // accz = accRaw[2]/accoffset;

    // measure force from load cells, only update at slower interval
    if ((LAST_SENSOR_UPDATE - LAST_LC_UPDATE) > LC_UPDATE_INTERVAL) {
      LAST_LC_UPDATE = LAST_SENSOR_UPDATE;
      weight1 = scale.get_units(1);  // Get the weight in lbs
      weight2 = scale2.get_units(1); // Get the weight in lbs
      weight3 = scale3.get_units(1); // Get the weight in lbs
    }

    // measure temp from thermocouples in °C
    float t1 = mcp.readThermocouple();
    
    // send data to serial monitor
    output_string(PORT, "t:");
    output_float(PORT, LAST_SENSOR_UPDATE);
    output_string(PORT, ",P1:");
    output_float(PORT, pressureCalculation(pt1_analog, 1));
    output_string(PORT, ",P2:");
    output_float(PORT, pressureCalculation(pt2_analog, 2));
    output_string(PORT, ",P3:");
    output_float(PORT, pressureCalculation(pt3_analog, 3));
    output_string(PORT, ",P4:");
    output_float(PORT, pressureCalculation(pt4_analog, 4));
    output_string(PORT, ",P5:");
    output_float(PORT, pressureCalculation(pt5_analog, 5));
    output_string(PORT, ",P6:");
    output_float(PORT, pressureCalculation(pt6_analog, 6));
    output_string(PORT, ",T1:");
    output_float(PORT, t1);
    output_string(PORT, ",L1:");
    output_float(PORT, weight1);
    output_string(PORT, ",L2:");
    output_float(PORT, weight2);
    output_string(PORT, ",L3:");
    output_float(PORT, weight3);
    output_string(PORT, ",t_loc:");
    float t_loc = (HUMAN_CONNECTION_TIMEOUT - (LAST_SENSOR_UPDATE -LAST_HUMAN_UPDATE)) / 1000000.0;
    output_float(PORT, t_loc);
    output_string(PORT, "\n");
    delay(10);
    // Serial.print("t:"); Serial.print(LAST_SENSOR_UPDATE);                             // print time reading in microseconds
    // Serial.print(",P1:"); Serial.print(pressureCalculation(pt1_analog, 1));           // print pressure calculation in psi
    // Serial.print(",P2:"); Serial.print(pressureCalculation(pt2_analog, 2));           // print pressure calculation in psi
    // Serial.print(",P3:"); Serial.print(pressureCalculation(pt3_analog, 3));           // print pressure calculation in psi
    // Serial.print(",P4:"); Serial.print(pressureCalculation(pt4_analog, 4));           // print pressure calculation in psi
    // Serial.print(",P5:"); Serial.print(pressureCalculation(pt5_analog, 5));           // print pressure calculation in psi
    // Serial.print(",P6:"); Serial.print(pressureCalculation(pt6_analog, 6));           // print pressure calculation in psi

    // Serial.print(",T1:"); Serial.print(t1);                                           // print thermocouple temperature in C
    // // Serial.print(",T2:"); Serial.print(mcp2.readThermocouple());                   // print thermocouple temperature in C
    // Serial.print(",L1:"); Serial.print(weight1);                                      // print load cell 1 in lbs
    // Serial.print(",L2:"); Serial.print(weight2);                                      // print load cell 2 in lbs
    // Serial.print(",L3:"); Serial.print(weight3);                                      // print load cell 3 in lbs
    // // Serial.print(",Ax:"); Serial.print(accx);                                      // print acceleration in x direction  <-- determine what direction x is in relation to engine
    // // Serial.print(",Ay:"); Serial.print(accy);                                      // print acceleration in y direction  <-- determine what direction y is in relation to engine
    // // Serial.print(",Az:"); Serial.print(accz);                                      // print acceleration in z direction  <-- determine what direction z is in relation to engine
    // float t_loc = (HUMAN_CONNECTION_TIMEOUT - (LAST_SENSOR_UPDATE -LAST_HUMAN_UPDATE)) / 1000000.0;
    // Serial.print(",t_loc:"); Serial.println(t_loc);                                     // print time until loss of communications occurs, in seconds (only due to human inaction)
    //Serial.println();
    //delay(10);
  }

  // Lost communication shutdown
  if (((micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT) || ((micros() - LAST_HUMAN_UPDATE) > HUMAN_CONNECTION_TIMEOUT)) {
    // Open NCS2
    digitalWrite(NCS2_PIN, HIGH);

    // Close ball valves & NCS1
    digitalWrite(NCS1_PIN, LOW);
    digitalWrite(NCS4_PIN, LOW);
    digitalWrite(LABV1_PIN, LOW);
    digitalWrite(LABV2_PIN, LOW);

    // Unpower igniters
    digitalWrite(IGN1_PIN, LOW);
    digitalWrite(IGN2_PIN, LOW);

    // If LABV1 is open, system purges with nitrogen
    if (is_LABV1_open) {
      // Open NCS4 for 3 seconds
      digitalWrite(NCS4_PIN, HIGH);
      delay(SHUTDOWN_PURGE_TIME);
      digitalWrite(NCS4_PIN, LOW);
    }

    // While system is aborted, print "aborted" until a start command is received
    bool aborted = true;
    while(aborted) {
      if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
        ABORT_TIME_TRACKING = micros();
        output_string(PORT, "Aborted\n");
        // Serial.println("Aborted");
      }

      udp.parsePacket();
      if (udp.available() > 0) {
        // String input = Serial.readStringUntil('\n');
        String input = input_until('\n');
        output_string(PORT, ("New Input= " + input + '\n').c_str());
        // Serial.println("New Input= " + input);

        if ((input == "start\r") || (input == "Start\r")){
          aborted = false;
          LAST_COMMUNICATION_TIME = micros();
          LAST_HUMAN_UPDATE = micros();
          digitalWrite(NCS2_PIN, LOW);
        }
      }
    }
  }
}