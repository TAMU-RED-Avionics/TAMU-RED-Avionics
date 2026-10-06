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

const int NCS1_PIN   = 31;   // relay 1
const int NCS2_PIN   = 30;   // relay 2
const int NCS3_PIN   = 29;   // relay 3
// NCS4 is a manual switch
const int NCS5_PIN   = 28;
const int PA_BV3_PIN = 27;
const int PA_BV1_PIN = 26;
const int PA_BV2_PIN = 24;
const int GV1_PIN    = 25;
const int GV2_PIN    = -1;
const int IGN1_PIN   = -1;
const int IGN2_PIN   = -1;
const int GIMBAL_PIN = -1;

const int ADS_CS_PIN  = 10;   // GPIO10 = CS1   <-- UNVERIFIED
const int ADS_MOSI    = 11;   // GPIO11 = SDI1  <-- UNVERIFIED
const int ADS_MISO    = 12;   // GPIO12 = SDO1  <-- UNVERIFIED
const int ADS_SCK     = 13;   // GPIO13 = SCLK1 <-- UNVERIFIED

// ADS7953 channel assignments
const float PT_SLOPE[12]     = { 0.1692f, 0.1692f, 0.1692f, 0.1692f,
                                  0.1692f, 0.1692f,
                                  0.1692f, 0.1692f,
                                  0.1692f, 0.1692f, 0.1692f, 0.1692f };   // 2-point fit: atmospheric + 50psig
const float PT_INTERCEPT[12] = { -171.9f, -171.9f, -171.9f, -171.9f,
                                   -171.9f, -171.9f,
                                   -171.9f, -171.9f,
                                   -171.9f, -171.9f, -171.9f, -171.9f };  // <-- USER INPUT, verify across more points

// ADS7953 channel i is NOT physical PTi - board routing is rotated
const uint8_t PT_NUM_FOR_CH[12] = { 6, 0, 7, 1, 8, 2, 9, 3, 10, 4, 11, 5 };

const float PT_EMA_ALPHA = 0.2f;   // 0=infinitely smooth/slow, 1=no smoothing
float pt_filtered[12] = { NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN, NAN };

const int ADS_PAD_PINS[4] = { ADS_CS_PIN, ADS_MOSI, ADS_MISO, ADS_SCK };
uint32_t ads_pad_saved[4];

void ads7953_save_pads() {
    for (int i = 0; i < 4; i++) ads_pad_saved[i] = *portControlRegister(ADS_PAD_PINS[i]);
}

void ads7953_set_slow_edges() {
    for (int i = 0; i < 4; i++) {
        volatile uint32_t* pad = portControlRegister(ADS_PAD_PINS[i]);
        if (ADS_PAD_PINS[i] == ADS_MISO) { *pad = ads_pad_saved[i] | IOMUXC_PAD_HYS; continue; }
        uint32_t v = ads_pad_saved[i] & ~(IOMUXC_PAD_DSE(7) | IOMUXC_PAD_SPEED(3) | IOMUXC_PAD_SRE);
        *pad = v | IOMUXC_PAD_DSE(1) | IOMUXC_PAD_SPEED(0);
    }
}

uint16_t ads7953_read(uint8_t channel) {
    uint16_t cmd = 0x1800 | ((uint16_t)(channel & 0x0F) << 7);

    digitalWrite(ADS_CS_PIN, LOW);
    SPI.transfer16(cmd);
    digitalWrite(ADS_CS_PIN, HIGH);

    // Result trails the channel select by two frames (verified on this board via
    // pt_4to20_test.ino's SPI sweep) - must repeat the SAME command, not send a
    // bogus 0x0000 frame, or the pipeline returns a neighboring channel's stale
    // conversion. That crosstalk is what was showing up as random spikes/dips.
    digitalWrite(ADS_CS_PIN, LOW);
    SPI.transfer16(cmd);
    digitalWrite(ADS_CS_PIN, HIGH);

    delayMicroseconds(10);   // let the internal sampling cap settle

    digitalWrite(ADS_CS_PIN, LOW);
    uint16_t val = SPI.transfer16(cmd);
    digitalWrite(ADS_CS_PIN, HIGH);

    return val & 0x0FFF;   // strip the echoed channel id, keep the 12-bit reading
}

