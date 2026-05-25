/*
====================================================================
  Only use for rag torch testing!
  This is almost the same as the Elysium Teensy, but with some modifications
  loadcell and thermocouple code are NOT in this.
====================================================================
*/

#include <Arduino.h>

/*
-------------------------------------------------------------------
  TIMING VARIABLES
-------------------------------------------------------------------
*/
long unsigned LAST_SENSOR_UPDATE      = 0;
const long unsigned SENSOR_UPDATE_INTERVAL   = 1000;      // µs


long unsigned LAST_COMMUNICATION_TIME = 0;
const long unsigned CONNECTION_TIMEOUT       = 200000;    // µs

long unsigned LAST_HUMAN_UPDATE       = 0;
const long unsigned HUMAN_CONNECTION_TIMEOUT = 300000000; // µs

long unsigned ABORT_TIME_TRACKING     = 0;
const long unsigned ABORTED_TIME_INTERVAL    = 500000;    // µs between "Aborted" prints

const int BAUD = 115200;

// ============================================================
// delete/update pin values when hardware is ready
const int NCS1_PIN = -1;   // <-- USER INPUT
const int NCS2_PIN = -1;   // <-- USER INPUT
const int NCS3_PIN = -1;   // <-- USER INPUT
const int NCS4_PIN = -1;   // <-- USER INPUT
const int NCS5_PIN = -1;   // <-- USER INPUT

const int EABV_PIN = -1;   // <-- USER INPUT
const int PABV_PIN = -1;   // <-- USER INPUT
const int SPARK_PIN = -1;  // <-- USER INPUT

// Spark continuous firing variables
bool is_sparking = false;
const unsigned int dwellTime = 3000; // us
const unsigned int sparkTime = 2000; // us
const unsigned int timeBetweenSparks = 50; // ms
unsigned long lastSparkMillis = 0;
// ============================================================

/*
-------------------------------------------------------------------
  COMMUNICATIONS
-------------------------------------------------------------------
*/
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

unsigned int PORT = 8888;
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];
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
  char buf[100];
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
  IPAddress GATEWAY(192, 168, 1, 1);
  IPAddress SUBNET(255, 255, 255, 0);
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


// Serial input parsing variables
String IDENTIFIER  = "";
int    CONTROL_STATE = 0;

int get_pin(String id) {
  if      (id == "NCS1")  return NCS1_PIN;
  else if (id == "NCS2")  return NCS2_PIN;
  else if (id == "NCS3")  return NCS3_PIN;
  else if (id == "NCS4")  return NCS4_PIN;
  else if (id == "NCS5")  return NCS5_PIN;
  else if (id == "EABV")  return EABV_PIN;
  else if (id == "PABV")  return PABV_PIN;
  else if (id == "SPARK") return SPARK_PIN;
  // h_nop is handled before get_pin() is called; ignore here
  return -1;
}

/*
-------------------------------------------------------------------
  PRESSURE TRANSDUCER SET UP
-------------------------------------------------------------------
*/
const int PT1_PIN = 23;  // <-- USER INPUT
const int PT2_PIN = 22;  // <-- USER INPUT
const int PT3_PIN = 21;  // <-- USER INPUT
const int PT4_PIN = 20;  // <-- USER INPUT
const int PT5_PIN = 17;  // <-- USER INPUT
const int PT6_PIN = 16;  // <-- USER INPUT

int pt1_analog = 0, pt2_analog = 0, pt3_analog = 0;
int pt4_analog = 0, pt5_analog = 0, pt6_analog = 0;

const float pt_slope[]     = {1.22983871, 1.22983871, 1.22983871, 1.22983871, 1.22983871, 1.22983871};
const float pt_intercept[] = {-111.9733871, -105.8241935, -109.5137097, -111.9733871, -108.283871, -113.2032258};

float pressureCalculation(float analog, size_t id) {
  return pt_slope[id - 1] * analog + pt_intercept[id - 1];
}

/*
===================================================================
  SETUP
===================================================================
*/
void setup() {
  init_comms(MAC_ADDRESS, PORT);
  Serial.begin(BAUD);

  auto safe_pinMode = [](int pin, int mode) {
    if (pin >= 0) pinMode(pin, mode);
  };
  auto safe_digitalWrite = [](int pin, int val) {
    if (pin >= 0) digitalWrite(pin, val);
  };

  safe_pinMode(NCS1_PIN,  OUTPUT);
  safe_pinMode(NCS2_PIN,  OUTPUT);
  safe_pinMode(NCS3_PIN,  OUTPUT);
  safe_pinMode(NCS4_PIN,  OUTPUT);
  safe_pinMode(NCS5_PIN,  OUTPUT);
  safe_pinMode(EABV_PIN,  OUTPUT);
  safe_pinMode(PABV_PIN,  OUTPUT);
  safe_pinMode(SPARK_PIN, OUTPUT);

  // Default all valves closed, spark driver idle
  safe_digitalWrite(NCS1_PIN,  LOW);
  safe_digitalWrite(NCS2_PIN,  LOW);
  safe_digitalWrite(NCS3_PIN,  LOW);
  safe_digitalWrite(NCS4_PIN,  LOW);
  safe_digitalWrite(NCS5_PIN,  LOW);
  safe_digitalWrite(EABV_PIN,  LOW);
  safe_digitalWrite(PABV_PIN,  LOW);
  safe_digitalWrite(SPARK_PIN, HIGH); // Safe startup state

  output_string(PORT, "RT: pins initialised\n");

}


