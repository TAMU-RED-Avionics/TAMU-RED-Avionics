#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

/*
-------------------------------------------------------------------
To test this with your laptop:

1. Test with a simple terminal, on my mac this is how I did it

  ifconfig         (check for an enX number to pop up that isn't there when the cable is unplugged)
  sudo ifconfig enX inet 192.168.1.175 netmask 255.255.255.0 up
  nc -u -l 8888

2. Test with the GUI
  cd Elysium_GUI
  python GUI_MAIN.py

  Type "192.168.1.174" in the IP section and "8888" in the Port section
  Connect and look at the graphs
-------------------------------------------------------------------
*/

// Timing variables
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

float CUR_FAKE_ANGLE = 0;      // Radians, used to generate sinusoidal fake data
float CUR_FAKE_VAL = 0;        // The current vake data val used for all sensors


// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT
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
  Serial.print("looping");

  // check for last reading update
  if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
    LAST_SENSOR_UPDATE = micros();                               // update time
        
    CUR_FAKE_ANGLE += PI / 12;
    CUR_FAKE_VAL = sin(CUR_FAKE_ANGLE) + 1;

    Serial.print("\t\tcurrent_angle: ");
    Serial.print(CUR_FAKE_ANGLE);
    Serial.print("\tcurrent_fake_val: ");
    Serial.println(CUR_FAKE_VAL);
    
    // send data to serial monitor
    output_string(PORT, "t:");
    output_float(PORT, LAST_SENSOR_UPDATE);
    output_string(PORT, ",P1:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",P2:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",P3:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",P4:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",P5:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",P6:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",T1:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",L1:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",L2:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",L3:");
    output_float(PORT, CUR_FAKE_VAL);
    output_string(PORT, ",t_loc:");
    float t_loc = (HUMAN_CONNECTION_TIMEOUT - (LAST_SENSOR_UPDATE -LAST_HUMAN_UPDATE)) / 1000000.0;
    output_float(PORT, t_loc);
    output_string(PORT, "\n");
    delay(100);
  }
}