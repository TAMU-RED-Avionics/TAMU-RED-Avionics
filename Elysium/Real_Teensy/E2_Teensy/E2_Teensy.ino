/*
VARIABLES & USER INPUT
*/

#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
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


const long unsigned SENSOR_UPDATE_INTERVAL     = 10000;         // sensor update interval (microsec)
const long unsigned LC_UPDATE_INTERVAL         = 100000;        // load cell update interval (microsec)
// Teensy-side comms watchdog: if nothing at all is received from the GUI for this long, close
// everything (trigger_shutdown). The GUI heartbeats every 10 ms and aborts on its own side after
// 150 ms without telemetry, so 200 ms (~20 missed heartbeats) lets the GUI trip first and keeps
// this as the backstop for when the GUI's abort can't reach the board. Was 5 s, which left
// MOV / IGN_1 / NV-1104 open for up to 5 s after the Nov 22 2026 link loss.
const long unsigned CONNECTION_TIMEOUT         = 200000;        // shutdown timeout for complete comms failure (microsec)
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
// (Teensy_Daughtercard.kicad_pcb v2.5, J6 -> U1). Relays 5, 6 and 14 stop at J6: their
// pins now carry SPI1 to the AD5420, so those three lines are not driven by anything.
// The other 13 are routed on copper. Relay 16 is spare.
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
// NCS4 is a manual switch (no relay). NCS5 = FV-1201 (ID 0x04) is wired to relay 13.
const int NCS5_PIN   = 3;    // relay 13 (FV-1201)
// Pins 26/27 are SPI1 MOSI/SCK, which the AD5420 (Bray valve) needs, so PA-BV1 has no
// relay and PA-BV3 / NCS6 (ID 0x06) moved from relay 5 to relay 15.
const int PA_BV3_PIN = 21;   // relay 15 (J6-1)
const int PA_BV1_PIN = -1;   // was 26 (relay 6)
const int PA_BV2_PIN = 24;   // relay 7
const int PNEUMA_PIN = -1;   // was pin 3 (relay 13); relay 13 now drives NCS5 / FV-1201
// Relay 9 powers the Bray positioner card (AD5420 daughtercard input J9). Relay outputs are
// LOW-SIDE switches, so relay 9 (GIGAPCB J5: +12 V on pins 1/2, switched return on 3/4) drives
// the coil of a small 12 V relay whose contacts switch the +12 V to J9 pin 2 - the card's own
// ground stays tied to the Teensy ground. -1 = card is wired straight to the rail (always on).
const int BRAY_PWR_PIN = 9;    // relay 9 (J6-7)
const int BRAY_AUX_PIN = -1;  // relay 14 = pin 1, but pin 1 is the AD5420's SPI1 MISO - unassigned until that moves
const int FP_1201_PIN = 29;   // relay 3 - fuel pump FP-1201 (ID 0x12)
const int AP_1601_PIN = 28;   // relay 4 - air compressor AP-1601 (ID 0x13)
const int GV1_PIN    = 25;   // relay 8
const int GV2_PIN    = -1;
const int IGN1_PIN   = 31;   // relay 1
const int IGN2_PIN   = 30;   // relay 2
const int GIMBAL_PIN = -1;
const int FV_1202_PIN = 20;  // relay 16 (J6-2) - was spare; FV-1202 is a plain on/off solenoid, not the SV2 servo channel


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

// ADS channel -> PT index (0-based; 0 = P1). Channel order per connector (PCB netlist):
//   J10 pins 1-4 = ch0-3, J15 pins 1-4 = ch4-7, J19 pins 1-4 = ch8-11
// PT assignment (P# = hw_id in REDControlSystem/PIDs/E2_RED_Spec.red):
//   J15-1 = P1 NPT-1101   J15-2 = P2 OPT-1301   J15-3 = P3 OPT-1501   J15-4 = P4 FPT-1401
//   J19-1 = P5 OPT-1502   J19-2 = P6 FPT-1402   J19-3 = P7 OMI_P      J19-4 = P8 MCC_P
//   J10-1..4 = P9-P12 (spare)
const uint8_t PT_NUM_FOR_CH[12] = { 8, 9, 10, 11, 0, 1, 2, 3, 4, 5, 6, 7 };

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

// ---- Load cells: NAU7802s behind a TCA9548A mux, read like the loadcell_cal sketch ----
// (the calibration constants below were measured with that sketch, so the chip is configured and read
// the same way here): hardware Wire1 (SCL1 = pin 16, SDA1 = pin 17) at 100 kHz, mux 0x70, NAU7802 0x2A:
// reset -> power up -> LDO 3.0 V, gain x128 -> chopper clock off + PGA cap -> rate -> internal offset
// calibration (CALS) of each input in use -> start converting. Which chip / input each load cell is on
// is in LC_MUX_CH[] / LC_VIN[] below. A chip with ONE load cell stays on its input at 80 samples/s
// (unchanged behaviour). A chip with TWO load cells (VIN1 + VIN2) runs at 320 samples/s and is
// alternated between its inputs by lc_shared_service() (non-blocking, see there).
#define LC_PIN_SCL        16
#define LC_PIN_SDA        17
#define LC_GAIN_BITS      7          // 0..7 = x1..x128
#define LC_LDO_BITS       5          // 0b101 = 3.0 V (excitation + ADC reference)
#define LC_RATE_BITS      3          // single-cell chips: 0=10, 1=20, 2=40, 3=80, 7=320 samples/s
#define LC_SHARED_RATE_BITS 7        // two-cell chips: 320 samples/s (3.125 ms per conversion, nominal)
// After a CHS (input) switch, wait this long before taking a sample: 5 nominal 320 SPS conversions
// (+15 % for the internal RC clock), so the sample used started ~3 conversions after the switch and the
// ones in between are thrown away. NOT verified on hardware - see the bench test notes.
#define LC_SHARED_SETTLE_US 18000

#define NAU7802_ADDR      0x2A
#define TCA_LC_ADDR       0x70
#define NAU_R_PU_CTRL     0x00
#define NAU_R_CTRL1       0x01
#define NAU_R_CTRL2       0x02
#define NAU_R_ADCO_B2     0x12
#define NAU_R_ADC         0x15
#define NAU_R_PGA_PWR     0x1C
#define NAU_PU_RR         0x01
#define NAU_PU_PUD        0x02
#define NAU_PU_PUA        0x04
#define NAU_PU_PUR        0x08
#define NAU_PU_CS         0x10
#define NAU_PU_CR         0x20
#define NAU_PU_AVDDS      0x80

void lc_i2c_begin() {
    static bool started = false;
    if (started) return;
    Wire1.begin();
    Wire1.setClock(100000);
    started = true;
}

static bool lc_mux_select(uint8_t mux_ch) {   // TCA9548A channel 0..7 (JLCn = channel n)
    Wire1.beginTransmission(TCA_LC_ADDR);
    Wire1.write((uint8_t)(1 << mux_ch));
    return Wire1.endTransmission() == 0;
}

static bool nau_write(uint8_t reg, uint8_t val) {
    Wire1.beginTransmission(NAU7802_ADDR);
    Wire1.write(reg);
    Wire1.write(val);
    return Wire1.endTransmission() == 0;
}

static bool nau_read_regs(uint8_t reg, uint8_t* buf, uint8_t n) {   // repeated start, auto-incrementing read
    Wire1.beginTransmission(NAU7802_ADDR);
    Wire1.write(reg);
    if (Wire1.endTransmission(false) != 0) return false;
    if (Wire1.requestFrom((uint8_t)NAU7802_ADDR, n) != n) return false;
    for (uint8_t i = 0; i < n; i++) buf[i] = Wire1.read();
    return true;
}

static int nau_read(uint8_t reg) {   // -1 = bus error
    uint8_t v;
    return nau_read_regs(reg, &v, 1) ? v : -1;
}

void lc_scan_trunk() {
    DBG_PRINTLN("  LC trunk scan (Wire1, pins 16/17):");
    uint8_t found = 0;
    for (uint8_t a = 0x08; a < 0x78; a++) {
        Wire1.beginTransmission(a);
        if (Wire1.endTransmission() == 0) {
            DBG_PRINT("    0x"); DBG_PRINTLN(a, HEX);
            found++;
        }
    }
    if (!found) DBG_PRINTLN("    NOTHING FOUND on LC trunk.");
}

// NAU7802 CTRL2 value: conversion rate + input select (CHS, bit 7: 0 = VIN1, 1 = VIN2).
static uint8_t lc_ctrl2(uint8_t rate_bits, uint8_t vin) {
    return (uint8_t)((rate_bits << 4) | (vin == 2 ? 0x80 : 0x00));
}

// Full NAU7802 bring-up for the chip on mux channel `mux_ch`. Runs the internal offset calibration once
// per input in vins[] (the chip keeps separate offset/gain registers for channel 1 and channel 2), and
// leaves the chip converting on vins[0]. Blocking; called from setup() only.
bool lc_init_chip(uint8_t mux_ch, uint8_t rate_bits, const uint8_t* vins, uint8_t nv) {
    if (!lc_mux_select(mux_ch)) return false;
    if (!nau_write(NAU_R_PU_CTRL, NAU_PU_RR)) return false;                    // reset
    delay(2);
    nau_write(NAU_R_PU_CTRL, NAU_PU_PUD);                                      // digital on
    nau_write(NAU_R_PU_CTRL, NAU_PU_PUD | NAU_PU_PUA);                         // analog on
    unsigned long t = millis();
    for (;;) {                                                                  // wait for power-up ready
        int pu = nau_read(NAU_R_PU_CTRL);
        if (pu >= 0 && (pu & NAU_PU_PUR)) break;
        if (millis() - t > 300) return false;
        delay(2);
    }
    nau_write(NAU_R_CTRL1, (uint8_t)((LC_LDO_BITS << 3) | LC_GAIN_BITS));      // LDO 3.0 V, gain x128
    nau_write(NAU_R_PU_CTRL, NAU_PU_AVDDS | NAU_PU_PUD | NAU_PU_PUA);          // AVDD from the internal LDO
    nau_write(NAU_R_ADC, 0x30);                                                 // chopper clock off (datasheet power-up sequence)
    int pga = nau_read(NAU_R_PGA_PWR);
    if (pga >= 0) nau_write(NAU_R_PGA_PWR, (uint8_t)(pga | 0x80));             // PGA cap on
    for (int i = (int)nv - 1; i >= 0; i--) {                                   // last one calibrated = vins[0]
        uint8_t c2 = lc_ctrl2(rate_bits, vins[i]);
        nau_write(NAU_R_CTRL2, c2);
        nau_write(NAU_R_CTRL2, c2 | 0x04);                                      // CALS: internal offset calibration
        t = millis();
        for (;;) {
            int c = nau_read(NAU_R_CTRL2);
            if (c >= 0 && !(c & 0x04)) { if (c & 0x08) return false; break; }   // done; CAL_ERR = failed
            if (millis() - t > 1000) return false;
            delay(5);
        }
    }
    nau_write(NAU_R_PU_CTRL, NAU_PU_AVDDS | NAU_PU_CS | NAU_PU_PUD | NAU_PU_PUA);   // start converting
    return true;
}

