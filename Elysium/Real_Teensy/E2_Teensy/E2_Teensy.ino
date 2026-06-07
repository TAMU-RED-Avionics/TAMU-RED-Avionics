/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_I2CRegister.h>
#include <Adafruit_MCP9600.h>
#include "EGCP.h"

#define SERIAL_DEBUG 1

#if defined(ARDUINO) && SERIAL_DEBUG
  #define DBG_PRINTLN(...) Serial.println(__VA_ARGS__)
  #define DBG_PRINT(...)   Serial.print(__VA_ARGS__)
#else
  #define DBG_PRINTLN(...)
  #define DBG_PRINT(...)
#endif


const long unsigned SENSOR_UPDATE_INTERVAL     = 10000;         // <-- USER INPUT       sensor update interval (microsec)
const long unsigned LC_UPDATE_INTERVAL         = 100000;        // <-- USER INPUT       load cell update interval (microsec)
const long unsigned CONNECTION_TIMEOUT         = 5000000;       // <-- USER INPUT       automated shutdown timeout for complete comms failure (microsec)
const long unsigned HUMAN_CONNECTION_TIMEOUT   = 3600000000;    // <-- USER INPUT       automated shutdown timeout for human comms failure (microsec)
                                        // NOTE: ^ THIS IS CURRENTLY 1 HOUR. THIS SHOULD NEVER TRIGGER, HOWEVER IT IS JUST TO BE SAFE (AND LEFTOVER FROM E1)

const long unsigned ABORTED_TIME_INTERVAL      = 500000;        // microsec between printing "aborted" (when aborted)
const long unsigned SHUTDOWN_PURGE_TIME        = 2000;          // duration of purge for shutdown, in milliseconds

long unsigned LAST_SENSOR_UPDATE               = 0;             // timestamp of last sensor reading (microsec)
long unsigned LAST_LC_UPDATE                   = 0;             // timestamp of last load cell reading (microsec)
long unsigned LAST_COMMUNICATION_TIME          = 0;             // timestamp of last communication of any type (microsec)
long unsigned LAST_HUMAN_UPDATE                = 0;             // timestamp of last human communication (microsec)
long unsigned ABORT_TIME_TRACKING              = 0;             // timestamp of last "aborted" print (when aborted)

const int BAUD = 115200;

// ---------------------------------------------------------------------------
// VALVE PIN ASSIGNMENTS
// Available RELAY→GPIO assignments from schematic:
//   RELAY1  → GPIO 2  or GPIO 32
//   RELAY3  → GPIO 33
//   RELAY4  → GPIO 3
//   RELAY5  → GPIO 34
//   RELAY6  → GPIO 4
//   RELAY7  → GPIO 5
//   RELAY8  → GPIO 35
//   RELAY9  → GPIO 36
//   RELAY10 → GPIO 6
//   RELAY11 → GPIO 37
//   RELAY12 → GPIO 38
//   RELAY13 → GPIO 39
//   RELAY14 → GPIO 40
//   RELAY15 → GPIO 14
//   RELAY16 → GPIO 41
// ---------------------------------------------------------------------------
const int NCS1_PIN   = -1;   // <-- USER INPUT  (available: see RELAY map above)
const int NCS2_PIN   = -1;   // <-- USER INPUT  (vent line — HIGH = open)
const int NCS3_PIN   = -1;   // <-- USER INPUT
// NCS4 is a manual switch
const int NCS5_PIN   = -1;   // <-- USER INPUT 
const int PA_BV3_PIN = -1;   // <-- USER INPUT  (prev. NCS6)
const int PA_BV1_PIN = -1;   // <-- USER INPUT  (prev. LA-BV1)
const int PA_BV2_PIN = -1;   // <-- USER INPUT  (prev. LA-BV2)
const int GV1_PIN    = -1;   // <-- USER INPUT
const int GV2_PIN    = -1;   // <-- USER INPUT
const int IGN1_PIN   = -1;   // <-- USER INPUT
const int IGN2_PIN   = -1;   // <-- USER INPUT
const int GIMBAL_PIN = -1;   // <-- USER INPUT

