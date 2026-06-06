/*
-------------------------------------------------------------------
VARIABLES & USER INPUT
-------------------------------------------------------------------
*/

#include <Arduino.h>
#include "EGCP.h"

#define SERIAL_DEBUG 1

#if defined(ARDUINO) && SERIAL_DEBUG
  #define DBG_PRINTLN(x) Serial.println(x)
  #define DBG_PRINT(x)   Serial.print(x)
#else
  #define DBG_PRINTLN(x)
  #define DBG_PRINT(x)
#endif


const long unsigned SENSOR_UPDATE_INTERVAL     = 1000;          // <-- USER INPUT       sensor update interval (microsec)
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
long unsigned ABORT_TIME_TRACKING              = 0;


// BAUD rate 
const int BAUD = 115200;                                        // serial com in bits per second

// Valves / Solenoids
const int NCS1_PIN   = -1;    // <-- USER INPUT
const int NCS2_PIN   = -1;    // <-- USER INPUT (vent line — HIGH = open/vent)
const int NCS3_PIN   = -1;    // <-- USER INPUT
// NCS4 is a manual switch
const int NCS5_PIN   = -1;    // <-- USER INPUT
const int PA_BV3_PIN = -1;    // <-- USER INPUT (was NCS6)
const int PA_BV1_PIN = -1;    // <-- USER INPUT (was LA-BV1; special: open triggers purge-on-close logic)
const int PA_BV2_PIN = -1;    // <-- USER INPUT (was LA-BV2)
const int GV1_PIN    = -1;    // <-- USER INPUT
const int GV2_PIN    = -1;    // <-- USER INPUT
const int GIMBAL_PIN = -1;    // <-- USER INPUT

// Igniters
const int IGN1_PIN   = -1;    // <-- USER INPUT
const int IGN2_PIN   = -1;    // <-- USER INPUT

const int PT1_PIN    = -1;    // <-- USER INPUT
const int PT2_PIN    = -1;    // <-- USER INPUT
const int PT3_PIN    = -1;    // <-- USER INPUT
const int PT4_PIN    = -1;    // <-- USER INPUT
const int PT5_PIN    = -1;    // <-- USER INPUT
const int PT6_PIN    = -1;    // <-- USER INPUT
const int PT7_PIN    = -1;    // <-- USER INPUT
const int PT8_PIN    = -1;    // <-- USER INPUT

// Load Cells
const int LC1_DOUT   = -1;    // <-- USER INPUT
const int LC1_CLK    = -1;    // <-- USER INPUT

const int LC2_DOUT   = -1;    // <-- USER INPUT
const int LC2_CLK    = -1;    // <-- USER INPUT

const int LC3_DOUT   = -1;    // <-- USER INPUT
const int LC3_CLK    = -1;    // <-- USER INPUT

const int LC4_DOUT   = -1;    // <-- USER INPUT
const int LC4_CLK    = -1;    // <-- USER INPUT

const int LC5_DOUT   = -1;    // <-- USER INPUT
const int LC5_CLK    = -1;    // <-- USER INPUT


const float pt_slope[]     = {2.0161f, 2.0161f, 2.0161f, 2.0161f,      // PT1-4: 0-1500 psi
                                2.0161f, 2.0161f,                       // PT5-6: 0-1500 psi
                                1.3441f, 1.3441f };                     // PT7-8: 0-1000 psi

const float pt_intercept[] = {-375.0f, -375.0f, -375.0f, -375.0f,      // PT1-4
                                -375.0f, -375.0f,                       // PT5-6
                                -250.0f, -250.0f};                     // PT7-8

inline float pressureCalculation(int raw, int channel) {
    return pt_slope[channel] * raw + pt_intercept[channel];
}


#include <NativeEthernet.h>
#include <NativeEthernetUdp.h>
#include <IPAddress.h>
#include "HX711.h"
#include <Wire.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_I2CRegister.h>
#include <Adafruit_MCP9600.h>


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

HX711 lc1, lc2, lc3, lc4, lc5;
float lc1_weight = 0.0f;
float lc2_weight = 0.0f;
float lc3_weight = 0.0f;
float lc4_weight = 0.0f;
float lc5_weight = 0.0f;


