// THIS CODE IS ONLY TO BE USED SPECIFICALLY FOR RAG TORCH TESTING.

#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
#include <PWMServo.h> 

unsigned int PORT = 8888;
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];

EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xD5};
IPAddress REMOTE(192, 168, 1, 174);
IPAddress LOCAL(192, 168, 1, 175);
IPAddress GATEWAY(192, 168, 1, 1);
IPAddress SUBNET(255, 255, 255, 0);

const int SPARK_PIN = 2;
const unsigned int DWELL_TIME    = 3000;   // µs
const unsigned int SPARK_TIME    = 2000;   // µs
const unsigned int BETWEEN_SPARKS = 50;    // ms

enum SparkPhase { SPARK_IDLE, SPARK_DWELL, SPARK_DISCHARGE, SPARK_WAIT };
SparkPhase spark_phase           = SPARK_IDLE;
unsigned long spark_phase_start  = 0;
bool is_sparking                 = false;


const int   EABV_PIN        = 6;    // <-- USER INPUT: whichever pin you desire
const int   EABV_OPEN_DEG   = 0;   // <-- USER INPUT: tune to valve's open position
const int   EABV_CLOSE_DEG  = 90;    // <-- USER INPUT: tune to valve's closed position
PWMServo    eabvServo;

void run_spark_state_machine() {
  if (!is_sparking) return;

  unsigned long now = micros();
  switch (spark_phase) {
    case SPARK_IDLE:
      digitalWrite(SPARK_PIN, HIGH);
      spark_phase_start = now;
      spark_phase = SPARK_DWELL;
      break;

    case SPARK_DWELL:
      if ((now - spark_phase_start) >= DWELL_TIME) {
        digitalWrite(SPARK_PIN, LOW);
        spark_phase_start = now;
        spark_phase = SPARK_DISCHARGE;
      }
      break;

    case SPARK_DISCHARGE:
      if ((now - spark_phase_start) >= SPARK_TIME) {
        spark_phase_start = now;
        spark_phase = SPARK_WAIT;
      }
      break;

    case SPARK_WAIT:
      if ((now - spark_phase_start) >= (BETWEEN_SPARKS * 1000UL)) {
        spark_phase = SPARK_IDLE;
      }
      break;
  }
}

void setup() {
  Ethernet.begin(MAC_ADDRESS, LOCAL, GATEWAY, SUBNET);
  Serial.begin(115200);

  pinMode(SPARK_PIN, OUTPUT);
  digitalWrite(SPARK_PIN, LOW);

  eabvServo.attach(EABV_PIN);
  eabvServo.write(EABV_CLOSE_DEG);  // default closed on boot

  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("ERR: Ethernet board disconnected");
    while (true) { delay(1); }
  }
  if (Ethernet.linkStatus() == LinkOFF) {
    Serial.println("ERR: Ethernet cable disconnected");
  }
  udp.begin(PORT);
  Serial.println("RX Teensy Booted");
}

void loop() {
  while (Ethernet.linkStatus() != LinkON) {
    Serial.println("ERR: Ethernet cable disconnected");
    delay(500);
  }

  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "SPARK:1") {
      is_sparking = true;
      spark_phase = SPARK_IDLE;

    } else if (cmd == "SPARK:0") {
      is_sparking = false;
      spark_phase = SPARK_IDLE;
      digitalWrite(SPARK_PIN, LOW);

    } else if (cmd == "EABV:1") {
      eabvServo.write(EABV_OPEN_DEG);
      // do NOT forward to main Teensy

    } else if (cmd == "EABV:0") {
      eabvServo.write(EABV_CLOSE_DEG);
      // do NOT forward to main Teensy

    } else {
      udp.beginPacket(REMOTE, PORT);
      for (size_t i = 0; i < cmd.length(); i++) udp.write(cmd.charAt(i));
      udp.write('\n');
      udp.write('\0');
      udp.endPacket();
    }
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

  run_spark_state_machine();

}