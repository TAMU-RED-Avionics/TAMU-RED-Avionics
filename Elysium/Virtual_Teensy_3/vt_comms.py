import socket
import threading
import time
import struct
from PyQt5.QtCore import QObject, pyqtSignal


class EGCPPacket:
    """Elysium Ground Communications Protocol packet handler"""
    
    # packet type constants
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
    
    # Valve ID mapping (same as GUI)
    VALVE_MAP = {
        0x01: 'NCS1', 0x02: 'NCS2', 0x03: 'NCS3', 0x04: 'NCS4',
        0x05: 'NCS5', 0x06: 'NCS6', 0x10: 'LA-BV1', 0x11: 'LA-BV2',
        0x20: 'GV-1', 0x21: 'GV-2', 0x30: 'IG1', 0x31: 'IG2',
    }
    
    # Sensor name to ID mapping (reverse of GUI SENSOR_MAP)
    SENSOR_MAP = {
        'P1': 0x01, 'P2': 0x02, 'P3': 0x03, 'P4': 0x04,
        'P5': 0x05, 'P6': 0x06, 'T1': 0x07, 'L1': 0x08,
        'L2': 0x09, 'L3': 0x0A,
    }
    
    def __init__(self, packet_id: int, packet_type: int, body: bytes = b''):
        self.packet_id = packet_id & 0xFFFFFF  # 24-bit packet ID
        self.packet_type = packet_type & 0xF   # 4-bit packet type
        self.body = body
        self.packet_length = len(body)         # 4-bit length in bytes (0-15)
    
    def encode(self) -> bytes:
        """Encode packet into binary format with 32-bit header + body"""
        # Build header: [24-bit ID][4-bit type][4-bit length]
        header = (self.packet_id << 8) | (self.packet_type << 4) | (self.packet_length & 0xF)
        # Pack as big-endian 32-bit integer
        packet = struct.pack('>I', header)
        return packet + self.body
    
    @staticmethod
    def decode(data: bytes):
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
    
    def __repr__(self):
        type_names = {0: 'ACK', 1: 'NCK', 2: 'HRT', 3: 'VSO', 4: 'VSC', 
                      5: 'GVS', 6: 'BGP', 7: 'HGP', 8: 'SFE', 9: 'ADC', 10: 'START'}
        type_name = type_names.get(self.packet_type, f'UNK({self.packet_type})')
        return f"EGCPPacket(id={self.packet_id}, type={type_name}, len={self.packet_length})"


