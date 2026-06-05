/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

#include <Arduino.h>
#include "EGCP.h"  // Elysium Ground Communications Protocol

#define SERIAL_DEBUG 1

#if defined(ARDUINO) && SERIAL_DEBUG
#define DBG_PRINTLN(x) Serial.println(x)
#define DBG_PRINT(x) Serial.print(x)
#else
#define DBG_PRINTLN(x)
#define DBG_PRINT(x)
#endif

// time variables
long unsigned LAST_SENSOR_UPDATE = 0;                     // Timestamp of last sensor reading (microsec)
const long unsigned SENSOR_UPDATE_INTERVAL = 1000;        // sensor update interval (microsec)              <-- USER INPUT

long unsigned LAST_LC_UPDATE = 0;                         // Timestamp of last Load Cell reading (microsec)
const long unsigned LC_UPDATE_INTERVAL = 100000;          // Load Cell update interval (microsec)           <-- USER INPUT

long unsigned LAST_COMMUNICATION_TIME = 0;                // Timestamp of last communication of any type (microsec)
const long unsigned CONNECTION_TIMEOUT = 5000000;         // automated shutdown timeout for complete comms failure (microsec)           <-- USER INPUT

long unsigned LAST_HUMAN_UPDATE = 0;                      // Timestamp of last human communication(microsec)
const long unsigned HUMAN_CONNECTION_TIMEOUT = 300000000; // automated shutdown timeout for human comms failure (microsec)              <-- USER INPUT

long unsigned ABORT_TIME_TRACKING = 0;
const long unsigned ABORTED_TIME_INTERVAL = 500000;       // microsec between printing "aborted" (when aborted)
const long unsigned SHUTDOWN_PURGE_TIME = 2000;           // duration of purge for shutdown, in milliseconds

// BAUD rate 
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT

// PA-BV1 state variable
bool is_PABV1_open = false;

/*
VALVE SETUP
*/

// Valves
const int NCS1_PIN = 7;                          // <-- USER INPUT
const int NCS2_PIN = 8;                          // <-- USER INPUT
const int NCS3_PIN = 11;                         // <-- USER INPUT
const int NCS4_PIN = 0;                          // <-- USER INPUT
const int NCS5_PIN = 0;                          // <-- USER INPUT
const int PA_BV3_PIN = 0;                        // <-- USER INPUT (was NCS6)
const int PA_BV1_PIN = 5;                        // <-- USER INPUT (was LABV1)
const int PA_BV2_PIN = 0;                        // <-- USER INPUT
const int GV1_PIN = 0;                           // <-- USER INPUT
const int GV2_PIN = 0;                           // <-- USER INPUT
const int GIMBAL_ENABLE_PIN = 14;                // <-- USER INPUT

// Igniter
const int IGN1_PIN = 10;                         // <-- USER INPUT
const int IGN2_PIN = 9;                          // <-- USER INPUT

// serial input variables
String IDENTIFIER = "";
int CONTROL_STATE = 0;

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
  } else if (id =="PA-BV3") {
    return PA_BV3_PIN;
  } else if (id =="PA-BV1") {
    return PA_BV1_PIN;
  } else if (id =="PA-BV2") {
    return PA_BV2_PIN;
  } else if (id =="GV1") {
    return GV1_PIN;
  } else if (id =="GV2") {
    return GV2_PIN;
  } else if (id =="IGN-1") {
    return IGN1_PIN;
  } else if (id =="IGN-2") {
    return IGN2_PIN;
  } else if (id =="GIMBAL") {
    return GIMBAL_ENABLE_PIN;
  }

  // Return -1 if no match was found
  return -1;
}

