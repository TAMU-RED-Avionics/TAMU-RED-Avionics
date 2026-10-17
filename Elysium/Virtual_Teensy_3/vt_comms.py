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
    PKT_POS = 0xB   # Actuator Position: body = [actuator id:1][position:2, big-endian, 0.01 % units]
    
    # Sensor ID mapping. The ID is the ADC channel the GUI's project binds each sensor to
    # (hardware.adc in the .red file), so these must match PIDs/Elysium.red and
    # PIDs/E2_RED_Spec.red (they share the same sensor bindings) or the GUI
    # shows the reading under the wrong name / not at all.
    SENSOR_MAP = {
        "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5, "P6": 6, "P7": 7, "P8": 8,
        "P9": 9, "P10": 10, "P11": 11, "P12": 12,
        "LC1": 25, "LC2": 26, "LC3": 27, "LC4": 28, "LC5": 29, "LC6": 30,
        "TC3": 109, "TC2": 110, "TC1": 111,
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
    actuator_position_signal = pyqtSignal(str, float)   # name, simulated position (%)
    actuator_target_signal = pyqtSignal(str, float)     # name, commanded target (%)

    # Proportional (position-commanded) actuators, addressed by PKT_POS.
    ACTUATOR_IDS = {0x51: "SV-1", 0x52: "SV-2", 0x53: "MFV"}   # 0x53 = FMV (Bray) valve

    # Relay ID -> name, matching E2_Teensy.ino's get_valve_name(). NCS4 is a manual
    # switch on the real hardware (no relay), so it has no ID here.
    RELAY_NAMES = {
        0x0A: "NCS1", 0x0B: "NCS2", 0x0C: "NCS3", 0x04: "NCS5",
        0x06: "PA-BV3", 0x10: "PA-BV1", 0x11: "PA-BV2",
        0x0D: "PNEUMA", 0x0E: "BRAY-AUX",
        0x20: "GV-1", 0x21: "GV-2",
        0x30: "IGN-1", 0x31: "IGN-2",
    }
    VALVE_NAMES = {**RELAY_NAMES, **ACTUATOR_IDS}

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
        # Keys are the IDs the project binds each valve to (hardware.relay in the .red file).
        self.valve_failures = {vid: False for vid in self.VALVE_NAMES}
        # Simulated actuators: they travel from their current position to the commanded
        # target at actuator_speed (% of full stroke per second), like a real motor would.
        self.actuator_speed = 50.0
        self.actuator_pos = {name: 0.0 for name in self.ACTUATOR_IDS.values()}
        self.actuator_target = dict(self.actuator_pos)
        self.ack_enabled = {} # component_name -> bool

        self.sensor_data = {
            "P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0, "P5": 0.0, "P6": 0.0, "P7": 0.0, "P8": 0.0,
            "P9": 0.0, "P10": 0.0, "P11": 0.0, "P12": 0.0,
            "TC1": 0.0, "TC2": 0.0, "TC3": 0.0,
            "LC1": 0.0, "LC2": 0.0, "LC3": 0.0, "LC4": 0.0, "LC5": 0.0, "LC6": 0.0,
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
                    
                    elif pkt.packet_type == EGCPPacket.PKT_POS:
                        # Actuator position command
                        if len(pkt.body) >= 3:
                            actuator_id = pkt.body[0]
                            pct = struct.unpack('>H', pkt.body[1:3])[0] / 100.0
                            self.log_signal.emit(
                                f"RX: POS (set position) packet ID {pkt.packet_id}, "
                                f"{self.get_valve_name(actuator_id)} -> {pct:.2f}%")
                            self.handle_actuator_command(actuator_id, pct, pkt.packet_id, addr)

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
        last_step_time = 0
        while self.running:
            try:
                current_time = time.time()
                # Send sensor data every 10ms (matching E2_Teensy)
                if current_time - last_sensor_time >= 0.01:
                    self.send_sensors()
                    last_sensor_time = current_time
                
                self.step_actuators(current_time - last_step_time if last_step_time else 0.01)
                last_step_time = current_time

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

    def handle_actuator_command(self, actuator_id, pct, cmd_packet_id, addr):
        """The GUI commanded an actuator to a position. ACK straight away (the GUI only
        waits ~60 ms per try), then travel there over time in step_actuators()."""
        name = self.get_valve_name(actuator_id)
        if self.valve_failures.get(actuator_id, False):
            self.log_signal.emit(f"SIMULATING FAILURE: {name} (packet {cmd_packet_id}) - NO ACK SENT")
            return
        pct = max(0.0, min(100.0, pct))
        self.actuator_pos.setdefault(name, 0.0)
        self.actuator_target[name] = pct
        self.send_ack(cmd_packet_id, addr)
        self.actuator_target_signal.emit(name, pct)
        self.log_signal.emit(f"✓ {name} moving to {pct:.1f}%")

    def step_actuators(self, dt):
        """Advance every actuator toward its target; report once it arrives."""
        for name, target in list(self.actuator_target.items()):
            pos = self.actuator_pos.get(name, 0.0)
            if abs(pos - target) < 1e-6:
                continue
            step = self.actuator_speed * dt
            pos = target if abs(target - pos) <= step else pos + (step if target > pos else -step)
            self.actuator_pos[name] = pos
            self.actuator_position_signal.emit(name, pos)
            if pos == target:
                self.log_signal.emit(f"{name} reached {pos:.1f}%")
                self.send_position(name)

    def actuate(self, name, pct):
        """Move an actuator by hand from this side (as if locally overridden): it jumps to
        pct and the position is reported to the GUI."""
        pct = max(0.0, min(100.0, float(pct)))
        self.actuator_pos[name] = self.actuator_target[name] = pct
        self.actuator_position_signal.emit(name, pct)
        self.actuator_target_signal.emit(name, pct)
        self.send_position(name)
        self.log_signal.emit(f"Manual: {name} set to {pct:.1f}%")

    def send_position(self, name):
        """Unsolicited position report to the GUI."""
        actuator_id = next((i for i, n in self.ACTUATOR_IDS.items() if n == name), None)
        if actuator_id is None or not self.last_addr or not self.sock:
            return
        raw = int(round(self.actuator_pos.get(name, 0.0) * 100))
        pkt = EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_POS, struct.pack('>BH', actuator_id, raw))
        self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
        try:
            self.sock.sendto(pkt.encode(), self.last_addr)
        except Exception as e:
            self.log_signal.emit(f"Send error: {e}")

    def get_valve_name(self, valve_id: int) -> str:
        """Convert valve ID to name"""
        return self.VALVE_NAMES.get(valve_id, f"VALVE_{valve_id:02X}")

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

