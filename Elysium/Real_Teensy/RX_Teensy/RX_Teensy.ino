#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

unsigned int PORT = 8888;
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];  // buffer to hold incoming packet,
// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xD5};
IPAddress REMOTE(192, 168, 1, 174);
IPAddress LOCAL(192, 168, 1, 175);
IPAddress GATEWAY(192, 168, 1, 1);
IPAddress SUBNET(255, 255, 255, 0);

void setup() {
  Ethernet.begin(MAC_ADDRESS, LOCAL, GATEWAY, SUBNET);
  Serial.begin(115200);
  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("ERR: Ethernet board disconnected");
    while (true) {
      delay(1); // do nothing, no point running without Ethernet hardware
    }
  }
  if (Ethernet.linkStatus() == LinkOFF) {
    Serial.println("ERR: Ethernet cable disconnected");
  }
  udp.begin(PORT);
}

void loop() {
  while (Ethernet.linkStatus() != LinkON) {
    Serial.println("ERR: Ethernet cable disconnected");
    delay(500);
  }

  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    size_t i = 0;
    udp.beginPacket(REMOTE, PORT);
    while (i < cmd.length()) {
      udp.write(cmd.charAt(i));
      i++;
    }
    udp.write('\n');
    udp.write('\0');
    udp.endPacket();
  }

  while (true) {
    int packetSize = udp.parsePacket();
    if (packetSize) {
      udp.read(packetBuffer, UDP_TX_PACKET_MAX_SIZE);
      packetBuffer[packetSize] = '\0';
      Serial.print(packetBuffer);
    } else {
      break;
    }
  }
  delay(1);
}