// Function to get pin number from EGCP valve ID
int get_pin_from_valve_id(uint8_t valve_id) {
  switch (valve_id) {
    case EGCPPacket::VALVE_NCS1: return NCS1_PIN;
    case EGCPPacket::VALVE_NCS2: return NCS2_PIN;
    case EGCPPacket::VALVE_NCS3: return NCS3_PIN;
    case EGCPPacket::VALVE_NCS5: return NCS5_PIN;
    case EGCPPacket::VALVE_NCS6: return PA_BV3_PIN;   // PA-BV3 (renamed from NCS6)
    case EGCPPacket::VALVE_LA_BV1: return PA_BV1_PIN; // PA-BV1 (renamed from LA-BV1)
    case EGCPPacket::VALVE_LA_BV2: return PA_BV2_PIN; // PA-BV2 (renamed from LA-BV2)
    case EGCPPacket::VALVE_GV1: return GV1_PIN;
    case EGCPPacket::VALVE_GV2: return GV2_PIN;
    case EGCPPacket::VALVE_IG1: return IGN1_PIN;
    case EGCPPacket::VALVE_IG2: return IGN2_PIN;
    case EGCPPacket::VALVE_GIMBAL: return GIMBAL_ENABLE_PIN;
    default: return -1;
  }
}

// Get valve name from ID (for logging)
const char* get_valve_name(uint8_t valve_id) {
  switch (valve_id) {
    case EGCPPacket::VALVE_NCS1: return "NCS1";
    case EGCPPacket::VALVE_NCS2: return "NCS2";
    case EGCPPacket::VALVE_NCS3: return "NCS3";
    case EGCPPacket::VALVE_NCS4: return "NCS4";
    case EGCPPacket::VALVE_NCS5: return "NCS5";
    case EGCPPacket::VALVE_NCS6: return "PA-BV3";   // renamed
    case EGCPPacket::VALVE_LA_BV1: return "PA-BV1"; // renamed
    case EGCPPacket::VALVE_LA_BV2: return "PA-BV2"; // renamed
    case EGCPPacket::VALVE_GV1: return "GV1";
    case EGCPPacket::VALVE_GV2: return "GV2";
    case EGCPPacket::VALVE_IG1: return "IGN-1";
    case EGCPPacket::VALVE_IG2: return "IGN-2";
    case EGCPPacket::VALVE_GIMBAL: return "GIMBAL"; 
    default: return "UNKNOWN";
  }
}

#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>

unsigned int PORT = 8888;
char packetBuffer[UDP_TX_PACKET_MAX_SIZE];  // buffer to hold incoming packet,
// An EthernetUDP instance to let us send and receive packets over UDP
EthernetUDP udp;
byte MAC_ADDRESS[] = {0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED};
IPAddress REMOTE(192, 168, 1, 175);
IPAddress LOCAL(192, 168, 1, 174);
IPAddress ACTIVE_REMOTE(192, 168, 1, 175);
unsigned int ACTIVE_REMOTE_PORT = 8888;
bool active_remote_valid = false;
const bool ENABLE_SETUP_UDP_TESTS = false;

// EGCP packet tracking
uint32_t tx_packet_id = 0;                  // Transmit packet ID counter
uint8_t egcp_binary_buffer[256];            // Buffer for assembling binary packets
uint16_t egcp_buffer_pos = 0;               // Current position in binary buffer
uint32_t heartbeat_rx_count = 0;
unsigned long last_loop_alive_log_ms = 0;

const char* packet_type_name(uint8_t packet_type) {
  switch (packet_type) {
    case EGCPPacket::PKT_ACK: return "ACK";
    case EGCPPacket::PKT_NCK: return "NCK";
    case EGCPPacket::PKT_HRT: return "HRT";
    case EGCPPacket::PKT_VSO: return "VSO";
    case EGCPPacket::PKT_VSC: return "VSC";
    case EGCPPacket::PKT_GVS: return "GVS";
    case EGCPPacket::PKT_BGP: return "BGP";
    case EGCPPacket::PKT_HGP: return "HGP";
    case EGCPPacket::PKT_SFE: return "SFE";
    case EGCPPacket::PKT_ADC: return "ADC";
    case EGCPPacket::PKT_STA: return "STA";
    default: return "UNK";
  }
}

void pack_float_big_endian(float value, uint8_t* out) {
  uint8_t raw[4];
  memcpy(raw, &value, 4);
  out[0] = raw[3];
  out[1] = raw[2];
  out[2] = raw[1];
  out[3] = raw[0];
}

// Helper to get next TX packet ID (24-bit wraparound)
uint32_t getNextTxId() {
    uint32_t id = tx_packet_id;
    tx_packet_id = (tx_packet_id + 1) & 0xFFFFFF;
    return id;
}