// One raw 24-bit sample from the chip on mux channel `mux_ch` if it has a new conversion ready;
// false = nothing new (never blocks). Leaves the mux on that channel.
bool lc_read_raw(uint8_t mux_ch, int32_t& raw) {
    if (!lc_mux_select(mux_ch)) return false;
    int pu = nau_read(NAU_R_PU_CTRL);
    if (pu < 0 || !(pu & NAU_PU_CR)) return false;
    uint8_t b[3];
    if (!nau_read_regs(NAU_R_ADCO_B2, b, 3)) return false;                      // all three bytes from one conversion
    int32_t v = ((int32_t)b[0] << 16) | ((int32_t)b[1] << 8) | b[2];
    if (v & 0x800000) v |= (int32_t)0xFF000000;                                 // sign extend
    raw = v;
    return true;
}

//const double LC_SLOPE[6]     = { 0.063616813928, 0.063616813928, 0.063616813928, 0.005974607916355, 0.006289308176101, 0.006546644844517 };
//const double LC_INTERCEPT[6] = { -1039.7978, -1039.7978, -1039.7978, 16.185212845407022, -104.044025157232709, -2.114566284779051 };

//const double LC_SLOPE[6]     = { 0.005974607916355, 0.006289308176101, 0.006546644844517, 0.005974607916355, 0.006289308176101, 0.006546644844517 };
//const double LC_INTERCEPT[6] = { 16.185212845407022, -104.044025157232709, -2.114566284779051, 16.185212845407022, -104.044025157232709, -2.114566284779051 };

// Load cells are sent as RAW counts (PKT_RAW). The slope / intercept that turn a count into pounds are no longer
// in the firmware: they are saved per load cell in the P&ID (cal_gain = slope, cal_offset = intercept) and applied
// by the GUI - calibrate in the Health tab > Load Cell Calibration. Last values this firmware used (Nov 2026),
// now stored in E2_RED_Spec.red:
//   LC_SLOPE[6]     = { 0.000550675207718, 0.067810206366926, 0.025277549395484, 0.006635070788728, 0.000094089290896, 0.006862648390970 };
//   LC_INTERCEPT[6] = { 3.057899428458018, -12976.122914337332986, -245.046371949874838, -195.854019541687677, -50.643148929450653, -116.994429769252121 };
/* calibration history log, not code:
point 1: raw 16350.5 = 0.000
point 2: raw 16404.1 = 4.200
fit of 2 points, worst error = 0.0000
LC_SLOPE[1] = 0.078358208954f;   LC_INTERCEPT[1] = -1281.1959f;
point 3: raw 16782.2 = 27.780
fit of 3 points, worst error = 0.4212
LC_SLOPE[1] = 0.063616813928f;   LC_INTERCEPT[1] = -1039.7978f;
point 4: raw 16400.3 = 2.580
fit of 4 points, worst error = 0.7141
LC_SLOPE[1] = 0.064285788756f;   LC_INTERCEPT[1] = -1051.0646f;
point 5: raw 16434.3 = 3.500
fit of 5 points, worst error = 1.5166
LC_SLOPE[1] = 0.064916693037f;   LC_INTERCEPT[1] = -1061.8438f;
fit of 5 points, worst error = 1.5166
LC_SLOPE[1] = 0.064916693037f;   LC_INTERCEPT[1] = -1061.8438f;
*/

int32_t lc_raw[6]    = { 0, 0, 0, 0, 0, 0 };            // latest raw count per load cell (what is sent as PKT_RAW)
bool    lc_raw_new[6] = { false, false, false, false, false, false };   // a fresh count not yet sent
bool  lc_ok[6]      = { false, false, false, false, false, false };   // LC_INSTALLED and answered at boot: only these are read / sent
// <-- USER INPUT: which load cells are fitted. Default = all six of the new wiring (JLC1 x2, JLC2, JLC3 x2, JLC5).
bool LC_INSTALLED[6] = { true, true, true, true, true, true };

// Load cell -> hardware, traced from GIGAPCB.kicad_sch. JLCn -> NAU7802 -> TCA9548A channel n:
//   JLC1 = U8 / ch1   JLC2 = U10 / ch2   JLC3 = U11 / ch3   JLC4 = U12 / ch4   JLC5 = U13 / ch5   JLC6 = U14 / ch6
// Every JLC: pin 4 = VIN1+, 5 = VIN1-, 2 = VIN2+, 3 = VIN2-, 1 = GND, 6 = excitation.
//                              LC1 LC2 LC3 LC4 LC5 LC6
const uint8_t LC_MUX_CH[6] = {   1,  1,  2,  3,  3,  5 };   // = JLC number
const uint8_t LC_VIN[6]    = {   1,  2,  1,  2,  1,  1 };   // 1 = JLC pins 4/5, 2 = JLC pins 2/3
const char*   LC_CHIP_U[8] = { "?", "U8", "U10", "U11", "U12", "U13", "U14", "?" };   // by mux channel

// One entry per NAU7802 in use (built in setup() from the tables above).
struct LcChip {
    uint8_t  mux_ch;
    uint8_t  n;          // installed load cells on this chip: 1, or 2 (= shared, alternating VIN1/VIN2)
    uint8_t  lc[2];      // load cell index (0 = LC1) per slot; slot 0 is the input the chip boots on
    bool     ok;
    uint8_t  cur;        // shared chips: slot currently selected (CHS)
    uint32_t t_switch;   // shared chips: micros() of the last CHS write
};
LcChip  lc_chips[6];
uint8_t lc_num_chips = 0;
bool    lc_shared[6]  = { false, false, false, false, false, false };   // that load cell's chip is shared
// Shared cells: every raw sample taken since the last send (the window), so bad ones can be thrown out before averaging.
#define LC_MAX_SAMPLES    16
#define LC_OUTLIER_COUNTS 2000     // <-- USER INPUT: a sample this many raw counts from the window's median is rejected
int32_t  lc_samples[6][LC_MAX_SAMPLES];
uint16_t lc_acc_n[6]  = { 0, 0, 0, 0, 0, 0 };
int32_t  lc_last_good[6]   = { 0, 0, 0, 0, 0, 0 };    // last accepted window mean
bool     lc_have_last[6]   = { false, false, false, false, false, false };
uint8_t  lc_reject_run[6]  = { 0, 0, 0, 0, 0, 0 };    // windows in a row where everything was rejected against lc_last_good
uint32_t lc_rejected = 0;                              // samples thrown out since the last status line

// A shared chip's VIN2 input sometimes returns a single sample thousands of counts off (bench: LC4 ~ -10,900,
// LC2 ~ -18,200), which in a 3-5 sample average shows up as a spike in the load cell reading. This averages the
// window's samples after dropping any that are more than LC_OUTLIER_COUNTS from the reference: the window's median
// when it has >= 3 samples, otherwise the last accepted value (no reference yet = accept everything).
// If every sample of a window disagrees with the last accepted value, the window is held back; a third such window
// in a row is accepted, so a real load step is followed after ~0.3 s instead of ignored forever.
// Returns false when there is nothing to update with (the previous weight is kept).
static bool lc_window_mean(uint8_t ch, double& mean) {
    uint16_t n = lc_acc_n[ch];
    if (n == 0) return false;

    bool have_ref = false;
    int32_t ref = 0;
    if (n >= 3) {
        int32_t s[LC_MAX_SAMPLES];
        for (uint16_t i = 0; i < n; i++) s[i] = lc_samples[ch][i];
        for (uint16_t i = 1; i < n; i++) {                                      // insertion sort
            int32_t v = s[i];
            int16_t j = (int16_t)i - 1;
            while (j >= 0 && s[j] > v) { s[j + 1] = s[j]; j--; }
            s[j + 1] = v;
        }
        ref = s[n / 2];
        have_ref = true;
    } else if (lc_have_last[ch]) {
        ref = lc_last_good[ch];
        have_ref = true;
    }

    int64_t sum = 0;
    uint16_t kept = 0;
    for (uint16_t i = 0; i < n; i++) {
        int32_t d = lc_samples[ch][i] - ref;
        if (!have_ref || (d >= -LC_OUTLIER_COUNTS && d <= LC_OUTLIER_COUNTS)) {
            sum += lc_samples[ch][i];
            kept++;
        }
    }

    if (kept == 0) {                                   // only possible against lc_last_good: a step, or a bad window
        if (++lc_reject_run[ch] < 3) { lc_rejected += n; return false; }
        for (uint16_t i = 0; i < n; i++) sum += lc_samples[ch][i];
        kept = n;
    } else {
        lc_rejected += (uint32_t)(n - kept);
    }
    lc_reject_run[ch] = 0;
    mean = (double)sum / (double)kept;
    lc_last_good[ch] = (int32_t)mean;
    lc_have_last[ch] = true;
    return true;
}

// Shared chips (two load cells): read the selected input once LC_SHARED_SETTLE_US has passed since the
// last switch, add it to that cell's running sum, flip CHS to the other input, restart the timer.
// Never waits: if the time isn't up or no conversion is ready, it returns and tries next pass.
// Each input gets a sample every ~20-30 ms (two settle periods + loop latency), so ~3-5 samples per
// 100 ms send, which are averaged in loop(). Called every loop() pass.
extern uint32_t lc_us_accum;   // defined with the other timing accumulators further down
void lc_shared_service() {
    uint32_t t0 = micros();
    bool did = false;
    for (uint8_t k = 0; k < lc_num_chips; k++) {
        LcChip& c = lc_chips[k];
        if (!c.ok || c.n < 2) continue;
        if (micros() - c.t_switch < LC_SHARED_SETTLE_US) continue;
        did = true;
        int32_t raw;
        if (!lc_read_raw(c.mux_ch, raw)) continue;                              // mux is left on c.mux_ch
        uint8_t lc = c.lc[c.cur];
        if (lc_acc_n[lc] < LC_MAX_SAMPLES) lc_samples[lc][lc_acc_n[lc]++] = raw;
        c.cur ^= 1;
        nau_write(NAU_R_CTRL2, lc_ctrl2(LC_SHARED_RATE_BITS, LC_VIN[c.lc[c.cur]]));
        c.t_switch = micros();
    }
    if (did) lc_us_accum += micros() - t0;
}

