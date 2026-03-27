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

IPAddress REMOTE(192, 168, 1, 175);                       // The IP Address of the master computer we are connecting to 
IPAddress LOCAL(192, 168, 1, 174);                        // The IP Address of this microcontroller on the master's network
const int BAUD = 115200;                                  // Serial BAUD rate (bits/second)
unsigned int PORT = 8888;                                 // The port to bind to (assumed to be identical to the GUI running on the master)

const int unsigned SYSTEM_LOOP_INTERVAL = 1;              // The loop delay of the overall system - configures the NOOP TX Rate (millisec)

const long unsigned NOOP_TX_INTERVAL = 10 * 1000;         // Minimum time to wait in between sending heartbeats (microsec) - 10ms
const long unsigned NOOP_RX_TIMEOUT =  60 * 1000;         // Timeout to consider a lack of a heartbeat as a miss (microsec) - 60ms (6x10ms)
const int unsigned MAX_NOOP_RX_MISSES = 3;                // The maximum number of missed heartbeats in order to trigger an abort state

const long unsigned ABORTED_MSG_INTERVAL = 500 * 1000;    // Interval for printing "aborted" when in an abort state (microsec)

// ----------------------------------------------------------------



//                       Global Parameters
// ----------------------------------------------------------------

// Timing variables
long unsigned LAST_NOOP_TX_TIME = 0;                      // Timestamp of the most recent transmit
long unsigned LAST_NOOP_RX_TIME = 0;                      // Timestamp of last communication of any type (microsec)
long unsigned LAST_ABORT_MSG_TX = 0;                      // Timestamp of the last abort message that was sent
int unsigned MISSED_NOOP_RX_COUNT = 0;                    // The current number of missed heartbeat packets     

// Heartbeat params
int unsigned HEARTBEAT_RX_COUNT = 0;                      // [DEBUG] The total number of heartbeat signals received
int unsigned HEARTBEAT_TX_COUNT = 0;                      // [DEBUG] The total number of heartbeat signals sent to the master

// Packet tracking
uint32_t PACKET_ID_COUNTER = 0;

// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};

// ----------------------------------------------------------------

// Send EGCP packet
void tx_egcp_packet(const EGCPPacket& packet) {
  uint8_t buffer[20];
  uint8_t packet_size = packet.encode(buffer, sizeof(buffer));
  
  udp.beginPacket(REMOTE, PORT);
  udp.write(buffer, packet_size);
  udp.endPacket();
}

// Send heartbeat
void tx_heartbeat() {
  EGCPPacket hrt_pkt(PACKET_ID_COUNTER++, EGCPPacket::PKT_HRT);
  tx_egcp_packet(hrt_pkt);
  HEARTBEAT_TX_COUNT++;
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
  // Initialize serial for debugging
  Serial.begin(BAUD);
  Serial.println("Initialized Serial");
  
  // Initialize the ethernet connection
  init_comms(MAC_ADDRESS, PORT);
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  // Send the TX NOOP Heartbeat
  if ((micros() - LAST_NOOP_TX_TIME) > NOOP_TX_INTERVAL) {
    tx_string(PORT, "NOOP\n");
    Serial.printf("NOOP TX - %d\n", ++HEARTBEAT_TX_COUNT);
    LAST_NOOP_TX_TIME = micros();
  }

  // Check for the RX NOOP Heartbeat
  udp.parsePacketHeartbeat
  if ((micros() - LAST_NOOP_TX_TIME) > NOOP_TX_INTERVAL) {
    tx_heartbeat();
    Serial.printf("HRT TX - %d\n", HEARTBEAT_TX_COUNT);
    LAST_NOOP_TX_TIME = micros();
  }

  // Check for incoming packets
  int packet_size = udp.parsePacket();
  if (packet_size > 0) {
    uint8_t buffer[UDP_TX_PACKET_MAX_SIZE];
    int bytes_read = udp.read(buffer, sizeof(buffer));
    
    EGCPPacket rx_pkt;
    if (EGCPPacket::decode(buffer, bytes_read, rx_pkt)) {
      if (rx_pkt.packet_type == EGCPPacket::PKT_HRT) {
        Serial.printf("HRT RX - %d\n", ++HEARTBEAT_RX_COUNT);
        LAST_NOOP_RX_TIME = micros();
        MISSED_NOOP_RX_COUNT = 0;
      }
    }
  }

  // If there hasn't been a received heartbeat in too long
  if ((micros() - LAST_NOOP_RX_TIME) > NOOP_RX_TIMEOUT) {
    LAST_NOOP_RX_TIME = micros();
    Serial.printf("Missed Heartbeat RX - %d\n", ++MISSED_NOOP_RX_COUNT);
  }

  // If there have been too many missed heartbeats, enter abort state
  if (MISSED_NOOP_RX_COUNT >= MAX_NOOP_RX_MISSES) {
    bool aborted = true;
    while(aborted) {
      // Send abort packet (SFE) once every interval
      if ((micros() - LAST_ABORT_MSG_TX) > ABORTED_MSG_INTERVAL) {
        EGCPPacket abort_pkt(PACKET_ID_COUNTER++, EGCPPacket::PKT_SFE);
        tx_egcp_packet(abort_pkt);
        Serial.println("ABORTED");
        LAST_ABORT_MSG_TX = micros();
      }
      
      // Check for START packet (STA)
      int pkt_size = udp.parsePacket();
      if (pkt_size > 0) {
        uint8_t buffer[UDP_TX_PACKET_MAX_SIZE];
        udp.read(buffer, sizeof(buffer));
        
        EGCPPacket start_pkt;
        if (EGCPPacket::decode(buffer, pkt_size, start_pkt)) {
          if (start_pkt.packet_type == EGCPPacket::PKT_STA) {
            aborted = false;
            MISSED_NOOP_RX_COUNT = 0;
            LAST_NOOP_RX_TIME = micros();
            Serial.println("LEAVING ABORT STATE");
          }
        }
      }
    }
  }