// ---------------------------------------------------------------------------
// ADS7953 SPI ADC  (pressure transducers + LC4/LC5 analog)
// Pins fixed by schematic — do not change
// ---------------------------------------------------------------------------
const int ADS_CS_PIN  = 10;   // GPIO10 = CS1
const int ADS_MOSI    = 11;   // GPIO11 = SDI1
const int ADS_MISO    = 12;   // GPIO12 = SDO1
const int ADS_SCK     = 13;   // GPIO13 = SCLK1

// ADS7953 channel assignments
// PT1-PT8 → CH0-CH7 (4-20mA sensors with 150Ω shunt, 0-3V on 3.3V rail)
// LC4, LC5 → CH8, CH9 (FX292X analog bridge via OPA192 amp)
// CH10-CH15 reserved / unassigned

// Calibration: psi = slope * raw12bit + intercept
// Raw range for 4-20mA / 150Ω shunt on 3.3V:
//   4mA  → 0.6V → raw = 4095*(0.6/3.3) = 744
//   20mA → 3.0V → raw = 4095*(3.0/3.3) = 3723
const float PT_SLOPE[8]     = { 0.5035f, 0.5035f, 0.5035f, 0.5035f,      // PT1-4: 0-1500 psi  <-- USER INPUT (verify gain)
                                 0.5035f, 0.5035f,                       // PT5-6: 0-1500 psi
                                 0.3357f, 0.3357f };                     // PT7-8: 0-1000 psi
const float PT_INTERCEPT[8] = { -374.6f, -374.6f, -374.6f, -374.6f,
                                  -374.6f, -374.6f,
                                  -249.7f, -249.7f };

// FX292X LC4/LC5: analog bridge, 0-200 lbs full scale
// Calibration depends on OPA192 gain — PLACEHOLDER, recalibrate on hardware
const float LC45_SLOPE     = 0.04884f;   // <-- USER INPUT  (lbs per raw count, no amp gain known)
const float LC45_INTERCEPT = 0.0f;       // <-- USER INPUT

uint16_t ads7953_read(uint8_t channel) {
    // ADS7953 manual-mode single-channel read
    // Command: bits[15:12]=0001 (manual), bits[11:8]=channel, bits[7:0]=0
    uint16_t cmd = (0x1000) | ((uint16_t)(channel & 0x0F) << 8);
    digitalWrite(ADS_CS_PIN, LOW);
    uint8_t hi = SPI.transfer((cmd >> 8) & 0xFF);
    uint8_t lo = SPI.transfer(cmd & 0xFF);
    digitalWrite(ADS_CS_PIN, HIGH);
    uint16_t result = ((uint16_t)(hi & 0x0F) << 8) | lo;
    return result;
}

inline float pt_psi(uint8_t channel) {
    uint16_t raw = ads7953_read(channel);
    return PT_SLOPE[channel] * raw + PT_INTERCEPT[channel];
}

// ---------------------------------------------------------------------------
// NAU7802 I2C ADC  (load cells LC1-LC3)
// I2C bus: SCL=GPIO16 (SCLLC), SDA=GPIO17 (SDALC)
// TCA9548A mux selects which NAU7802 is active
// NAU7802 default I2C address: 0x2A
// ---------------------------------------------------------------------------
#define NAU7802_ADDR     0x2A
#define TCA_LC_ADDR      0x70   // <-- USER INPUT  (TCA9548A address for LC bus, set by A0-A2 strapping)

// NAU7802 register addresses
#define NAU7802_PU_CTRL  0x00
#define NAU7802_CTRL1    0x01
#define NAU7802_ADCO_B2  0x12

TwoWire& LC_WIRE  = Wire1;   // GPIO16/17 = Wire1 on Teensy 4.1  <-- confirm with pinout

void tca_lc_select(uint8_t channel) {
    // Select TCA9548A channel (0-7) on the LC I2C bus
    LC_WIRE.beginTransmission(TCA_LC_ADDR);
    LC_WIRE.write(1 << channel);
    LC_WIRE.endTransmission();
}

bool nau7802_write(uint8_t reg, uint8_t val) {
    LC_WIRE.beginTransmission(NAU7802_ADDR);
    LC_WIRE.write(reg);
    LC_WIRE.write(val);
    return LC_WIRE.endTransmission() == 0;
}

uint8_t nau7802_read_byte(uint8_t reg) {
    LC_WIRE.beginTransmission(NAU7802_ADDR);
    LC_WIRE.write(reg);
    LC_WIRE.endTransmission(false);
    LC_WIRE.requestFrom((uint8_t)NAU7802_ADDR, (uint8_t)1);
    return LC_WIRE.available() ? LC_WIRE.read() : 0;
}