class VTComms(QObject):
    log_signal = pyqtSignal(str)
    valve_update_signal = pyqtSignal(str, bool)
    connected_signal = pyqtSignal(str)

    def __init__(self, port=8888, target_port=8888):
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

        # EGCP packet tracking
        self.tx_packet_id = 0  # Transmit packet ID counter
        self.binary_buffer = b""  # Buffer for binary packet parsing

        self.sensor_data = {
            "P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0, "P5": 0.0, "P6": 0.0, "P7": 0.0, "P8": 0.0,
            "TC1": 0.0, "TC2": 0.0, "TC3": 0.0,
            "LC1": 0.0, "LC2": 0.0, "LC3": 0.0,
            "B1": 0.0, "B2": 0.0
        }
        self.start_time = time.time()
    
    def _get_next_tx_id(self) -> int:
        """Get next transmit packet ID and increment counter"""
        packet_id = self.tx_packet_id
        self.tx_packet_id = (self.tx_packet_id + 1) & 0xFFFFFF  # Keep in 24-bit range
        return packet_id
    
    def _send_packet(self, packet: EGCPPacket):
        """Send an EGCP binary packet"""
        if not self.sock:
            return
        
        target = None
        if self.auto_reply and self.last_addr:
            target = self.last_addr
        else:
            target = (self.target_ip, self.target_port)
        
        try:
            self.sock.sendto(packet.encode(), target)
        except Exception as e:
            self.log_signal.emit(f"Send error: {e}")
    
    def _send_ack(self, packet_id_to_ack: int):
        """Send an ACK packet for the given packet ID"""
        # ACK body is 3 bytes: the ID of the packet being acknowledged
        body = struct.pack('>I', packet_id_to_ack)[1:]  # Take last 3 bytes
        ack_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_ACK, body)
        self._send_packet(ack_packet)

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
                
                if self.auto_reply:
                    if self.last_addr != addr:
                         print(f"New client connected: {addr}")
                         self.log_signal.emit(f"New client connected: {addr}")
                         self.connected_signal.emit(f"{addr[0]}:{addr[1]}")
                    self.last_addr = addr

                # Add to binary buffer
                self.binary_buffer += data
                
                # Process complete binary packets
                while len(self.binary_buffer) >= 4:
                    try:
                        # Peek at packet length from header
                        header = struct.unpack('>I', self.binary_buffer[:4])[0]
                        packet_length = header & 0xF
                        total_packet_size = 4 + packet_length
                        
                        # Wait for complete packet
                        if len(self.binary_buffer) < total_packet_size:
                            break
                        
                        # Extract and decode packet
                        packet_data = self.binary_buffer[:total_packet_size]
                        self.binary_buffer = self.binary_buffer[total_packet_size:]
                        
                        packet = EGCPPacket.decode(packet_data)
                        self.log_signal.emit(f"RX: {packet}")
                        
                        # Handle packet types
                        if packet.packet_type == EGCPPacket.PKT_STA:
                            # Connection handshake
                            self._send_ack(packet.packet_id)
                            self.log_signal.emit("Received START - connection established")
                        
                        elif packet.packet_type == EGCPPacket.PKT_HRT:
                            # Heartbeat - just ACK it
                            self._send_ack(packet.packet_id)
                        
                        elif packet.packet_type == EGCPPacket.PKT_VSO:
                            # Valve open command
                            if len(packet.body) >= 1:
                                valve_id = packet.body[0]
                                valve_name = EGCPPacket.VALVE_MAP.get(valve_id, f"UNKNOWN_{valve_id}")
                                self.valve_update_signal.emit(valve_name, True)
                                self._send_ack(packet.packet_id)
                                self.log_signal.emit(f"VALVE OPEN: {valve_name}")
                        
                        elif packet.packet_type == EGCPPacket.PKT_VSC:
                            # Valve close command
                            if len(packet.body) >= 1:
                                valve_id = packet.body[0]
                                valve_name = EGCPPacket.VALVE_MAP.get(valve_id, f"UNKNOWN_{valve_id}")
                                self.valve_update_signal.emit(valve_name, False)
                                self._send_ack(packet.packet_id)
                                self.log_signal.emit(f"VALVE CLOSE: {valve_name}")
                    
                    except (ValueError, struct.error) as e:
                        # Bad packet, skip one byte and try again
                        print(f"Packet decode error: {e}")
                        self.log_signal.emit(f"Packet decode error: {e}")
                        self.binary_buffer = self.binary_buffer[1:]
                        break

            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                    self.log_signal.emit(f"Receive error: {e}")

    def set_heartbeat_enabled(self, enabled):
        self.heartbeat_enabled = enabled
        self.log_signal.emit(f"Heartbeat {'enabled' if enabled else 'disabled'}")

    def heartbeat_loop(self):
        last_sensor_time = 0
        while self.running:
            try:
                current_time = time.time()
                
                # Send HRT packet every 10ms (approx) if enabled
                if self.heartbeat_enabled:
                    hrt_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_HRT)
                    self._send_packet(hrt_packet)
                
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

    def send_valve_response(self, valve, state):
        # No longer used - valve responses are ACKs now
        pass

    def send_sensors(self):
        """Send sensor data as binary ADC packets"""
        # Send each sensor as a separate PKT_ADC packet
        for sensor_name, value in self.sensor_data.items():
            # Map sensor name to ID
            sensor_id = EGCPPacket.SENSOR_MAP.get(sensor_name)
            
            if sensor_id is not None:
                # Pack as 1-byte sensor ID + 4-byte IEEE 754 float
                body = struct.pack('B', sensor_id) + struct.pack('>f', float(value))
                adc_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_ADC, body)
                self._send_packet(adc_packet)

    def send_udp(self, message):
        if not self.sock:
            return

        target = None
        if self.auto_reply and self.last_addr:
            target = self.last_addr
        else:
            target = (self.target_ip, self.target_port)
            
        try:
            self.sock.sendto(message.encode('utf-8'), target)
        except Exception as e:
            self.log_signal.emit(f"Send error: {e}")

    def update_sensor(self, name, value):
        if name in self.sensor_data:
            self.sensor_data[name] = value

