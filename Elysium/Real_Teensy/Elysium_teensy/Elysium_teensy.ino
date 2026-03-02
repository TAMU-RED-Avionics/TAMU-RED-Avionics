/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

#include <Arduino.h>
#include "EGCP.h"  // Elysium Ground Communications Protocol

// time variables
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
const int BAUD = 115200;                   // serial com in bits per second     <-- USER INPUT

// LABV 1 state variable
bool is_LABV1_open = false;

/*
VALVE SETUP
*/

// Valves
const int NCS1_PIN = 7;           // <-- USER INPUT
const int NCS2_PIN = 8;           // <-- USER INPUT
const int NCS4_PIN = 11;           // <-- USER INPUT
const int LABV1_PIN = 5;          // <-- USER INPUT
const int LABV2_PIN = 6;          // <-- USER INPUT

// Igniter
const int IGN1_PIN = 10;          // <-- USER INPUT
const int IGN2_PIN = 9;          // <-- USER INPUT

// serial input variables
String IDENTIFIER = "";
int CONTROL_STATE = 0;

// Function to get pin number from string
int get_pin(String id) {
  if (id == "NCS1") {
    return NCS1_PIN;
  } else if (id =="NCS2") {
    return NCS2_PIN;
  } else if (id =="NCS4") {
    return NCS4_PIN;
  } else if (id =="LA-BV1") {
    return LABV1_PIN;
  } else if (id =="LA-BV2") {
    return LABV2_PIN;
  } else if (id =="IG1") {
    return IGN1_PIN;
  } else if (id =="IG2") {
    return IGN2_PIN;
  }

  // Return -1 if no match was found
  return -1;
}

