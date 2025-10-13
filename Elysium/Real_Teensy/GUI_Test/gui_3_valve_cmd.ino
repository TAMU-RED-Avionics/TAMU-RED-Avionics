#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

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

const long unsigned NOOP_TX_INTERVAL = 10 * 1000;          // Minimum time to wait in between sending NOOP heartbeats (microsec)
const long unsigned NOOP_RX_TIMEOUT =  100 * 1000;         // Timeout to consider a lack of a NOOP packet coming in as a miss (microsec)


// Valves
const int NCS1_PIN = 0;
const int NCS2_PIN = 0;
const int NCS3_PIN = 0;
const int NCS5_PIN = 0;
const int NCS6_PIN = 0;
const int LABV1_PIN = 0;
const int GV1_PIN = 0;
const int GV2_PIN = 0;

// Igniter
const int IGN1_PIN = 0;
const int IGN2_PIN = 0;

// ----------------------------------------------------------------



//                       Global Variables
// ----------------------------------------------------------------

// Timing variables
long unsigned LAST_NOOP_TX_TIME = 0;                      // Timestamp of the most recent transmit
long unsigned LAST_NOOP_RX_TIME = 0;                      // Timestamp of last communication of any type (microsec)
long unsigned LAST_ABORT_MSG_TX = 0;                      // Timestamp of the last abort message that was sent
long unsigned LAST_SENSOR_UPDATE = 0;                     // Timestamp of the last time sensor reading was sent

// Heartbeat variables
int unsigned HEARTBEAT_RX_COUNT = 0;                      // [DEBUG] The total number of heartbeat signals received
int unsigned HEARTBEAT_TX_COUNT = 0;                      // [DEBUG] The total number of heartbeat signals sent to the master

// Fake data variables
double CUR_FAKE_ANGLE = 0;
double CUR_FAKE_VAL = 0;

// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];                // Buffer to hold incoming packet,

const unsigned long PRECISION = 5;                        // Precision of float -> string conversion
const size_t BUFFER_SIZE = 1024;                          // *slaps roof* yeah that'll do nicely (buffer for outgoing packet)

// String IDENTIFIER = "";
// int CONTROL_STATE = 0;

bool LABV1_IS_OPEN = false;


// ----------------------------------------------------------------


// COMMS FUNCTIONS
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


// CONTROL FUNCTIONS

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
        
    CUR_FAKE_ANGLE += PI / 12;
    CUR_FAKE_VAL = sin(CUR_FAKE_ANGLE) + 1;
    
    // Send data to serial monitor
    udp.beginPacket(REMOTE, PORT);
    pkt_add_string(udp, "t:");
    pkt_add_float(udp, LAST_SENSOR_UPDATE);
    pkt_add_string(udp, ",P1:");
    pkt_add_float(udp, CUR_FAKE_VAL);
    pkt_add_string(udp, ",P2:");
    pkt_add_float(udp, CUR_FAKE_VAL);
    pkt_add_string(udp, ",P3:");
    pkt_add_float(udp, CUR_FAKE_VAL);
    pkt_add_string(udp, ",P4:");
    pkt_add_float(udp, CUR_FAKE_VAL);
    pkt_add_string(udp, ",P5:");
    pkt_add_float(udp, CUR_FAKE_VAL);
    pkt_add_string(udp, ",P6:");
    pkt_add_float(udp, CUR_FAKE_VAL);
    pkt_add_string(udp, "\n");
    udp.endPacket();

  } // If sensor readings should be sent

} // loop