// Thermocouple I2C addresses - Default I2C addresses for MCP9600 are 0x60–0x67 (set by ADDR pin strapping).
#define TC1_I2C_ADDR  0x67    // <-- USER INPUT  (match board address strapping)
#define TC2_I2C_ADDR  0x66    // <-- USER INPUT
#define TC3_I2C_ADDR  0x65    // <-- USER INPUT
#define STRINGIFY(x) #x
#define TOSTRING(x) STRINGIFY(x)

Adafruit_MCP9600 tc1_sensor;
Adafruit_MCP9600 tc2_sensor;
Adafruit_MCP9600 tc3_sensor;

bool tc1_ok = false;
bool tc2_ok = false;
bool tc3_ok = false;

// bool is_PABV1_open = false;     // tracks PA-BV1 open/closed for purge-on-close logic

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
    IPAddress dst_ip   = active_remote_valid ? ACTIVE_REMOTE : REMOTE_IP;
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

// Function to get pin number from EGCP valve ID
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

// Get valve name from ID (for logging)
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

// Shutdown procedure - triggered by timeout or emergency abort
void trigger_shutdown(const char* reason) {
    DBG_PRINT("[TEENSY] Trigger Shutdown: ");
    DBG_PRINTLN(reason ? reason : "UNKNOWN");

    // Safe valve configuration: vent via NCS2, everything else closed
    digitalWrite(NCS2_PIN, HIGH);           // Open vent
    digitalWrite(NCS1_PIN, LOW);
    digitalWrite(NCS3_PIN, LOW);
    digitalWrite(NCS5_PIN, LOW);
    digitalWrite(PA_BV3_PIN, LOW);
    digitalWrite(PA_BV1_PIN, LOW);
    digitalWrite(PA_BV2_PIN, LOW);
    digitalWrite(GV1_PIN, LOW);
    digitalWrite(GV2_PIN, LOW);
    digitalWrite(IGN1_PIN, LOW);
    digitalWrite(IGN2_PIN, LOW);
    digitalWrite(GIMBAL_PIN, LOW);

    // PA-BV1 close purge: if PA-BV1 was open, momentarily open NCS4 to purge propellant lines
    /*if (is_PABV1_open) {
        DBG_PRINTLN("[E2] PA-BV1 purge sequence");           NCS4 is a manual valve.
        digitalWrite(NCS4_PIN, HIGH);
        delay(SHUTDOWN_PURGE_TIME);
        digitalWrite(NCS4_PIN, LOW);
        is_PABV1_open = false;
    }*/

    // Try to notify GUI we are in abort state
    EGCPPacket sfe(next_tx_id(), EGCPPacket::PKT_SFE);
    send_packet(sfe);

    // Spin waiting for STA (restart handshake) from GUI
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
                uint8_t  body_len   = egcp_rx_buf[3] & 0xF;
                uint16_t total_sz   = 4 + body_len;
                if (egcp_rx_pos < total_sz) break;

                EGCPPacket rx;
                if (EGCPPacket::decode(egcp_rx_buf, total_sz, rx)) {
                    if (rx.packet_type == EGCPPacket::PKT_STA) {
                        DBG_PRINTLN("[TEENSY] STA received | Exiting abort state");
                        aborted = false;
                        LAST_COMMUNICATION_TIME = micros();
                        LAST_HUMAN_UPDATE       = micros();
                        digitalWrite(NCS2_PIN, LOW);    // Close vent after restart confirmed
                        send_ack(rx.packet_id);
                        egcp_rx_pos = 0;
                        break;
                    }
                    // Ignore everything else while aborted
                }

                memmove(egcp_rx_buf, egcp_rx_buf + total_sz, egcp_rx_pos - total_sz);
                egcp_rx_pos -= total_sz;
            }
        }
    }
    egcp_rx_pos = 0;
    // Brief pause then discard one more round of anything queued
    delay(100);
    while (udp.parsePacket() > 0) {
        while (udp.available()) udp.read();
    }
    DBG_PRINTLN("[TEENSY] Exited abort state, returning to main loop");
}