#define TCA_TC_ADDR      0x70
#define MCP9600_MUXED_ADDR 0x67

const uint8_t TC_DIRECT_ADDR[4] = { 0x65, 0x66, 0x64, 0x60 };

TwoWire& TC_WIRE = Wire;

Adafruit_MCP9600 tc_sensor[12];
bool tc_ok[12] = { false };
float tc_temps[12] = { 0.0f };

// TEMP (Nov 2026): TCADC1-8 are dead because the TCA9548 mux (U2, 0x70) doesn't respond on I2C,
// and TCADC9 (0x65) doesn't respond either. Only TCADC10-12 (direct, 0x66/0x64/0x60) work.
// Disabled channels aren't sent at all, so the GUI doesn't show a fake flat 0.0 for them.
// Set back to all-true once U2 / TCADC9 are fixed.
bool TC_INSTALLED[12] = { false, false, false, false, false, false, false, false, false, true, true, true };

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

extern uint32_t diag_tx;
void send_packet(const EGCPPacket& pkt) {
    uint8_t buf[20];
    uint8_t sz = pkt.encode(buf, sizeof(buf));
    if (sz == 0) return;
    IPAddress dst_ip      = active_remote_valid ? ACTIVE_REMOTE : REMOTE_IP;
    unsigned int dst_port = active_remote_valid ? ACTIVE_REMOTE_PORT : UDP_PORT;
    udp.beginPacket(dst_ip, dst_port);
    udp.write(buf, sz);
    udp.endPacket();
    diag_tx++;
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

// 64-bit microseconds since boot. micros() is 32-bit and wraps every ~71.6 min; this extends it.
// Must be called at least once per wrap - it runs on every sensor packet and every pass of the
// main loop and the abort loop, so that always holds while the board is powered.
uint64_t teensy_us() {
    static uint32_t last = 0;
    static uint64_t high = 0;
    uint32_t now = micros();
    if (now < last) high += (1ULL << 32);
    last = now;
    return high | now;
}

// PKT_ADC body: [sensor id:1][value: float32 BE:4][teensy_us: uint64 BE:8] = 13 bytes.
// The timestamp is the "Teensy Timestamp (us from boot)" column in the GUI's DAQ log, and it is when
// the board sent the reading, so it shows exactly when the data stops - independent of the laptop's
// clock. A GUI that only reads the first 5 bytes still works. If it ever jumps backwards, the Teensy
// rebooted.
void send_adc_packet(uint8_t sensor_id, float value) {
    uint8_t body[13];
    body[0] = sensor_id;
    pack_float_be(value, &body[1]);
    uint64_t ts = teensy_us();
    for (int i = 0; i < 8; i++) body[5 + i] = (uint8_t)(ts >> (56 - 8 * i));
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_ADC, body, 13);
    send_packet(pkt);
}

// PKT_RAW body: [sensor id:1][raw int32 BE:4][info:1 = (JLC<<4)|(VIN<<1)|shared]. Load cells are sent ONLY like
// this, every time a cell's count is recomputed (10 Hz). The sensor ID is the P&ID's load cell channel (25..30).
void send_lc_raw(uint8_t ch) {
    uint8_t body[6];
    body[0] = 0x19 + ch;
    uint32_t r = (uint32_t)lc_raw[ch];
    body[1] = (uint8_t)(r >> 24); body[2] = (uint8_t)(r >> 16); body[3] = (uint8_t)(r >> 8); body[4] = (uint8_t)r;
    body[5] = (uint8_t)((LC_MUX_CH[ch] << 4) | (LC_VIN[ch] << 1) | (lc_shared[ch] ? 1 : 0));
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_RAW, body, 6);
    send_packet(pkt);
}

int get_pin_from_valve_id(uint8_t id) {
    switch (id) {
        case 0x0A: return NCS1_PIN;   // NCS1 = relay 10
        case 0x0B: return NCS2_PIN;   // NCS2 = relay 11
        case 0x0C: return NCS3_PIN;   // NCS3 = relay 12
        case 0x04: return NCS5_PIN;   // NCS5 (FV-1201) is relay 13
        case 0x06: return PA_BV3_PIN;   // NCS6 = relay 15
        case 0x0D: return PNEUMA_PIN;   // Pneuma - unassigned (relay 13 went to NCS5)
        case 0x0E: return BRAY_AUX_PIN;  // relay 14, also follows the Bray valve
        case 0x10: return PA_BV1_PIN;   // was LA-BV1
        case 0x11: return PA_BV2_PIN;   // was LA-BV2
        case 0x12: return FP_1201_PIN;  // FP-1201 fuel pump = relay 3
        case 0x13: return AP_1601_PIN;  // AP-1601 air compressor = relay 4
        case 0x14: return FV_1202_PIN;  // FV-1202 solenoid = relay 16
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
        case 0x14: return "FV-1202";
        case 0x20: return "GV-1";
        case 0x21: return "GV-2";
        case 0x30: return "IGN-1";
        case 0x31: return "IGN-2";
        case 0x40: return "GIMBAL";
        default:   return "UNKNOWN";
    }
}

enum ActuatorDriver : uint8_t { ACT_PWM_ANALOG, ACT_AD5420 };

// AD5420 (Bray valve, SPI1) - driver ported from the validated
// AD5420_Sweep_Test_Daughtercard sketch (Real_Teensy/AD5420_Sweep_Test_Daughtercard/),
// which bench-confirmed this pin map, register set, and init order against the real card.
const int AD5420_LATCH_PIN = 0;    // CS1 / LATCH
const int AD5420_MOSI_PIN  = 26;   // MOSI1 / SDIN
const int AD5420_MISO_PIN  = 1;    // MISO1 / SDO
const int AD5420_SCK_PIN   = 27;   // SCK1 / SCLK
const int AD5420_CLEAR_PIN = -1;   // was 19 - but pin 19 is the thermocouple I2C SCL (/SCLTC) on this PCB; CLEAR has its own pull-down

const uint8_t  AD5420_ADDR_NOP      = 0x00;
const uint8_t  AD5420_ADDR_DATA     = 0x01;
const uint8_t  AD5420_ADDR_READBACK = 0x02;
const uint8_t  AD5420_ADDR_CONTROL  = 0x55;
const uint8_t  AD5420_ADDR_RESET    = 0x56;

const uint16_t AD5420_CTRL_REXT  = 1u << 13;
const uint16_t AD5420_CTRL_OUTEN = 1u << 12;
const uint16_t AD5420_RANGE_4_20 = 0b101;
const uint16_t AD5420_CTRL_WORD  = AD5420_CTRL_OUTEN | AD5420_RANGE_4_20;   // 0x3005

const uint16_t AD5420_RB_STATUS  = 0b00;
const uint16_t AD5420_RB_DATA    = 0b01;
const uint16_t AD5420_RB_CONTROL = 0b10;

const uint16_t AD5420_STATUS_IOUT_FAULT = 1u << 2;   // open load / out of compliance
const uint16_t AD5420_STATUS_SLEW       = 1u << 1;
const uint16_t AD5420_STATUS_OVER_TEMP  = 1u << 0;

const SPISettings ad5420Settings(1000000, MSBFIRST, SPI_MODE0);

// One 24-bit SPI frame: [addr][data_hi][data_lo], LATCH held low for the whole transfer -
// the rising edge on LATCH is what loads the register. No post-frame delay: this runs on
// every position update (act_apply -> ad5420_write), and the Bray valve is a mechanical
// positioner already far slower than this SPI transfer, so any firmware-added delay here
// is pure lag with no benefit. The 24-bit frame at 1 MHz (~24 us) plus beginTransaction()/
// endTransaction() overhead already leaves LATCH high well longer than the AD5420 needs
// before the next frame can start - no extra margin required.
static uint32_t ad5420_transfer24(uint8_t address, uint16_t data) {
    SPI1.beginTransaction(ad5420Settings);
    digitalWriteFast(AD5420_LATCH_PIN, LOW);
    uint32_t rx = (uint32_t)SPI1.transfer(address) << 16;
    rx |= (uint32_t)SPI1.transfer((data >> 8) & 0xFF) << 8;
    rx |= SPI1.transfer(data & 0xFF);
    digitalWriteFast(AD5420_LATCH_PIN, HIGH);
    SPI1.endTransaction();
    return rx;
}

static void ad5420_write(uint8_t address, uint16_t data) { ad5420_transfer24(address, data); }

static uint16_t ad5420_read(uint16_t select) {
    ad5420_transfer24(AD5420_ADDR_READBACK, select & 0x3);
    return (uint16_t)(ad5420_transfer24(AD5420_ADDR_NOP, 0x0000) & 0xFFFF);
}

// Prints the control register (should read back 0x3005) and any fault bits.
static void ad5420_print_status() {
    uint16_t control = ad5420_read(AD5420_RB_CONTROL);
    uint16_t status  = ad5420_read(AD5420_RB_STATUS);
    DBG_PRINT("AD5420 control=0x"); DBG_PRINT(control, HEX);
    DBG_PRINT(control == AD5420_CTRL_WORD ? " (OK)" : " (MISMATCH - check SPI wiring/mode)");
    DBG_PRINT(" status=0x"); DBG_PRINT(status, HEX);
    if (status & AD5420_STATUS_IOUT_FAULT) DBG_PRINT(" [IOUT FAULT: open load or out of compliance]");
    if (status & AD5420_STATUS_OVER_TEMP)  DBG_PRINT(" [OVER TEMP]");
    DBG_PRINTLN("");
}

// MFV (Bray) current: standard 4-20 mA positioner scaling - 0 % = 4 mA = closed,
// 100 % = 20 mA = open.
const uint16_t BRAY_CLOSED_DATA = 0x0000;   // zero-scale = 4 mA
static uint16_t bray_data(float pct) { return (uint16_t)(pct / 100.0f * 65535.0f + 0.5f); }

