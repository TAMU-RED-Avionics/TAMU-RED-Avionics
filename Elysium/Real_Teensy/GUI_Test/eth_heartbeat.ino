#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

/*
-------------------------------------------------------------------
To test this with your laptop:
  cd Elysium_GUI
  python GUI_MAIN.py

  Type "192.168.1.174" in the IP section and "8888" in the Port section
  Connect and look at the graphs
-------------------------------------------------------------------
*/

// Timing variables
const int unsigned SYSTEM_LOOP_INTERVAL = 10;             // milliseconds

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
const int BAUD = 115200;                                  // serial com in bits per second     <-- USER INPUT
unsigned int PORT = 8888;
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];                // buffer to hold incoming packet,

// Heartbeat params
int unsigned HEARTBEAT_RX_COUNT = 0;
int unsigned HEARTBEAT_TX_COUNT = 0;

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
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  Serial.println("Initialized Serial");
  
  init_comms(MAC_ADDRESS, PORT);  // does what it says on the tin
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // Send the TX NOOP Heartbeat
  output_string(PORT, "NOOP\n");
  Serial.printf("NOOP TX - %d\n", ++HEARTBEAT_TX_COUNT);

  // Check for the RX NOOP Heartbeat
  udp.parsePacket();
  if (udp.available() > 0) {
    // read communication
    String input = input_until('\n');

    if (input == "NOOP") {
      Serial.printf("NOOP RX - %d\n", ++HEARTBEAT_RX_COUNT);
      LAST_COMMUNICATION_TIME = micros();
    }
  }

  // If there hasn't been a heartbeat (or other packet) received in a sufficiently recent amount of time, enter abort state
  if ((micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT) {
    
    // While system is aborted, print "aborted" until a start command is received
    bool aborted = true;
    while(aborted) {
      // Spit out a packet saying ABORTED once every ABORT_TIME_INTERVAL number of seconds
      if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
        ABORT_TIME_TRACKING = micros();
        output_string(PORT, "ABORTED\n");
        // Also print it to the terminal
        Serial.println("ABORTED");
      }
      
      // Check for a packet coming in that says START
      udp.parsePacket();
      if (udp.available() > 0) {
        String input = input_until('\n');

        if (input == "START") {
          // Exit the abort state if you receive a START packet
          aborted = false;
          LAST_COMMUNICATION_TIME = micros();
          LAST_HUMAN_UPDATE = micros();
          Serial.println("LEAVING ABORT STATE");
        }
      }

    }
  } // if in abort state

  delay(SYSTEM_LOOP_INTERVAL);
}