// Send an EGCP binary packet
void sendEGCPPacket(const EGCPPacket& pkt) {
    uint8_t buffer[20];
    uint8_t size = pkt.encode(buffer, sizeof(buffer));
    if (size > 0) {
    IPAddress target_ip = active_remote_valid ? ACTIVE_REMOTE : REMOTE;
    unsigned int target_port = active_remote_valid ? ACTIVE_REMOTE_PORT : PORT;
    udp.beginPacket(target_ip, target_port);
        udp.write(buffer, size);
        udp.endPacket();
    }
}

// Send ACK for received packet
void sendACK(uint32_t packet_id_to_ack) {
    // ACK body is 3 bytes: the packet ID being acknowledged (take low 3 bytes)
    uint8_t body[3] = {
        (uint8_t)((packet_id_to_ack >> 16) & 0xFF),
        (uint8_t)((packet_id_to_ack >> 8) & 0xFF),
        (uint8_t)(packet_id_to_ack & 0xFF)
    };
    EGCPPacket ack(getNextTxId(), EGCPPacket::PKT_ACK, body, 3);
    sendEGCPPacket(ack);
}

void output_string(unsigned int port, const char *to_write) {
  IPAddress target_ip = active_remote_valid ? ACTIVE_REMOTE : REMOTE;
  unsigned int target_port = active_remote_valid ? ACTIVE_REMOTE_PORT : port;
  udp.beginPacket(target_ip, target_port);
  udp.write((const uint8_t*)to_write, strlen(to_write));
  udp.endPacket();
}

void output_float(unsigned int port, float to_write) {
  char buf[100]; // *slaps roof* yeah that'll do nicely
  constexpr unsigned long PRECISION = 5;
  dtostrf(to_write, 1, PRECISION, buf);
  udp.beginPacket(REMOTE, port);
  udp.write((const uint8_t*)buf, strlen(buf));
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
  Ethernet.begin(mac, LOCAL, GATEWAY, SUBNET);
  DBG_PRINTLN("[E2] Ethernet.begin complete");
  if (Ethernet.hardwareStatus() == EthernetNoHardware) {
    DBG_PRINTLN("ERR: No Ethernet board detected");
    return false;
  } else if (Ethernet.linkStatus() == LinkOFF) {
    DBG_PRINTLN("ERR: Ethernet cable disconnected");
    return false;
  }
  udp.begin(port);
  DBG_PRINT("[E2] UDP listening on port ");
  DBG_PRINTLN(port);
  return true;
}

/*
LOAD CELL SET UP
----------------
*/

// import library
#include "HX711.h"

// define data and clock pins for each loadcell
const int LC1_D_OUT_PIN = 28;            // <-- USER INPUT
const int LC1_CLK_PIN = 29;              // <-- USER INPUT
const int LC2_D_OUT_PIN2 = 26;           // <-- USER INPUT
const int LC2_CLK_PIN2 = 27;             // <-- USER INPUT
const int LC3_D_OUT_PIN3 = 24;           // <-- USER INPUT
const int LC3_CLK_PIN3 = 25;             // <-- USER INPUT

// measurement set up
float weight1 = 0;
float weight2 = 0;
float weight3 = 0;
HX711 scale, scale2, scale3;



/*
THERMOCOUPLE SET UP
----------------
*/

// Thermocouple libraries
#include <Wire.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_I2CRegister.h>
#include <Adafruit_MCP9600.h>

// Thermocouple I2C addresses
#define I2C_ADDRESS1 (0x67)
//#define I2C_ADDRESS2 (0x66)

// Thermocouple mcp identifier
// Adafruit_MCP9600 mcp;
//Adafruit_MCP9600 mcp2;


/*
PRESSURE TRANSDUCER SET UP
--------------------------------
*/

// teensy pins to read signals
const int PT1_PIN = 23;                    // <-- USER INPUT
const int PT2_PIN = 22;                    // <-- USER INPUT
const int PT3_PIN = 21;                    // <-- USER INPUT
const int PT4_PIN = 20;                    // <-- USER INPUT
const int PT5_PIN = 17;                    // <-- USER INPUT
const int PT6_PIN = 16;                    // <-- USER INPUT
 

