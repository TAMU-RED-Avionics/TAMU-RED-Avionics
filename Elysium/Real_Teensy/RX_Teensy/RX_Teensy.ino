// THIS CODE IS ONLY TO BE USED SPECIFICALLY FOR RAG TORCH TESTING.
// UNCOMMENT (AND FIX AS NEEDED) THE SERVO STUFF WHEN YOU ACTUALLY WIRE IT UP

#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
// #include <PWMServo.h>  // uncomment when servo is wired up

unsigned int PORT = 8888;
char packetBuffer[512];

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

// ---- Servo (ox ball valve) config ----
// const int   SERVO_PIN        = 6;    // <-- USER INPUT: whichever PWM-capable pin you wire to
// const int   SERVO_OPEN_DEG   = 90;   // <-- USER INPUT: tune to your valve's open position
// const int   SERVO_CLOSE_DEG  = 0;    // <-- USER INPUT: tune to your valve's closed position
// PWMServo    oxValveServo;

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

  // oxValveServo.attach(SERVO_PIN);
  // oxValveServo.write(SERVO_CLOSE_DEG);  // default closed on boot

  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    Serial.println("ERR: Ethernet board disconnected");
    while (true) { delay(1); }
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
    cmd.trim();

    if (cmd == "SPARK:1") {
      is_sparking = true;
      spark_phase = SPARK_IDLE;

    } else if (cmd == "SPARK:0") {
      is_sparking = false;
      spark_phase = SPARK_IDLE;
      digitalWrite(SPARK_PIN, LOW);

    // } else if (cmd == "SERV:1") {
    //   oxValveServo.write(SERVO_OPEN_DEG);
    //   // do NOT forward to main Teensy — servo is local

    // } else if (cmd == "SERV:0") {
    //   oxValveServo.write(SERVO_CLOSE_DEG);
    //   // do NOT forward to main Teensy — servo is local

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