bool nau7802_data_ready() {
    return (nau7802_read_byte(NAU7802_PU_CTRL) & 0x20) != 0;
}

int32_t nau7802_read_adc() {
    // Read 24-bit signed result from ADCO registers
    LC_WIRE.beginTransmission(NAU7802_ADDR);
    LC_WIRE.write(NAU7802_ADCO_B2);
    LC_WIRE.endTransmission(false);
    LC_WIRE.requestFrom((uint8_t)NAU7802_ADDR, (uint8_t)3);
    int32_t val = 0;
    if (LC_WIRE.available() >= 3) {
        val  = (int32_t)LC_WIRE.read() << 16;
        val |= (int32_t)LC_WIRE.read() << 8;
        val |= (int32_t)LC_WIRE.read();
        if (val & 0x800000) val |= 0xFF000000;   // sign extend
    }
    return val;
}

bool nau7802_init() {
    // Reset and power up NAU7802
    nau7802_write(NAU7802_PU_CTRL, 0x01);   // RR: reset
    delay(1);
    nau7802_write(NAU7802_PU_CTRL, 0x02);   // PUD: power up digital
    delay(1);
    uint8_t ready = nau7802_read_byte(NAU7802_PU_CTRL);
    if (!(ready & 0x08)) return false;       // PUR bit must set
    nau7802_write(NAU7802_PU_CTRL, 0x86);   // AVDDS=1, PGA=1, PUD=1
    nau7802_write(NAU7802_CTRL1, 0x30);     // gain=128, LDO=3.0V  <-- USER INPUT if gain differs
    return true;
}

// LC1-LC3 calibration: lbs = slope * raw24bit + intercept
const float LC_SLOPE[3]     = { 1.0f, 1.0f, 1.0f };     // <-- USER INPUT  (calibrate on hardware)
const float LC_INTERCEPT[3] = { 0.0f, 0.0f, 0.0f };     // <-- USER INPUT

float lc_weights[5] = { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f };

// ---------------------------------------------------------------------------
// THERMOCOUPLES  (MCP9600 via I2C)
// I2C bus: SCL=GPIO18 (SCLTC), SDA=GPIO19 (SDATC)  = Wire2 on Teensy 4.1
// TCA9548A mux selects which MCP9600 is active
// ---------------------------------------------------------------------------
#define TCA_TC_ADDR  0x71   // <-- USER INPUT  (TCA9548A address for TC bus)

TwoWire& TC_WIRE = Wire2;   // GPIO18/19 = Wire2 on Teensy 4.1  <-- confirm with pinout

#define TC1_MUX_CH  0   // <-- USER INPUT  (which TCA9548A channel each MCP9600 is on)
#define TC2_MUX_CH  1   // <-- USER INPUT
#define TC3_MUX_CH  2   // <-- USER INPUT

Adafruit_MCP9600 tc1_sensor;
Adafruit_MCP9600 tc2_sensor;
Adafruit_MCP9600 tc3_sensor;
bool tc1_ok = false;
bool tc2_ok = false;
bool tc3_ok = false;

#define MCP9600_ADDR  0x60   // MCP9600 fixed I2C address (all instances share same addr, mux selects)

void tca_tc_select(uint8_t channel) {
    TC_WIRE.beginTransmission(TCA_TC_ADDR);
    TC_WIRE.write(1 << channel);
    TC_WIRE.endTransmission();
}

float lc45_weights[2] = { 0.0f, 0.0f };


byte MAC_ADDRESS[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };
IPAddress LOCAL_IP(192, 168, 1, 174);
IPAddress REMOTE_IP(192, 168, 1, 175);
unsigned int UDP_PORT = 8888;
// Dynamic peer (updated on first packet received from GUI)
IPAddress ACTIVE_REMOTE(192, 168, 1, 175);
unsigned int ACTIVE_REMOTE_PORT = 8888;
bool active_remote_valid = false;

EthernetUDP udp;
uint8_t egcp_rx_buf[256];
uint16_t egcp_rx_pos = 0;

// EGCP packet tracking
uint32_t tx_packet_id = 0;
uint32_t heartbeat_rx_count = 0;
unsigned long last_loop_log_ms = 0;

