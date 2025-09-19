#include <Arduino.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

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
  Serial.println("looping");

  //Intended to just be printed to a terminal using something like netcat
  //Make sure you have set up the ethernet connection to be 192.168.1.175 on your laptop
  // ifconfig         (check for an enX number to pop up that isn't there when the cable is unplugged)
  // sudo ifconfig enX inet 192.168.1.175 netmask 255.255.255.0 up
  // nc -u -l 192.168.1.175
  output_string(PORT, "skill issue\n");
}