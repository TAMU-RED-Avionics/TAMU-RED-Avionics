#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
#include "EGCP.h"

/*
-------------------------------------------------------------------
To test this with your laptop: (mac example)

  ifconfig         (check for an enX number to pop up that isn't there when the cable is unplugged)
  sudo ifconfig enX inet 192.168.1.175 netmask 255.255.255.0 up (replace enX with your etherent interface)
  nc -u -l 8888

-------------------------------------------------------------------
*/

// BAUD rate 
const int BAUD = 115200;
unsigned int PORT = 8888;

// Packet tracking
uint32_t PACKET_ID_COUNTER = 0;

// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
IPAddress REMOTE(192, 168, 1, 175);
IPAddress LOCAL(192, 168, 1, 174);

void tx_egcp_packet(const EGCPPacket& packet) {
  uint8_t buffer[20];
  uint8_t packet_size = packet.encode(buffer, sizeof(buffer));
  udp.beginPacket(REMOTE, PORT);
  udp.write(buffer, packet_size);
  udp.endPacket();
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
  Serial.println("looping");

  //Intended to just be printed to a terminal using something like netcat
  //Make sure you have set up the ethernet connection to be 192.168.1.175 on your laptop
  // ifconfig         (check for an enX number to pop up that isn't there when the cable is unplugged)
  // sudo ifconfig enX inet 192.168.1.175 netmask 255.255.255.0 up
  // nc -u -l 192.168.1.175
  output_string(PORT, "skill issue\n");
}  
  // Send heartbeat packet
  EGCPPacket hrt_pkt(PACKET_ID_COUNTER++, EGCPPacket::PKT_HRT);
  tx_egcp_packet(hrt_pkt);
  
  delay(1000