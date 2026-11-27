import os
import collections
import socket
import threading
import math
import random
import time
import struct
from PyQt5.QtCore import QObject, pyqtSignal

_BOOT = time.monotonic()      # the simulated board's "boot": its clock for the sensor-packet timestamp

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
    PKT_REC = 0xC   # Flight recorder (GUI -> Teensy): body = [1 = start, 0 = stop]
    PKT_RAW = 0xD   # Load cell raw count (Teensy -> GUI): body = [sensor id:1][raw int32 BE:4][info:1]
    
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

    # --- Teensy behaviour mimicked from E2_Teensy.ino ------------------------------------------
    CONNECTION_TIMEOUT_S = 0.2        # nothing received from the GUI for this long -> shutdown
    REC_CAPACITY = 3600               # flight recorder: samples kept (one per 10 ms sensor pass = 36 s)
    # Outputs whose on/off state is recorded: bit k of out_mask = REC_OUT_IDS[k] (same as the firmware)
    REC_OUT_IDS = [0x0A, 0x0B, 0x0C, 0x04, 0x06, 0x0D, 0x0E, 0x10,
                   0x11, 0x12, 0x13, 0x14, 0x20, 0x21, 0x30, 0x31]
    REC_SAMPLE_FMT = "<Q12H12h6fHHHH"                 # keep in step with RecSample (88 bytes) in the firmware
    REC_HEADER_FMT = "<8sHHIQQ24s12B12fff16B"         # ... and RecHeader (padded to a 512-byte block)

    # Proportional (position-commanded) actuators, addressed by PKT_POS.
    ACTUATOR_IDS = {0x51: "SV-1", 0x52: "SV-2", 0x53: "MFV"}   # 0x53 = FMV (Bray) valve

    # Relay ID -> name, matching E2_Teensy.ino's get_valve_name(). NCS4 is a manual
    # switch on the real hardware (no relay), so it has no ID here.
    # The (label) after each name is the component the E2 P&ID binds to that ID, so a test shows
    # which real valve a command is for (e.g. the MOV is PA-BV2). FV-1202 (0x14) is a plain
    # on/off solenoid in the current firmware.
    RELAY_NAMES = {
        0x0A: "NCS1 (NV-1104)", 0x0B: "NCS2 (OV-1303)", 0x0C: "NCS3 (NV-1105)", 0x04: "NCS5 (FV-1201)",
        0x06: "PA-BV3 (NV-1600)", 0x10: "PA-BV1", 0x11: "PA-BV2 (MOV)",
        0x12: "FP-1201", 0x13: "AP-1601", 0x14: "FV-1202",
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

        # Simulated Teensy state: which relay outputs are energized, whether the link is "cut", and the
        # shutdown state (the firmware's abort loop: sends nothing, ignores everything except START).
        self.valve_on = {vid: False for vid in self.RELAY_NAMES}
        self.link_down = False
        self.sd_present = True                    # False = no SD card in the (simulated) socket
        self.chip_fault = ""                      # "" = healthy, "reset" = chip reset itself to defaults, "silent" = no MDIO answer
        self.watchdog_enabled = True
        self.shutdown_state = False
        self.shutdown_reason = ""
        self.last_rx_time = 0.0
        self._last_values = {}                      # what the last sensor pass sent (the recorder stores these)
        self._last_raw_time = 0.0
        # Load cells go out as RAW counts (like the real firmware); the GUI turns them into pounds with the slope /
        # intercept saved in the P&ID. This simulator takes pounds on its sliders and converts back with the same
        # P&ID numbers (identity - raw = pounds - when the P&ID has none).
        self.lc_cal = self._load_lc_calibration()

        # Flight recorder (see "Flight recorder" in E2_Teensy.ino). The simulated SD card is a folder.
        self.rec_active = False
        self.rec_start_us = 0
        self.rec_ring = collections.deque(maxlen=self.REC_CAPACITY)
        self._rec_lock = threading.Lock()
        self.sd_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sd_card")
        self.last_rec_file = ""
        self._rec_last_fileno = 0
        self.diag_events = collections.deque(maxlen=128)      # (microseconds, text): the firmware's event log
        self.diag_rx_ok = 0
        self.diag_last_rx_us = 0
        self.diag_last_rx_type = 0

        # Noise on top of the slider values ("true" readings), applied as each packet is sent.
        # Off by default so the sliders behave as before. Spikes are in multiples of sigma.
        self.noise = {
            "enabled": False,
            "pt_sigma": 1.0,       # psi, white noise per sample
            "tc_sigma": 0.3,       # degC
            "lc_sigma": 0.5,       # lbf
            "spike_pct": 0.2,      # % of samples that carry a spike
            "spike_sigmas": 25.0,  # spike size, in sigmas (random sign)
            "drift_amp": 0.3,      # psi, slow wander on PTs (what averaging can't remove)
            "drift_period": 40.0,  # s
        }
        self._drift_phase = {n: random.uniform(0, 2 * math.pi) for n in self.sensor_data}

        # Leak-check scenario: the listed PTs start at p0 and then fall by rate psi/min
        # (plus an optional exponential settling drop, like gas cooling after pressurizing).
        # None while idle. See start_leak_sim().
        self.leak_sim = None

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
                if self.link_down:
                    continue                    # simulated dead link: nothing is received
                
                # Try to parse as EGCP packet
                try:
                    pkt = EGCPPacket.decode(data)
                    self.last_rx_time = time.time()
                    self.diag_rx_ok += 1
                    self.diag_last_rx_type = pkt.packet_type
                    self.diag_last_rx_us = int((time.monotonic() - _BOOT) * 1e6)
                    if self.shutdown_state and pkt.packet_type != EGCPPacket.PKT_STA:
                        continue                # the firmware's abort loop only listens for START
                    
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
                        self.diag_event("STA received (GUI connected)")
                        self.send_ack(pkt.packet_id, addr)
                        self.send_sd_status(addr)
                        if self.shutdown_state:
                            self.shutdown_state = False
                            self.log_signal.emit("[TEENSY] STA received | exiting abort state")
                            for name in list(self.actuator_pos):
                                self.send_position(name)
                    
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

                    elif pkt.packet_type == EGCPPacket.PKT_REC:
                        # Flight recorder start / stop (the simulator has no SD card: just acknowledge)
                        if len(pkt.body) >= 1:
                            self.log_signal.emit(f"RX: REC ({'start' if pkt.body[0] else 'stop'}) packet ID {pkt.packet_id}")
                            if pkt.body[0]:
                                self.rec_start()
                            else:
                                self.rec_stop()
                            self.send_ack(pkt.packet_id, addr)
                            self.send_sd_status(addr)

                    elif pkt.packet_type == EGCPPacket.PKT_SFE:
                        # Abort from the GUI: acknowledge, then shut down like the real board
                        self.log_signal.emit(f"RX: SFE (abort) packet ID {pkt.packet_id}")
                        self.diag_event("SFE received (GUI abort)")
                        self.send_ack(pkt.packet_id, addr)
                        self.trigger_shutdown("RX_SFE")

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
                # Lost-comms watchdog, like E2_Teensy: nothing received from the GUI for 200 ms
                if (self.watchdog_enabled and self.last_addr and not self.shutdown_state and self.last_rx_time
                        and current_time - self.last_rx_time > self.CONNECTION_TIMEOUT_S):
                    self.trigger_shutdown("CONNECTION_TIMEOUT")

                # Send sensor data every 10ms (matching E2_Teensy). In its shutdown state the real board
                # sends nothing; on a cut link the readings are still taken (and recorded) but not delivered.
                if current_time - last_sensor_time >= 0.01 and not self.shutdown_state:
                    self.send_sensors()
                    self.rec_sample()
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
        
        if valve_id in self.valve_on:
            self.valve_on[valve_id] = is_open
        self.diag_event(f"{'VALVE OPEN' if is_open else 'VALVE CLOSE'} cmd  {valve_name}")
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
        self.diag_event(f"POSITION cmd  {name} -> {pct:.2f} %")
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
        
        # Filter out NULL values and string placeholders; apply the leak scenario and noise.
        now = time.time()
        active_sensors = []
        for name, val in list(self.sensor_data.items()):
            if val == "NULL" or name not in EGCPPacket.SENSOR_MAP:
                continue
            try:
                active_sensors.append((name, self._noisy(name, self._true_value(name, val, now), now)))
            except (TypeError, ValueError):
                continue
        # Load cells: the slider is in pounds; the board sends the raw count that gives those pounds
        lc_raw = {}
        for name, lbf in active_sensors:
            if name.startswith("LC") and name[2:].isdigit() and 1 <= int(name[2:]) <= 6:
                a, b = self.lc_cal[int(name[2:])]
                lc_raw[int(name[2:])] = int(max(-2**31, min(2**31 - 1, round((float(lbf) - b) / a if a else 0.0))))
        active_sensors = [(n, v) for (n, v) in active_sensors if not (n.startswith("LC") and n[2:].isdigit())]
        self._last_values = dict(active_sensors)
        for n, r in lc_raw.items():
            self._last_values[f"LC{n}"] = float(r)           # the recorder stores raw counts, like the firmware
        if self.link_down:
            return                                  # simulated dead link: readings are taken but never delivered

        # PKT_RAW at 10 Hz (the firmware recomputes load cells at 10 Hz); info = (JLC << 4) | (VIN << 1) | shared
        if now - self._last_raw_time >= 0.1:
            self._last_raw_time = now
            info = {1: (1 << 4) | (1 << 1) | 1, 2: (1 << 4) | (2 << 1) | 1, 3: (2 << 4) | (1 << 1),
                    4: (3 << 4) | (2 << 1) | 1, 5: (3 << 4) | (1 << 1) | 1, 6: (5 << 4) | (1 << 1)}
            for n, r in lc_raw.items():
                body = bytes([24 + n]) + struct.pack('>i', r) + bytes([info[n]])
                try:
                    self.sock.sendto(EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_RAW, body).encode(), self.last_addr)
                    self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
                except Exception:
                    pass

        # One sensor per packet, like the real Teensy: 1-byte sensor ID + 4-byte IEEE 754 float +
        # 8-byte big-endian microseconds since boot (13 bytes)
        for i in range(0, len(active_sensors)):
            body = b''
            for sensor_name, sensor_value in active_sensors[i:i+1]:
                sensor_id = EGCPPacket.SENSOR_MAP.get(sensor_name, 0x00)
                try:
                    body += (bytes([sensor_id]) + struct.pack('>f', float(sensor_value))
                             + struct.pack('>Q', int((time.monotonic() - _BOOT) * 1e6)))
                except (ValueError, TypeError):
                    continue
            if not body:
                continue
            
            pkt = EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_ADC, body)
            self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
            
            try:
                self.sock.sendto(pkt.encode(), self.last_addr)
            except Exception as e:
                self.log_signal.emit(f"Send error: {e}")

    # -- simulated Teensy behaviour ---------------------------------------------------
    def diag_event(self, text: str):
        self.diag_events.append((int((time.monotonic() - _BOOT) * 1e6), text))

    def set_link_down(self, down: bool):
        """Cut / restore the link without touching the sockets: nothing is received or sent while down."""
        self.link_down = bool(down)
        self.diag_event("ETHERNET LINK DOWN  BMSR=0x7849" if down else "ETHERNET LINK UP  BMSR=0x786D")
        self.log_signal.emit("LINK DOWN (simulated comms loss)" if down else "Link restored")

    def set_sd_present(self, present: bool):
        """Insert / remove the simulated SD card. Without one the Teensy refuses to start a recording, writes
        nothing at shutdown, and tells the GUI (which then warns)."""
        self.sd_present = bool(present)
        self.log_signal.emit("SD card inserted" if present else "SD card REMOVED")

    def send_sd_status(self, addr=None):
        target = addr or self.last_addr
        if not target or not self.sock or self.link_down:
            return
        try:
            self.sock.sendto(EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_REC,
                                        bytes([1 if self.sd_present else 0])).encode(), target)
            self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
        except Exception:
            pass

    def set_chip_fault(self, kind: str):
        """Simulate a bad Ethernet chip. 'reset': it reset itself to its defaults (wrong clock mode, link down, the
        two registers the firmware writes at boot are back to 0). 'silent': it no longer answers on its management bus.
        Either way the link goes down; '' restores a healthy chip (and the link)."""
        self.chip_fault = kind if kind in ("reset", "silent") else ""
        if self.chip_fault:
            self.diag_event("ETHERNET CHIP RESET ITSELF (registers back to defaults)" if kind == "reset"
                            else "ETHERNET CHIP STOPPED ANSWERING (MDIO)")
            self.log_signal.emit(f"CHIP FAULT: {self.chip_fault}")
            self.set_link_down(True)
        else:
            self.log_signal.emit("Ethernet chip healthy again")
            self.set_link_down(False)

    def set_watchdog_enabled(self, enabled: bool):
        self.watchdog_enabled = bool(enabled)
        self.log_signal.emit(f"Watchdog ({int(self.CONNECTION_TIMEOUT_S * 1000)} ms) {'on' if enabled else 'OFF'}")

    def trigger_shutdown(self, reason: str):
        """The firmware's trigger_shutdown(): close every output, save the flight recorder, tell the GUI,
        then sit in the abort loop (no sensor data, only START is answered)."""
        if self.shutdown_state:
            return
        self.log_signal.emit(f"[TEENSY] Trigger Shutdown: {reason} - closing every valve")
        for vid, on in list(self.valve_on.items()):
            if on:
                self.valve_on[vid] = False
                self.valve_update_signal.emit(self.get_valve_name(vid), False)
        for name in list(self.actuator_pos):
            self.actuator_pos[name] = self.actuator_target[name] = 0.0
            self.actuator_position_signal.emit(name, 0.0)
            self.actuator_target_signal.emit(name, 0.0)
        self.diag_event("SHUTDOWN")
        self.rec_dump(reason)
        self.diag_dump(reason)
        if self.last_addr and self.sock and not self.link_down:
            try:
                self.sock.sendto(EGCPPacket(self.packet_id_counter, EGCPPacket.PKT_SFE).encode(), self.last_addr)
                self.packet_id_counter = (self.packet_id_counter + 1) & 0xFFFFFF
            except Exception:
                pass
        self.shutdown_state = True
        self.shutdown_reason = reason

    def diag_dump(self, reason: str):
        """The firmware's diagnostics report, simulated: RECnnnn.TXT beside the recording, DIAGnnnn.TXT otherwise."""
        if not self.sd_present:
            self._rec_last_fileno = 0
            self.log_signal.emit("DIAG: no SD card - report not written")
            return
        os.makedirs(self.sd_dir, exist_ok=True)
        if self._rec_last_fileno:
            name = f"REC{self._rec_last_fileno:04d}.TXT"
        else:
            n = 1
            while os.path.exists(os.path.join(self.sd_dir, f"DIAG{n:04d}.TXT")):
                n += 1
            name = f"DIAG{n:04d}.TXT"
        self._rec_last_fileno = 0
        now = int((time.monotonic() - _BOOT) * 1e6)
        down = self.link_down
        lines = [f"ELYSIUM TEENSY DIAGNOSTICS - {name}   (SIMULATED by the Virtual Teensy: no real chip behind these numbers)",
                 f"Why the Teensy shut down : {reason}",
                 f"Teensy clock             : {now / 1e6:.3f} s since boot",
                 (f"Last packet from the GUI  : {(now - self.diag_last_rx_us) / 1000.0:.1f} ms before the shutdown "
                  f"(type {self.diag_last_rx_type})" if self.diag_last_rx_us else "Last packet from the GUI  : none since boot"),
                 f"Packets                  : {self.diag_rx_ok} received OK, 0 undecodable",
                 "Reset cause at boot      : SRSR=0x00000001  POWER-ON reset (simulated)",
                 "", "ETHERNET CHIP (DP83825I) registers, read now (hex, register 0x00..0x1F, simulated):"]
        regs = [0] * 32
        if self.chip_fault == "silent":
            regs = [0xFFFF] * 32
        else:
            regs[0], regs[1], regs[2], regs[3], regs[4], regs[5] = 0x3100, (0x7849 if down else 0x786D), 0x2000, 0xA140, 0x01E1, 0xC1E1
            regs[0x10] = 0x0000 if down else 0x0105
            regs[0x17], regs[0x18] = (0x0000, 0x0000) if self.chip_fault == "reset" else (0x0081, 0x0280)
        for i in range(0, 32, 8):
            lines.append(f"  {i:02X}: " + " ".join(f"{v:04X}" for v in regs[i:i + 8]))
        if self.chip_fault == "silent":
            lines += ["  -> The chip did NOT answer on its management bus. Either it has no power / is held in reset, or the",
                      "     bus is stuck. This is not a software problem."]
        else:
            rc_ok, led_ok = regs[0x17] == 0x0081, regs[0x18] == 0x0280
            lines += [f"  Link up (BMSR bit 2)     : {'NO' if down else 'YES'}    BMSR=0x{regs[1]:04X}  BMCR=0x{regs[0]:04X}  PHYSTS=0x{regs[0x10]:04X}",
                      f"  RCSR=0x{regs[0x17]:04X} (the firmware writes 0x0081) {'ok' if rc_ok else '<-- DIFFERENT'}",
                      f"  LEDCR=0x{regs[0x18]:04X} (the firmware writes 0x0280) {'ok' if led_ok else '<-- DIFFERENT'}"]
            if not rc_ok or not led_ok:
                lines += ["  -> The chip's settings are NOT what the firmware wrote at boot: it RESET ITSELF to defaults (a supply",
                          "     dip, ESD or noise on its supply), which leaves it on the wrong clock mode with no working link."]
        lines += ["", "EVENT LOG, oldest first (time is relative to the moment of this report):"]
        for us, text in list(self.diag_events):
            lines.append(f"  {(us - now) / 1e6:+10.3f} s  {text}")
        with open(os.path.join(self.sd_dir, name), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        self.log_signal.emit(f"DIAG: saved {name}")

    # -- flight recorder (RAM ring; written to the simulated SD card only on a shutdown) ----------
    def rec_start(self):
        if self.rec_active:
            return                                  # a retransmitted start must not wipe the buffer
        if not self.sd_present:
            self.diag_event("REC start refused (no SD card)")
            self.log_signal.emit("REC: NOT started - there is no SD card")
            return
        with self._rec_lock:
            self.rec_ring.clear()
        self.rec_start_us = int((time.monotonic() - _BOOT) * 1e6)
        self.diag_event("REC start")
        self.rec_active = True
        self.log_signal.emit("REC: started (RAM only - written to the SD folder only if the Teensy shuts down)")

    def rec_stop(self):
        self.diag_event("REC stop")
        if self.rec_active:
            self.log_signal.emit("REC: stopped - buffer discarded")
        self.rec_active = False
        with self._rec_lock:
            self.rec_ring.clear()

    def rec_sample(self):
        if not self.rec_active:
            return
        v = self._last_values
        pt = []
        for n in range(1, 13):
            psi = v.get(f"P{n}")
            if psi is None:
                pt.append(0)                        # NULL sensor: no loop current
                continue
            fs = 1000.0 if n in (7, 8) else 1500.0
            mA = 4.0 + 16.0 * max(0.0, float(psi) - 14.7) / fs      # 14.7 psi = atmosphere = 4 mA
            pt.append(min(65535, int(mA * 1000 + 0.5)))
        tc = [0x7FFF] * 12
        for name, ch in (("TC3", 9), ("TC2", 10), ("TC1", 11)):     # the sim's TC1-3 = firmware TC12/11/10
            if name in v:
                tc[ch] = max(-32000, min(32000, int(float(v[name]) * 16)))
        lc = [float(v[f"LC{i + 1}"]) if f"LC{i + 1}" in v else float("nan") for i in range(6)]
        mask = 0
        for k, oid in enumerate(self.REC_OUT_IDS):
            if self.valve_on.get(oid):
                mask |= 1 << k
        bray = int(round(self.actuator_pos.get("MFV", 0.0) * 100))
        us = int((time.monotonic() - _BOOT) * 1e6)
        with self._rec_lock:
            if self.chip_fault == "silent":
                bmsr, sts = 0, 0                                                     # the chip does not answer
            else:
                bmsr, sts = (0x7849, 0x0000) if self.link_down else (0x786D, 0x0105)  # link bit clear while the link is cut
            self.rec_ring.append(struct.pack(self.REC_SAMPLE_FMT, us, *pt, *tc, *lc, mask, bray, bmsr, sts))

    def rec_dump(self, reason: str):
        """Write the buffer to the simulated SD card (a folder next to this file), oldest sample first."""
        if not self.rec_active:
            return
        self.rec_active = False
        if not self.sd_present:
            self.log_signal.emit("REC: no SD card - recording lost, nothing written")
            return
        with self._rec_lock:
            samples = list(self.rec_ring)
            self.rec_ring.clear()
        if not samples:
            return
        os.makedirs(self.sd_dir, exist_ok=True)
        n = 1
        while os.path.exists(os.path.join(self.sd_dir, f"REC{n:04d}.BIN")):
            n += 1
        name = f"REC{n:04d}.BIN"
        header = struct.pack(
            self.REC_HEADER_FMT, b"ELYREC1\x00", 3, struct.calcsize(self.REC_SAMPLE_FMT), len(samples),
            self.rec_start_us, int((time.monotonic() - _BOOT) * 1e6), reason.encode("ascii", "replace")[:23],
            *range(12), *([1000.0 if i in (6, 7) else 1500.0 for i in range(12)]), 0.0, 14.7,
            *self.REC_OUT_IDS)
        with open(os.path.join(self.sd_dir, name), "wb") as fh:
            fh.write(header.ljust(512, b"\0"))
            fh.write(b"".join(samples))
        self.last_rec_file = name
        self._rec_last_fileno = n
        self.log_signal.emit(f"REC: saved {len(samples)} samples to {name} ({reason}) in {self.sd_dir}")

    @staticmethod
    def _load_lc_calibration():
        """{1..6: (slope, intercept)} from the E2 P&ID next to this folder (cal_gain / cal_offset on LC1-LC6)."""
        here = os.path.dirname(os.path.abspath(__file__))
        cal = {n: (1.0, 0.0) for n in range(1, 7)}
        for rel in (("..", "REDControlSystem", "PIDs", "E2_RED_Spec.red"), ("..", "RED Control System", "PIDs", "E2_RED_Spec.red")):
            path = os.path.normpath(os.path.join(here, *rel))
            if not os.path.isfile(path):
                continue
            try:
                import json
                with open(path, encoding="utf-8") as fh:
                    comps = json.load(fh).get("components", [])
                comps = comps.values() if isinstance(comps, dict) else comps
                for c in comps:
                    adc = (c.get("hardware") or {}).get("adc")
                    ex = c.get("extras") or {}
                    if adc is not None and 25 <= int(adc) <= 30 and "cal_gain" in ex:
                        cal[int(adc) - 24] = (float(ex["cal_gain"]), float(ex.get("cal_offset", 0.0)))
                return cal
            except (OSError, ValueError):
                continue
        return cal

    def update_sensor(self, name, value):
        if name in self.sensor_data:
            self.sensor_data[name] = value

    # -- noise ------------------------------------------------------------------
    def set_noise(self, **kw):
        self.noise.update(kw)

    def _noisy(self, name, value, now):
        n = self.noise
        if not n["enabled"]:
            return value
        if name.startswith("P"):
            sigma = n["pt_sigma"]
        elif name.startswith("TC"):
            sigma = n["tc_sigma"]
        else:
            sigma = n["lc_sigma"]
        out = value + random.gauss(0.0, sigma)
        if name.startswith("P") and n["drift_amp"] > 0 and n["drift_period"] > 0:
            out += n["drift_amp"] * math.sin(2 * math.pi * now / n["drift_period"] + self._drift_phase.get(name, 0.0))
        if n["spike_pct"] > 0 and random.random() < n["spike_pct"] / 100.0:
            out += random.choice((-1, 1)) * n["spike_sigmas"] * sigma
        return out

    # -- leak-check scenario -----------------------------------------------------------
    def start_leak_sim(self, rates, p0, settle_drop=0.0, settle_tau=15.0):
        """rates: {pt_name: leak rate in psi/min}. Each listed PT jumps to p0 (the line was just
        pressurized) and then decays: p0 - settle_drop*(1-exp(-t/tau)) - rate*t/60."""
        self.leak_sim = {"t0": time.time(), "rates": dict(rates), "p0": float(p0),
                         "settle": float(settle_drop), "tau": max(float(settle_tau), 0.1)}
        self.log_signal.emit(f"Leak sim started: {len(rates)} PT(s) at {p0:.0f} psi")

    def leak_value(self, name, now=None):
        """Current simulated pressure of a PT in the leak scenario, or None if it isn't in it."""
        sim = self.leak_sim
        if sim is None or name not in sim["rates"]:
            return None
        t = max(0.0, (now or time.time()) - sim["t0"])
        p = sim["p0"] - sim["settle"] * (1.0 - math.exp(-t / sim["tau"])) - sim["rates"][name] * t / 60.0
        return max(p, 0.0)

    def _true_value(self, name, base, now):
        v = self.leak_value(name, now)
        return base if v is None else v

    def stop_leak_sim(self):
        """End the scenario; each PT holds the pressure it had reached. Returns {name: value}."""
        sim, now = self.leak_sim, time.time()
        if sim is None:
            return {}
        finals = {n: self.leak_value(n, now) for n in sim["rates"]}
        self.sensor_data.update(finals)
        self.leak_sim = None
        self.log_signal.emit("Leak sim stopped (PTs hold their last value)")
        return finals