// analog and digital reading variables setup
int pt1_analog = 0;                        // analog reading from PT output signal
int pt2_analog = 0;                        // analog reading from PT output signal
int pt3_analog = 0;                        // analog reading from PT output signal
int pt4_analog = 0;                        // analog reading from PT output signal
int pt5_analog = 0;                        // analog reading from PT output signal
int pt6_analog = 0;                        // analog reading from PT output signal

// Calibration constants
const float pt_slope[] = {1.22983871, 1.22983871, 1.22983871, 1.22983871, 1.22983871, 1.22983871};
const float pt_intercept[] = {-111.9733871, -105.8241935, -109.5137097, -111.9733871, -108.283871, -113.2032258};

// Calibration constants for pure analog readings
//const float pt_slope[] = {1, 1, 1, 1, 1, 1};
//const float pt_intercept[] = {0, 0, 0, 0, 0, 0};

// Function to calculate pressure
float pressureCalculation(float analog, size_t id) {
    // Calculate pressure based on analog input
    return pt_slope[id-1] * analog + pt_intercept[id-1];
}

/*
ACCELEROMETER SET UP
----------------
*/

// import libraries
#include "IMU.h"
#include "LSM6DSL.h"
#include "LIS3MDL.h"

// measurement variable setup
byte buff[6];
int accRaw[3];
float accx, accy, accz;
const float accoffset = 4180;

