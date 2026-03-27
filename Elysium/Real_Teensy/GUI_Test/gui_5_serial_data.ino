// Simeon Shaffar Oct 25 2025
#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
#include "../Elysium_teensy/EGCP.h"


/*
-------------------------------------------------------------------
To test this with your laptop:
  cd Elysium_GUI
  python GUI_MAIN.py

  You might need to get your ip address set up, in mac or linux, do:
    1. ifconfig (look for an interface that pops up only when the eth is plugged in)
    2. sudo ifconfig <NAME> inet 192.168.1.175 netmask 255.255.255.0 up

  Type "192.168.1.174" in the IP section and "8888" in the Port section
  Connect and look at the graphs
-------------------------------------------------------------------
*/


//                       USER INPUT SETTINGS
// ----------------------------------------------------------------

// Ethernet & Comms
IPAddress REMOTE(192, 168, 1, 175);                       // The IP Address of the master computer we are connecting to 
IPAddress LOCAL(192, 168, 1, 174);                        // The IP Address of this microcontroller on the master's network
const int BAUD = 115200;                                  // Serial BAUD rate (bits/second)
unsigned int PORT = 8888;                                 // The port to bind to (assumed to be identical to the GUI running on the master)

// Timing Intervals
const int unsigned SYSTEM_LOOP_INTERVAL = 1;              // The loop delay of the overall system - configures the NOOP TX Rate (millisec)
const long unsigned ABORTED_MSG_INTERVAL = 500 * 1000;    // Interval for printing "aborted" when in an abort state (microsec)
const long unsigned SENSOR_UPDATE_INTERVAL = 100 * 1000;  // Interval for sending sensor data (microsec)

const long unsigned NOOP_TX_INTERVAL = 10 * 1000;          // Minimum time to wait in between sending heartbeats (microsec) - 10ms
const long unsigned NOOP_RX_TIMEOUT =  60 * 1000;          // Timeout to consider a lack of a heartbeat as a miss (microsec) - 60ms (6x10ms)


// Timing variables
long unsigned LAST_NOOP_TX_TIME = 0;                      // Timestamp of the most recent transmit
long unsigned LAST_NOOP_RX_TIME = 0;                      // Timestamp of last communication of any type (microsec)
long unsigned LAST_ABORT_MSG_TX = 0;                      // Timestamp of the last abort message that was sent
long unsigned LAST_SENSOR_UPDATE = 0;                     // Timestamp of the last time sensor reading was sent


// Valves
const int NCS1_PIN = 0;
const int NCS2_PIN = 0;
const int NCS3_PIN = 0;
const int NCS5_PIN = 0;
const int NCS6_PIN = 0;
const int LABV1_PIN = 0;
const int GV1_PIN = 0;
const int GV2_PIN = 0;

// ----------------------------------------------------------------


/*
--------------------------------
ETHERNET
--------------------------------
*/

// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];                // Buffer to hold incoming packet,

const unsigned long PRECISION = 5;                        // Precision of float -> string conversion
const size_t BUFFER_SIZE = 1024;                          // *slaps roof* yeah that'll do nicely (buffer for outgoing packet)

// Heartbeat variables
int unsigned HEARTBEAT_RX_COUNT = 0;                      // [DEBUG] The total number of heartbeat signals received
int unsigned HEARTBEAT_TX_COUNT = 0;                      // [DEBUG] The total number of heartbeat signals sent to the master

void tx_data(const char* to_write) {
  udp.beginPacket(REMOTE, PORT);
  udp.write(to_write);
  udp.endPacket();
}

void tx_float(float to_write) {
  char buf[100]; // *slaps roof* yeah that'll do nicely
  dtostrf(to_write, 1, PRECISION, buf);
  udp.beginPacket(REMOTE, PORT);
  udp.write(buf);
  udp.endPacket();
}

void pkt_add_float(EthernetUDP& pkt, float to_write) {
  char buf[100]; // *slaps roof* yeah that'll do nicely
  dtostrf(to_write, 1, PRECISION, buf);
  udp.write(buf);
}

void pkt_add_string(EthernetUDP& pkt, const char* to_write) {
  udp.write(to_write);
}