void emergency_close_all() {
  // All solenoids / actuators off
  if (NCS1_PIN >= 0) digitalWrite(NCS1_PIN, LOW);
  if (NCS2_PIN >= 0) digitalWrite(NCS2_PIN, LOW);
  if (NCS3_PIN >= 0) digitalWrite(NCS3_PIN, LOW);
  if (NCS4_PIN >= 0) digitalWrite(NCS4_PIN, LOW);
  if (NCS5_PIN >= 0) digitalWrite(NCS5_PIN, LOW);
  if (EABV_PIN >= 0) digitalWrite(EABV_PIN, LOW);
  if (PABV_PIN >= 0) digitalWrite(PABV_PIN, LOW);

  is_sparking = false;
  if (SPARK_PIN >= 0) digitalWrite(SPARK_PIN, HIGH);
}

void loop() {

  udp.parsePacket();
  if (udp.available() > 0) {
    String input = input_until('\n');
    LAST_COMMUNICATION_TIME = micros();

    // nop = heartbeat only, no human action
    if (input == "nop\r") return;
    LAST_HUMAN_UPDATE = micros();

    // h_nop = explicit no-op from a button — update timers, ignore
    if (input == "h_nop:0\r" || input == "h_nop:1\r") return;

    // Parse "ID:STATE"
    int delim = input.indexOf(':');
    if (delim == -1) return;
    IDENTIFIER    = input.substring(0, delim);
    CONTROL_STATE = input.substring(delim + 1).toInt();

    int pin = get_pin(IDENTIFIER);
    if (pin == -1) return;   // unknown or unassigned pin

    // -------------------------------------------------------
    //  VALVE / SPARK COMMAND DISPATCH
    // -------------------------------------------------------
    if (IDENTIFIER == "SPARK") {

      switch (CONTROL_STATE) {

        case 1:
          // Enable continuous spark mode
          is_sparking = true;

          // Ensure safe initial state
          digitalWrite(SPARK_PIN, HIGH);

          break;

        case 0:
          // Disable ignition
          is_sparking = false;

          // Ensure MOSFET OFF
          digitalWrite(SPARK_PIN, HIGH);

          break;
      }

    } else {

      // Standard active-high valves
      switch (CONTROL_STATE) {

        case 0:
          if (pin >= 0) digitalWrite(pin, LOW);
          break;

        case 1:
          if (pin >= 0) digitalWrite(pin, HIGH);
          break;
      }
    }
  }


  if (is_sparking) {
    if ((millis() - lastSparkMillis) >= timeBetweenSparks) {

      lastSparkMillis = millis();

      // -------------------------------------------
      // 1. CHARGE COIL
      // LOW -> MOSFET ON
      // -------------------------------------------
      digitalWrite(SPARK_PIN, LOW);

      delayMicroseconds(dwellTime);

      // -------------------------------------------
      // 2. FIRE SPARK
      // HIGH -> MOSFET OFF
      // Spark generated here
      // -------------------------------------------
      digitalWrite(SPARK_PIN, HIGH);

      delayMicroseconds(sparkTime);
    }
  }

  if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
    LAST_SENSOR_UPDATE = micros();

    pt1_analog = analogRead(PT1_PIN);
    pt2_analog = analogRead(PT2_PIN);
    pt3_analog = analogRead(PT3_PIN);
    pt4_analog = analogRead(PT4_PIN);
    pt5_analog = analogRead(PT5_PIN);
    pt6_analog = analogRead(PT6_PIN);

    output_string(PORT, "t:");
    output_float(PORT, LAST_SENSOR_UPDATE);
    output_string(PORT, ",P1:");
    output_float(PORT, pressureCalculation(pt1_analog, 1));
    output_string(PORT, ",P2:");
    output_float(PORT, pressureCalculation(pt2_analog, 2));
    output_string(PORT, ",P3:");
    output_float(PORT, pressureCalculation(pt3_analog, 3));
    output_string(PORT, ",P4:");
    output_float(PORT, pressureCalculation(pt4_analog, 4));
    output_string(PORT, ",P5:");
    output_float(PORT, pressureCalculation(pt5_analog, 5));
    output_string(PORT, ",P6:");
    output_float(PORT, pressureCalculation(pt6_analog, 6));
    output_string(PORT, ",t_loc:");
    float t_loc = (HUMAN_CONNECTION_TIMEOUT - (LAST_SENSOR_UPDATE - LAST_HUMAN_UPDATE)) / 1000000.0;
    output_float(PORT, t_loc);
    output_string(PORT, "\n");
    delay(10);
  }

  bool comms_lost = (micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT;
  bool human_lost = (micros() - LAST_HUMAN_UPDATE)       > HUMAN_CONNECTION_TIMEOUT;

  if (comms_lost || human_lost) {
    emergency_close_all();

    // Sit in abort loop until "start" is received
    bool aborted = true;
    while (aborted) {
      if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
        ABORT_TIME_TRACKING = micros();
        output_string(PORT, "Aborted\n");
      }

      udp.parsePacket();
      if (udp.available() > 0) {
        String input = input_until('\n');
        output_string(PORT, ("New Input= " + input + '\n').c_str());

        if ((input == "start\r") || (input == "Start\r")) {
          aborted = false;
          LAST_COMMUNICATION_TIME = micros();
          LAST_HUMAN_UPDATE       = micros();
          // Leave all valves closed after recovery — operator must re-sequence
        }
      }
    }
  }
}