/*
-------------------------------------------------------------------
SETUP LOOP
-------------------------------------------------------------------
*/
void setup() {
#if defined(ARDUINO)
  Serial.begin(BAUD);           // initializes serial communication at set baud rate
  delay(50);
#endif
  DBG_PRINTLN("[E2] Booting E2_Teensy firmware");
  DBG_PRINT("[E2] LOCAL IP: ");
  DBG_PRINT(LOCAL[0]); DBG_PRINT('.'); DBG_PRINT(LOCAL[1]); DBG_PRINT('.'); DBG_PRINT(LOCAL[2]); DBG_PRINT('.'); DBG_PRINTLN(LOCAL[3]);
  DBG_PRINT("[E2] REMOTE IP: ");
  DBG_PRINT(REMOTE[0]); DBG_PRINT('.'); DBG_PRINT(REMOTE[1]); DBG_PRINT('.'); DBG_PRINT(REMOTE[2]); DBG_PRINT('.'); DBG_PRINTLN(REMOTE[3]);
  DBG_PRINT("[E2] PORT: ");
  DBG_PRINTLN(PORT);
  DBG_PRINTLN("[E2] Dynamic peer mode: enabled");

  init_comms(MAC_ADDRESS, PORT);  // does what it says on the tin
  LAST_COMMUNICATION_TIME = micros();
  LAST_HUMAN_UPDATE = micros();
#if defined(ARDUINO)
  Wire.begin();
#endif
  DBG_PRINTLN("[E2] Stage: Wire initialized");

  /*
  VALVE SET UP
  -----------------------
  */
  if (ENABLE_SETUP_UDP_TESTS) {
    output_string(PORT, "test1");
  }
  // Serial.println("test1");

  pinMode(NCS1_PIN, OUTPUT); 
  pinMode(NCS2_PIN, OUTPUT); 
  pinMode(NCS3_PIN, OUTPUT); 
  pinMode(NCS4_PIN, OUTPUT); 
  pinMode(NCS5_PIN, OUTPUT); 
  pinMode(PA_BV3_PIN, OUTPUT);
  pinMode(PA_BV1_PIN, OUTPUT);
  pinMode(PA_BV2_PIN, OUTPUT);
  pinMode(GV1_PIN, OUTPUT);
  pinMode(GV2_PIN, OUTPUT);
  pinMode(IGN1_PIN, OUTPUT);
  pinMode(IGN2_PIN, OUTPUT);
  pinMode(GIMBAL_ENABLE_PIN, OUTPUT);
  DBG_PRINTLN("[E2] Stage: Valve/igniter pins initialized");
  DBG_PRINTLN("[E2] Stage: Before setup UDP test 2");
  

  // Serial.println("test2_Pins");
  if (ENABLE_SETUP_UDP_TESTS) {
    output_string(PORT, "test2_Pins");
  }
  DBG_PRINTLN("[E2] Stage: After setup UDP test 2");

  /*
  THERMOCOUPLE SET UP
  -----------------------
  */
/*
  // Initialize MCP9600 sensors
  mcp.begin(I2C_ADDRESS1);
  //mcp2.begin(I2C_ADDRESS2);

  // Configure both sensors
  mcp.setADCresolution(MCP9600_ADCRESOLUTION_18);
  mcp.setThermocoupleType(MCP9600_TYPE_K);
  mcp.setFilterCoefficient(3);
  mcp.enable(true);

  //mcp2.setADCresolution(MCP9600_ADCRESOLUTION_18);
  //mcp2.setThermocoupleType(MCP9600_TYPE_K);
  //mcp2.setFilterCoefficient(3);
  //mcp2.enable(true);

  // Serial.println("test3_TC");
  output_string(PORT, "test3_TC");
*/
  /*
  LOAD CELL SET UP
  -----------------------
  */

  DBG_PRINTLN("[E2] Stage: Starting load cell init");
  // load cell setup
  scale.begin(LC1_D_OUT_PIN, LC1_CLK_PIN);
  scale2.begin(LC2_D_OUT_PIN2, LC2_CLK_PIN2);
  scale3.begin(LC3_D_OUT_PIN3, LC3_CLK_PIN3);
  DBG_PRINTLN("[E2] Stage: HX711 begin complete");

  // Scale config
  scale.set_scale(-3980.f);  // Set the scale factor for conversion to pounds
  scale2.set_scale(-3880.f); // Set the scale factor for conversion to pounds
  scale3.set_scale(-3780.f); // Set the scale factor for conversion to pounds

  // Avoid setup stalls: do readiness checks only in setup.
  // Tare/get_units can block on some disconnected HX711 boards.
  DBG_PRINTLN("[E2] Stage: LC1 readiness check");
  if (scale.wait_ready_timeout(500)) {
    DBG_PRINTLN("[E2] LC1 ready");
  } else {
    DBG_PRINTLN("[E2] WARN: LC1 not ready during setup");
  }

  DBG_PRINTLN("[E2] Stage: LC2 readiness check");
  if (scale2.wait_ready_timeout(500)) {
    DBG_PRINTLN("[E2] LC2 ready");
  } else {
    DBG_PRINTLN("[E2] WARN: LC2 not ready during setup");
  }

  DBG_PRINTLN("[E2] Stage: LC3 readiness check");
  if (scale3.wait_ready_timeout(500)) {
    DBG_PRINTLN("[E2] LC3 ready");
  } else {
    DBG_PRINTLN("[E2] WARN: LC3 not ready during setup");
  }

  DBG_PRINTLN("[E2] Stage: Skipping load-cell tare in setup to avoid blocking");
  
  // Serial.println("test4_LC");
  if (ENABLE_SETUP_UDP_TESTS) {
    output_string(PORT, "test4_LC");
  }
  DBG_PRINTLN("[E2] Setup complete");
  DBG_PRINTLN("[E2] Entering main loop");
  /*
  ACCELEROMETER SET UP
  -----------------------
  */

  // detect and enable IMU
  // detectIMU();
  // enableIMU();
}