String rx_until(char stop_character) {
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

  // Apparently the intended behavior of this function is to BLOCK execution until it establishes a connection
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
--------------------------------
CONTROLS
--------------------------------
*/

bool LABV1_IS_OPEN = false;

// Function to get pin number from string
int get_pin(String id) {
  if (id == "NCS1") {
    return NCS1_PIN;
  } else if (id =="NCS2") {
    return NCS2_PIN;
  } else if (id =="NCS3") {
    return NCS3_PIN;
  } else if (id =="NCS5") {
    return NCS5_PIN;
  } else if (id =="NCS6") {
    return NCS6_PIN;
  } else if (id =="LA-BV1") {
    return LABV1_PIN;
  } else if (id =="GV-1") {
    return GV1_PIN;
  } else if (id =="GV-2") {
    return GV2_PIN;
  }

  // Return -1 if no match was found
  return -1;
}



// returns -1 if there was a failure, otherwise returns 0
int update_valve(String identifier, int control_state) {
  int pin = get_pin(identifier);
  if (pin == -1) { return -1; }

  if (control_state == HIGH) {
      digitalWrite(pin, HIGH);  // Open Valve

      if (identifier == "LA-BV1") {
        LABV1_IS_OPEN = true;
      }

      // We can worry more about more advanced ways to validate success later
      return 0;
  } else {
      digitalWrite(pin, LOW);   // Close Valve

      if (identifier == "LA-BV1") {
        if (LABV1_IS_OPEN) {
          digitalWrite(NCS2_PIN, HIGH);
        }
        LABV1_IS_OPEN = false;
      }

      // We can worry more about more advanced ways to validate success later
      return 0;
  } // control state
}

/*
--------------------------------
THERMOCOUPLE DECLARATIONS
--------------------------------
*/

// Thermocouple libraries
// See example https://github.com/adafruit/Adafruit_MCP9600/blob/master/examples/mcp9600_test/mcp9600_test.ino

#include <Adafruit_MCP9600.h>

// Thermocouple I2C addresses
#define TC1_I2C_ADDR (0x60)   // 1100 000x  Corresponding to MCP9600 Address 0 (Vaddr = GND)
#define TC2_I2C_ADDR (0x67)   // 1100 111x  Corresponding to MCP9600 Address 7 (Vaddr = VDD = 3V3)

// Thermocouple mcp identifier
Adafruit_MCP9600 mcp1;
Adafruit_MCP9600 mcp2;

/*
--------------------------------
PRESSURE TRANSDUCER DECLARATIONS
--------------------------------
*/

// teensy pins to read signals
const int PT1_PIN = 23;                    // <-- USER INPUT
const int PT2_PIN = 22;                    // <-- USER INPUT

// analog and digital reading variables setup
int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal


// For the 0-5V digital signal PTs - Honeywell PX2AF1... series
// https://tinyurl.com/y9549dww
//
// parameter: a digital 0 - 1023 reading 
// returns: a reading in psi
//
double convert_PX2AF1XX500PAAAX_PT(int reading) {
  // 0 - 500 psia going into PT
  // 0.5 - 4.5 V comes out from that range
  // 0.33 - 2.97 V after voltage divider on the board
  // 102(.3) - 920(.7) range from the digital reading based off Teensy's 0 - 3.3V digital pin

  // So basically 102.3 - 920.7 range corresponds to 15 - 1000 psi range
  // y = (y2-y1)/(x2-x1) * (x - x1) + y1
  return (500.0 - 0.0) / (920.7 - 102.3) * (reading - 102.3) + 0.0;
}

// For the 4-20mA signal coming out of a 0-1500psi PT
// https://www.mcmaster.com/6017N19/

double convert_6017N19_PT(int reading) {
  // 0 - 1500 psia into PT
  // 4 - 20 mA coming out of PT
  // current goes through 160 Ohm resistor
  // 0.64 - 3.2 V coming off of 160 Ohm resistor
  // 198(.4) - 992 range from digital reading based off Teensy's 0 - 3.3V digital pin

  // So 198(.4) - 992 range corresponds to 0 - 1500 psi range
  // y = (y2-y1)/(x2-x1) * (x - x1) + y1
  return (1500.0 - 0.0) / (992.0 - 198.4) * (reading - 198.4) + 0.0;
}

/*
--------------------------------
LOAD CELL DECLARATIONS
--------------------------------
*/

#include <Adafruit_NAU7802.h>


// The Address of the bus on I2C1
#define LC_BUS_ADDR 0x70
#define LC1_ADDR 0
#define LC2_ADDR 1

// This is the object that talks directly to the LC ADC
Adafruit_NAU7802 nau1;
Adafruit_NAU7802 nau2;

// Lil' functioon that switches between bus outputs
void lc_select(uint8_t i) {
  if (i > 7) return;
  
  // Wire1 corresponds to sending data on I2C1
  Wire1.beginTransmission(LC_BUS_ADDR);
  Wire1.write(1 << i);
  Wire1.endTransmission();  
}

int32_t lc_read(uint8_t i) {
  lc_select(i);

  if (i == LC1_ADDR)
    return nau1.read();
  else if (i == LC2_ADDR)
    return nau2.read();
  else 
    return nau1.read(); //Default to nau1
}

double convert_DLY_103_500kg_LC(int32_t reading) {
  // Capacity of 0 to 500kg weight -> 0 to 500*9.81 N
  // Vref of 3V3
  // Product page says 2mV/V output
  // Manual test - weighing my 174g iPhone 13 it reads a digital reading of 1500 ± 100 (eyballing it)

  // 0 to 174g for my iphone
  // 0 to 1500 digital reading
  // y = (y2-y1)/(x2-x1) * (x-x1) + y1
  
  return (0.174 - 0.0) / (1500.0 - 0.0) * (reading - 0.0) + 0.0;
}



/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  // Initialize serial for debugging
  Serial.begin(BAUD);
  Serial.println("Initialized Serial");

  // Initialize the ethernet connection
  init_comms(MAC_ADDRESS, PORT);

  /*
  -----------------------
  THERMOCOUPLE SET UP
  -----------------------
  */

  // Initialize MCP9600 sensors

  // This stuff is hella finnicky, at least on the test PCB
  // Try pulling out the teensy, flashing it outside the board, unplugging it, remounting, and replugging in 
  if (!mcp1.begin(TC1_I2C_ADDR)) {
    Serial.println("TC1 ADC not found!");
    while (1); delay(10);  // Don't proceed.
  }

  if (!mcp2.begin(TC2_I2C_ADDR)) {
    Serial.println("TC2 ADC not found!");
    while (1); delay(10);  // Don't proceed.
  }

  Serial.println("Found both TC1 and TC2 ADC!");

  // Configure both sensors
  // 18 bit resolution, which is the highest and has up to 300ms conversion time
  mcp1.setADCresolution(MCP9600_ADCRESOLUTION_18);
  // 0.0625C As the resolution (step size) of cold junction temperature - based on MCP9600 datasheet
  mcp1.setAmbientResolution(RES_ZERO_POINT_0625);
  //Type K - Nickel-Chromium and Nickel-Aluminum TCs operating from -200C to 1372C according to Grok
  mcp1.setThermocoupleType(MCP9600_TYPE_K);  
  // Filter coeff ranges from 0 to 15, where 0 is all data being raw and 15 is heavy averaging of all the data (minimal noise) 
  mcp1.setFilterCoefficient(3);
  mcp1.enable(true);

  mcp2.setADCresolution(MCP9600_ADCRESOLUTION_18);
  mcp2.setAmbientResolution(RES_ZERO_POINT_0625);
  mcp2.setThermocoupleType(MCP9600_TYPE_K);
  mcp2.setFilterCoefficient(3);
  mcp2.enable(true);


  /*
  -----------------------
  LOAD CELL SET UP
  -----------------------
  */

  // Wire1 corresponds to I2C1 (The TCs use I2C0)
  Wire1.begin();
  lc_select(LC1_ADDR);
  if (!nau1.begin(&Wire1)) {
    Serial.println("Failed to find NAU7802");
    while (1) delay(10);  // Don't proceed.
  }
  lc_select(LC2_ADDR);
  if (!nau2.begin(&Wire1)) {
    Serial.println("Failed to find NAU7802");
    while (1) delay(10);  // Don't proceed.
  }
  Serial.println("Found both NAU7802 ICs!");
  
  //LC1 SETUP
  
  // Set config params for NAU chip (I have no idea what they should be but these were the default)
  lc_select(LC1_ADDR);
  nau1.setLDO(NAU7802_3V3);
  nau1.setGain(NAU7802_GAIN_128);
  nau1.setRate(NAU7802_RATE_10SPS);
  nau1.setPGACap(true); // Single channel setting - enable use of PGA stabilizer caps (Cfilter) on VIN2

  if (!nau1.calibrate(NAU7802_CALMOD_INTERNAL))
    Serial.println("Failed to Calibrate First NAU7802");
  else Serial.println("Calibrated First NAU7802");

  // Take 10 readings to flush out readings
  for (uint8_t i=0; i<10; i++) {
    while (! nau1.available()) delay(1);
    nau1.read();
  }
  

  //LC2 SETUP

  lc_select(LC2_ADDR);
  nau2.setLDO(NAU7802_3V3);
  nau2.setGain(NAU7802_GAIN_128);
  nau2.setRate(NAU7802_RATE_10SPS);
  nau2.setPGACap(true);

  if (!nau2.calibrate(NAU7802_CALMOD_INTERNAL))
    Serial.println("Failed to Calibrate Second NAU7802");
  else Serial.println("Calibrated Second NAU7802");

  for (uint8_t i=0; i<10; i++) {
    while (! nau2.available()) delay(1);
    nau2.read();
  }
  
  Serial.println("Finished Setup");
} // setup