bool init_comms(byte* mac, unsigned int port) {
    IPAddress GATEWAY(192, 168, 1, 1);   // there is no router, so this is meaningless 
    IPAddress SUBNET(255, 255, 255, 0);  // could be almost anything else tbh
    Ethernet.begin(mac, LOCAL_IP, GATEWAY, SUBNET);
    if (Ethernet.hardwareStatus() == EthernetNoHardware) {
        DBG_PRINTLN("[TEENSY] ERR: No Ethernet hardware");
        return false;
    }
    if (Ethernet.linkStatus() == LinkOFF) {
        DBG_PRINTLN("[TEENSY] ERR: Ethernet cable disconnected");
        return false;
    }
    udp.begin(port);
    DBG_PRINT("[TEENSY] UDP listening on port "); DBG_PRINTLN(port);
    return true;
}

void setup() {
#if defined(ARDUINO)
    Serial.begin(BAUD);
    delay(50);
#endif

    DBG_PRINTLN("Booting E2 Teensy firmware");

    // ---- Comms ----
    init_comms(MAC_ADDRESS, UDP_PORT);
    LAST_COMMUNICATION_TIME = micros();
    LAST_HUMAN_UPDATE       = micros();

    Wire.begin();

    // ---- Valve / Actuator Pins ----
    const int output_pins[] = {NCS1_PIN, NCS2_PIN, NCS3_PIN, NCS5_PIN, PA_BV3_PIN, PA_BV1_PIN, PA_BV2_PIN, GV1_PIN, GV2_PIN, IGN1_PIN, IGN2_PIN, GIMBAL_PIN};
    for (int pin : output_pins) {
        if (pin > -1) pinMode(pin, OUTPUT);
    }
    DBG_PRINTLN("Valve pins initialized");

    // ---- Load Cells ----
    lc1.begin(LC1_DOUT, LC1_CLK);
    lc2.begin(LC2_DOUT, LC2_CLK);
    lc3.begin(LC3_DOUT, LC3_CLK);
    lc4.begin(LC4_DOUT, LC4_CLK);
    lc5.begin(LC5_DOUT, LC5_CLK);

    lc1.set_scale(-3980.0f);    // <-- USER INPUT (calibration factor)
    lc2.set_scale(-3880.0f);    // <-- USER INPUT
    lc3.set_scale(-3780.0f);    // <-- USER INPUT
    lc4.set_scale(-3680.0f);    // <-- USER INPUT
    lc5.set_scale(-3580.0f);    // <-- USER INPUT


    lc1.wait_ready_timeout(500) ? DBG_PRINTLN("LC1 ready") : DBG_PRINTLN("WARN: LC1 not ready");
    lc2.wait_ready_timeout(500) ? DBG_PRINTLN("LC2 ready") : DBG_PRINTLN("WARN: LC2 not ready");
    lc3.wait_ready_timeout(500) ? DBG_PRINTLN("LC3 ready") : DBG_PRINTLN("WARN: LC3 not ready");
    lc4.wait_ready_timeout(500) ? DBG_PRINTLN("LC4 ready") : DBG_PRINTLN("WARN: LC4 not ready");
    lc5.wait_ready_timeout(500) ? DBG_PRINTLN("LC5 ready") : DBG_PRINTLN("WARN: LC5 not ready");
    DBG_PRINTLN("Load cell init complete (no tare in setup to avoid blocking)");

    // ---- Thermocouples (MCP9600 via I2C) ----
    // If a sensor is absent, tc_ok stays false and we transmit 0.0 as a sentinel.
    tc1_ok = tc1_sensor.begin(TC1_I2C_ADDR);
    if (tc1_ok) {
        tc1_sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
        tc1_sensor.setThermocoupleType(MCP9600_TYPE_K);
        tc1_sensor.setFilterCoefficient(3);
        tc1_sensor.enable(true);
        DBG_PRINTLN("TC1 ready");
    } else {
        DBG_PRINTLN("WARN: TC1 not found at I2C addr " TOSTRING(TC1_I2C_ADDR));
    }

    tc2_ok = tc2_sensor.begin(TC2_I2C_ADDR);
    if (tc2_ok) {
        tc2_sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
        tc2_sensor.setThermocoupleType(MCP9600_TYPE_K);
        tc2_sensor.setFilterCoefficient(3);
        tc2_sensor.enable(true);
        DBG_PRINTLN("TC2 ready");
    } else {
        DBG_PRINTLN("WARN: TC2 not found at I2C addr " TOSTRING(TC2_I2C_ADDR));
    }

    tc3_ok = tc3_sensor.begin(TC3_I2C_ADDR);
    if (tc3_ok) {
        tc3_sensor.setADCresolution(MCP9600_ADCRESOLUTION_18);
        tc3_sensor.setThermocoupleType(MCP9600_TYPE_K);
        tc3_sensor.setFilterCoefficient(3);
        tc3_sensor.enable(true);
        DBG_PRINTLN("TC3 ready");
    } else {
        DBG_PRINTLN("WARN: TC3 not found at I2C addr " TOSTRING(TC3_I2C_ADDR));
    }

    DBG_PRINTLN("Setup complete | Entering main loop");
}