// Init sequence bench-validated by AD5420_Sweep_Test_Daughtercard: configure the range with
// OUTEN still clear (output stays off), zero the DATA register (4 mA = closed) WHILE the
// output is still disabled, and only then enable OUTEN - so the valve never briefly sees
// a stale/garbage DATA value with the output already live. Writing the full CTRL_WORD
// (OUTEN included) before zeroing DATA, as an earlier revision did, risks exactly that.
static void ad5420_begin() {
    if (AD5420_CLEAR_PIN >= 0) {
        pinMode(AD5420_CLEAR_PIN, OUTPUT);
        digitalWrite(AD5420_CLEAR_PIN, LOW);
    }
    pinMode(AD5420_LATCH_PIN, OUTPUT);
    digitalWriteFast(AD5420_LATCH_PIN, HIGH);
    SPI1.setMOSI(AD5420_MOSI_PIN);
    SPI1.setMISO(AD5420_MISO_PIN);
    SPI1.setSCK(AD5420_SCK_PIN);
    SPI1.begin();
    delay(10);

    ad5420_write(AD5420_ADDR_RESET, 0x0001);                                  // software reset, output tristated
    delay(1);
    ad5420_write(AD5420_ADDR_CONTROL, AD5420_RANGE_4_20);  // configure range, OUTEN still off
    ad5420_write(AD5420_ADDR_DATA, BRAY_CLOSED_DATA);                         // zero-scale = 4 mA = closed, output still off
    ad5420_write(AD5420_ADDR_CONTROL, AD5420_CTRL_WORD);                      // enable IOUT
    delay(1);

    // Stay silent when healthy (this runs on every automatic power-up); only report a problem.
    uint16_t control = ad5420_read(AD5420_RB_CONTROL);
    uint16_t status  = ad5420_read(AD5420_RB_STATUS);
    if (control != AD5420_CTRL_WORD || (status & (AD5420_STATUS_IOUT_FAULT | AD5420_STATUS_OVER_TEMP))) ad5420_print_status();
}

struct ActuatorConfig {
    uint8_t        id;
    const char*    name;
    ActuatorDriver driver;
    int            pin;
    float          safe_pct;       // where abort / boot / loss-of-comms puts it
    // ACT_PWM_ANALOG
    float          duty_min_pct, duty_max_pct;
    uint32_t       pwm_hz;
};

const ActuatorConfig ACTUATORS[] = {
    // FMV (Bray): modulating valve driven 4-20 mA by the AD5420 on SPI1.
    // 0 % = 4 mA (closed), 100 % = 20 mA (open). pin = AD5420 LATCH (CS1).
    // There is no ACT_PWM_ANALOG row; that driver is kept in case the PWM-to-analog
    // slave card comes back.
    { EGCPPacket::ACTUATOR_BRAY, "FMV (Bray)", ACT_AD5420, AD5420_LATCH_PIN, 0.0f,
      0.0f, 0.0f, 0 },
};
const int NUM_ACTUATORS = sizeof(ACTUATORS) / sizeof(ACTUATORS[0]);

float act_pct[NUM_ACTUATORS];

int act_index(uint8_t id) {
    for (int i = 0; i < NUM_ACTUATORS; i++) if (ACTUATORS[i].id == id) return i;
    return -1;
}

// Bray card power is automatic - there is no separate BRAY-PWR control in the GUI:
//   * any Bray command above 0 % closes relay 9 (if it isn't already), waits for the card's
//     12 V rail (BRAY_POWER_SETTLE_MS = 10 ms, non-blocking), resets + configures the AD5420, and
//     only then drives the commanded position;
//   * a command of 0 % (this is also what every abort / SAFE sends the Bray) drives 4 mA =
//     closed FIRST and then drops the relay, and SFE / comms-loss shutdown does the same.
// The AD5420 forgets its setup whenever it loses power, so the position is never restored
// after a power cycle: the valve starts closed and only opens on a new command.
bool bray_powered = false;
bool bray_power_pending = false;             // relay closed, waiting for the 12 V rail before configuring
unsigned long bray_power_pending_since_ms = 0;
const unsigned long BRAY_POWER_SETTLE_MS = 10;   // 12 V rail settle before the card is configured (keep this short)

void bray_power(bool on) {
    int i = act_index(EGCPPacket::ACTUATOR_BRAY);
    if (!on) {
        bray_power_pending = false;   // cancel a power-up that hasn't finished settling yet
        if (bray_powered) {
            if (i >= 0) act_pct[i] = 0.0f;
            ad5420_write(AD5420_ADDR_DATA, BRAY_CLOSED_DATA);   // 4 mA = closed, BEFORE the supply goes
            delay(20);                                 // let the DAC output settle
        }
        if (BRAY_PWR_PIN >= 0) {
            digitalWrite(BRAY_PWR_PIN, LOW);
            bray_powered = false;
        }   // else: card is wired straight to the rail, so it stays configured at 4 mA
        return;
    }
    if (bray_powered || bray_power_pending) return;   // already on, or already waiting on the rail
    if (BRAY_PWR_PIN >= 0) {
        digitalWrite(BRAY_PWR_PIN, HIGH);
        bray_power_pending = true;
        bray_power_pending_since_ms = millis();
    } else {
        ad5420_begin();   // wired straight to the rail: already up, configure now
        bray_powered = true;
    }
}

// Call every loop() iteration: finishes a pending Bray power-up once the 12 V rail has had
// BRAY_POWER_SETTLE_MS to settle, without blocking comms while waiting, then drives the
// position that was commanded while the card was still powering up.
void bray_power_poll() {
    if (!bray_power_pending) return;
    if (millis() - bray_power_pending_since_ms < BRAY_POWER_SETTLE_MS) return;
    bray_power_pending = false;
    ad5420_begin();   // registers are blank after power-up; starts at 4 mA = closed
    bray_powered = true;
    int i = act_index(EGCPPacket::ACTUATOR_BRAY);
    if (i >= 0 && act_pct[i] > 0.0f)
        ad5420_write(AD5420_ADDR_DATA, bray_data(act_pct[i]));
}

// Appends a short Bray token to the existing once-a-second "Loop alive" line (no newline,
// no separate line): " Bray=off", " Bray=ramping", or " Bray=12.0mA" plus "!SPI" / "!IOUT" /
// "!TEMP" if the AD5420 reports a problem.
void bray_log_token() {
    int i = act_index(EGCPPacket::ACTUATOR_BRAY);
    if (i < 0) return;
    if (bray_power_pending) { DBG_PRINT(" Bray=ramping"); return; }
    if (!bray_powered)      { DBG_PRINT(" Bray=off");     return; }
    uint16_t control = ad5420_read(AD5420_RB_CONTROL);
    uint16_t status  = ad5420_read(AD5420_RB_STATUS);
    DBG_PRINT(" Bray="); DBG_PRINT(4.0f + 16.0f * act_pct[i] / 100.0f, 1); DBG_PRINT("mA");
    if (control != AD5420_CTRL_WORD)             DBG_PRINT("!SPI");
    if (status & AD5420_STATUS_IOUT_FAULT)       DBG_PRINT("!IOUT");
    if (status & AD5420_STATUS_OVER_TEMP)        DBG_PRINT("!TEMP");
}

