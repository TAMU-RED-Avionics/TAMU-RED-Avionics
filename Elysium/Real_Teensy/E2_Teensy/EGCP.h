#pragma once

#include <Arduino.h>
#include <cstring>

/*
 * Elysium Ground Communications Protocol (EGCP)
 * Binary packet format for Teensy <-> GUI communication
 * 
 * Header (4 bytes): [24-bit packet ID][4-bit type][4-bit length]
 * Body (0-15 bytes): Variable length data
 */

class EGCPPacket {
public:
    // Packet type constants
    static constexpr uint8_t PKT_ACK = 0x0;   // Acknowledge
    static constexpr uint8_t PKT_NCK = 0x1;   // Not-Acknowledge
    static constexpr uint8_t PKT_HRT = 0x2;   // Heartbeat
    static constexpr uint8_t PKT_VSO = 0x3;   // Valve/Solenoid Open
    static constexpr uint8_t PKT_VSC = 0x4;   // Valve/Solenoid Close
    static constexpr uint8_t PKT_GVS = 0x5;   // Globe Valve Step
    static constexpr uint8_t PKT_BGP = 0x6;   // Begin Gimbaling Program
    static constexpr uint8_t PKT_HGP = 0x7;   // Halt Gimbaling Program
    static constexpr uint8_t PKT_SFE = 0x8;   // Enter Safe Mode (Emergency Abort)
    static constexpr uint8_t PKT_ADC = 0x9;   // ADC Reading (sensor data)
    static constexpr uint8_t PKT_STA = 0xA;   // Connection Start/Handshake

    // Valve ID mapping (1-byte IDs)
    static constexpr uint8_t VALVE_NCS1 = 0x01;
    static constexpr uint8_t VALVE_NCS2 = 0x02;
    static constexpr uint8_t VALVE_NCS3 = 0x03;
    static constexpr uint8_t VALVE_NCS4 = 0x04;
    static constexpr uint8_t VALVE_NCS5 = 0x05;
    static constexpr uint8_t VALVE_NCS6 = 0x06;
    static constexpr uint8_t VALVE_LA_BV1 = 0x10;
    static constexpr uint8_t VALVE_LA_BV2 = 0x11;
    static constexpr uint8_t VALVE_GV_1 = 0x20;
    static constexpr uint8_t VALVE_GV_2 = 0x21;
    static constexpr uint8_t VALVE_GV1 = VALVE_GV_1; // Backward-compatible alias
    static constexpr uint8_t VALVE_GV2 = VALVE_GV_2; // Backward-compatible alias
    static constexpr uint8_t VALVE_IG1 = 0x30;
    static constexpr uint8_t VALVE_IG2 = 0x31;
    static constexpr uint8_t VALVE_GIMBAL = 0x40;

    // Sensor ID mapping (1-byte IDs)
    static constexpr uint8_t SENSOR_P1 = 0x01;
    static constexpr uint8_t SENSOR_P2 = 0x02;
    static constexpr uint8_t SENSOR_P3 = 0x03;
    static constexpr uint8_t SENSOR_P4 = 0x04;
    static constexpr uint8_t SENSOR_P5 = 0x05;
    static constexpr uint8_t SENSOR_P6 = 0x06;
    static constexpr uint8_t SENSOR_P7 = 0x07;
    static constexpr uint8_t SENSOR_P8 = 0x08;
    static constexpr uint8_t SENSOR_TC1 = 0x09;
    static constexpr uint8_t SENSOR_TC2 = 0x0A;
    static constexpr uint8_t SENSOR_TC3 = 0x0B;
    static constexpr uint8_t SENSOR_L1 = 0x0C;
    static constexpr uint8_t SENSOR_L2 = 0x0D;
    static constexpr uint8_t SENSOR_L3 = 0x0E;
    static constexpr uint8_t SENSOR_T1 = SENSOR_TC1; // Backward-compatible alias

    uint32_t packet_id;     // 24-bit packet ID (wraparound at 2^24)
    uint8_t packet_type;    // 4-bit packet type
    uint8_t body_length;    // 4-bit body length (0-15 bytes)
    uint8_t body[15];       // Variable body data

    EGCPPacket() : packet_id(0), packet_type(0), body_length(0) {}
    
    EGCPPacket(uint32_t id, uint8_t type, const uint8_t* data = nullptr, uint8_t len = 0)
        : packet_id(id & 0xFFFFFF), packet_type(type & 0xF), body_length(len & 0xF) {
        if (data && len > 0) {
            memcpy(body, data, len);
        }
    }

    // Encode packet to binary format
    // Returns number of bytes written to buffer
    uint8_t encode(uint8_t* buffer, uint8_t max_len) const {
        if (max_len < 4 + body_length) {
            return 0; // Buffer too small
        }

        // Build 32-bit header: [24-bit ID][4-bit type][4-bit length]
        uint32_t header = (packet_id << 8) | (packet_type << 4) | (body_length & 0xF);
        
        // Write header as big-endian
        buffer[0] = (header >> 24) & 0xFF;
        buffer[1] = (header >> 16) & 0xFF;
        buffer[2] = (header >> 8) & 0xFF;
        buffer[3] = header & 0xFF;

        // Write body
        if (body_length > 0) {
            memcpy(buffer + 4, body, body_length);
        }

        return 4 + body_length;
    }

    // Decode packet from binary buffer
    // Returns true if successful, false if buffer is incomplete or invalid
    static bool decode(const uint8_t* buffer, uint8_t buffer_len, EGCPPacket& out_packet) {
        if (buffer_len < 4) {
            return false; // Not enough data for header
        }

        // Parse header as big-endian
        uint32_t header = ((uint32_t)buffer[0] << 24) | 
                          ((uint32_t)buffer[1] << 16) | 
                          ((uint32_t)buffer[2] << 8) | 
                          buffer[3];

        // Extract fields
        out_packet.packet_id = (header >> 8) & 0xFFFFFF;
        out_packet.packet_type = (header >> 4) & 0xF;
        out_packet.body_length = header & 0xF;

        uint8_t total_packet_size = 4 + out_packet.body_length;
        if (buffer_len < total_packet_size) {
            return false; // Incomplete packet
        }

        // Extract body
        if (out_packet.body_length > 0) {
            memcpy(out_packet.body, buffer + 4, out_packet.body_length);
        }

        return true;
    }

    // Get total packet size
    uint8_t getTotalSize() const {
        return 4 + body_length;
    }
};