void loop() {
    // ---- Periodic debug heartbeat ----
    unsigned long now_ms = millis();
    if (now_ms - last_loop_log_ms >= 1000) {
        last_loop_log_ms = now_ms;
        DBG_PRINT("Loop alive; peer=");
        if (active_remote_valid) {
            DBG_PRINT(ACTIVE_REMOTE[0]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[1]); DBG_PRINT('.');
            DBG_PRINT(ACTIVE_REMOTE[2]); DBG_PRINT('.'); DBG_PRINT(ACTIVE_REMOTE[3]);
            DBG_PRINT(':'); DBG_PRINTLN(ACTIVE_REMOTE_PORT);
        } else {
            DBG_PRINTLN("none");
        }
    }

    // Read incoming packets
    int pkt_sz = udp.parsePacket();
    if (pkt_sz > 0) {
        // Capture dynamic remote address so we can reply to whoever sent us a packet
        ACTIVE_REMOTE      = udp.remoteIP();
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
            uint8_t  body_len  = egcp_rx_buf[3] & 0xF;
            uint16_t total_sz  = 4 + body_len;
            if (egcp_rx_pos < total_sz) break;

            EGCPPacket rx;
            if (EGCPPacket::decode(egcp_rx_buf, total_sz, rx)) {

                // ---- STA: connection handshake ----
                if (rx.packet_type == EGCPPacket::PKT_STA) {
                    DBG_PRINTLN("STA received -> ACK");
                    send_ack(rx.packet_id);
                }

                // ---- HRT: heartbeat ----
                else if (rx.packet_type == EGCPPacket::PKT_HRT) {
                    heartbeat_rx_count++;
                    send_ack(rx.packet_id);
                }

                // ---- VSO: open a valve ----
                else if (rx.packet_type == EGCPPacket::PKT_VSO) {
                    if (rx.body_length >= 1) {
                        uint8_t vid = rx.body[0];
                        int     pin = get_pin_from_valve_id(vid);
                        if (pin > 0) {
                            digitalWrite(pin, HIGH);
                            DBG_PRINT("VSO "); DBG_PRINT(get_valve_name(vid));
                            DBG_PRINT(" pin="); DBG_PRINTLN(pin);

                            //if (vid == 0x10) is_PABV1_open = true;   // PA-BV1 tracking

                            LAST_HUMAN_UPDATE = micros();
                        } else {
                            DBG_PRINT("VSO unknown valve id="); DBG_PRINTLN(vid);
                        }
                        send_ack(rx.packet_id);
                    }
                }

                // ---- VSC: close a valve ----
                else if (rx.packet_type == EGCPPacket::PKT_VSC) {
                    if (rx.body_length >= 1) {
                        uint8_t vid = rx.body[0];
                        int     pin = get_pin_from_valve_id(vid);
                        if (pin > 0) {
                            // PA-BV1 close: if it was open, vent via NCS2 before fully closing
                            //if (vid == 0x10 && is_PABV1_open) {
                            //    digitalWrite(NCS2_PIN, HIGH);
                            //}

                            digitalWrite(pin, LOW);
                            DBG_PRINT("VSC "); DBG_PRINT(get_valve_name(vid));
                            DBG_PRINT(" pin="); DBG_PRINTLN(pin);

                            //if (vid == 0x10) is_PABV1_open = false;

                            LAST_HUMAN_UPDATE = micros();
                        } else {
                            DBG_PRINT("VSC unknown valve id="); DBG_PRINTLN(vid);
                        }
                        send_ack(rx.packet_id);
                    }
                }

                // ---- SFE: emergency abort from GUI ----
                else if (rx.packet_type == EGCPPacket::PKT_SFE) {
                    DBG_PRINTLN("SFE from GUI");
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

        // ---- Pressure Transducers (P1–P8, sensor IDs 0x01–0x08) ----
        const int pt_pins[8] = { PT1_PIN, PT2_PIN, PT3_PIN, PT4_PIN, PT5_PIN, PT6_PIN, PT7_PIN, PT8_PIN };
        for (int i = 0; i < 8; i++) {
            float psi = (pt_pins[i] > 0) ? pressureCalculation(analogRead(pt_pins[i]), i) : 0.0f;
            send_adc_packet(0x01 + i, psi);
        }

        // ---- Thermocouples (TC1–TC3, sensor IDs 0x09–0x0B) ----
        float tc1_temp = tc1_ok ? tc1_sensor.readThermocouple() : 0.0f;
        float tc2_temp = tc2_ok ? tc2_sensor.readThermocouple() : 0.0f;
        float tc3_temp = tc3_ok ? tc3_sensor.readThermocouple() : 0.0f;
        send_adc_packet(0x09, tc1_temp);
        send_adc_packet(0x0A, tc2_temp);
        send_adc_packet(0x0B, tc3_temp);

        // ---- Load Cells (LC1–LC3, sensor IDs 0x0C–0x0E) ----
        if ((LAST_SENSOR_UPDATE - LAST_LC_UPDATE) > LC_UPDATE_INTERVAL) {
            LAST_LC_UPDATE = LAST_SENSOR_UPDATE;

            if (lc1.is_ready()) lc1_weight = lc1.get_units(1);
            if (lc2.is_ready()) lc2_weight = lc2.get_units(1);
            if (lc3.is_ready()) lc3_weight = lc3.get_units(1);
            if (lc4.is_ready()) lc4_weight = lc4.get_units(1);
            if (lc5.is_ready()) lc5_weight = lc5.get_units(1);
        }
        send_adc_packet(0x0C, lc1_weight);
        send_adc_packet(0x0D, lc2_weight);
        send_adc_packet(0x0E, lc3_weight);
        send_adc_packet(0x0F, lc4_weight);
        send_adc_packet(0x10, lc5_weight);

        /*// ---- Battery Voltage (B1, B2 — sensor IDs 0x0F, 0x10) ----
        // The E2 board routes battery sense through the jumper-select headers (J24-J56)
        // to analog inputs. Values below are raw-to-voltage placeholders; update
        // the scale factor once the resistor divider values are known from the schematic.
        float b1_volts = (BAT1_PIN > 0) ? (analogRead(BAT1_PIN) * (3.3f / 1023.0f)) : 0.0f;
        float b2_volts = (BAT2_PIN > 0) ? (analogRead(BAT2_PIN) * (3.3f / 1023.0f)) : 0.0f;
        send_adc_packet(0x11, b1_volts);
        send_adc_packet(0x12, b2_volts);*/

        delay(1);   // brief yield to prevent starving UDP receive on heavy TX bursts
    }

    // Lost communication shutdown
    if ((micros() - LAST_COMMUNICATION_TIME) > CONNECTION_TIMEOUT) {
        trigger_shutdown("CONNECTION_TIMEOUT");
    }
    if ((micros() - LAST_HUMAN_UPDATE) > HUMAN_CONNECTION_TIMEOUT) {
        trigger_shutdown("HUMAN_TIMEOUT");
    }
}