void act_apply(int i) {
    const ActuatorConfig& a = ACTUATORS[i];
    if (a.pin < 0) return;
    float frac = act_pct[i] / 100.0f;
    if (a.driver == ACT_AD5420) {
        if (act_pct[i] <= 0.0f) { bray_power(false); return; }   // closed: 4 mA first, then the card's power off
        if (!bray_powered) { bray_power(true); return; }          // power the card up; bray_power_poll() drives the position once it's configured
        ad5420_write(AD5420_ADDR_DATA, bray_data(act_pct[i]));
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
        if (a.driver == ACT_AD5420) {
            if (BRAY_PWR_PIN >= 0) { bray_powered = false; continue; }   // card stays off until the first Bray command above 0 %
            bray_power(true);                                            // wired straight to the rail: configure now
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

// ---- Igniters: always a 50 ms pulse ----
// IGN_AUTO_OFF 1 = the 50 ms cut-off is active. Set it to 0 to disable it (igniters then behave like
// valves: on from a VSO until a VSC / abort) - only ever for a deliberate test.
#define IGN_AUTO_OFF 1
#if IGN_AUTO_OFF
// An igniter is switched on by a VSO like a valve, but it must NEVER stay energized: every time it is
// turned on, a hardware timer shuts it off IGN_PULSE_US later, whatever igniter it is, whatever the GUI
// or a sequence is doing, and however busy (or stuck) the main loop is. It runs in an interrupt, so it
// is non-blocking and not tied to the ~10 ms loop pass. A VSC (or any abort / shutdown) turns it off
// immediately and cancels the timer. A VSO for an igniter that is already on does not extend the pulse
// (a retransmitted command can't make it longer). If no timer is available the igniter is NOT energized.
const uint32_t IGN_PULSE_US = 50000;   // <-- USER INPUT: how long an igniter stays on (microseconds)
IntervalTimer   ign_timer[2];          // [0] = IGN-1, [1] = IGN-2
volatile bool   ign_on[2] = { false, false };

static inline int ign_pin(int i)       { return i == 0 ? IGN1_PIN : IGN2_PIN; }
static inline int ign_index(uint8_t vid) { return vid == 0x30 ? 0 : (vid == 0x31 ? 1 : -1); }   // valve ID -> igniter

static void ign_off(int i) {           // runs in the timer interrupt (and from ign_cancel)
    ign_timer[i].end();
    if (ign_pin(i) >= 0) digitalWrite(ign_pin(i), LOW);
    ign_on[i] = false;
}
static void ign_off_isr0() { ign_off(0); }
static void ign_off_isr1() { ign_off(1); }

// Turn igniter i on for IGN_PULSE_US. Returns false if it could not be started safely.
static bool ign_fire(int i) {
    if (ign_pin(i) < 0) return false;
    if (ign_on[i]) return true;                                   // already firing: keep the original 50 ms
    // Start the shut-off timer FIRST: if it can't be armed, never energize the igniter.
    if (!ign_timer[i].begin(i == 0 ? ign_off_isr0 : ign_off_isr1, IGN_PULSE_US)) return false;
    ign_on[i] = true;
    digitalWrite(ign_pin(i), HIGH);
    return true;
}

static void ign_cancel(int i) {
    noInterrupts();
    ign_off(i);
    interrupts();
}
#endif   // IGN_AUTO_OFF

void safe_all_valves() {
#if IGN_AUTO_OFF
    ign_cancel(0);
    ign_cancel(1);
#endif
    const int pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PNEUMA_PIN, BRAY_AUX_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, FP_1201_PIN, AP_1601_PIN, FV_1202_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
    for (int pin : pins) {
        if (pin >= 0) digitalWrite(pin, LOW);
    }
    // E2 abort state (confirmed): every valve closed, including NCS2 - no valve
    // is left open on abort/comms loss.
    safe_all_actuators();
    bray_power(false);   // Bray (main fuel): 4 mA / closed first, then the card's relay off
}

// ---- Diagnostics: what the Teensy itself saw ----
// "Connection lost" says nothing about WHY. This keeps what the board knows about itself, and writes it to the SD
// card with the flight recorder (RECnnnn.TXT next to RECnnnn.BIN; DIAGnnnn.TXT when nothing was recording) every
// time the Teensy shuts down, plus a BOOTLOG.TXT line at every boot:
//   * why the chip last RESET (SRC_SRSR: power-on / watchdog / software / lockup ...) and any CrashReport - a
//     brownout or crash reboot shows up here, a "stayed up, link died" event shows none;
//   * the Ethernet chip's registers: does it answer, is the link up, and are the two settings the firmware writes at
//     boot still what it wrote (RCSR 0x0081 / LEDCR 0x0280 - if not, the chip reset itself, e.g. a supply dip or ESD);
//   * a timestamped event log (commands, link up/down, bad packets, shutdown, recovery attempts) in the Teensy's own
//     clock, and a few counters (packets, bad packets, how long since the GUI was last heard, chip temperature).
// Everything is read or composed at shutdown time, after every output is closed, never during a run - except one
// pair of Ethernet-chip status reads (~50 us) per 10 ms sensor pass, which also fill the recorder's link columns.
static bool phy_read(uint32_t reg, uint16_t& val);          // defined with the Ethernet recovery code below
extern bool sd_ok;                                           // the SD card is up (defined with the flight recorder)
extern uint32_t eth_recover_attempts;

enum : uint8_t { EV_BOOT = 1, EV_STA, EV_VSO, EV_VSC, EV_POS, EV_REC_START, EV_REC_STOP, EV_SFE_RX, EV_SHUTDOWN,
                 EV_LINK_DOWN, EV_LINK_UP, EV_ETH_RECOVER, EV_RX_BAD, EV_MDIO_FAIL, EV_MDIO_OK, EV_SD_FAIL };
static const char* const DIAG_EV_NAMES[] = { "?", "BOOT", "STA received (GUI connected)", "VALVE OPEN cmd", "VALVE CLOSE cmd",
    "POSITION cmd", "REC start", "REC stop", "SFE received (GUI abort)", "SHUTDOWN", "ETHERNET LINK DOWN",
    "ETHERNET LINK UP", "ETH recovery attempt", "undecodable packet", "ETHERNET CHIP STOPPED ANSWERING (MDIO)",
    "ethernet chip answering again", "SD CARD WRITE FAILED" };
#define DIAG_NUM_EVENTS 128
struct DiagEvent { uint64_t us; uint8_t code; uint8_t arg; uint16_t val; };
static DiagEvent diag_ev[DIAG_NUM_EVENTS];
static uint32_t  diag_ev_n = 0;                                  // events ever logged (ring slot = n % DIAG_NUM_EVENTS)
static void diag_event(uint8_t code, uint8_t arg = 0, uint16_t val = 0) {
    DiagEvent& e = diag_ev[diag_ev_n % DIAG_NUM_EVENTS];
    e.us = teensy_us(); e.code = code; e.arg = arg; e.val = val;
    diag_ev_n++;
}

uint32_t diag_rx_ok = 0, diag_rx_bad = 0, diag_tx = 0;           // packets from the GUI decoded / not, packets sent
uint8_t  diag_last_rx_type = 0;
uint64_t diag_last_rx_us = 0;
static uint32_t diag_srsr = 0;                                   // SRC_SRSR at boot: why the chip last reset
static uint16_t diag_bmsr = 0, diag_physts = 0;                  // Ethernet chip status, refreshed every sensor pass
static bool     diag_mdio_ok = true, diag_link_prev = true;

// Once per 10 ms sensor pass: read the Ethernet chip's status (BMSR bit 2 = link up, latched low so a drop between
// reads is still seen) and log link / MDIO changes with the Teensy's clock.
static void diag_poll() {
    uint16_t b = 0, p = 0;
    bool ok = phy_read(0x01, b);
    ok = phy_read(0x10, p) && ok;
    if (ok != diag_mdio_ok) { diag_mdio_ok = ok; diag_event(ok ? EV_MDIO_OK : EV_MDIO_FAIL); }
    if (!ok) { diag_bmsr = 0; diag_physts = 0; return; }
    diag_bmsr = b; diag_physts = p;
    bool link = (b & 0x0004) != 0;
    if (link != diag_link_prev) { diag_link_prev = link; diag_event(link ? EV_LINK_UP : EV_LINK_DOWN, 0, b); }
}

static const char* diag_reset_names(uint32_t srsr, char* out, size_t cap) {      // bits per the i.MX RT1060 reference manual
    static const char* const names[] = { "POWER-ON reset", "software reset or CPU lockup", "CSU reset", "external user reset",
        "WATCHDOG timeout", "JTAG reset", "JTAG software reset", "WDOG3 reset", "temperature-sensor reset" };
    out[0] = 0;
    for (int i = 0; i < 9; i++)
        if (srsr & (1u << i)) { if (out[0]) strncat(out, " + ", cap - strlen(out) - 1); strncat(out, names[i], cap - strlen(out) - 1); }
    if (!out[0]) strncpy(out, "none recorded (the Teensy core may have cleared it - see CrashReport)", cap - 1);
    return out;
}

class DiagBuf : public Print {                       // collects a CrashReport into a string
public:
    char* p; size_t cap, n = 0;
    DiagBuf(char* buf, size_t c) : p(buf), cap(c) { if (cap) p[0] = 0; }
    size_t write(uint8_t c) override { if (n + 1 < cap) { p[n++] = (char)c; p[n] = 0; } return 1; }
};

// The whole report as text. No SD access here (so it is easy to test); diag_dump() writes it out.
static size_t diag_build_text(char* buf, size_t cap, const char* title, const char* reason) {
    size_t n = 0;
#define DP(...) do { if (n < cap) { int w_ = snprintf(buf + n, cap - n, __VA_ARGS__); if (w_ > 0) n += (size_t)w_; if (n >= cap) n = cap - 1; } } while (0)
    uint64_t now = teensy_us();
    char tmp[160];
    DP("ELYSIUM TEENSY DIAGNOSTICS - %s\n", title);
    DP("Why the Teensy shut down : %s\n", reason ? reason : "?");
    DP("Teensy clock             : %.3f s since boot\n", (double)now / 1e6);
    if (diag_last_rx_us) DP("Last packet from the GUI  : %.1f ms before the shutdown (type %u)\n",
                            (double)(now - diag_last_rx_us) / 1000.0, (unsigned)diag_last_rx_type);
    else DP("Last packet from the GUI  : none since boot\n");
    DP("Packets                  : %lu received OK, %lu undecodable, %lu sent\n",
       (unsigned long)diag_rx_ok, (unsigned long)diag_rx_bad, (unsigned long)diag_tx);
    DP("Reset cause at boot      : SRSR=0x%08lX  %s\n", (unsigned long)diag_srsr, diag_reset_names(diag_srsr, tmp, sizeof(tmp)));
    DP("Chip temperature         : %.1f C\n", (double)tempmonGetTemp());
    DP("Sensor read errors       : ADS7953 bad echoes since the last 1 s log=%lu, load cell outliers rejected=%lu\n",
       (unsigned long)pt_addr_mismatch, (unsigned long)lc_rejected);
    DP("Load cells answering     : ");
    for (int i = 0; i < 6; i++) DP("LC%d=%s ", i + 1, lc_ok[i] ? "yes" : "NO");
    DP("\nEthernet recovery attempts : %lu (since the link was last good)\n", (unsigned long)eth_recover_attempts);

    DP("\nETHERNET CHIP (DP83825I) registers, read now (hex, register 0x00..0x1F):\n");
    uint16_t r[32];
    int fails = 0;
    for (int i = 0; i < 32; i++) { r[i] = 0; if (!phy_read((uint32_t)i, r[i])) fails++; }
    for (int i = 0; i < 32; i++) { if (i % 8 == 0) DP("  %02X:", i); DP(" %04X", (unsigned)r[i]); if (i % 8 == 7) DP("\n"); }
    if (fails >= 30) {
        DP("  -> The chip did NOT answer on its management bus. Either it has no power / is held in reset, or the\n"
           "     bus is stuck. This is not a software problem.\n");
    } else {
        DP("  Link up (BMSR bit 2)     : %s    BMSR=0x%04X  BMCR=0x%04X  PHYSTS=0x%04X\n",
           (r[1] & 4) ? "YES" : "NO", (unsigned)r[1], (unsigned)r[0], (unsigned)r[0x10]);
        DP("  Auto-negotiation done    : %s    partner ability (ANLPAR)=0x%04X\n", (r[1] & 0x20) ? "yes" : "no", (unsigned)r[5]);
        bool rc_ok = (r[0x17] == 0x0081), led_ok = (r[0x18] == 0x0280);
        DP("  RCSR=0x%04X (the firmware writes 0x0081) %s\n", (unsigned)r[0x17], rc_ok ? "ok" : "<-- DIFFERENT");
        DP("  LEDCR=0x%04X (the firmware writes 0x0280) %s\n", (unsigned)r[0x18], led_ok ? "ok" : "<-- DIFFERENT");
        if (!rc_ok || !led_ok)
            DP("  -> The chip's settings are NOT what the firmware wrote at boot: it RESET ITSELF to defaults (a supply\n"
               "     dip, ESD or noise on its supply), which leaves it on the wrong clock mode with no working link.\n");
    }

    DP("\nEVENT LOG, oldest first (time is relative to the moment of this report; the Teensy's own clock):\n");
    uint32_t total = diag_ev_n < DIAG_NUM_EVENTS ? diag_ev_n : DIAG_NUM_EVENTS;
    uint32_t first = diag_ev_n < DIAG_NUM_EVENTS ? 0 : diag_ev_n % DIAG_NUM_EVENTS;
    if (diag_ev_n > DIAG_NUM_EVENTS) DP("  (%lu older events dropped)\n", (unsigned long)(diag_ev_n - DIAG_NUM_EVENTS));
    for (uint32_t k = 0; k < total; k++) {
        const DiagEvent& e = diag_ev[(first + k) % DIAG_NUM_EVENTS];
        const char* nm = e.code < (sizeof(DIAG_EV_NAMES) / sizeof(DIAG_EV_NAMES[0])) ? DIAG_EV_NAMES[e.code] : "?";
        DP("  %+10.3f s  %s", (double)((int64_t)e.us - (int64_t)now) / 1e6, nm);
        if (e.code == EV_VSO || e.code == EV_VSC) DP("  %s", get_valve_name(e.arg));
        else if (e.code == EV_POS) DP("  actuator 0x%02X -> %.2f %%", (unsigned)e.arg, e.val / 100.0);
        else if (e.code == EV_BOOT) DP("  (SRSR low bits 0x%04X)", (unsigned)e.val);
        else if (e.code == EV_LINK_DOWN || e.code == EV_LINK_UP) DP("  BMSR=0x%04X", (unsigned)e.val);
        else if (e.code == EV_ETH_RECOVER) DP("  attempt %u", (unsigned)e.arg);
        DP("\n");
    }
#undef DP
    return n;
}

// Boot: remember why the chip reset, and append that (plus any CrashReport) to BOOTLOG.TXT on the SD card.
static void diag_boot_log() {
    char text[900], tmp[160];
    DiagBuf out(text, sizeof(text));
    size_t n = (size_t)snprintf(text, sizeof(text), "---- boot: SRSR=0x%08lX  %s | chip %.1f C | millis %lu\n",
                                (unsigned long)diag_srsr, diag_reset_names(diag_srsr, tmp, sizeof(tmp)),
                                (double)tempmonGetTemp(), (unsigned long)millis());
    if (CrashReport) {
        out.n = n < sizeof(text) ? n : sizeof(text) - 1;
        out.write('\n');
        CrashReport.printTo(out);                    // fault / watchdog / brownout details from the previous run
        CrashReport.clear();
        n = out.n;
    }
    if (n >= sizeof(text)) n = sizeof(text) - 1;
    DBG_PRINT(text);
    if (!sd_ok) return;
    File f = SD.open("BOOTLOG.TXT", FILE_WRITE);     // appends
    if (f) {
        size_t w = f.write((const uint8_t*)text, n) + f.write((const uint8_t*)"\n", 1);
        f.close();
        if (w != n + 1) { DBG_PRINTLN("BOOTLOG: SD WRITE FAILED"); sd_ok = false; }
    } else { DBG_PRINTLN("BOOTLOG: could not open the file on the SD card"); sd_ok = false; }
}

// ---- Flight recorder ("black box") ----
// What the Teensy itself saw is exactly what the GUI loses when the link drops: its recording only has
// what arrived. So while the GUI is running an automatic (sequence) recording, this keeps the last
// REC_CAPACITY sensor passes (one per 10 ms = ~36 s: terminal count + burn + the shutdown tail) in RAM.
//   * GUI sends PKT_REC start  -> the buffer is cleared and starts filling (nothing touches the SD card).
//   * GUI sends PKT_REC stop   -> the buffer is thrown away: the GUI recorded the same data.
//   * Teensy shuts down (comms loss, abort from the GUI, ...) while recording -> the buffer is written to
//     the SD card as RECnnnn.BIN, after every valve has been closed. Convert it on the PC with
//     teensy_rec_to_xlsx.py (REDControlSystem folder).
// The SD card is NEVER written while a run is in progress: a card can stall for 10-100+ ms on a write,
// which would delay the control loop (and the 200 ms comms watchdog). The only SD access outside the
// shutdown path is the one-time SD.begin() in setup().
// The buffer lives in DMAMEM (RAM2) so it does not use up the fast RAM1 the rest of the firmware needs.
#define REC_NUM_OUT 16
// Outputs whose on/off state is recorded, bit k of out_mask = REC_OUT_IDS[k] (same IDs as the GUI's relay IDs)
static const uint8_t REC_OUT_IDS[REC_NUM_OUT] = { 0x0A, 0x0B, 0x0C, 0x04, 0x06, 0x0D, 0x0E, 0x10,
                                                  0x11, 0x12, 0x13, 0x14, 0x20, 0x21, 0x30, 0x31 };
const uint32_t REC_CAPACITY = 3600;     // <-- USER INPUT: samples kept (84 bytes each, ~300 KB of RAM2)

struct __attribute__((packed)) RecSample {
    uint64_t us;            // teensy_us() when the sample was taken
    uint16_t pt_uA[12];     // raw 4-20 mA loop current per ADS channel, microamps (a collapsed loop shows here)
    int16_t  tc16[12];      // thermocouple per channel, 1/16 degC; 0x7FFF = not installed / no reading
    float    lc[6];         // load cells: RAW counts (NaN = no reading); the converter applies the P&ID calibration
    uint16_t out_mask;      // energized outputs, bit k = REC_OUT_IDS[k] (igniters, MOV, ...)
    uint16_t bray_x100;     // Bray valve commanded position, 0.01 %
    uint16_t phy_bmsr;      // Ethernet chip BMSR (bit 2 = link up), read every sample; 0 = chip not answering
    uint16_t phy_sts;       // Ethernet chip PHYSTS
};
static_assert(sizeof(RecSample) == 88, "RecSample layout changed - update teensy_rec_to_xlsx.py and vt_comms.py");

struct __attribute__((packed)) RecHeader {
    char     magic[8];              // "ELYREC1"
    uint16_t version;               // 3 (2 = 84-byte samples, no link columns; 1 = load cells in pounds)
    uint16_t sample_size;           // sizeof(RecSample)
    uint32_t sample_count;
    uint64_t rec_start_us;          // when the GUI's start arrived
    uint64_t dump_us;               // when the shutdown wrote this file
    char     reason[24];            // why: CONNECTION_TIMEOUT, RX_SFE, ...
    uint8_t  pt_num_for_ch[12];     // ADS channel -> PT number (0 = P1)
    float    pt_fs_psi[12];         // psi at 20 mA, per ADS channel
    float    pt_psi_at_4ma;
    float    pt_atm_psi;
    uint8_t  out_ids[REC_NUM_OUT];  // REC_OUT_IDS
};
static_assert(sizeof(RecHeader) <= 512, "RecHeader must fit its 512-byte block");

DMAMEM static RecSample rec_ring[REC_CAPACITY];
bool     rec_active   = false;
uint32_t rec_head     = 0;              // next slot to write
uint32_t rec_count    = 0;              // valid samples (<= REC_CAPACITY)
uint64_t rec_start_us = 0;
bool     sd_ok        = false;
static int rec_last_file = 0;                   // number of the RECnnnn.BIN just written (0 = none)

static unsigned long sd_last_try_ms = 0;

// Is there a usable card? Probing a missing card can take a while, so after one failed attempt it is not tried
// again for 5 s (one shutdown calls this twice - for the recording and for the report). Never called during a run.
static bool sd_try_begin() {
    if (sd_ok) return true;
    if (sd_last_try_ms && millis() - sd_last_try_ms < 5000) return false;
    sd_last_try_ms = millis();
    sd_ok = SD.begin(BUILTIN_SDCARD);
    return sd_ok;
}

void rec_sd_init() {                    // setup() only: SD.begin() can take a few hundred ms
    sd_last_try_ms = millis();
    sd_ok = SD.begin(BUILTIN_SDCARD);
    DBG_PRINTLN(sd_ok ? "SD card ready (flight recorder dumps here)"
                      : "WARN: NO SD CARD - the flight recorder and diagnostics reports will NOT be saved");
}

// Tell the GUI whether there is a card (PKT_REC, Teensy -> GUI: 1 = ready, 0 = none) so it can warn the operator
// BEFORE a test. Sent after every STA handshake and every recorder start / stop.
static void send_sd_status() {
    uint8_t b = sd_ok ? 1 : 0;
    EGCPPacket pkt(next_tx_id(), EGCPPacket::PKT_REC, &b, 1);
    send_packet(pkt);
}

static void rec_start() {
    diag_event(EV_REC_START);
    if (rec_active) return;
    if (!sd_ok) {                                   // never probe the card mid-run: just don't record
        DBG_PRINTLN("REC: NOT started - there is no SD card");
        return;
    }                         // a retransmitted start must not wipe what is recorded
    rec_head = 0; rec_count = 0;
    rec_start_us = teensy_us();
    rec_active = true;
    DBG_PRINTLN("REC: started (RAM only - written to SD only if the Teensy shuts down)");
}

static void rec_stop() {
    diag_event(EV_REC_STOP);
    if (rec_active) DBG_PRINTLN("REC: stopped - buffer discarded");
    rec_active = false; rec_head = 0; rec_count = 0;
}

// One sample per 10 ms sensor pass, called from loop(). RAM writes only - a few microseconds.
static void rec_sample() {
    if (!rec_active) return;
    RecSample& s = rec_ring[rec_head];
    s.us = teensy_us();
    for (int i = 0; i < 12; i++) {
        float mA = pt_mA[i];
        float uA = (isnan(mA) || mA < 0.0f) ? 0.0f : mA * 1000.0f + 0.5f;
        s.pt_uA[i] = uA > 65535.0f ? 65535 : (uint16_t)uA;
    }
    for (int i = 0; i < 12; i++) {
        float t = tc_temps[i] * 16.0f;
        s.tc16[i] = (!TC_INSTALLED[i] || !tc_ok[i] || isnan(t) || t > 32000.0f || t < -32000.0f) ? (int16_t)0x7FFF : (int16_t)t;
    }
    for (int ch = 0; ch < 6; ch++) s.lc[ch] = lc_ok[ch] ? (float)lc_raw[ch] : NAN;     // raw counts (exact in a float)
    uint16_t m = 0;
    for (int k = 0; k < REC_NUM_OUT; k++) {
        int pin = get_pin_from_valve_id(REC_OUT_IDS[k]);
        if (pin >= 0 && digitalRead(pin)) m |= (uint16_t)(1u << k);
    }
    s.out_mask = m;
    s.bray_x100 = NUM_ACTUATORS > 0 ? (uint16_t)(act_pct[0] * 100.0f + 0.5f) : 0;
    s.phy_bmsr = diag_bmsr;
    s.phy_sts = diag_physts;
    rec_head = (rec_head + 1) % REC_CAPACITY;
    if (rec_count < REC_CAPACITY) rec_count++;
}

// Write the buffer to the SD card. Only called from trigger_shutdown(), after everything is closed.
static void rec_dump(const char* reason) {
    if (!rec_active || rec_count == 0) { rec_active = false; return; }
    rec_active = false;                             // dump once; the GUI's later "stop" is then a no-op
    uint32_t t0 = millis();
    if (!sd_try_begin()) { DBG_PRINTLN("REC: no SD card - recording lost, nothing written"); return; }

    char name[16];
    int fileno = 1;
    for (; fileno <= 9999; fileno++) {
        snprintf(name, sizeof(name), "REC%04d.BIN", fileno);
        if (!SD.exists(name)) break;
    }
    File f = SD.open(name, FILE_WRITE);
    if (!f) { DBG_PRINTLN("REC: could not create the file - recording lost"); return; }
    rec_last_file = fileno;                         // diag_dump() puts its report next to this file

    uint8_t block[512];
    memset(block, 0, sizeof(block));
    RecHeader h;
    memset(&h, 0, sizeof(h));
    memcpy(h.magic, "ELYREC1", 8);
    h.version = 3;                                  // 3 = + Ethernet link columns (2 = raw load cells, 84-byte samples; 1 = pounds)
    h.sample_size = sizeof(RecSample);
    h.sample_count = rec_count;
    h.rec_start_us = rec_start_us;
    h.dump_us = teensy_us();
    strncpy(h.reason, reason ? reason : "", sizeof(h.reason) - 1);
    for (int i = 0; i < 12; i++) {
        h.pt_num_for_ch[i] = PT_NUM_FOR_CH[i];
        h.pt_fs_psi[i] = PT_PSI_AT_20MA[PT_NUM_FOR_CH[i]];
    }
    h.pt_psi_at_4ma = PT_PSI_AT_4MA;
    h.pt_atm_psi = PT_ATM_PSI;
    memcpy(h.out_ids, REC_OUT_IDS, REC_NUM_OUT);
    memcpy(block, &h, sizeof(h));
    size_t want = sizeof(block), got = f.write(block, sizeof(block));

    // Oldest sample first: when the ring has wrapped that is the slot rec_head points at.
    uint32_t first = (rec_count == REC_CAPACITY) ? rec_head : 0;
    uint32_t n1 = (first == 0) ? rec_count : (REC_CAPACITY - first);
    want += n1 * sizeof(RecSample);
    got  += f.write((const uint8_t*)&rec_ring[first], n1 * sizeof(RecSample));
    if (first != 0) {
        want += first * sizeof(RecSample);
        got  += f.write((const uint8_t*)&rec_ring[0], first * sizeof(RecSample));
    }
    f.close();
    if (got != want) {                              // card full, removed or failing: say so, and re-probe next time
        DBG_PRINTLN("REC: SD WRITE FAILED (card full or removed) - the recording is incomplete");
        sd_ok = false;
        diag_event(EV_SD_FAIL);
        return;
    }

    DBG_PRINT("REC: saved "); DBG_PRINT(rec_count); DBG_PRINT(" samples to "); DBG_PRINT(name);
    DBG_PRINT(" ("); DBG_PRINT(reason ? reason : ""); DBG_PRINT(") in "); DBG_PRINT(millis() - t0); DBG_PRINTLN(" ms");
}

// The diagnostics report -> SD card: RECnnnn.TXT beside the recording, or DIAGnnnn.TXT when nothing was recording.
// Called from trigger_shutdown() after every output is closed (and before any Ethernet recovery changes the chip).
DMAMEM static char diag_text[12000];
static void diag_dump(const char* reason) {
    if (!sd_try_begin()) { rec_last_file = 0; DBG_PRINTLN("DIAG: no SD card - report not written"); return; }
    char name[16];
    if (rec_last_file > 0) {
        snprintf(name, sizeof(name), "REC%04d.TXT", rec_last_file);
    } else {
        int n = 1;
        for (; n <= 9999; n++) {
            snprintf(name, sizeof(name), "DIAG%04d.TXT", n);
            if (!SD.exists(name)) break;
        }
    }
    rec_last_file = 0;
    size_t len = diag_build_text(diag_text, sizeof(diag_text), name, reason);
    File f = SD.open(name, FILE_WRITE);
    if (!f) return;
    size_t wrote = f.write((const uint8_t*)diag_text, len);
    f.close();
    if (wrote != len) { DBG_PRINTLN("DIAG: SD WRITE FAILED (card full or removed)"); sd_ok = false; diag_event(EV_SD_FAIL); return; }
    DBG_PRINT("DIAG: saved "); DBG_PRINTLN(name);
}

// ---- Ethernet link recovery ----
// On Nov 22 2026 an igniter transient knocked the Teensy's Ethernet PHY (DP83825I) offline while the
// CPU kept running: link LED dark, nothing got through until the Teensy was power-cycled.
// NativeEthernet never restarts the PHY on its own, and Ethernet.begin() can't be used to recover:
// it spins in while(!link_status){} and hangs the CPU forever if the link is down. So this resets
// the PHY directly and re-applies the two registers the Teensy core writes at boot (LEDCR, RCSR).
// A PHY reset only drops the link for the couple of seconds auto-negotiation takes.
// Runs from the abort loop only: a dead link trips CONNECTION_TIMEOUT in 200 ms, so by the time
// this runs, every valve is already closed.
const unsigned long ETH_RECOVER_AFTER_MS      = 1000;  // nothing received for this long -> reset the PHY
const unsigned long ETH_RECOVER_RETRY_MS      = 5000;  // retry interval (auto-negotiation needs ~2-3 s)
const uint32_t      ETH_HARD_RESET_EVERY      = 2;     // every 2nd attempt pulses the PHY's reset pin instead of an MDIO soft reset
const uint32_t      ETH_REBOOT_AFTER_ATTEMPTS = 6;     // still no link after this many -> reboot the Teensy (what fixed it in the field)
                                                       // only if the PHY reports link DOWN; 0 = never reboot
void safe_all_valves();   // defined below
uint32_t      eth_recover_attempts = 0;
unsigned long eth_last_recover_ms  = 0;

// MDIO access. NativeEthernet's FNET mutexes are no-ops and its poll interrupt also reads the PHY
// (link status), so block interrupts for the ~25 us of each MDIO frame to keep them from colliding.
static bool phy_read(uint32_t reg, uint16_t& val) {
    fnet_uint16_t v = 0;
    noInterrupts();
    fnet_return_t r = fnet_eth_phy_read(fnet_netif_get_default(), reg, &v);
    interrupts();
    val = v;
    return r == FNET_OK;
}
static bool phy_write(uint32_t reg, uint16_t val) {
    noInterrupts();
    fnet_return_t r = fnet_eth_phy_write(fnet_netif_get_default(), reg, val);
    interrupts();
    return r == FNET_OK;
}

void eth_phy_reset(bool hard) {
    uint16_t bmcr = 0, bmsr = 0, rcsr = 0, ledcr = 0;
    bool mdio_ok = phy_read(0x00, bmcr) & phy_read(0x01, bmsr) & phy_read(0x17, rcsr) & phy_read(0x18, ledcr);
    // Before-reset snapshot: RCSR != 0081 or LEDCR != 0280 means the PHY reset itself to defaults
    // (e.g. a brownout/transient), which leaves it on the wrong RMII clock and the link LED inverted.
    DBG_PRINT("[ETH] PHY "); DBG_PRINT(hard ? "HARD" : "soft"); DBG_PRINT(" reset #"); DBG_PRINT(eth_recover_attempts);
    DBG_PRINT(" | before: MDIO="); DBG_PRINT(mdio_ok ? "ok" : "FAIL");
    DBG_PRINT(" BMCR=0x"); DBG_PRINT(bmcr, HEX); DBG_PRINT(" BMSR=0x"); DBG_PRINT(bmsr, HEX);
    DBG_PRINT(" RCSR=0x"); DBG_PRINT(rcsr, HEX); DBG_PRINT(" LEDCR=0x"); DBG_PRINTLN(ledcr, HEX);

    if (hard) {
        // PHY reset line: GPIO_B0_14 = GPIO7 bit 14 (same pin the Teensy core pulses at boot).
        GPIO7_DR_CLEAR = (1 << 14);
        delayMicroseconds(100);
        GPIO7_DR_SET = (1 << 14);
        delay(10);
    } else {
        phy_write(0x00, 0x8000);                             // BMCR software reset
        unsigned long t0 = millis();
        while (millis() - t0 < 20) {                         // self-clears when done
            uint16_t v;
            if (phy_read(0x00, v) && !(v & 0x8000)) break;
        }
    }
    phy_write(0x18, 0x0280);                                 // LEDCR: LED shows link status, active high
    phy_write(0x17, 0x0081);                                 // RCSR: 50 MHz RMII reference clock input
    uint16_t cr = 0;
    phy_read(0x00, cr);
    phy_write(0x00, (cr | 0x1000 | 0x0200) & ~(0x0400 | 0x0800));   // auto-neg on + restart; not isolated / powered down
}

// Called on every pass of the abort loop. last_rx_ms = when the abort loop last received anything.
void eth_recovery_poll(unsigned long last_rx_ms) {
    unsigned long now = millis();
    if (now - last_rx_ms < ETH_RECOVER_AFTER_MS) { eth_recover_attempts = 0; return; }
    // Link UP but still nothing received after the full set of attempts = the PHY is fine and the
    // problem is on the laptop side (e.g. GUI closed), so back off instead of bouncing the link.
    bool exhausted = ETH_REBOOT_AFTER_ATTEMPTS > 0 && eth_recover_attempts >= ETH_REBOOT_AFTER_ATTEMPTS;
    unsigned long retry_ms = exhausted ? 30000UL : ETH_RECOVER_RETRY_MS;
    if (eth_recover_attempts > 0 && now - eth_last_recover_ms < retry_ms) return;

    if (exhausted && Ethernet.linkStatus() != LinkON) {
        DBG_PRINTLN("[ETH] PHY resets didn't bring the link back -> rebooting (all valves already closed)");
        safe_all_valves();
        delay(50);
        SCB_AIRCR = 0x05FA0004;                              // system reset
        while (1) {}
    }

    eth_recover_attempts++;
    eth_last_recover_ms = now;
    diag_event(EV_ETH_RECOVER, (uint8_t)eth_recover_attempts);
    eth_phy_reset(eth_recover_attempts % ETH_HARD_RESET_EVERY == 0);
}

void trigger_shutdown(const char* reason) {
    diag_event(EV_SHUTDOWN);
    DBG_PRINT("[TEENSY] Trigger Shutdown: ");
    DBG_PRINTLN(reason ? reason : "UNKNOWN");

    safe_all_valves();

    EGCPPacket sfe(next_tx_id(), EGCPPacket::PKT_SFE);
    send_packet(sfe);

    rec_dump(reason);   // flight recorder: if the GUI was recording, save what this board saw to the SD card
    diag_dump(reason);  // and always write the diagnostics report (reset cause, Ethernet chip registers, event log)

    // Clear the local parse buffer entirely before entering the loop
    egcp_rx_pos = 0; 
    memset(egcp_rx_buf, 0, sizeof(egcp_rx_buf));

    while (udp.parsePacket() > 0) { while (udp.available()) udp.read(); }

    bool aborted = true;
    unsigned long abort_last_rx_ms = millis();
    eth_recover_attempts = 0;
    while (aborted) {
        teensy_us();   // keep the 64-bit timestamp counter from missing a micros() wrap while parked here
        Ethernet.maintain();
        eth_recovery_poll(abort_last_rx_ms);   // bring a dead link back without a power cycle

        if ((micros() - ABORT_TIME_TRACKING) > ABORTED_TIME_INTERVAL) {
            ABORT_TIME_TRACKING = micros();
            DBG_PRINTLN("[TEENSY] ABORTED | Waiting for STA");
        }

        int pkt_sz = udp.parsePacket();
        if (pkt_sz > 0) {
            abort_last_rx_ms = millis();
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
                    diag_rx_ok++; diag_last_rx_type = rx.packet_type; diag_last_rx_us = teensy_us();
                    if (rx.packet_type == EGCPPacket::PKT_STA) {
                        diag_event(EV_STA);
                        DBG_PRINTLN("[TEENSY] STA received | Exiting abort state");
                        aborted = false;
                        
                        LAST_COMMUNICATION_TIME = micros();
                        LAST_HUMAN_UPDATE       = micros();
                        LAST_SENSOR_UPDATE      = micros();
                        LAST_LC_UPDATE          = micros();
                        
                        if (NCS2_PIN >= 0) digitalWrite(NCS2_PIN, LOW);
                        send_ack(rx.packet_id);
                        send_sd_status();
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
    // Valves / relays / igniters to a known OFF state before anything else. Ethernet.begin() below
    // blocks forever if there's no link, and until these are set the relay gate pins are floating.
    // (They're set again further down; that's harmless.)
    {
        const int boot_safe_pins[] = {BRAY_PWR_PIN, NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PNEUMA_PIN, BRAY_AUX_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, FP_1201_PIN, AP_1601_PIN, FV_1202_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
        for (int pin : boot_safe_pins) {
            if (pin >= 0) { digitalWrite(pin, LOW); pinMode(pin, OUTPUT); }
        }
    }
    diag_srsr = SRC_SRSR;                           // why the chip last reset (before anything can clear it)
    diag_event(EV_BOOT, 0, (uint16_t)diag_srsr);
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
            DBG_PRINTLN("  ** unpowered, ground reference wrong, or pins 16/17 not on the trunk.");
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

    rec_sd_init();   // flight recorder: SD card (boot only - never touched during a run)
    diag_boot_log(); // BOOTLOG.TXT: why this boot happened (reset cause, crash report)

    // ---- SPI for ADS7953 (PTs) - same init as the proven standalone sketch ----
    pinMode(ADS_CS_PIN, OUTPUT);
    digitalWrite(ADS_CS_PIN, HIGH);
    SPI.begin();
    ads_flush();            // prime the 2-frame pipeline so the first real scan is valid
    ads_boot_report();

    // ---- I2C for NAU7802 load cells (LC1-LC6, all muxed, hardware Wire1) ----
    // Group the installed load cells by chip, bring each chip up once, then report per load cell.
    lc_i2c_begin();
    lc_num_chips = 0;
    for (uint8_t ch = 0; ch < 6; ch++) {
        if (!LC_INSTALLED[ch]) {
            DBG_PRINT("LC"); DBG_PRINT(ch + 1); DBG_PRINTLN(" skipped (not installed)");
            continue;
        }
        int k = -1;
        for (uint8_t j = 0; j < lc_num_chips; j++) if (lc_chips[j].mux_ch == LC_MUX_CH[ch]) k = j;
        if (k < 0) {
            k = lc_num_chips++;
            lc_chips[k].mux_ch = LC_MUX_CH[ch];
            lc_chips[k].n = 0;
        }
        LcChip& c = lc_chips[k];
        if (c.n >= 2 || (c.n == 1 && LC_VIN[c.lc[0]] == LC_VIN[ch])) {
            DBG_PRINT("ERR: LC"); DBG_PRINT(ch + 1); DBG_PRINT(" uses the same JLC"); DBG_PRINT(c.mux_ch);
            DBG_PRINTLN(" input as another load cell - check LC_MUX_CH / LC_VIN; skipped");
            continue;
        }
        c.lc[c.n++] = ch;
    }
    for (uint8_t k = 0; k < lc_num_chips; k++) {
        LcChip& c = lc_chips[k];
        bool shared = (c.n == 2);
        uint8_t vins[2] = { LC_VIN[c.lc[0]], shared ? LC_VIN[c.lc[1]] : (uint8_t)0 };
        c.ok = lc_init_chip(c.mux_ch, shared ? LC_SHARED_RATE_BITS : LC_RATE_BITS, vins, c.n);
        c.cur = 0;
        c.t_switch = micros();
        for (uint8_t s = 0; s < c.n; s++) {
            uint8_t ch = c.lc[s];
            lc_ok[ch] = c.ok;
            lc_shared[ch] = shared;
            DBG_PRINT(c.ok ? "" : "WARN: ");
            DBG_PRINT("LC"); DBG_PRINT(ch + 1);
            DBG_PRINT(" (JLC"); DBG_PRINT(c.mux_ch); DBG_PRINT(" / "); DBG_PRINT(LC_CHIP_U[c.mux_ch & 7]);
            DBG_PRINT(" / mux ch"); DBG_PRINT(c.mux_ch); DBG_PRINT(" / VIN"); DBG_PRINT(LC_VIN[ch]);
            DBG_PRINT(shared ? ", shared, 320 SPS)" : ", 80 SPS)");
            DBG_PRINTLN(c.ok ? " ready" : " NAU7802 not responding - skipped");
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
        const int output_pins[] = {BRAY_PWR_PIN, NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PNEUMA_PIN, BRAY_AUX_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, FP_1201_PIN, AP_1601_PIN, FV_1202_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
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
    teensy_us();   // keep the 64-bit timestamp counter from missing a micros() wrap


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
        DBG_PRINT(" LC_rej="); DBG_PRINT(lc_rejected); lc_rejected = 0;
        bray_log_token();
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

    bray_power_poll();   // non-blocking finish of a pending Bray power-up; check every pass
    lc_shared_service(); // non-blocking VIN1/VIN2 alternation on NAU7802s that carry two load cells

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
                diag_rx_ok++; diag_last_rx_type = rx.packet_type; diag_last_rx_us = teensy_us();
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
                    diag_event(EV_STA);
                    LAST_COMMUNICATION_TIME = micros();
                    LAST_HUMAN_UPDATE = micros();
                    send_ack(rx.packet_id);
                    send_sd_status();                       // warns the operator if there is no SD card
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
#if IGN_AUTO_OFF
                            int ii = ign_index(vid);
                            if (ii >= 0) {
                                if (!ign_fire(ii)) DBG_PRINTLN("WARN: igniter NOT fired (shut-off timer unavailable)");
                            } else {
                                digitalWrite(pin, HIGH);
                            }
#else
                            digitalWrite(pin, HIGH);
#endif
                            diag_event(EV_VSO, vid);
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
#if IGN_AUTO_OFF
                            int ii = ign_index(vid);
                            if (ii >= 0) ign_cancel(ii);          // igniter off now + cancel its timer
#endif
                            digitalWrite(pin, LOW);
                            diag_event(EV_VSC, vid);
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
                            diag_event(EV_POS, aid, raw);
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

                // REC: the GUI's automatic recording started (1) / stopped (0)
                else if (rx.packet_type == EGCPPacket::PKT_REC) {
                    if (rx.body_length >= 1) {
                        if (rx.body[0]) rec_start(); else rec_stop();
                        send_ack(rx.packet_id);
                        send_sd_status();
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
                    diag_event(EV_SFE_RX);
                    trigger_shutdown("RX_SFE");
                    break;
                }
            } else {
                diag_rx_bad++; diag_event(EV_RX_BAD);
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
                if (!lc_ok[ch]) continue;
                if (lc_shared[ch]) {                    // averaged samples collected by lc_shared_service()
                    if (lc_acc_n[ch] > 0) {
                        double mean;
                        if (lc_window_mean(ch, mean)) {      // outliers thrown out; false = keep the previous count
                            lc_raw[ch] = (int32_t)llround(mean);
                            lc_raw_new[ch] = true;
                        }
                        lc_acc_n[ch] = 0;
                    }
                    continue;
                }
                int32_t raw;
                if (lc_read_raw(LC_MUX_CH[ch], raw)) {
                    lc_raw[ch] = raw;
                    lc_raw_new[ch] = true;
                }
            }
            for (uint8_t ch = 0; ch < 6; ch++) {                // raw counts to the GUI (it applies the P&ID calibration)
                if (lc_ok[ch] && lc_raw_new[ch]) { send_lc_raw(ch); lc_raw_new[ch] = false; }
            }
            lc_us_accum += micros() - t0;
        }

        diag_poll();    // Ethernet chip status for the event log and the recorder's link columns
        rec_sample();   // flight recorder (RAM only, nothing if the GUI isn't recording)

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