/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {

  // Listen for packets 
  udp.parsePacket();
  if (udp.available() > 0) {
    // read communication
    String input = rx_until('\n');

    

    // Respond to the heartbeat, which have no specification
    if (input == "NOOP") {
      LAST_NOOP_RX_TIME = micros();
    } else {
      Serial.println(input);
      // Break string into identifier and control state
      int delimiterIndex = input.indexOf(':');
      if (delimiterIndex != -1) {

        String cmd = input.substring(0, delimiterIndex);
        String spec = input.substring(delimiterIndex + 1);
        
        // Valve control command
        if (cmd == "VALVE_SET") {
          int secondDelimiterIndex = spec.indexOf(':');
          String identifier = spec.substring(0, secondDelimiterIndex);
          int control_state = spec.substring(secondDelimiterIndex + 1).toInt();

          int result = update_valve(identifier, control_state);
          if (result != -1) {
            char buffer[64];
            sprintf(buffer, "VALVE_SUCCESS:%s:%d\n", identifier.c_str(), control_state);
            tx_data(buffer);
            Serial.print(buffer);
          } else {
            char buffer[64];
            sprintf(buffer, "VALVE_FAIL:%s:%d\n", identifier.c_str(), control_state);
            tx_data(buffer);
            Serial.print(buffer);
          }
        } // Valve control command

      } // If a delimiter was found for continuing 
    } // If it is not a NOOP

  } // If there is a UDP packet available

  // Send the TX NOOP Heartbeat
  if ((micros() - LAST_NOOP_TX_TIME) > NOOP_TX_INTERVAL) {
    tx_data("NOOP\n");
    LAST_NOOP_TX_TIME = micros();
  }


  // If there have been too many missed hearbeats, enter abort state
  if ((micros() - LAST_NOOP_RX_TIME) > NOOP_RX_TIMEOUT) {
    Serial.printf("Missed Heartbeat RX\n");

    // While system is aborted, print "aborted" until a start command is received
    bool aborted = true;
    while(aborted) {
      // Spit out a packet saying ABORTED once every ABORT_TIME_INTERVAL number of seconds
      if ((micros() - LAST_ABORT_MSG_TX) > ABORTED_MSG_INTERVAL) {
        tx_data("ABORTED\n");
        Serial.println("ABORTED");
        
        LAST_ABORT_MSG_TX = micros();
      } // If an abort message should be sent
      
      // Check for a packet coming in that says START
      udp.parsePacket();
      if (udp.available() > 0) {
        String input = rx_until('\n');

        if (input == "START") {
          // Exit the abort state if you receive a START packet
          aborted = false;
          // MISSED_NOOP_RX_COUNT = 0;
          LAST_NOOP_RX_TIME = micros();
          Serial.println("LEAVING ABORT STATE");
        } // If the command was to start
      } // If there is a packet available

    } // Abort state while loop
  } // If an abort state should trigger

  
  // Sensor readings
  if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
    LAST_SENSOR_UPDATE = micros();                               // update time
    
    float p1_psia = convert_PX2AF1XX500PAAAX_PT(analogRead(PT1_PIN));
    float p2_psig = convert_6017N19_PT(analogRead(PT2_PIN));

    float tc1_degC = mcp1.readThermocouple();
    float tc2_degC = mcp2.readThermocouple();
    
    float lc1_kg = convert_DLY_103_500kg_LC(lc_read(LC1_ADDR));
    float lc2_kg = convert_DLY_103_500kg_LC(lc_read(LC2_ADDR));
    
    // Send data to serial monitor
    udp.beginPacket(REMOTE, PORT);
    pkt_add_string(udp, "t:");
    pkt_add_float(udp, LAST_SENSOR_UPDATE);
    pkt_add_string(udp, ",P1:");
    pkt_add_float(udp, p1_psia);
    pkt_add_string(udp, ",P2:");
    pkt_add_float(udp, p2_psig);

    pkt_add_string(udp, ",TC1:");
    pkt_add_float(udp, tc1_degC);
    pkt_add_string(udp, ",TC2:");
    pkt_add_float(udp, tc2_degC);
    pkt_add_string(udp, ",LC1:");
    pkt_add_float(udp, lc1_kg);
    pkt_add_string(udp, ",LC2:");
    pkt_add_float(udp, lc2_kg);
    pkt_add_string(udp, "\n");
    udp.endPacket();

    // Read PTs
    Serial.print("\nPT1 ADC (psia): "); Serial.print(p1_psia);
    Serial.print("\tPT2 ADC (psig): "); Serial.print(p2_psig);

    // Read TCs
    Serial.print("\tTC1 H (°C): "); Serial.print(tc1_degC);
    Serial.print("\tTC2 H (°C): "); Serial.print(tc2_degC);

    // Read LCs
    Serial.print("\tLC1 ADC (kg): "); Serial.print(lc1_kg);
    Serial.print("\tLC2 ADC (kg): "); Serial.print(lc2_kg);

  } // If sensor readings should be sent

} // loop