// Function to get pin number from EGCP valve ID
int get_pin_from_valve_id(uint8_t valve_id) {
  switch (valve_id) {
    case EGCPPacket::VALVE_NCS1: return NCS1_PIN;
    case EGCPPacket::VALVE_NCS2: return NCS2_PIN;
    case EGCPPacket::VALVE_NCS3: return NCS4_PIN;  // Note: NCS3 maps to NCS4_PIN
    case EGCPPacket::VALVE_NCS4: return NCS4_PIN;
    case EGCPPacket::VALVE_NCS5: return NCS4_PIN;  // Note: NCS5 maps to NCS4_PIN (pin doesn't exist)
    case EGCPPacket::VALVE_NCS6: return NCS4_PIN;  // Note: NCS6 maps to NCS4_PIN (pin doesn't exist)
    case EGCPPacket::VALVE_LA_BV1: return LABV1_PIN;
    case EGCPPacket::VALVE_LA_BV2: return LABV2_PIN;
    case EGCPPacket::VALVE_IG1: return IGN1_PIN;
    case EGCPPacket::VALVE_IG2: return IGN2_PIN;
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
    case EGCPPacket::VALVE_NCS6: return "NCS6";
    case EGCPPacket::VALVE_LA_BV1: return "LA-BV1";
    case EGCPPacket::VALVE_LA_BV2: return "LA-BV2";
    case EGCPPacket::VALVE_IG1: return "IG1";
    case EGCPPacket::VALVE_IG2: return "IG2";
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

// EGCP packet tracking
uint32_t tx_packet_id = 0;                  // Transmit packet ID counter
uint8_t egcp_binary_buffer[256];            // Buffer for assembling binary packets
uint16_t egcp_buffer_pos = 0;               // Current position in binary buffer

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
        udp.beginPacket(REMOTE, PORT);
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
Adafruit_MCP9600 mcp;
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
  // Serial.begin(BAUD);           // initializes serial communication at set baud rate
  init_comms(MAC_ADDRESS, PORT);  // does what it says on the tin
  Wire.begin();

  /*
  VALVE SET UP
  -----------------------
  */
  output_string(PORT, "test1");
  // Serial.println("test1");

  pinMode(NCS1_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 1 MOSFET
  pinMode(NCS2_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 2 MOSFET
  pinMode(NCS4_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 4 MOSFET
  pinMode(LABV1_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 5 MOSFET
  pinMode(LABV2_PIN, OUTPUT);    // sets the digital pin as output for controlling Valve 6 MOSFET
  pinMode(IGN1_PIN, OUTPUT);
  pinMode(IGN2_PIN, OUTPUT);

  // Serial.println("test2_Pins");
  output_string(PORT, "test2_Pins");

  /*
  THERMOCOUPLE SET UP
  -----------------------
  */

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

  /*
  LOAD CELL SET UP
  -----------------------
  */

  // load cell setup
  scale.begin(LC1_D_OUT_PIN, LC1_CLK_PIN);
  scale2.begin(LC2_D_OUT_PIN2, LC2_CLK_PIN2);
  scale3.begin(LC3_D_OUT_PIN3, LC3_CLK_PIN3);

  // scale and tare load cells
  scale.set_scale(-3980.f);  // Set the scale factor for conversion to pounds
  scale.tare();             // Reset the scale to zero

  scale2.set_scale(-3880.f); // Set the scale factor for conversion to pounds
  scale2.tare();            // Reset the scale to zero

  scale3.set_scale(-3780.f); // Set the scale factor for conversion to pounds
  scale3.tare();            // Reset the scale to zero
  
  // Serial.println("test4_LC");
  output_string(PORT, "test4_LC");
  /*
  ACCELEROMETER SET UP
  -----------------------
  */

  // detect and enable IMU
  // detectIMU();
  // enableIMU();
}

// Shutdown procedure - triggered by timeout or emergency abort
void trigger_shutdown() {
  // Open NCS2
  digitalWrite(NCS2_PIN, HIGH);

  // Close ball valves & NCS1
  digitalWrite(NCS1_PIN, LOW);
  digitalWrite(NCS4_PIN, LOW);
  digitalWrite(LABV1_PIN, LOW);
  digitalWrite(LABV2_PIN, LOW);

  // Unpower igniters
  digitalWrite(IGN1_PIN, LOW);
  digitalWrite(IGN2_PIN, LOW);

  // If LABV1 is open, system purges with nitrogen
  if (is_LABV1_open) {
    // Open NCS4 for 3 seconds
    digitalWrite(NCS4_PIN, HIGH);
    delay(SHUTDOWN_PURGE_TIME);
    digitalWrite(NCS4_PIN, LOW);
  }

  // Send emergency abort packet to GUI
  EGCPPacket abort_pkt(getNextTxId(), EGCPPacket::PKT_SFE);
  sendEGCPPacket(abort_pkt);

  // While system is aborted, wait for restart command
  bool aborted = true;
  while(aborted) {
    if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
      ABORT_TIME_TRACKING = micros();
      // Send abort status ping (using a heartbeat)
      EGCPPacket alive_pkt(getNextTxId(), EGCPPacket::PKT_HRT);
      sendEGCPPacket(alive_pkt);
    }

    int packet_size = udp.parsePacket();
    if (packet_size >= 4) {
      uint8_t header_buffer[4];
      for (int i = 0; i < 4 && udp.available() > 0; i++) {
        header_buffer[i] = udp.read();
      }
      
      // Parse packet type from header
      uint8_t packet_type = (header_buffer[2] >> 4) & 0xF;
      
      if (packet_type == EGCPPacket::PKT_STA) {
        // START packet received - exit abort state
        aborted = false;
        LAST_COMMUNICATION_TIME = micros();
        LAST_HUMAN_UPDATE = micros();
        digitalWrite(NCS2_PIN, LOW);
        
        // Clear buffer
        egcp_buffer_pos = 0;
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
  // Read incoming packets
  int packet_size = udp.parsePacket();
  if (packet_size > 0) {
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
        
        // Handle different packet types
        if (rxPacket.packet_type == EGCPPacket::PKT_STA) {
          // Connection START handshake
          sendACK(rxPacket.packet_id);
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_HRT) {
          // Heartbeat - just send ACK back
          sendACK(rxPacket.packet_id);
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_VSO) {
          // Valve open command
          if (rxPacket.body_length >= 1) {
            uint8_t valve_id = rxPacket.body[0];
            int pin = get_pin_from_valve_id(valve_id);
            if (pin >= 0) {
              digitalWrite(pin, HIGH);  // Open valve
              
              // Special handling for LA-BV1
              if (valve_id == EGCPPacket::VALVE_LA_BV1) {
                is_LABV1_open = true;
              }
              
              LAST_HUMAN_UPDATE = micros();
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
              
              // Special handling for LA-BV1
              if (valve_id == EGCPPacket::VALVE_LA_BV1) {
                if (is_LABV1_open) {
                  digitalWrite(NCS2_PIN, HIGH);  // Vent to NCS2
                }
                is_LABV1_open = false;
              }
              
              LAST_HUMAN_UPDATE = micros();
            }
            sendACK(rxPacket.packet_id);
          }
        }
        
        else if (rxPacket.packet_type == EGCPPacket::PKT_SFE) {
          // Emergency abort / safe mode
          sendACK(rxPacket.packet_id);
          trigger_shutdown();
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
      weight1 = scale.get_units(1);
      weight2 = scale2.get_units(1);
      weight3 = scale3.get_units(1);
    }

    // Measure temperature from thermocouple
    float t1 = mcp.readThermocouple();

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
      memcpy(&body[1], &p_values[i], 4);  // Copy float as bytes (big-endian)
      EGCPPacket adc(getNextTxId(), EGCPPacket::PKT_ADC, body, 5);
      sendEGCPPacket(adc);
    }

    // Temperature (T1)
    {
      uint8_t body[5];
      body[0] = EGCPPacket::SENSOR_T1;
      memcpy(&body[1], &t1, 4);
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
      memcpy(&body[1], &l_values[i], 4);
      EGCPPacket adc(getNextTxId(), EGCPPacket::PKT_ADC, body, 5);
      sendEGCPPacket(adc);
    }

    delay(10);
  }

  // Lost communication shutdown
  if (((micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT) || 
      ((micros() - LAST_HUMAN_UPDATE) > HUMAN_CONNECTION_TIMEOUT)) {
    trigger_shutdown();
  }
}