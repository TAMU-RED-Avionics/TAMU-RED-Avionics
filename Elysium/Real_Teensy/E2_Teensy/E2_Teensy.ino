/*
VARIABLES & USER INPUT
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
#include <Servo.h>
#include "EGCP.h"

#define SERIAL_DEBUG 1

#if defined(ARDUINO) && SERIAL_DEBUG
  #define DBG_PRINTLN(...) Serial.println(__VA_ARGS__)
  #define DBG_PRINT(...)   Serial.print(__VA_ARGS__)
#else
  #define DBG_PRINTLN(...)
  #define DBG_PRINT(...)
#endif


const long unsigned SENSOR_UPDATE_INTERVAL     = 10000;         // sensor update interval (microsec)
const long unsigned LC_UPDATE_INTERVAL         = 100000;        // load cell update interval (microsec)
const long unsigned CONNECTION_TIMEOUT         = 5000000;       // shutdown timeout for complete comms failure (microsec)
const long unsigned HUMAN_CONNECTION_TIMEOUT   = 3600000000;    // shutdown timeout for human comms failure (microsec)
                                        // NOTE: ^ THIS IS CURRENTLY 1 HOUR. THIS SHOULD NEVER TRIGGER, HOWEVER IT IS JUST TO BE SAFE (AND LEFTOVER FROM E1)

const long unsigned ABORTED_TIME_INTERVAL      = 500000;        // microsec between printing "aborted" (when aborted)
const long unsigned SHUTDOWN_PURGE_TIME        = 2000;          // duration of purge for shutdown, in milliseconds

long unsigned LAST_SENSOR_UPDATE               = 0;             // timestamp of last sensor reading (microsec)
long unsigned LAST_LC_UPDATE                   = 0;             // timestamp of last load cell reading (microsec)
long unsigned LAST_COMMUNICATION_TIME          = 0;             // timestamp of last communication of any type (microsec)
long unsigned LAST_HUMAN_UPDATE                = 0;             // timestamp of last human communication (microsec)
long unsigned ABORT_TIME_TRACKING              = 0;             // timestamp of last "aborted" print (when aborted)

const int BAUD = 115200;

// Relay line -> Teensy pin, traced from the daughter card PCB
// (Teensy_Daughtercard.kicad_pcb, J6 -> U1; all 16 lines are routed on copper):
//   relay  1 = pin 31 (J6-11)    relay  9 = pin  9 (J6-7)
//   relay  2 = pin 30 (J6-36)    relay 10 = pin  8 (J6-32)
//   relay  3 = pin 29 (J6-10)    relay 11 = pin  7 (J6-6)
//   relay  4 = pin 28 (J6-35)    relay 12 = pin  5 (J6-5)
//   relay  5 = pin 27 (J6-9)     relay 13 = pin  3 (J6-4)
//   relay  6 = pin 26 (J6-34)    relay 14 = pin  1 (J6-3)
//   relay  7 = pin 24 (J6-33)    relay 15 = pin 21 (J6-1)
//   relay  8 = pin 25 (J6-8)     relay 16 = pin 20 (J6-2)
const int NCS1_PIN   = 8;    // relay 10
const int NCS2_PIN   = 7;    // relay 11
const int NCS3_PIN   = 5;    // relay 12
// NCS4 is a manual switch (no relay). NCS5 is wired to relay 4 (ID 0x04).
const int NCS5_PIN   = 28;   // relay 4
// Pins 26/27 are SPI1 MOSI/SCK, which the AD5420 (Bray valve) needs, so
// PA-BV1/PA-BV3 are unavailable while the Bray valve is wired.
const int PA_BV3_PIN = -1;   // was 27 (relay 5)
const int PA_BV1_PIN = -1;   // was 26 (relay 6)
const int PA_BV2_PIN = 24;   // relay 7 (NOTE: pins 24/25 are also Wire2 = TC_WIRE)
const int PNEUMA_PIN = 3;    // relay 13
const int BRAY_AUX_PIN = -1;  // relay 14 = pin 1, but pin 1 is the AD5420's SPI1 MISO - unassigned until that moves
const int FP_1201_PIN = -1;   // relay 18 - fuel pump FP-1201, TODO: set to the Teensy pin wired to this relay
const int AP_1601_PIN = -1;   // relay 19 - air compressor AP-1601, TODO: set to the Teensy pin wired to this relay
const int GV1_PIN    = 25;   // relay 8
const int GV2_PIN    = -1;
const int IGN1_PIN   = -1;
const int IGN2_PIN   = -1;
const int GIMBAL_PIN = -1;


const int ADS_CS_PIN  = 10;   // -> J6 pin 49 (CS1)    (verified)
const int ADS_MOSI    = 11;   // -> J6 pin 25 (SDI1)   (verified)
const int ADS_MISO    = 12;   // -> J6 pin 24 (SDO1)   (verified)
const int ADS_SCK     = 13;   // -> J6 pin 50 (SCLK1)  (verified)

const bool     ADS_RANGE2     = true;      // true: 0..2xVREF (0-5 V), false: 0..VREF (0-2.5 V)
const float    ADS_VREF       = 2.5f;      // REF5025
const uint32_t ADS_SPI_HZ     = 1000000;   // sweep showed MODE0 is clean from 250 kHz to 4 MHz

// Same math as the pt_read bring-up sketch: 160 ohm shunt, 4-20 mA -> 0-full-scale psig (per PT, below),
// no per-channel calibration. PT_ATM_PSI is added so the GUI shows absolute pressure.
const float    PT_SHUNT_OHMS   = 160.0f;
const float    PT_PSI_AT_4MA   = 0.0f;
// Full-scale (20 mA) pressure per PT, indexed by PT number (0 = P1). P7 = OMI_P and
// P8 = MCC_P are 0-1000 psi transducers; every other PT is 0-1500 psi.
const float    PT_PSI_AT_20MA[12] = { 1500, 1500, 1500, 1500, 1500, 1500,
                                      1000, 1000,
                                      1500, 1500, 1500, 1500 };
const float    PT_ATM_PSI      = 14.7f;
// A healthy 4-20 mA PT never reads below ~3.92 mA, while a floating / unplugged input
// wanders around ~3.7 mA (it showed up as a phantom -2 psi). Below this threshold the
// channel is sent as NaN, which the GUI shows as no signal.
const float    PT_NO_SIGNAL_MA = 3.85f;

// ADS channel -> PT index (0-based; 0 = P1), traced from the PCB netlist:
//   J10 pins 1-4 = ch0-3  = PT6, PT0, PT7, PT1
//   J15 pins 1-4 = ch4-7  = PT8, PT2, PT9, PT3
//   J19 pins 1-4 = ch8-11 = PT10, PT4, PT11, PT5
// Confirmed on the bench: P2 = ch3, P6 = ch11, P8 = ch2.
const uint8_t PT_NUM_FOR_CH[12] = { 6, 0, 7, 1, 8, 2, 9, 3, 10, 4, 11, 5 };

const float PT_EMA_ALPHA = 0.2f;   // 0=infinitely smooth/slow, 1=no smoothing
float pt_filtered[12] = { NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN };
float pt_mA[12]       = { 0 };     // last loop current per ADS channel (for diagnostics)
uint32_t pt_addr_mismatch = 0;     // channels whose echoed address didn't match (reset every 1 s log)

// One 16-bit SPI frame. A transaction per frame (the working sketch does the same).
static uint16_t ads_frame(uint16_t tx) {
    SPI.beginTransaction(SPISettings(ADS_SPI_HZ, MSBFIRST, SPI_MODE0));
    digitalWriteFast(ADS_CS_PIN, LOW);
    uint16_t rx = SPI.transfer16(tx);
    digitalWriteFast(ADS_CS_PIN, HIGH);
    SPI.endTransaction();
    return rx;
}

// Manual mode: DI15-12 = 0001, DI11 = 1 (program), DI10-07 = channel, DI06 = range,
// DI05 = 0 (no power-down), DI04 = 0 (SDO returns channel address + 12-bit result).
static uint16_t ads_cmd(uint8_t ch) {
    return 0x1800 | ((uint16_t)ch << 7) | (ADS_RANGE2 ? 0x0040 : 0);
}

static bool ads_scan(uint16_t word[12], bool ok[12]) {
    bool all_ok = true;
    for (int i = 0; i < 14; i++) {
        uint16_t rx = ads_frame(ads_cmd(i < 12 ? i : 0));
        if (i >= 2) {
            uint8_t k = i - 2;
            ok[k] = ((rx >> 12) == k);
            if (!ok[k]) all_ok = false;
            word[k] = rx;
        }
    }
    return all_ok;
}

static void ads_flush() { for (int i = 0; i < 4; i++) ads_frame(ads_cmd(0)); }

// raw 12-bit count -> loop current (mA) -> psi, for ADS channel ch.
static float ads_counts_to_mA(uint16_t raw12) {
    float lsb = (ADS_RANGE2 ? 2.0f : 1.0f) * ADS_VREF / 4096.0f;
    return raw12 * lsb / PT_SHUNT_OHMS * 1000.0f;
}
static float ads_mA_to_psi(float mA, uint8_t pt_num) {
    return PT_PSI_AT_4MA + (mA - 4.0f) / 16.0f * (PT_PSI_AT_20MA[pt_num] - PT_PSI_AT_4MA) + PT_ATM_PSI;
}

// Boot-time report: proves SPI is talking to the ADC and shows each loop's current.
static void ads_boot_report() {
    uint16_t word[12]; bool ok[12];
    bool all_ok = ads_scan(word, ok);
    DBG_PRINTLN(all_ok ? "ADS7953 link OK: SPI_MODE0 @ 1 MHz, all channel addresses echoed correctly"
                       : "ADS7953 link BAD: channel address mismatch (check MISO/CS/SCK/MOSI, GND, VA+ at TP6)");
    for (int k = 0; k < 12; k++) {
        float mA = ads_counts_to_mA(word[k] & 0x0FFF);
        DBG_PRINT("  breakout "); DBG_PRINT(k + 1); DBG_PRINT(" (ADS ch"); DBG_PRINT(k); DBG_PRINT(" -> P"); DBG_PRINT(PT_NUM_FOR_CH[k] + 1);
        DBG_PRINT("): raw="); DBG_PRINT(word[k] & 0x0FFF);
        DBG_PRINT(" "); DBG_PRINT(mA); DBG_PRINT("mA ");
        DBG_PRINTLN(mA < PT_NO_SIGNAL_MA ? "(no signal)" : "");
    }
}

#define NAU7802_ADDR     0x2A
#define TCA_LC_ADDR      0x70

// NAU7802 register addresses
#define NAU7802_PU_CTRL  0x00
#define NAU7802_CTRL1    0x01
#define NAU7802_ADCO_B2  0x12

// ---- Load-cell I2C trunk: bit-banged (software) I2C ----
// The daughter card routes SCLLC/SDALC to Teensy pins 17 and 18, which are
// SDA1 and SDA on two DIFFERENT hardware I2C peripherals (Wire1/Wire) - no
// single hardware bus can drive both lines, so this trunk must be bit-banged.
#define LC_PIN_SCL       17
#define LC_PIN_SDA       18
#define LC_HALF_US       5     // ~100 kHz

inline void lc_dly()    { delayMicroseconds(LC_HALF_US); }
inline void lc_sdaRel() { pinMode(LC_PIN_SDA, INPUT); }
inline void lc_sdaLow() { pinMode(LC_PIN_SDA, OUTPUT); digitalWrite(LC_PIN_SDA, LOW); }
inline void lc_sclLow() { pinMode(LC_PIN_SCL, OUTPUT); digitalWrite(LC_PIN_SCL, LOW); }
inline void lc_sclRel() {
    pinMode(LC_PIN_SCL, INPUT);
    uint32_t t = micros();
    // A dead/disconnected bus pins SCL low on every bit, and this gets called
    // ~48-96 times per channel - at 2ms that stalled the WHOLE main loop (and
    // therefore all UDP/valve handling) for 1.4s/cycle when the LC bus died.
    // 100us is still generous for real NAU7802 clock stretching but lets a
    // dead bus fail fast instead of blocking everything else on the Teensy.
    while (!digitalRead(LC_PIN_SCL) && micros() - t < 100) {}
}

void lc_i2c_start() {   // also serves as repeated start
    lc_sdaRel(); lc_dly(); lc_sclRel(); lc_dly();
    lc_sdaLow(); lc_dly(); lc_sclLow(); lc_dly();
}

void lc_i2c_stop() {
    lc_sdaLow(); lc_dly(); lc_sclRel(); lc_dly(); lc_sdaRel(); lc_dly();
}

bool lc_i2c_write_byte(uint8_t b) {
    for (int i = 0; i < 8; i++) {
        if (b & 0x80) lc_sdaRel(); else lc_sdaLow();
        lc_dly(); lc_sclRel(); lc_dly(); lc_sclLow();
        b <<= 1;
    }
    lc_sdaRel(); lc_dly(); lc_sclRel(); lc_dly();
    bool ack = !digitalRead(LC_PIN_SDA);
    lc_sclLow(); lc_dly();
    return ack;
}

uint8_t lc_i2c_read_byte(bool ack) {
    uint8_t b = 0;
    lc_sdaRel();
    for (int i = 0; i < 8; i++) {
        lc_dly(); lc_sclRel(); lc_dly();
        b = (b << 1) | (digitalRead(LC_PIN_SDA) ? 1 : 0);
        lc_sclLow();
    }
    if (ack) lc_sdaLow(); else lc_sdaRel();
    lc_dly(); lc_sclRel(); lc_dly(); lc_sclLow();
    lc_sdaRel(); lc_dly();
    return b;
}

bool lc_i2c_write(uint8_t addr, const uint8_t* d, uint8_t n) {
    lc_i2c_start();
    bool ok = lc_i2c_write_byte(addr << 1);
    for (uint8_t i = 0; ok && i < n; i++) ok = lc_i2c_write_byte(d[i]);
    lc_i2c_stop();
    return ok;
}

bool lc_i2c_write_read(uint8_t addr, uint8_t reg, uint8_t* d, uint8_t n) {
    lc_i2c_start();
    if (!lc_i2c_write_byte(addr << 1) || !lc_i2c_write_byte(reg)) { lc_i2c_stop(); return false; }
    lc_i2c_start();
    if (!lc_i2c_write_byte((addr << 1) | 1)) { lc_i2c_stop(); return false; }
    for (uint8_t i = 0; i < n; i++) d[i] = lc_i2c_read_byte(i < n - 1);
    lc_i2c_stop();
    return true;
}

void lc_i2c_bus_recover() {
    lc_sdaRel();
    for (int i = 0; i < 9; i++) { lc_sclLow(); lc_dly(); lc_sclRel(); lc_dly(); }
    lc_i2c_stop();
}

void lc_i2c_begin() {
    lc_sdaRel();
    lc_sclRel();
    lc_i2c_bus_recover();
}

bool lc_i2c_ping(uint8_t addr) {
    return lc_i2c_write(addr, nullptr, 0);
}

void lc_scan_trunk() {
    DBG_PRINTLN("  LC trunk scan (pins 17/18):");
    uint8_t found = 0;
    for (uint8_t a = 0x08; a < 0x78; a++) {
        if (lc_i2c_ping(a)) {
            DBG_PRINT("    0x"); DBG_PRINTLN(a, HEX);
            found++;
        }
    }
    if (!found) DBG_PRINTLN("    NOTHING FOUND on LC trunk.");
}

void tca_lc_select(uint8_t channel) {
    // Select TCA9548A channel on the LC I2C bus. Physical mapping is rotated:
    // LC1-6 sit on mux channels 1-6 (bytes 0x02-0x40); channel 0 (0x01) is unused.
    uint8_t b = 1 << (channel + 1);
    lc_i2c_write(TCA_LC_ADDR, &b, 1);
}

bool nau7802_write(uint8_t reg, uint8_t val) {
    uint8_t d[2] = { reg, val };
    return lc_i2c_write(NAU7802_ADDR, d, 2);
}

uint8_t nau7802_read_byte(uint8_t reg) {
    uint8_t val = 0;
    lc_i2c_write_read(NAU7802_ADDR, reg, &val, 1);
    return val;
}

bool nau7802_data_ready() {
    return (nau7802_read_byte(NAU7802_PU_CTRL) & 0x20) != 0;
}

int32_t nau7802_read_adc() {
    // Read 24-bit signed result from ADCO registers
    uint8_t b[3];
    int32_t val = 0;
    if (lc_i2c_write_read(NAU7802_ADDR, NAU7802_ADCO_B2, b, 3)) {
        val  = (int32_t)b[0] << 16;
        val |= (int32_t)b[1] << 8;
        val |= (int32_t)b[2];
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
    nau7802_write(NAU7802_CTRL1, 0x2F);     // gain=128, LDO=3.0V  <-- USER INPUT if gain differs
    return true;
}

// LC1-LC6 calibration: lbs = slope * raw24bit + intercept
const float LC_SLOPE[6]     = { 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f };     // <-- USER INPUT  (calibrate on hardware)
const float LC_INTERCEPT[6] = { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f };     // <-- USER INPUT

float lc_weights[6] = { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f };
bool LC_INSTALLED[6] = { false, false, false, false, false, false };   // daughtercard not connected in current bench setup - no pull-ups/chips on the bus

#define TCA_TC_ADDR      0x70
#define MCP9600_MUXED_ADDR 0x67

const uint8_t TC_DIRECT_ADDR[4] = { 0x65, 0x66, 0x64, 0x60 };

// NOTE: must NOT be Wire (pins 18/19) or Wire1 (pins 16/17) - both collide with
// the load-cell bit-bang trunk on pins 17/18 above. Wire2 (pins 24/25 default)
// is the only hardware I2C bus that doesn't fight over those pins.
TwoWire& TC_WIRE = Wire2;

Adafruit_MCP9600 tc_sensor[12];
bool tc_ok[12] = { false };
float tc_temps[12] = { 0.0f };

bool TC_INSTALLED[12] = { true, true, true, true, true, true, true, true, true, true, true, true };   // set per hardware

void tca_tc_select(uint8_t channel) {
    TC_WIRE.beginTransmission(TCA_TC_ADDR);
    TC_WIRE.write(1 << channel);
    TC_WIRE.endTransmission();
}

void mcp9600_configure(Adafruit_MCP9600 &sensor) {
    sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
    sensor.setThermocoupleType(MCP9600_TYPE_K);
    sensor.setFilterCoefficient(3);
    sensor.enable(true);
}


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
        case 0x0A: return NCS1_PIN;   // NCS1 = relay 10
        case 0x0B: return NCS2_PIN;   // NCS2 = relay 11
        case 0x0C: return NCS3_PIN;   // NCS3 = relay 12
        case 0x04: return NCS5_PIN;   // NCS5 is relay 4
        case 0x06: return PA_BV3_PIN;   // was NCS6
        case 0x0D: return PNEUMA_PIN;   // Pneuma = relay 13
        case 0x0E: return BRAY_AUX_PIN;  // relay 14, also follows the Bray valve
        case 0x10: return PA_BV1_PIN;   // was LA-BV1
        case 0x11: return PA_BV2_PIN;   // was LA-BV2
        case 0x12: return FP_1201_PIN;  // FP-1201 fuel pump = relay 18
        case 0x13: return AP_1601_PIN;  // AP-1601 air compressor = relay 19
        case 0x20: return GV1_PIN;
        case 0x21: return GV2_PIN;
        case 0x30: return IGN1_PIN;
        case 0x31: return IGN2_PIN;
        case 0x40: return GIMBAL_PIN;
        default:   return -1;
    }
}

const char* get_valve_name(uint8_t id) {
    switch (id) {
        case 0x0A: return "NCS1";
        case 0x0B: return "NCS2";
        case 0x0C: return "NCS3";
        case 0x04: return "NCS5";
        case 0x06: return "PA-BV3";
        case 0x0D: return "PNEUMA";
        case 0x0E: return "BRAY-AUX";
        case 0x10: return "PA-BV1";
        case 0x11: return "PA-BV2";
        case 0x12: return "FP-1201";
        case 0x13: return "AP-1601";
        case 0x20: return "GV-1";
        case 0x21: return "GV-2";
        case 0x30: return "IGN-1";
        case 0x31: return "IGN-2";
        case 0x40: return "GIMBAL";
        default:   return "UNKNOWN";
    }
}

// ---------------------------------------------------------------------------
// PROPORTIONAL ACTUATORS (PKT_POS)
//
// The GUI sends a position in percent (0-100) to an actuator ID; everything
// about HOW that becomes a physical signal lives in this table, not in the GUI.
// The same ID goes in the component's "Binding" field in the P&ID. To add an
// actuator: add its ID to EGCP.h, add a row here, and bind it in the P&ID
// (the GUI's range / safe / open / presets live in that component's
// "Proportional Actuator" section).
//
//   ACT_RC_SERVO   - hobby servo straight off a GPIO: 50 Hz, pulse us_min..us_max
//   ACT_PWM_ANALOG - fixed-frequency PWM into the PWM-to-analog slave card
//                    (AD5420 4-20 mA DAC). Duty duty_min..duty_max percent
//                    maps to position 0..100 %.
//
// pin = -1 means "not wired yet": commands are still ACK'd (same convention
// as the valve pins above) so the GUI can be exercised on the bench.
// ---------------------------------------------------------------------------
enum ActuatorDriver : uint8_t { ACT_RC_SERVO, ACT_PWM_ANALOG, ACT_AD5420 };

// ---- AD5420 4-20 mA DAC on SPI1 (FMV / Bray valve) ----
// Ported from the standalone sketch that is KNOWN TO WORK. Position 0..100 %
// -> 16-bit code -> 4..20 mA. Not wired through ActuatorConfig::pin (the SPI
// pins are fixed here); the row's pin field is just the LATCH pin.
const int AD5420_LATCH_PIN = 0;    // CS1
const int AD5420_MOSI_PIN  = 26;   // MOSI1
const int AD5420_MISO_PIN  = 1;    // MISO1
const int AD5420_SCK_PIN   = 27;   // SCK1
const int AD5420_CLEAR_PIN = 19;   // CLEAR (held low)

const uint8_t  AD5420_ADDR_DATA    = 0x01;
const uint8_t  AD5420_ADDR_CONTROL = 0x55;
const uint8_t  AD5420_ADDR_RESET   = 0x56;
const uint16_t AD5420_CTRL_WORD    = 0x3005;   // REXT | OUTEN | 4-20 mA range

const SPISettings ad5420Settings(1000000, MSBFIRST, SPI_MODE0);

static void ad5420_write(uint8_t address, uint16_t data) {
    SPI1.beginTransaction(ad5420Settings);
    digitalWrite(AD5420_LATCH_PIN, LOW);
    SPI1.transfer(address);
    SPI1.transfer((data >> 8) & 0xFF);
    SPI1.transfer(data & 0xFF);
    digitalWrite(AD5420_LATCH_PIN, HIGH);
    SPI1.endTransaction();
}

static void ad5420_begin() {
    pinMode(AD5420_CLEAR_PIN, OUTPUT);
    digitalWrite(AD5420_CLEAR_PIN, LOW);
    pinMode(AD5420_LATCH_PIN, OUTPUT);
    digitalWrite(AD5420_LATCH_PIN, HIGH);
    SPI1.setMOSI(AD5420_MOSI_PIN);
    SPI1.setMISO(AD5420_MISO_PIN);
    SPI1.setSCK(AD5420_SCK_PIN);
    SPI1.begin();
    delay(10);
    ad5420_write(AD5420_ADDR_RESET, 0x0001);
    delay(1);
    ad5420_write(AD5420_ADDR_CONTROL, AD5420_CTRL_WORD);
}

struct ActuatorConfig {
    uint8_t        id;
    const char*    name;
    ActuatorDriver driver;
    int            pin;
    float          safe_pct;       // where abort / boot / loss-of-comms puts it
    // ACT_RC_SERVO
    uint16_t       us_min, us_max; // pulse widths at 0 % and 100 %
    // ACT_PWM_ANALOG
    float          duty_min_pct, duty_max_pct;
    uint32_t       pwm_hz;
};

const ActuatorConfig ACTUATORS[] = {
    // =====================================================================
    // *** TEMPORARY TEST SETUP - NOT THE FINAL WIRING ***
    //
    // Two 35 kg hobby RC servos, signal wires plugged DIRECTLY into the Teensy so we
    // can exercise the GUI / PKT_POS path end to end. Wiring per servo:
    //   - signal (PWM) wire -> Teensy pin (23 for SV-1, 22 for SV-2)
    //   - power (red)       -> EXTERNAL supply at the servo's rated voltage. The servos
    //                          are ALWAYS powered; the Teensy only sends the PWM signal.
    //                          Nothing in this firmware or the GUI switches servo power.
    //   - ground            -> external supply ground AND Teensy GND tied together
    //                          (MUST be common, or the signal has no reference and the
    //                          servo jitters).
    // Do NOT power them from the Teensy 5 V pin: a 35 kg servo pulls several amps and
    // can brown out / reset the Teensy (which trips the comms-loss abort).
    //
    // Because the servo is always powered, it moves as soon as a pulse appears: at
    // boot it is driven to safe_pct, so expect it to snap to its us_min position
    // when the Teensy starts. (After the direction flip that is the 2000 us end, i.e. CLOSED.)
    //
    // The FMV (Bray) modulating valve is driven by an AD5420 over SPI1
    // (ACT_AD5420 row below). There is no ACT_PWM_ANALOG row; that driver is
    // kept in case the PWM-to-analog slave card comes back.
    //
    // DIRECTION FLIP (test setup): us_min/us_max are deliberately "backwards"
    // (2000, 1000) so that 0 % = CLOSED = 2000 us and 100 % = OPEN = 1000 us. With
    // the original (1000, 2000) these servos were reversed (100 % closed, 0 % open).
    // To flip it back, just swap the two numbers on both rows. The math handles
    // us_min > us_max fine.
    //
    // us_min/us_max = pulse widths at 0 % / 100 % in the GUI. 1000-2000 us is
    // the standard RC range and a SAFE starting point. Many 35 kg servos can go
    // wider (500-2500 us) but if the linkage hits a hard stop the servo will
    // stall and draw max current, so widen it gradually while watching it.
    // safe_pct = 0 means: boot, abort, comms loss and the GUI "SAFE" button all
    // drive the servo to its us_min position.
    // =====================================================================

    // SV-1: servo #1, signal on Teensy pin 23
    { EGCPPacket::ACTUATOR_SV1, "SV-1", ACT_RC_SERVO, 23, 0.0f,
      2000, 1000,   0.0f, 0.0f, 0 },

    // SV-2: servo #2, same setup but signal on Teensy pin 22
    { EGCPPacket::ACTUATOR_SV2, "SV-2", ACT_RC_SERVO, 22, 0.0f,
      2000, 1000,   0.0f, 0.0f, 0 },

    // FMV (Bray): modulating valve driven 4-20 mA by the AD5420 on SPI1.
    // 0 % = 4 mA, 100 % = 20 mA. pin = AD5420 LATCH (CS1).
    { EGCPPacket::ACTUATOR_BRAY, "FMV (Bray)", ACT_AD5420, AD5420_LATCH_PIN, 0.0f,
      0, 0,   0.0f, 0.0f, 0 },
};
const int NUM_ACTUATORS = sizeof(ACTUATORS) / sizeof(ACTUATORS[0]);

Servo act_servo[NUM_ACTUATORS];
float act_pct[NUM_ACTUATORS];

int act_index(uint8_t id) {
    for (int i = 0; i < NUM_ACTUATORS; i++) if (ACTUATORS[i].id == id) return i;
    return -1;
}

void act_apply(int i) {
    const ActuatorConfig& a = ACTUATORS[i];
    if (a.pin < 0) return;
    float frac = act_pct[i] / 100.0f;
    if (a.driver == ACT_RC_SERVO) {
        act_servo[i].writeMicroseconds((int)(a.us_min + (a.us_max - a.us_min) * frac + 0.5f));
    } else if (a.driver == ACT_AD5420) {
        ad5420_write(AD5420_ADDR_DATA, (uint16_t)(frac * 65535.0f + 0.5f));
        // Relay 14 rides along with the Bray valve: on whenever it is commanded
        // above 0 %, off at 0 % (which is also the safe position).
        if (BRAY_AUX_PIN >= 0) digitalWrite(BRAY_AUX_PIN, act_pct[i] > 0.0f ? HIGH : LOW);
    } else {
        float duty = a.duty_min_pct + (a.duty_max_pct - a.duty_min_pct) * frac;   // percent
        analogWrite(a.pin, (int)(duty / 100.0f * 4095.0f + 0.5f));                // 12-bit, see setup()
    }
}

void act_set(int i, float pct) {
    act_pct[i] = constrain(pct, 0.0f, 100.0f);
    act_apply(i);
}

void act_init() {
    analogWriteResolution(12);
    for (int i = 0; i < NUM_ACTUATORS; i++) {
        const ActuatorConfig& a = ACTUATORS[i];
        act_pct[i] = a.safe_pct;
        if (a.pin < 0) continue;
        if (a.driver == ACT_RC_SERVO) {
            act_servo[i].attach(a.pin, a.us_min < 500 ? a.us_min : 500, a.us_max > 2500 ? a.us_max : 2500);
        } else if (a.driver == ACT_AD5420) {
            ad5420_begin();
        } else {
            pinMode(a.pin, OUTPUT);
            analogWriteFrequency(a.pin, a.pwm_hz);
        }
        act_apply(i);   // drive to the safe position right at boot
    }
}

void safe_all_actuators() {
    for (int i = 0; i < NUM_ACTUATORS; i++) act_set(i, ACTUATORS[i].safe_pct);
}

void send_pos_packet(uint8_t id, float pct) {
    uint16_t raw = (uint16_t)constrain((int)(pct * 100.0f + 0.5f), 0, 10000);
    uint8_t body[3] = { id, (uint8_t)(raw >> 8), (uint8_t)(raw & 0xFF) };
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_POS, body, 3);
    send_packet(pkt);
}

// Tell the GUI where every actuator actually is (sent on each STA handshake so a
// freshly connected / reconnected GUI shows the real position, not a guess).
void send_all_actuator_positions() {
    for (int i = 0; i < NUM_ACTUATORS; i++) send_pos_packet(ACTUATORS[i].id, act_pct[i]);
}

void send_nck(uint32_t nacked_id) {
    uint8_t body[3] = {
        (uint8_t)((nacked_id >> 16) & 0xFF),
        (uint8_t)((nacked_id >>  8) & 0xFF),
        (uint8_t)( nacked_id        & 0xFF)
    };
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_NCK, body, 3);
    send_packet(pkt);
}

void safe_all_valves() {
    const int pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PNEUMA_PIN, BRAY_AUX_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, FP_1201_PIN, AP_1601_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
    for (int pin : pins) {
        if (pin >= 0) digitalWrite(pin, LOW);
    }
    // E2 abort state (confirmed): every valve closed, including NCS2 - no valve
    // is left open on abort/comms loss.
    safe_all_actuators();
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
                        
                        LAST_COMMUNICATION_TIME = micros();
                        LAST_HUMAN_UPDATE       = micros();
                        LAST_SENSOR_UPDATE      = micros();
                        LAST_LC_UPDATE          = micros();
                        
                        if (NCS2_PIN >= 0) digitalWrite(NCS2_PIN, LOW);
                        send_ack(rx.packet_id);
                        send_all_actuator_positions();
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

    // ---- LC trunk diagnostic: run FIRST, before Ethernet/SPI touch anything ----
    {
        pinMode(LC_PIN_SDA, INPUT);
        pinMode(LC_PIN_SCL, INPUT);
        delay(5);
        DBG_PRINT("LC bus idle level  SDA=");
        DBG_PRINT(digitalRead(LC_PIN_SDA) ? "HIGH" : "LOW");
        DBG_PRINT("  SCL=");
        DBG_PRINTLN(digitalRead(LC_PIN_SCL) ? "HIGH" : "LOW");
        if (!digitalRead(LC_PIN_SDA) || !digitalRead(LC_PIN_SCL)) {
            DBG_PRINTLN("  ** Line(s) LOW with nothing driving them yet -> VMC+ missing/");
            DBG_PRINTLN("  ** unpowered, ground reference wrong, or pins 17/18 not on the trunk.");
        }
        lc_i2c_begin();
        lc_scan_trunk();
    }

    {
        IPAddress GATEWAY(192, 168, 1, 1);   // there is no router, so this is meaningless
        IPAddress SUBNET(255, 255, 255, 0);  // could be almost anything else tbh
        Ethernet.begin(MAC_ADDRESS, LOCAL_IP, GATEWAY, SUBNET);
        if (Ethernet.hardwareStatus() == EthernetNoHardware) {DBG_PRINTLN("ERR: No Ethernet hardware");}
        if (Ethernet.linkStatus() == LinkOFF) {DBG_PRINTLN("WARN: Ethernet cable disconnected");}
        udp.begin(UDP_PORT);
        DBG_PRINT("UDP listening on port "); DBG_PRINTLN(UDP_PORT);
    }

    // ---- SPI for ADS7953 (PTs) - same init as the proven standalone sketch ----
    pinMode(ADS_CS_PIN, OUTPUT);
    digitalWrite(ADS_CS_PIN, HIGH);
    SPI.begin();
    ads_flush();            // prime the 2-frame pipeline so the first real scan is valid
    ads_boot_report();

    // ---- I2C for NAU7802 load cells (LC1-LC6, all muxed, bit-banged) ----
    lc_i2c_begin();
    for (uint8_t ch = 0; ch < 6; ch++) {
        if (!LC_INSTALLED[ch]) {
            DBG_PRINT("LC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" skipped (not installed)");
            continue;
        }
        tca_lc_select(ch);
        if (nau7802_init()) {
            DBG_PRINT("LC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" (NAU7802) ready");
        } else {
            DBG_PRINT("WARN: LC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" NAU7802 not responding");
        }
    }

    // ---- I2C for MCP9600 thermocouples (TCADC1-12) ----
    TC_WIRE.begin();
    TC_WIRE.setClock(400000);

    for (uint8_t ch = 0; ch < 8; ch++) {
        if (!TC_INSTALLED[ch]) {
            DBG_PRINT("TCADC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" skipped (not installed)");
            continue;
        }
        tca_tc_select(ch);
        tc_ok[ch] = tc_sensor[ch].begin(MCP9600_MUXED_ADDR, &TC_WIRE);
        if (tc_ok[ch]) {
            mcp9600_configure(tc_sensor[ch]);
            DBG_PRINT("TCADC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" ready");
        } else {
            DBG_PRINT("WARN: TCADC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" not found");
        }
    }

    for (uint8_t i = 0; i < 4; i++) {
        uint8_t idx = 8 + i;
        if (!TC_INSTALLED[idx]) {
            DBG_PRINT("TCADC"); DBG_PRINT(idx + 1); DBG_PRINTLN(" skipped (not installed)");
            continue;
        }
        tc_ok[idx] = tc_sensor[idx].begin(TC_DIRECT_ADDR[i], &TC_WIRE);
        if (tc_ok[idx]) {
            mcp9600_configure(tc_sensor[idx]);
            DBG_PRINT("TCADC"); DBG_PRINT(idx + 1); DBG_PRINTLN(" ready");
        } else {
            DBG_PRINT("WARN: TCADC"); DBG_PRINT(idx + 1); DBG_PRINTLN(" not found (check address, esp. TCADC11)");
        }
    }

    {
        const int output_pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PNEUMA_PIN, BRAY_AUX_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, FP_1201_PIN, AP_1601_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
        for (int pin : output_pins) {
            if (pin >= 0) { pinMode(pin, OUTPUT); digitalWrite(pin, LOW); }
        }
        DBG_PRINTLN("Valve pins initialized");
    }

    act_init();
    DBG_PRINT("Actuators initialized: "); DBG_PRINTLN(NUM_ACTUATORS);

    LAST_COMMUNICATION_TIME = micros();
    LAST_HUMAN_UPDATE = micros();
    DBG_PRINTLN("Setup complete | Entering main loop");
}

uint32_t loop_iter_count = 0;
uint32_t pt_us_accum = 0, tc_us_accum = 0, lc_us_accum = 0;

void loop() {
    loop_iter_count++;


    unsigned long now_ms = millis();
    if (now_ms - last_loop_log_ms >= 1000) {
        last_loop_log_ms = now_ms;
        DBG_PRINT("Loop alive; iters/sec="); DBG_PRINT(loop_iter_count);
        loop_iter_count = 0;
        DBG_PRINT("; PT_us="); DBG_PRINT(pt_us_accum);
        DBG_PRINT(" PT_addr_bad="); DBG_PRINT(pt_addr_mismatch);
        pt_addr_mismatch = 0;
        { int nosig = 0; for (int i = 0; i < 12; i++) if (pt_mA[i] < PT_NO_SIGNAL_MA) nosig++;
          DBG_PRINT(" PT_nosignal="); DBG_PRINT(nosig); }
        DBG_PRINT(" mA[ch0-11]=");
        for (int i = 0; i < 12; i++) { DBG_PRINT(pt_mA[i], 2); DBG_PRINT(i < 11 ? "," : ""); }
        DBG_PRINT(" TC_us="); DBG_PRINT(tc_us_accum);
        DBG_PRINT(" LC_us="); DBG_PRINT(lc_us_accum);
        pt_us_accum = 0; tc_us_accum = 0; lc_us_accum = 0;
        DBG_PRINT("; link=");
        DBG_PRINT(Ethernet.linkStatus() == LinkON ? "UP" : "DOWN");
        DBG_PRINT("; last_rx=");
        DBG_PRINT((micros() - LAST_COMMUNICATION_TIME) / 1000);
        DBG_PRINT("ms ago; peer=");
        if (active_remote_valid) {
            DBG_PRINT(ACTIVE_REMOTE[0]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[1]); DBG_PRINT('.');
            DBG_PRINT(ACTIVE_REMOTE[2]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[3]);
            DBG_PRINT(':'); DBG_PRINTLN(ACTIVE_REMOTE_PORT);
        } else { DBG_PRINTLN("none"); }
    }

    // Read incoming packets. Drain up to RX_BURST datagrams per pass: one pass can
    // take ~10 ms (ADS7953 scan, TC I2C reads, ~30 UDP sends, delay(1)), and handling
    // only one datagram per pass let a valve command sit in the receive queue behind
    // heartbeats/ACKs long enough to miss the GUI's ACK retry window (~0.6 s).
    const int RX_BURST = 32;
    int pkt_sz = 0;
    int rx_burst_n = 0;
    while (rx_burst_n++ < RX_BURST && (pkt_sz = udp.parsePacket()) > 0) {
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
                // HRT/ACK arrive at ~100Hz; printing every one of them was slow
                // enough over USB serial to delay udp.parsePacket() and cause
                // real heartbeat misses. Only log the packet types we're
                // actually chasing (VSO/VSC/SFE/STA/anything unexpected).
                if (rx.packet_type != EGCPPacket::PKT_HRT && rx.packet_type != EGCPPacket::PKT_ACK) {
                    DBG_PRINT("RX type="); DBG_PRINT(rx.packet_type);
                    DBG_PRINT(" id="); DBG_PRINT(rx.packet_id);
                    DBG_PRINT(" len="); DBG_PRINTLN(rx.body_length);
                }

                // STA: Connection Handshake
                if (rx.packet_type == EGCPPacket::PKT_STA) {
                    DBG_PRINTLN("STA received -> ACK");
                    LAST_COMMUNICATION_TIME = micros();
                    LAST_HUMAN_UPDATE = micros();
                    send_ack(rx.packet_id);
                    send_all_actuator_positions();
                    egcp_rx_pos = 0; 
                    memset(egcp_rx_buf, 0, sizeof(egcp_rx_buf));
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

                // POS: Actuator position command from GUI
                else if (rx.packet_type == EGCPPacket::PKT_POS) {
                    if (rx.body_length >= 3) {
                        uint8_t  aid = rx.body[0];
                        uint16_t raw = ((uint16_t)rx.body[1] << 8) | rx.body[2];
                        int      idx = act_index(aid);
                        if (idx >= 0) {
                            act_set(idx, raw / 100.0f);
                            DBG_PRINT("POS "); DBG_PRINT(ACTUATORS[idx].name);
                            DBG_PRINT(" = "); DBG_PRINT(act_pct[idx]);
                            DBG_PRINT("% pin="); DBG_PRINTLN(ACTUATORS[idx].pin);
                            LAST_HUMAN_UPDATE = micros();
                            send_ack(rx.packet_id);
                        } else {
                            // Unknown ID is a P&ID/firmware mismatch - say so loudly
                            // (GUI shows the command as failed) instead of ACKing it.
                            DBG_PRINT("POS unknown actuator id=0x"); DBG_PRINTLN(aid, HEX);
                            send_nck(rx.packet_id);
                        }
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
            } else {
                DBG_PRINT("RX DECODE FAILED, raw bytes: ");
                for (int i = 0; i < total_sz; i++) {
                    DBG_PRINT(egcp_rx_buf[i], HEX); DBG_PRINT(' ');
                }
                DBG_PRINTLN("");
            }

            memmove(egcp_rx_buf, egcp_rx_buf + total_sz, egcp_rx_pos - total_sz);
            egcp_rx_pos -= total_sz;
        }
    }

    if ((micros() - LAST_SENSOR_UPDATE) > SENSOR_UPDATE_INTERVAL) {
        LAST_SENSOR_UPDATE = micros();

        uint32_t t0 = micros();
        {
            uint16_t word[12]; bool ok[12];
            ads_scan(word, ok);
            for (int i = 0; i < 12; i++) {
                if (!ok[i]) { pt_addr_mismatch++; continue; }   // bad echo: skip this sample, GUI keeps the last value
                float mA  = ads_counts_to_mA(word[i] & 0x0FFF);
                float psi = ads_mA_to_psi(mA, PT_NUM_FOR_CH[i]);
                pt_mA[i]  = mA;
                // An unplugged / broken loop (< PT_NO_SIGNAL_MA) is sent as NaN, which the
                // GUI shows as "NO SIGNAL" instead of a bogus negative psi.
                if (mA < PT_NO_SIGNAL_MA) {
                    pt_filtered[i] = NAN;
                    send_adc_packet(0x01 + PT_NUM_FOR_CH[i], NAN);
                    continue;
                }
                // Light EMA smoothing - trims sample-to-sample jitter without much
                // lag at the 10 ms sensor rate.
                pt_filtered[i] = isnan(pt_filtered[i]) ? psi : (PT_EMA_ALPHA * psi + (1.0f - PT_EMA_ALPHA) * pt_filtered[i]);
                send_adc_packet(0x01 + PT_NUM_FOR_CH[i], pt_filtered[i]);
            }
        }
        pt_us_accum += micros() - t0;

        t0 = micros();
        for (uint8_t ch = 0; ch < 8; ch++) {
            if (!TC_INSTALLED[ch] || !tc_ok[ch]) continue;
            tca_tc_select(ch);
            tc_temps[ch] = tc_sensor[ch].readThermocouple();
        }

        for (uint8_t i = 0; i < 4; i++) {
            uint8_t idx = 8 + i;
            if (!TC_INSTALLED[idx] || !tc_ok[idx]) continue;
            tc_temps[idx] = tc_sensor[idx].readThermocouple();
        }

        for (uint8_t i = 0; i < 12; i++) {
            if (!TC_INSTALLED[i]) continue;   // don't send stale/zero data for uninstalled channels
            send_adc_packet(0x64 + i, tc_temps[i]);  // 0x64-0x6F for TC1-12
        }
        tc_us_accum += micros() - t0;

        if ((LAST_SENSOR_UPDATE - LAST_LC_UPDATE) > LC_UPDATE_INTERVAL) {
            LAST_LC_UPDATE = LAST_SENSOR_UPDATE;
            t0 = micros();
            for (uint8_t ch = 0; ch < 6; ch++) {
                if (!LC_INSTALLED[ch]) continue;
                tca_lc_select(ch);
                if (nau7802_data_ready()) {
                    int32_t raw = nau7802_read_adc();
                    lc_weights[ch] = LC_SLOPE[ch] * raw + LC_INTERCEPT[ch];
                }
            }
            lc_us_accum += micros() - t0;
        }

        for (uint8_t ch = 0; ch < 6; ch++) {
            if (!LC_INSTALLED[ch]) continue;
            send_adc_packet(0x19 + ch, lc_weights[ch]);
        }

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