uint32_t next_tx_id() {
    uint32_t id = tx_packet_id;
    tx_packet_id = (tx_packet_id + 1) & 0xFFFFFF;
    return id;
}

void pack_float_be(float value, uint8_t* out) {
    uint8_t raw[4];
    memcpy(raw, &value, 4);
    out[0] = raw[3]; out[1] = raw[2]; out[2] = raw[1]; out[3] = raw[0];
}

void send_packet(const EGCPPacket& pkt) {
    uint8_t buf[20];
    uint8_t sz = pkt.encode(buf, sizeof(buf));
    if (sz == 0) return;
    IPAddress dst_ip      = active_remote_valid ? ACTIVE_REMOTE : REMOTE_IP;
    unsigned int dst_port = active_remote_valid ? ACTIVE_REMOTE_PORT : UDP_PORT;
    udp.beginPacket(dst_ip, dst_port);
    udp.write(buf, sz);
    udp.endPacket();
}

void send_ack(uint32_t acked_id) {
    uint8_t body[3] = {
        (uint8_t)((acked_id >> 16) & 0xFF),
        (uint8_t)((acked_id >>  8) & 0xFF),
        (uint8_t)( acked_id        & 0xFF)
    };
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_ACK, body, 3);
    send_packet(pkt);
}

void send_adc_packet(uint8_t sensor_id, float value) {
    uint8_t body[5];
    body[0] = sensor_id;
    pack_float_be(value, &body[1]);
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_ADC, body, 5);
    send_packet(pkt);
}

int get_pin_from_valve_id(uint8_t id) {
    switch (id) {
        case 0x01: return NCS1_PIN;
        case 0x02: return NCS2_PIN;
        case 0x03: return NCS3_PIN;
        case 0x05: return NCS5_PIN;
        case 0x06: return PA_BV3_PIN;   // was NCS6
        case 0x10: return PA_BV1_PIN;   // was LA-BV1
        case 0x11: return PA_BV2_PIN;   // was LA-BV2
        case 0x20: return GV1_PIN;
        case 0x21: return GV2_PIN;
        case 0x30: return IGN1_PIN;
        case 0x31: return IGN2_PIN;
        case 0xFF: return GIMBAL_PIN;
        default:   return -1;
    }
}

const char* get_valve_name(uint8_t id) {
    switch (id) {
        case 0x01: return "NCS1";
        case 0x02: return "NCS2";
        case 0x03: return "NCS3";
        case 0x05: return "NCS5";
        case 0x06: return "PA-BV3";
        case 0x10: return "PA-BV1";
        case 0x11: return "PA-BV2";
        case 0x20: return "GV-1";
        case 0x21: return "GV-2";
        case 0x30: return "IGN-1";
        case 0x31: return "IGN-2";
        case 0xFF: return "GIMBAL";
        default:   return "UNKNOWN";
    }
}

void safe_all_valves() {
    const int pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
    for (int pin : pins) {
        if (pin >= 0) digitalWrite(pin, LOW);
    }
    // if (NCS2_PIN >= 0) digitalWrite(NCS2_PIN, HIGH); // check with ops
}