// Shutdown procedure - triggered by timeout or emergency abort
void trigger_shutdown(const char* reason) {
  DBG_PRINT("[E2] trigger_shutdown reason=");
  DBG_PRINTLN(reason ? reason : "UNKNOWN");

  // Open NCS2 (Vent)
  digitalWrite(NCS2_PIN, HIGH);

  // Close all other valves
  digitalWrite(NCS1_PIN, LOW);
  digitalWrite(NCS3_PIN, LOW);
  digitalWrite(NCS4_PIN, LOW);
  digitalWrite(NCS5_PIN, LOW);
  digitalWrite(PA_BV3_PIN, LOW);
  digitalWrite(PA_BV1_PIN, LOW);
  digitalWrite(PA_BV2_PIN, LOW);
  digitalWrite(GV1_PIN, LOW);
  digitalWrite(GV2_PIN, LOW);
  digitalWrite(GIMBAL_ENABLE_PIN, LOW);

  // Unpower igniters
  digitalWrite(IGN1_PIN, LOW);
  digitalWrite(IGN2_PIN, LOW);

  // If PA-BV1 is open, system purges with nitrogen
  if (is_PABV1_open) {
    // Open NCS4 for 3 seconds
    digitalWrite(NCS4_PIN, HIGH);
    delay(SHUTDOWN_PURGE_TIME);
    digitalWrite(NCS4_PIN, LOW);
    is_PABV1_open = false; // Reset state since we shut it down
  }

  // Send emergency abort packet to GUI
  EGCPPacket abort_pkt(getNextTxId(), EGCPPacket::PKT_SFE);
  sendEGCPPacket(abort_pkt);

  // While system is aborted, wait for restart command
  bool aborted = true;
  while(aborted) {
    if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
      ABORT_TIME_TRACKING = micros();
      DBG_PRINTLN("[E2] Waiting for handshake packet");
      // Send abort status ping (using SFE to keep clients aware we are still aborted)
      EGCPPacket alive_pkt(getNextTxId(), EGCPPacket::PKT_SFE);
      sendEGCPPacket(alive_pkt);
    }

    int packet_size = udp.parsePacket();
    if (packet_size > 0) {
      // Read bytes into buffer safely
      int bytes_read = 0;
      while (udp.available() > 0 && bytes_read < (int)sizeof(egcp_binary_buffer) - egcp_buffer_pos) {
        egcp_binary_buffer[egcp_buffer_pos + bytes_read] = udp.read();
        bytes_read++;
      }
      egcp_buffer_pos += bytes_read;

      // Process complete packets from buffer
      while (egcp_buffer_pos >= 4) {
        // Peek at packet length from header (low 4 bits)
        uint8_t packet_length = egcp_binary_buffer[3] & 0xF;
        uint16_t total_packet_size = 4 + packet_length;

        if (egcp_buffer_pos < total_packet_size) {
          break; // Wait for complete packet
        }

        // Decode packet
        EGCPPacket rxPacket;
        if (EGCPPacket::decode(egcp_binary_buffer, total_packet_size, rxPacket)) {
          if (rxPacket.packet_type == EGCPPacket::PKT_STA) {
            // START packet received - exit abort state
            DBG_PRINTLN("[E2] STA received while aborted, exiting shutdown state");
            aborted = false;
            LAST_COMMUNICATION_TIME = micros();
            LAST_HUMAN_UPDATE = micros();
            digitalWrite(NCS2_PIN, LOW);
            sendACK(rxPacket.packet_id);
            
            // Clear buffer
            egcp_buffer_pos = 0;
            break; // Exit buffer processing
          } else {
            // We can ACK other things like HRT if we want, but typically in SFE we ignore commands.
            // For now, only STA pulls us out. Since GUI knows we're SFE, it shouldn't expect ACKs for other commands except maybe HRT.
          }
        }

        if (!aborted) break;

        // Remove processed packet from buffer
        memmove(egcp_binary_buffer, egcp_binary_buffer + total_packet_size, 
                egcp_buffer_pos - total_packet_size);
        egcp_buffer_pos -= total_packet_size;
      }
    }
  }
}