// ---- ADS7953 bring-up diagnostic (prints once at boot) ----
// Reads a few channels and prints the FULL 16-bit words. In manual mode the top
// 4 bits echo the channel address of the conversion, so:
//   * echo bits match the channel      -> SPI is working. If the 12-bit value is still
//                                         ~0 the ADC INPUTS are at 0 V (PT loop supply
//                                         off / sense resistor open or shorted).
//   * every word is 0x0000 (or 0xFFFF) -> the chip is not answering: check MISO (pin 12),
//                                         CS (pin 10), SCK (13), MOSI (11), ADC power/ref.
// A healthy 0 psi PT on a 4-20 mA loop reads raw ~1016 (0.1692*1016 - 171.9 = 0).
void ads7953_diagnostic() {
    DBG_PRINTLN("ADS7953 diagnostic (channel: full16 -> echo, 12-bit):");
    uint8_t chans[3] = { 0, 5, 11 };
    bool any_echo = false;
    for (uint8_t i = 0; i < 3; i++) {
        uint8_t ch = chans[i];
        uint16_t cmd = 0x1800 | ((uint16_t)(ch & 0x0F) << 7);
        uint16_t w = 0;
        for (int k = 0; k < 3; k++) {          // same 3-frame pipeline as ads7953_read()
            digitalWrite(ADS_CS_PIN, LOW);
            w = SPI.transfer16(cmd);
            digitalWrite(ADS_CS_PIN, HIGH);
            delayMicroseconds(10);
        }
        uint8_t echo = (w >> 12) & 0xF;
        if (echo == ch) any_echo = true;
        DBG_PRINT("  ch"); DBG_PRINT(ch); DBG_PRINT(": 0x"); DBG_PRINT(w, HEX);
        DBG_PRINT(" echo="); DBG_PRINT(echo); DBG_PRINT(" raw12="); DBG_PRINTLN(w & 0x0FFF);
    }
    DBG_PRINTLN(any_echo ? "  -> ADC IS responding over SPI. If raw12 ~0, check PT loop power / sense resistors."
                         : "  -> NO channel echo: ADC not answering. Check MISO/CS/SCK/MOSI wiring and ADC power.");
}

inline float pt_psi(uint8_t channel) {
    uint16_t raw = ads7953_read(channel);
    return PT_SLOPE[channel] * raw + PT_INTERCEPT[channel];
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
        case 0x40: return GIMBAL_PIN;
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
enum ActuatorDriver : uint8_t { ACT_RC_SERVO, ACT_PWM_ANALOG };

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
    // The Bray modulating valve + PWM-to-analog slave card is NOT in use right
    // now, so there is no ACT_PWM_ANALOG row. The driver code is still above if
    // we want it back later.
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
    const int pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
    for (int pin : pins) {
        if (pin >= 0) digitalWrite(pin, LOW);
    }
    // if (NCS2_PIN >= 0) digitalWrite(NCS2_PIN, HIGH); // check ops
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

    // ---- SPI for ADS7953 ----
    pinMode(ADS_CS_PIN, OUTPUT);
    digitalWrite(ADS_CS_PIN, HIGH);
    SPI.begin();
    ads7953_save_pads();
    ads7953_set_slow_edges();
    SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
    // Dummy read to put ADS7953 into manual mode (each read() already runs the full frame handshake)
    ads7953_read(0);
    DBG_PRINTLN("ADS7953 SPI initialized");
    ads7953_diagnostic();

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
        const int output_pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
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
        for (int i = 0; i < 12; i++) {
            uint16_t raw = ads7953_read(i);
            float psi = PT_SLOPE[i] * raw + PT_INTERCEPT[i];
            // Light EMA smoothing on top of the crosstalk fix above - trims
            // remaining sample-to-sample jitter without adding much lag at
            // the 10ms sensor rate.
            pt_filtered[i] = isnan(pt_filtered[i]) ? psi : (PT_EMA_ALPHA * psi + (1.0f - PT_EMA_ALPHA) * pt_filtered[i]);
            send_adc_packet(0x01 + PT_NUM_FOR_CH[i], pt_filtered[i]);
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