void trigger_shutdown(const char* reason) {
    DBG_PRINT("[TEENSY] Trigger Shutdown: ");
    DBG_PRINTLN(reason ? reason : "UNKNOWN");

    safe_all_valves();

    EGCPPacket sfe(next_tx_id(), EGCPPacket::PKT_SFE);
    send_packet(sfe);

    // Clear the local parse buffer entirely before entering the loop
    egcp_rx_pos = 0; 
    memset(egcp_rx_buf, 0, sizeof(egcp_rx_buf));

    // Clear hardware UDP buffer entirely
    while (udp.parsePacket() > 0) { while (udp.available()) udp.read(); }

    bool aborted = true;
    while (aborted) {
        Ethernet.maintain();

        if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
            ABORT_TIME_TRACKING = micros();
            DBG_PRINTLN("[TEENSY] ABORTED | Waiting for STA");
        }

        int pkt_sz = udp.parsePacket();
        if (pkt_sz > 0) {
            int n = 0;
            while (udp.available() > 0 && n < (int)sizeof(egcp_rx_buf) - egcp_rx_pos) {
                egcp_rx_buf[egcp_rx_pos + n++] = udp.read();
            }
            egcp_rx_pos += n;

            while (egcp_rx_pos >= 4) {
                uint8_t  body_len = egcp_rx_buf[3] & 0xF;
                uint16_t total_sz = 4 + body_len;
                if (egcp_rx_pos < total_sz) break;

                EGCPPacket rx;
                if (EGCPPacket::decode(egcp_rx_buf, total_sz, rx)) {
                    if (rx.packet_type == EGCPPacket::PKT_STA) {
                        DBG_PRINTLN("[TEENSY] STA received | Exiting abort state");
                        aborted = false;
                        
                        // Sync timers to NOW so it doesn't instantly timeout on exit
                        LAST_COMMUNICATION_TIME = micros();
                        LAST_HUMAN_UPDATE       = micros();
                        LAST_SENSOR_UPDATE      = micros();
                        LAST_LC_UPDATE          = micros();
                        
                        if (NCS2_PIN >= 0) digitalWrite(NCS2_PIN, LOW);
                        send_ack(rx.packet_id);
                        break;
                    }
                }
                memmove(egcp_rx_buf, egcp_rx_buf + total_sz, egcp_rx_pos - total_sz);
                egcp_rx_pos -= total_sz;
            }
        }
    }
    
    egcp_rx_pos = 0;
    memset(egcp_rx_buf, 0, sizeof(egcp_rx_buf));
    while (udp.parsePacket() > 0) { while (udp.available()) udp.read(); }
    
    DBG_PRINTLN("[TEENSY] Exited abort state, returning to main loop");
}

