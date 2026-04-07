import socket
import threading
import time
import struct
from PyQt5.QtCore import QObject, pyqtSignal

class EGCPPacket:
    """Elysium Ground Communications Protocol packet handler (Python version)"""
    
    # Packet type constants
    PKT_ACK = 0x0   # Acknowledge
    PKT_NCK = 0x1   # Not-Acknowledge
    PKT_HRT = 0x2   # Heartbeat
    PKT_VSO = 0x3   # Valve/Solenoid Open
    PKT_VSC = 0x4   # Valve/Solenoid Close
    PKT_GVS = 0x5   # Globe Valve Step
    PKT_BGP = 0x6   # Begin Gimbaling Program
    PKT_HGP = 0x7   # Halt Gimbaling Program
    PKT_SFE = 0x8   # Enter Safe Mode
    PKT_ADC = 0x9   # ADC Reading
    PKT_STA = 0xA   # Connection Start/Handshake
    
    # Sensor ID mapping
    SENSOR_MAP = {
        "P1": 0x01, "P2": 0x02, "P3": 0x03, "P4": 0x04, "P5": 0x05, "P6": 0x06,
        "P7": 0x07, "P8": 0x08,
        "TC1": 0x09, "TC2": 0x0A, "TC3": 0x0B,
        "LC1": 0x0C, "LC2": 0x0D, "LC3": 0x0E,
        "B1": 0x0F, "B2": 0x10,
    }
    
    def __init__(self, packet_id: int, packet_type: int, body: bytes = b''):
        self.packet_id = packet_id & 0xFFFFFF  # 24-bit packet ID
        self.packet_type = packet_type & 0xF   # 4-bit packet type
        self.body = body
        self.packet_length = len(body)         # 4-bit length in bytes (0-15)
    
    def encode(self) -> bytes:
        """Encode packet into binary format: 32-bit header + body"""
        # Build header: [24-bit ID][4-bit type][4-bit length]
        header = (self.packet_id << 8) | (self.packet_type << 4) | (self.packet_length & 0xF)
        # Pack as big-endian 32-bit integer
        packet = struct.pack('>I', header)
        return packet + self.body
    
    @staticmethod
    def decode(data: bytes) -> 'EGCPPacket':
        """Decode binary packet from bytes"""
        if len(data) < 4:
            raise ValueError("Packet too short")
        
        # Unpack header as big-endian 32-bit integer
        header = struct.unpack('>I', data[:4])[0]
        
        # Extract fields
        packet_id = (header >> 8) & 0xFFFFFF
        packet_type = (header >> 4) & 0xF
        packet_length = header & 0xF
        
        # Extract body
        body = data[4:4+packet_length] if packet_length > 0 else b''
        
        return EGCPPacket(packet_id, packet_type, body)