/*
-------------------------------------------------------------------
LOOP
-------------------------------------------------------------------
*/
void loop() {
  unsigned long now_ms = millis();
  if (now_ms - last_loop_alive_log_ms >= 1000) {
    last_loop_alive_log_ms = now_ms;
    DBG_PRINT("[E2] Loop alive; peer=");
    if (active_remote_valid) {
      DBG_PRINT(ACTIVE_REMOTE[0]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[1]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[2]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[3]);
      DBG_PRINT(":");
      DBG_PRINT(ACTIVE_REMOTE_PORT);
      DBG_PRINTLN("");
    } else {
      DBG_PRINTLN("none");
    }
  }

  // Read incoming packets
  int packet_size = udp.parsePacket();
  if (packet_size > 0) {
    ACTIVE_REMOTE = udp.remoteIP();
    ACTIVE_REMOTE_PORT = udp.remotePort();
    active_remote_valid = true;

    DBG_PRINT("[E2] UDP packet from ");
    DBG_PRINT(ACTIVE_REMOTE[0]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[1]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[2]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[3]);
    DBG_PRINT(":");
    DBG_PRINT(ACTIVE_REMOTE_PORT);
    DBG_PRINT(" bytes=");
    DBG_PRINTLN(packet_size);

    // Read bytes into buffer
    int bytes_read = 0;
    while (udp.available() > 0 && bytes_read < (int)sizeof(egcp_binary_buffer) - egcp_buffer_pos) {
      egcp_binary_buffer[egcp_buffer_pos + bytes_read] = udp.read();
      bytes_read++;
    }
    egcp_buffer_pos += bytes_read;
    LAST_COMMUNICATION_TIME = micros();

    // Process complete packets from buffer
    while (egcp_buffer_pos >= 4) {
      // Peek at packet length from header (low 4 bits)
      uint8_t packet_length = egcp_binary_buffer[3] & 0xF;
      uint16_t total_packet_size = 4 + packet_length;

      if (egcp_buffer_pos < total_packet_size) {
        break; // Wait for complete packet
      }

      // Decode packet
      EGCPPacket rxPacket;
      if (EGCPPacket::decode(egcp_binary_buffer, total_packet_size, rxPacket)) {
        DBG_PRINT("[E2] RX ");
        DBG_PRINT(packet_type_name(rxPacket.packet_type));
        DBG_PRINT(" id=");
        DBG_PRINT(rxPacket.packet_id);
        DBG_PRINT(" len=");
        DBG_PRINTLN(rxPacket.body_length);
        
        // Handle different packet types
        if (rxPacket.packet_type == EGCPPacket::PKT_STA) {
          // Connection START handshake
          DBG_PRINTLN("[E2] Handshake STA received -> sending ACK");
          sendACK(rxPacket.packet_id);
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_HRT) {
          // Heartbeat - just send ACK back
          heartbeat_rx_count++;
          if (heartbeat_rx_count == 1 || heartbeat_rx_count % 10 == 0) {
            DBG_PRINT("[E2] Heartbeat RX count=");
            DBG_PRINTLN(heartbeat_rx_count);
          }
          sendACK(rxPacket.packet_id);
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_VSO) {
          // Valve open command
          if (rxPacket.body_length >= 1) {
            uint8_t valve_id = rxPacket.body[0];
            int pin = get_pin_from_valve_id(valve_id);
            if (pin >= 0) {
              digitalWrite(pin, HIGH);  // Open valve
              DBG_PRINT("[E2] VSO valve=");
              DBG_PRINT(get_valve_name(valve_id));
              DBG_PRINT(" pin=");
              DBG_PRINTLN(pin);
              
              // Special handling for PA-BV1
              if (valve_id == EGCPPacket::VALVE_LA_BV1) {
                is_PABV1_open = true;
              }
              
              LAST_HUMAN_UPDATE = micros();
            } else {
              DBG_PRINT("[E2] VSO unknown valve id=");
              DBG_PRINTLN(valve_id);
            }
            sendACK(rxPacket.packet_id);
          }
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_VSC) {
          // Valve close command
          if (rxPacket.body_length >= 1) {
            uint8_t valve_id = rxPacket.body[0];
            int pin = get_pin_from_valve_id(valve_id);
            if (pin >= 0) {
              digitalWrite(pin, LOW);  // Close valve
              DBG_PRINT("[E2] VSC valve=");
              DBG_PRINT(get_valve_name(valve_id));
              DBG_PRINT(" pin=");
              DBG_PRINTLN(pin);
              
              // Special handling for PA-BV1
              if (valve_id == EGCPPacket::VALVE_LA_BV1) {
                if (is_PABV1_open) {
                  digitalWrite(NCS2_PIN, HIGH);  // Vent to NCS2
                }
                is_PABV1_open = false;
              }
              
              LAST_HUMAN_UPDATE = micros();
            } else {
              DBG_PRINT("[E2] VSC unknown valve id=");
              DBG_PRINTLN(valve_id);
            }
            sendACK(rxPacket.packet_id);
          }
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_SFE) {
          // Emergency abort / safe mode
          DBG_PRINTLN("[E2] SFE received from GUI");
          sendACK(rxPacket.packet_id);
          trigger_shutdown("RX_SFE");
        }
      }

      // Remove processed packet from buffer
      memmove(egcp_binary_buffer, egcp_binary_buffer + total_packet_size, 
              egcp_buffer_pos - total_packet_size);
      egcp_buffer_pos -= total_packet_size;
    }
  }

  // Sensor reading and transmission
  if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
    LAST_SENSOR_UPDATE = micros();

    // Read pressure data
    pt1_analog = analogRead(PT1_PIN);
    pt2_analog = analogRead(PT2_PIN);
    pt3_analog = analogRead(PT3_PIN);
    pt4_analog = analogRead(PT4_PIN);
    pt5_analog = analogRead(PT5_PIN);
    pt6_analog = analogRead(PT6_PIN);

    // Measure force from load cells (slower update rate)
    if ((LAST_SENSOR_UPDATE - LAST_LC_UPDATE) > LC_UPDATE_INTERVAL) {
      LAST_LC_UPDATE = LAST_SENSOR_UPDATE;
      if (scale.wait_ready_timeout(20)) {
        weight1 = scale.get_units(1);
      }
      if (scale2.wait_ready_timeout(20)) {
        weight2 = scale2.get_units(1);
      }
      if (scale3.wait_ready_timeout(20)) {
        weight3 = scale3.get_units(1);
      }
    }

    // Measure temperature from thermocouple
    float t1 = 1; // mcp.readThermocouple();

    // Send each sensor as individual ADC binary packet
    // Format: 1 byte sensor ID + 4 bytes IEEE 754 float
    
    // Pressure sensors (P1-P6)
    float p_values[] = {
      pressureCalculation(pt1_analog, 1),
      pressureCalculation(pt2_analog, 2),
      pressureCalculation(pt3_analog, 3),
      pressureCalculation(pt4_analog, 4),
      pressureCalculation(pt5_analog, 5),
      pressureCalculation(pt6_analog, 6)
    };
    uint8_t p_ids[] = {
      EGCPPacket::SENSOR_P1,
      EGCPPacket::SENSOR_P2,
      EGCPPacket::SENSOR_P3,
      EGCPPacket::SENSOR_P4,
      EGCPPacket::SENSOR_P5,
      EGCPPacket::SENSOR_P6
    };

    for (int i = 0; i < 6; i++) {
      uint8_t body[5];
      body[0] = p_ids[i];
      pack_float_big_endian(p_values[i], &body[1]);
      EGCPPacket adc(getNextTxId(), EGCPPacket::PKT_ADC, body, 5);
      sendEGCPPacket(adc);
    }

    // Temperature (T1)
    {
      uint8_t body[5];
      body[0] = EGCPPacket::SENSOR_T1;
      pack_float_big_endian(t1, &body[1]);
      EGCPPacket adc(getNextTxId(), EGCPPacket::PKT_ADC, body, 5);
      sendEGCPPacket(adc);
    }

    // Load cells (L1-L3)
    float l_values[] = {weight1, weight2, weight3};
    uint8_t l_ids[] = {
      EGCPPacket::SENSOR_L1,
      EGCPPacket::SENSOR_L2,
      EGCPPacket::SENSOR_L3
    };

    for (int i = 0; i < 3; i++) {
      uint8_t body[5];
      body[0] = l_ids[i];
      pack_float_big_endian(l_values[i], &body[1]);
      EGCPPacket adc(getNextTxId(), EGCPPacket::PKT_ADC, body, 5);
      sendEGCPPacket(adc);
    }

    delay(10);
  }

  // Lost communication shutdown
  if ((micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT) {
    trigger_shutdown("CONNECTION_TIMEOUT");
  }

  if ((micros() - LAST_HUMAN_UPDATE) > HUMAN_CONNECTION_TIMEOUT) {
    trigger_shutdown("HUMAN_CONNECTION_TIMEOUT");
  }
}