void setup() {
#if defined(ARDUINO)
    Serial.begin(BAUD);
    delay(50);
#endif
    DBG_PRINTLN("Booting E2 Teensy firmware");
    {
        IPAddress GATEWAY(192, 168, 1, 1);   // there is no router, so this is meaningless
        IPAddress SUBNET(255, 255, 255, 0);  // could be almost anything else tbh
        Ethernet.begin(MAC_ADDRESS, LOCAL_IP, GATEWAY, SUBNET);
        if (Ethernet.hardwareStatus() == EthernetNoHardware) {DBG_PRINTLN("ERR: No Ethernet hardware");}
        if (Ethernet.linkStatus() == LinkOFF) {DBG_PRINTLN("WARN: Ethernet cable disconnected");}
        udp.begin(UDP_PORT);
        DBG_PRINT("UDP listening on port "); DBG_PRINTLN(UDP_PORT);
    }

    // ---- SPI for ADS7953 ----
    pinMode(ADS_CS_PIN, OUTPUT);
    digitalWrite(ADS_CS_PIN, HIGH);
    SPI.begin();
    SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
    // Send a dummy read to put ADS7953 into manual mode
    ads7953_read(0);
    ads7953_read(0);
    DBG_PRINTLN("ADS7953 SPI initialized");

    // ---- I2C for NAU7802 load cells ----
    LC_WIRE.begin();
    LC_WIRE.setClock(400000);
    for (uint8_t ch = 0; ch < 3; ch++) {
        tca_lc_select(ch);
        if (nau7802_init()) {
            DBG_PRINT("LC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" (NAU7802) ready");
        } else {
            DBG_PRINT("WARN: LC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" NAU7802 not responding");
        }
    }

    // ---- I2C for MCP9600 thermocouples ----
    TC_WIRE.begin();
    TC_WIRE.setClock(400000);

    tca_tc_select(TC1_MUX_CH);
    tc1_ok = tc1_sensor.begin(MCP9600_ADDR, &TC_WIRE);
    if (tc1_ok) {
        tc1_sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
        tc1_sensor.setThermocoupleType(MCP9600_TYPE_K);
        tc1_sensor.setFilterCoefficient(3);
        tc1_sensor.enable(true);
        DBG_PRINTLN("TC1 ready");
    } else { DBG_PRINTLN("WARN: TC1 not found"); }

    tca_tc_select(TC2_MUX_CH);
    tc2_ok = tc2_sensor.begin(MCP9600_ADDR, &TC_WIRE);
    if (tc2_ok) {
        tc2_sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
        tc2_sensor.setThermocoupleType(MCP9600_TYPE_K);
        tc2_sensor.setFilterCoefficient(3);
        tc2_sensor.enable(true);
        DBG_PRINTLN("TC2 ready");
    } else { DBG_PRINTLN("WARN: TC2 not found"); }

    tca_tc_select(TC3_MUX_CH);
    tc3_ok = tc3_sensor.begin(MCP9600_ADDR, &TC_WIRE);
    if (tc3_ok) {
        tc3_sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
        tc3_sensor.setThermocoupleType(MCP9600_TYPE_K);
        tc3_sensor.setFilterCoefficient(3);
        tc3_sensor.enable(true);
        DBG_PRINTLN("TC3 ready");
    } else { DBG_PRINTLN("WARN: TC3 not found"); }

    // ---- Valve output pins ----
    {
        const int output_pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
        for (int pin : output_pins) {
            if (pin >= 0) { pinMode(pin, OUTPUT); digitalWrite(pin, LOW); }
        }
        DBG_PRINTLN("Valve pins initialized");
    }

    LAST_COMMUNICATION_TIME = micros();
    LAST_HUMAN_UPDATE = micros();
    DBG_PRINTLN("Setup complete | Entering main loop");
}

void loop() {
    unsigned long now_ms = millis();
    if (now_ms - last_loop_log_ms >= 1000) {
        last_loop_log_ms = now_ms;
        DBG_PRINT("Loop alive; peer=");
        if (active_remote_valid) {
            DBG_PRINT(ACTIVE_REMOTE[0]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[1]); DBG_PRINT('.');
            DBG_PRINT(ACTIVE_REMOTE[2]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[3]);
            DBG_PRINT(':'); DBG_PRINTLN(ACTIVE_REMOTE_PORT);
        } else { DBG_PRINTLN("none"); }
    }

    // Read incoming packets
    int pkt_sz = udp.parsePacket();
    if (pkt_sz > 0) {
        // Capture dynamic remote address so we can reply to whoever sent us a packet
        ACTIVE_REMOTE = udp.remoteIP();
        ACTIVE_REMOTE_PORT = udp.remotePort();
        active_remote_valid = true;

        int n = 0;
        while (udp.available() > 0 && n < (int)sizeof(egcp_rx_buf) - egcp_rx_pos) {
            egcp_rx_buf[egcp_rx_pos + n++] = udp.read();
        }
        egcp_rx_pos += n;
        LAST_COMMUNICATION_TIME = micros();

        // Process all complete packets from the receive buffer
        while (egcp_rx_pos >= 4) {
            uint8_t  body_len = egcp_rx_buf[3] & 0xF;
            uint16_t total_sz = 4 + body_len;
            if (egcp_rx_pos < total_sz) break;

            EGCPPacket rx;
            if (EGCPPacket::decode(egcp_rx_buf, total_sz, rx)) {

                // STA: Connection Handshake
                if (rx.packet_type == EGCPPacket::PKT_STA) {
                    DBG_PRINTLN("STA received -> ACK");
                    LAST_COMMUNICATION_TIME = micros();
                    LAST_HUMAN_UPDATE = micros();
                    send_ack(rx.packet_id);
                    egcp_rx_pos = 0; 
                    memset(egcp_rx_buf, 0, sizeof(egcp_rx_buf)); // Optional: completely clear memory
                    break;
                }

                // HRT: Heartbeat
                else if (rx.packet_type == EGCPPacket::PKT_HRT) {
                    heartbeat_rx_count++;
                    send_ack(rx.packet_id);
                }

                // VSO: Valve Open
                else if (rx.packet_type == EGCPPacket::PKT_VSO) {
                    if (rx.body_length >= 1) {
                        uint8_t vid = rx.body[0];
                        int     pin = get_pin_from_valve_id(vid);
                        if (pin >= 0) {
                            digitalWrite(pin, HIGH);
                            DBG_PRINT("VSO "); DBG_PRINT(get_valve_name(vid));
                            DBG_PRINT(" pin="); DBG_PRINTLN(pin);
                            LAST_HUMAN_UPDATE = micros();
                        } else {
                            DBG_PRINT("VSO pin=-1 (unassigned) valve="); DBG_PRINTLN(get_valve_name(vid));
                        }
                        send_ack(rx.packet_id);
                    }
                }

                // VSC: Valve Close
                else if (rx.packet_type == EGCPPacket::PKT_VSC) {
                    if (rx.body_length >= 1) {
                        uint8_t vid = rx.body[0];
                        int     pin = get_pin_from_valve_id(vid);
                        if (pin >= 0) {
                            digitalWrite(pin, LOW);
                            DBG_PRINT("VSC "); DBG_PRINT(get_valve_name(vid));
                            DBG_PRINT(" pin="); DBG_PRINTLN(pin);
                            LAST_HUMAN_UPDATE = micros();
                        } else {
                            DBG_PRINT("VSC pin=-1 (unassigned) valve="); DBG_PRINTLN(get_valve_name(vid));
                        }
                        send_ack(rx.packet_id);
                    }
                }

                // SFE: Abort from GUI
                else if (rx.packet_type == EGCPPacket::PKT_SFE) {
                    DBG_PRINTLN("SFE from GUI");
                    DBG_PRINT(rx.packet_id, HEX);
                    DBG_PRINT(" body_len="); DBG_PRINT(rx.body_length);
                    DBG_PRINT(" raw bytes: ");
                    for (int i = 0; i < total_sz; i++) {
                        DBG_PRINT(egcp_rx_buf[i], HEX); DBG_PRINT(' ');
                    }
                    DBG_PRINTLN("");
                    send_ack(rx.packet_id);
                    trigger_shutdown("RX_SFE");
                    break;
                }
            }

            // Consume processed bytes from buffer
            memmove(egcp_rx_buf, egcp_rx_buf + total_sz, egcp_rx_pos - total_sz);
            egcp_rx_pos -= total_sz;
        }
    }

    // Sensor reading and transmission
    if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
        LAST_SENSOR_UPDATE = micros();

        // PT1-PT8 via ADS7953 CH0-CH7
        for (int i = 0; i < 8; i++) {
            uint16_t raw = ads7953_read(i);
            float psi = PT_SLOPE[i] * raw + PT_INTERCEPT[i];
            send_adc_packet(0x01 + i, psi);
        }

        // TC1-TC3 via MCP9600 through TCA9548A mux
        tca_tc_select(TC1_MUX_CH);
        float tc1_temp = tc1_ok ? tc1_sensor.readThermocouple() : 0.0f;
        tca_tc_select(TC2_MUX_CH);
        float tc2_temp = tc2_ok ? tc2_sensor.readThermocouple() : 0.0f;
        tca_tc_select(TC3_MUX_CH);
        float tc3_temp = tc3_ok ? tc3_sensor.readThermocouple() : 0.0f;
        send_adc_packet(0x09, tc1_temp);
        send_adc_packet(0x0A, tc2_temp);
        send_adc_packet(0x0B, tc3_temp);

        // LC1-LC3 via NAU7802 through TCA9548A mux (slower update rate)
        if ((LAST_SENSOR_UPDATE - LAST_LC_UPDATE) > LC_UPDATE_INTERVAL) {
            LAST_LC_UPDATE = LAST_SENSOR_UPDATE;
            for (uint8_t ch = 0; ch < 3; ch++) {
                tca_lc_select(ch);
                if (nau7802_data_ready()) {
                    int32_t raw = nau7802_read_adc();
                    lc_weights[ch] = LC_SLOPE[ch] * raw + LC_INTERCEPT[ch];
                }
            }
            // LC4 and LC5 via ADS7953 CH8-CH9 (FX292X analog bridge)
            uint16_t raw4 = ads7953_read(8);
            uint16_t raw5 = ads7953_read(9);
            lc45_weights[0] = LC45_SLOPE * raw4 + LC45_INTERCEPT;
            lc45_weights[1] = LC45_SLOPE * raw5 + LC45_INTERCEPT;
        }

        send_adc_packet(0x0C, lc_weights[0]);
        send_adc_packet(0x0D, lc_weights[1]);
        send_adc_packet(0x0E, lc_weights[2]);
        send_adc_packet(0x0F, lc45_weights[0]);
        send_adc_packet(0x10, lc45_weights[1]);

        delay(1);
    }

    // Lost comms shutdown
    if ((micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT) {
        trigger_shutdown("CONNECTION_TIMEOUT");
    }
    if ((micros() - LAST_HUMAN_UPDATE) > HUMAN_CONNECTION_TIMEOUT) {
        trigger_shutdown("HUMAN_TIMEOUT");
    }
}