class VTComms(QObject):
    log_signal = pyqtSignal(str)
    valve_update_signal = pyqtSignal(str, bool)
    connected_signal = pyqtSignal(str)

    def __init__(self, port=8889, target_port=8888):
        super().__init__()
        self.local_port = port
        self.target_port = target_port
        self.target_ip = "127.0.0.1"
        self.sock = None
        self.running = False
        self.listen_thread = None
        self.heartbeat_thread = None
        self.auto_reply = True  # If true, reply to whoever sent the last packet
        self.last_addr = None
        self.heartbeat_enabled = True
        self.packet_id_counter = 1  # For outgoing packets
        
        # Per-valve failure simulation
        self.valve_failures = {
            0x01: False,  # NCS1
            0x02: False,  # NCS2
            0x03: False,  # NCS3
            0x04: False,  # NCS4
            0x05: False,  # NCS5
            0x06: False,  # NCS6
            0x10: False,  # LA-BV1
            0x11: False,  # LA-BV2
            0x20: False,  # GV-1
            0x21: False,  # GV-2
            0x30: False,  # IG1
            0x31: False,  # IG2
        }
        self.ack_enabled = {} # component_name -> bool

        self.sensor_data = {
            "P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0, "P5": 0.0, "P6": 0.0, "P7": 0.0, "P8": 0.0,
            "TC1": 0.0, "TC2": 0.0, "TC3": 0.0,
            "LC1": 0.0, "LC2": 0.0, "LC3": 0.0,
            "B1": 0.0, "B2": 0.0,
        }
        self.start_time = time.time()

    def start(self):
        if self.running:
            return
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("0.0.0.0", self.local_port))
            self.running = True
            
            self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
            self.listen_thread.start()
            
            self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop, daemon=True)
            self.heartbeat_thread.start()
            
            print(f"Started listening on port {self.local_port}")
            self.log_signal.emit(f"Started listening on port {self.local_port}")
            return True
        except Exception as e:
            print(f"Failed to start: {e}")
            self.log_signal.emit(f"Failed to start: {e}")
            return False

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()
            self.sock = None
        self.log_signal.emit("Stopped")

    def listen_loop(self):
        while self.running and self.sock:
            try:
                data, addr = self.sock.recvfrom(1024)
                
                # Try to parse as EGCP packet
                try:
                    pkt = EGCPPacket.decode(data)
                    
                    if self.auto_reply:
                        if self.last_addr != addr:
                            print(f"New client connected: {addr}")
                            self.log_signal.emit(f"New client connected: {addr}")
                            self.connected_signal.emit(f"{addr[0]}:{addr[1]}")
                        self.last_addr = addr
                    
                    # Handle packet types
                    if pkt.packet_type == EGCPPacket.PKT_STA:
                        # Connection start
                        self.log_signal.emit(f"RX: STA (start) packet ID {pkt.packet_id}")
                        self.send_ack(pkt.packet_id, addr)
                    
                    elif pkt.packet_type == EGCPPacket.PKT_VSO:
                        # Valve open
                        if len(pkt.body) >= 1:
                            valve_id = pkt.body[0]
                            self.log_signal.emit(f"RX: VSO (valve open) packet ID {pkt.packet_id}, valve 0x{valve_id:02X}")
                            self.handle_valve_command(valve_id, True, pkt.packet_id, addr)
                    
                    elif pkt.packet_type == EGCPPacket.PKT_VSC:
                        # Valve close
                        if len(pkt.body) >= 1:
                            valve_id = pkt.body[0]
                            self.log_signal.emit(f"RX: VSC (valve close) packet ID {pkt.packet_id}, valve 0x{valve_id:02X}")
                            self.handle_valve_command(valve_id, False, pkt.packet_id, addr)
                    
                    elif pkt.packet_type == EGCPPacket.PKT_HRT:
                        # Heartbeat - just acknowledge
                        # Don't log every heartbeat to reduce spam, but send ACK
                        if self.heartbeat_enabled:
                            self.send_ack(pkt.packet_id, addr)
                            
                    elif pkt.packet_type == EGCPPacket.PKT_ACK:
                        # Ignore ACKs to prevent log spam
                        pass
                        
                    else:
                        self.log_signal.emit(f"RX: Packet type {pkt.packet_type} (ID: {pkt.packet_id})")
                
                except ValueError as e:
                    self.log_signal.emit(f"Invalid packet: {e}")

            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                    self.log_signal.emit(f"Receive error: {e}")

    def set_heartbeat_enabled(self, enabled):
        self.heartbeat_enabled = enabled
        self.log_signal.emit(f"Heartbeat {'enabled' if enabled else 'disabled'}")
    
    def set_valve_failure(self, valve_id, enabled):
        """Enable/disable failure simulation for a specific valve"""
        if valve_id in self.valve_failures:
            self.valve_failures[valve_id] = enabled
            valve_name = self.get_valve_name(valve_id)
            self.log_signal.emit(f"{'FAIL' if enabled else 'OK'}: {valve_name} failure mode {'ENABLED' if enabled else 'disabled'}")

    def set_ack_enabled(self, name, enabled):
        self.ack_enabled[name] = enabled
        self.log_signal.emit(f"ACK for {name} {'enabled' if enabled else 'disabled'}")

    def heartbeat_loop(self):
        last_sensor_time = 0
        while self.running:
            try:
                current_time = time.time()
                
                # Send HRT (heartbeat) every 10ms if enabled
                if self.heartbeat_enabled and self.last_addr:
                    pkt = EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_HRT)
                    self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
                    self.sock.sendto(pkt.encode(), self.last_addr)
                
                # Send sensor data every 100ms
                if current_time - last_sensor_time >= 0.1:
                    self.send_sensors()
                    last_sensor_time = current_time
                
                # Wait 10ms
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    print(f"Heartbeat error: {e}")
                    self.log_signal.emit(f"Heartbeat error: {e}")
                time.sleep(1)

    def handle_valve_command(self, valve_id, is_open, cmd_packet_id, addr):
        """Handle valve open/close command"""
        valve_name = self.get_valve_name(valve_id)
        
        # Simulate failure: Drop the command and don't send ACK if this valve is in failure mode
        if self.valve_failures.get(valve_id, False):
            self.log_signal.emit(f"SIMULATING FAILURE: {valve_name} (packet {cmd_packet_id}) - NO ACK SENT")
            return
        
        self.valve_update_signal.emit(valve_name, is_open)
        self.send_ack(cmd_packet_id, addr)
        self.log_signal.emit(f"✓ {valve_name} -> {'OPEN' if is_open else 'CLOSED'}")

    def get_valve_name(self, valve_id: int) -> str:
        """Convert valve ID to name"""
        valve_names = {
            0x01: "NCS1", 0x02: "NCS2", 0x03: "NCS3", 0x04: "NCS4", 0x05: "NCS5", 0x06: "NCS6",
            0x10: "LA-BV1", 0x11: "LA-BV2",
            0x20: "GV-1", 0x21: "GV-2",
            0x30: "IG1", 0x31: "IG2",
        }
        return valve_names.get(valve_id, f"VALVE_{valve_id:02X}")

    def send_ack(self, cmd_packet_id, addr=None):
        """Send ACK packet"""
        # ACK body must contain the referenced packet ID (3 bytes)
        body = struct.pack('>I', cmd_packet_id)[1:]
        pkt = EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_ACK, body)
        self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
        target = addr if addr else self.last_addr
        if target and self.sock:
            self.sock.sendto(pkt.encode(), target)

    def send_sensors(self):
        """Send ADC (sensor) readings as EGCP packets"""
        if not self.last_addr or not self.sock:
            return
        
        # Filter out NULL values and string placeholders
        active_sensors = [(name, val) for name, val in self.sensor_data.items() if val != "NULL" and name in EGCPPacket.SENSOR_MAP]
        
        # Send in groups of 3 (5 bytes per sensor = 15 bytes per packet)
        for i in range(0, len(active_sensors)):
            body = b''
            for sensor_name, sensor_value in active_sensors[i:i+3]:
                sensor_id = EGCPPacket.SENSOR_MAP.get(sensor_name, 0x00)
                # Pack as: 1-byte sensor ID + 4-byte IEEE 754 float
                try:
                    body += bytes([sensor_id]) + struct.pack('>f', float(sensor_value))
                except (ValueError, TypeError):
                    continue
            
            pkt = EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_ADC, body)
            self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
            
            try:
                self.sock.sendto(pkt.encode(), self.last_addr)
            except Exception as e:
                self.log_signal.emit(f"Send error: {e}")

    def update_sensor(self, name, value):
        if name in self.sensor_data:
            self.sensor_data[name] = value

