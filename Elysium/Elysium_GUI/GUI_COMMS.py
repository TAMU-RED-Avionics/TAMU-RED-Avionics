from re import I
import errno
from socket import socket, SocketKind, AddressFamily, timeout as SocketTimeout
from threading import Thread
import time
import struct
from PyQt5.QtCore import QObject, pyqtSignal, QDate, Qt, QTimer, QDateTime, QThread


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
    
    def __repr__(self):
        type_names = {0: 'ACK', 1: 'NCK', 2: 'HRT', 3: 'VSO', 4: 'VSC', 
                      5: 'GVS', 6: 'BGP', 7: 'HGP', 8: 'SFE', 9: 'ADC', 10: 'START'}
        type_name = type_names.get(self.packet_type, f'UNK({self.packet_type})')
        return f"EGCPPacket(id={self.packet_id}, type={type_name}, len={self.packet_length})"


class EthernetClient:
    # valve to ID map (1-byte actuator IDs)
    VALVE_MAP = {
        'NCS1': 0x01,
        'NCS2': 0x02,
        'NCS3': 0x03,
        'NCS4': 0x04,
        'NCS5': 0x05,
        'NCS6': 0x06,
        'LA-BV1': 0x10,
        'LA-BV2': 0x11,
        'GV-1': 0x20,
        'GV-2': 0x21,
        'IG1': 0x30,
        'IG2': 0x31,
    }
    # reverse mapping for ADC sensor IDs to names
    SENSOR_MAP = {
        0x01: 'P1',   # pressure sensors
        0x02: 'P2',
        0x03: 'P3',
        0x04: 'P4',
        0x05: 'P5',
        0x06: 'P6',
        0x07: 'P7',
        0x08: 'P8',
        0x09: 'TC1',  # thermocouples
        0x0A: 'TC2',
        0x0B: 'TC3',
        0x0C: 'LC1',  # load cells
        0x0D: 'LC2',
        0x0E: 'LC3',
        0x0F: 'B1',
        0x10: 'B2',
    }
    
    def __init__(self, log_event_callback: (str)=None, receive_callback: (str)=None, connect_callback: (bool)=None, disconnect_callback: (str)=None):
        self.log_event_callback: (str) = log_event_callback
        self.receive_callback: (str) = receive_callback
        self.connect_callback: (bool) = connect_callback
        self.disconnect_callback: (str) = disconnect_callback
        
        self.remote_ip: str = None
        self.remote_port: int = None
        self.sock: socket = None
        self.last_connection_error: str = ""
        self.local_source_ip: str = ""
        
        # Declaration of the three threads in this controller
        self.connection_thread: QThread = None
        self.heartbeat_thread: QThread = None
        self.listen_thread: QThread = None

        # State values related to the threads
        self.connecting = False
        self.connected = False
        self.heartbeat_active = False
        self.listening_active = False

        self.timeout: float = 3                             # seconds
        self.heartbeat_tx_cadence: int = 10                 # ms
        self.heartbeat_rx_miss_interval: int = 100          # ms (11x missed heartbeats at 10ms cadence; occasionally missing at 101ms)

        self.heartbeat_last_tx: int = 0                     # ms since Jan 1 1970
        self.heartbeat_last_rx: int = 0                     # ms since Jan 1 1970
        self.heartbeat_tx_count: int = 0
        self.heartbeat_miss_abort_active: bool = False
        self.heartbeat_miss_last_rx_ms: int = 0
        self.heartbeat_miss_triggered_ms: int = 0
        self.heartbeat_miss_recovery_logged: bool = False
        
        # EGCP packet tracking
        self.tx_packet_id: int = 0                          # Transmit packet ID counter
        self.rx_packet_id: int = 0                          # Receive packet ID counter
        self.pending_acks: dict = {}                        # Map of packet_id -> (timestamp, packet, retry_count)
        self.ack_timeout: int = 60                          # ms to wait for ACK before retry
        self.max_retries: int = 10                          # Maximum retry attempts

        # System state and auto-abort countdown behavior
        self.system_state: str = "NONE"
        self.auto_abort_countdown_ms: int = 10000            # 10 seconds
        self.auto_abort_deadline_ms: int = 0
        self.auto_abort_reason: str = ""
        self.auto_abort_countdown_active: bool = False
        self.auto_abort_last_announce_second: int = -1
    
    def _get_next_tx_id(self) -> int:
        """Get next transmit packet ID and increment counter"""
        packet_id = self.tx_packet_id
        self.tx_packet_id = (self.tx_packet_id + 1) & 0xFFFFFF  # Keep in 24-bit range
        return packet_id

    def _describe_connection_error(self, err: Exception, ip: str, port: int) -> str:
        """Build a user-friendly connection failure reason for logs/UI."""
        if isinstance(err, SocketTimeout):
            e2_hint = ""
            if self.local_source_ip:
                e2_hint = (
                    f" For E2_Teensy, confirm REMOTE is {self.local_source_ip}, "
                    f"LOCAL is {ip}, and PORT is {port}."
                )
            return (
                f"Timed out waiting {self.timeout:.1f}s for response from {ip}:{port}. "
                "Verify host/port, target firmware is running, and UDP traffic is allowed."
                f"{e2_hint}"
            )

        if isinstance(err, OSError):
            if err.errno == errno.EADDRINUSE:
                return (
                    f"Local UDP port {port} is already in use. "
                    "Close conflicting process or choose a different local/remote port."
                )
            if err.errno == errno.ENETUNREACH:
                return (
                    f"Network unreachable for {ip}:{port}. "
                    "Check Ethernet/Wi-Fi route and subnet configuration."
                )
            if err.errno == errno.EHOSTUNREACH:
                return (
                    f"Host {ip} is unreachable on UDP {port}. "
                    "Check cable, switch, and destination IP settings."
                )
            if err.errno == errno.EACCES:
                return (
                    f"Permission denied opening UDP socket for {ip}:{port}. "
                    "Try a non-privileged port (>1024) and check local firewall rules."
                )

        raw = str(err).strip() or type(err).__name__
        return f"Connection setup failed for {ip}:{port}: {raw}"
    
    def _send_packet(self, packet: EGCPPacket, track_ack: bool = False):
        """Send an EGCP packet over the socket"""
        if self.sock and self.remote_ip and self.remote_port:
            self.sock.sendto(packet.encode(), (self.remote_ip, self.remote_port))
            # Track packets that need ACK for retransmission
            if track_ack:
                timestamp = QDateTime.currentMSecsSinceEpoch()
                self.pending_acks[packet.packet_id] = (timestamp, packet, 0)
    
    def _send_ack(self, packet_id_to_ack: int):
        """Send an ACK packet for the given packet ID"""
        # ACK body is 3 bytes: the ID of the packet being acknowledged
        body = struct.pack('>I', packet_id_to_ack)[1:]  # Take last 3 bytes
        ack_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_ACK, body)
        self._send_packet(ack_packet)
    
    def _send_nck(self, packet_id_to_nck: int):
        """Send an NCK packet for the given packet ID"""
        # NCK body is 3 bytes: the ID of the packet being not-acknowledged
        body = struct.pack('>I', packet_id_to_nck)[1:]  # Take last 3 bytes
        nck_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_NCK, body)
        self._send_packet(nck_packet)

    def set_system_state(self, state: str):
        """Set current high-level system state (e.g. Fire, Safe State, etc.)"""
        self.system_state = state if state else "NONE"

    def cancel_auto_abort_countdown(self):
        """Allow operator/UI to cancel a pending comms-triggered auto-abort countdown."""
        if self.auto_abort_countdown_active:
            self.auto_abort_countdown_active = False
            self.auto_abort_deadline_ms = 0
            self.auto_abort_reason = ""
            self.auto_abort_last_announce_second = -1
            if self.log_event_callback:
                self.log_event_callback("AUTO_ABORT_COUNTDOWN:CANCELED")

    def _is_fire_state(self) -> bool:
        return str(self.system_state).strip().upper() == "FIRE"

    def _trigger_comms_auto_abort(self, reason: str):
        """Trigger emergency abort behavior from comms layer."""
        try:
            sfe_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_SFE)
            self._send_packet(sfe_packet, track_ack=True)
        except Exception:
            pass

        if self.log_event_callback:
            self.log_event_callback(f"COMMS_AUTO_ABORT:{reason}")

        if self.receive_callback:
            # Pass the reason through so the GUI can display it
            self.receive_callback(f"ABORTED:COMMS:{reason}")

    def _handle_command_failure(self, packet: EGCPPacket, pkt_id: int):
        """Handle repeated failure for command packets."""
        # Only handle valve commands (open or close)
        if packet.packet_type not in [EGCPPacket.PKT_VSO, EGCPPacket.PKT_VSC]:
            return

        # Extract valve ID from packet body and get valve name
        valve_name = "UNKNOWN"
        if len(packet.body) >= 1:
            valve_id = packet.body[0]
            # Reverse lookup valve name from ID
            for name, vid in self.VALVE_MAP.items():
                if vid == valve_id:
                    valve_name = name
                    break

        cmd_type = "OPEN" if packet.packet_type == EGCPPacket.PKT_VSO else "CLOSE"
        reason = f"{cmd_type}_{valve_name}_timeout:packet_id={pkt_id}"

        if self._is_fire_state():
            if self.log_event_callback:
                self.log_event_callback(f"CRITICAL:FIRE_STATE_FAILURE:Immediate abort triggered")
            self._trigger_comms_auto_abort(reason)
            return

        # Non-fire: start operator-cancellable countdown
        now = QDateTime.currentMSecsSinceEpoch()
        if not self.auto_abort_countdown_active:
            self.auto_abort_countdown_active = True
            self.auto_abort_deadline_ms = now + self.auto_abort_countdown_ms
            self.auto_abort_reason = reason
            self.auto_abort_last_announce_second = -1
            if self.log_event_callback:
                countdown_seconds = (self.auto_abort_countdown_ms + 999) // 1000
                self.log_event_callback(f"AUTO_ABORT_COUNTDOWN:START:{countdown_seconds}:{valve_name}:{cmd_type}")
                self.log_event_callback(f"WARNING:Click CONFIRM_SAFE_STATE to cancel abort countdown")

    def _tick_auto_abort_countdown(self, now_ms: int):
        """Update auto-abort countdown and trigger abort if timer expires."""
        if not self.auto_abort_countdown_active:
            return

        remaining_ms = self.auto_abort_deadline_ms - now_ms
        if remaining_ms <= 0:
            self.auto_abort_countdown_active = False
            reason = self.auto_abort_reason or "valve_open_ack_timeout"
            self.auto_abort_reason = ""
            self.auto_abort_last_announce_second = -1
            self._trigger_comms_auto_abort(f"countdown_expired:{reason}")
            return

        remaining_seconds = (remaining_ms + 999) // 1000
        if remaining_seconds != self.auto_abort_last_announce_second:
            self.auto_abort_last_announce_second = remaining_seconds
            if self.log_event_callback:
                self.log_event_callback(f"AUTO_ABORT_COUNTDOWN:REMAINING:{remaining_seconds}")

    # Connects to the MCU over Ethernet in an asynchronous manner to preserve the main thread
    # The callback function is called with the result of the connection attempt
    def connect(self, ip: str, port: int):
        self.remote_ip = ip     # In the future we can probably automatically determine remote_ip when we sniff the first heartbeat packets
        self.remote_port = port
        self.last_connection_error = ""

        if self.connecting or self.connected:     # If it is already connecting, just bounce because the command is redundant
            return
        
        self.connecting = True

        # The connection worker is a separate thread that handles the connection attempt
        def connection_worker():
            print(f"[EthernetClient] Starting UDP connect attempt to {ip}:{port} (timeout={self.timeout:.1f}s)")
            try:
                # Create the socket
                self.sock = socket(AddressFamily.AF_INET, SocketKind.SOCK_DGRAM)
                self.sock.settimeout(self.timeout)   # seconds

                # Tells the socket to connect to the MCU's IP and port
                # host = socket.get
                try:
                    self.sock.bind(("", port))     # bind to the hardcoded port (should be configurable live in the future
                except OSError:
                    print(f"[EthernetClient] Local UDP port {port} in use, binding to ephemeral port")
                    self.sock.bind(("", 0))

                local_host, local_port = self.sock.getsockname()
                print(f"[EthernetClient] Local socket bound on {local_host}:{local_port}")

                # Determine which local source IP the OS will use for this destination.
                self.local_source_ip = ""
                probe_sock = None
                try:
                    probe_sock = socket(AddressFamily.AF_INET, SocketKind.SOCK_DGRAM)
                    probe_sock.connect((ip, port))
                    self.local_source_ip = probe_sock.getsockname()[0]
                    print(f"[EthernetClient] Routed source IP toward {ip}:{port} is {self.local_source_ip}")
                except Exception:
                    pass
                finally:
                    if probe_sock:
                        probe_sock.close()
                
                # self.sock.connect((ip, port))
                
                # Send START packet to announce presence and initiate connection
                # Retry handshake packets until timeout expires. This avoids false failures
                # when the first UDP packet is dropped during ARP resolution.
                handshake_deadline = time.monotonic() + self.timeout
                handshake_rx = b""
                handshake_attempts = 0

                self.sock.settimeout(0.25)
                while time.monotonic() < handshake_deadline:
                    handshake_attempts += 1
                    start_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_STA)
                    self._send_packet(start_packet, track_ack=False)
                    if handshake_attempts <= 3 or handshake_attempts % 5 == 0:
                        print(f"[EthernetClient] Handshake attempt {handshake_attempts}: sent PKT_STA to {ip}:{port}")

                    try:
                        data = self.sock.recv(1024)
                        if data:
                            handshake_rx = data
                            break
                    except SocketTimeout:
                        continue

                self.sock.settimeout(self.timeout)
                if not handshake_rx:
                    raise TimeoutError(
                        f"No UDP response received after {handshake_attempts} handshake attempts"
                    )

                print(f"[EthernetClient] Handshake response received ({len(handshake_rx)} bytes) from {ip}:{port}")

                # If we reach past this point in execution, it means that we have NOT timed out or encountered some other issue

                self.connected = True
                self.connecting = False
                self.last_connection_error = ""

                # Start NOOP heartbeat (Req 25)
                self.start_heartbeat()
                
                # Start the listening thread in order to receive telemetry
                self.start_listening()

                if self.connect_callback:
                    self.connect_callback(True)  # Success
            
            # Handle errors, notably timeouts which will be common
            except Exception as e:
                detailed_error = self._describe_connection_error(e, ip, port)
                self.last_connection_error = detailed_error
                if self.log_event_callback:
                    self.log_event_callback(f"CONNECTION_ERROR:{detailed_error}")

                print(f"[EthernetClient] Connection attempt failed: {detailed_error}")
                if isinstance(e, SocketTimeout):
                    print("[EthernetClient] Diagnostic: no UDP response packet received after START handshake")
                
                self.connecting = False
                self.connected = False

                if self.connect_callback:
                    self.connect_callback(False)  # Failure

                print("[EthernetClient] Raw exception:", repr(e))
        
        # Start connection in the separate thread
        self.connection_thread = QThread()
        self.connection_thread.run = connection_worker
        self.connection_thread.start()

    def start_heartbeat(self):
        """Start sending heartbeat NOOP signals (Req 25)"""
        if self.heartbeat_active:
            return

        self.heartbeat_active = True

        # Configure the last received heartbeat time to be right now to start the process
        self.heartbeat_last_rx = QDateTime.currentMSecsSinceEpoch()
        
        def heartbeat_loop():
            while self.connected and self.heartbeat_active:    # For now I am going to ignore the connection requirement
                # Send the TX heartbeat
                now = QDateTime.currentMSecsSinceEpoch()
                if (now - self.heartbeat_last_tx) > self.heartbeat_tx_cadence:
                    try:
                        # print("heartbeat loop tx time: ", now - self.heartbeat_last_tx)
                        if self.remote_ip and self.remote_port:
                            # Send binary HRT packet instead of text NOOP
                            hrt_packet = EGCPPacket(self._get_next_tx_id(), EGCPPacket.PKT_HRT)
                            self._send_packet(hrt_packet)
                            self.heartbeat_last_tx = now
                            self.heartbeat_tx_count += 1

                        if self.log_event_callback:
                            self.log_event_callback("HEARTBEAT:HRT")
                    except Exception as e:
                        self.disconnect(str(e))
                        break
                
                # Check for pending ACKs and retry if needed
                now = QDateTime.currentMSecsSinceEpoch()
                packets_to_retry = []
                packets_to_fail = []
                
                for pkt_id, (sent_time, packet, retry_count) in list(self.pending_acks.items()):
                    if (now - sent_time) > self.ack_timeout:
                        if retry_count < self.max_retries:
                            packets_to_retry.append((pkt_id, packet, retry_count))
                        else:
                            packets_to_fail.append((pkt_id, packet))
                
                # Retry packets that timed out
                for pkt_id, packet, retry_count in packets_to_retry:
                    self.sock.sendto(packet.encode(), (self.remote_ip, self.remote_port))
                    self.pending_acks[pkt_id] = (now, packet, retry_count + 1)
                    if self.log_event_callback:
                        self.log_event_callback(f"RETRY:packet_id={pkt_id} attempt={retry_count + 1}")
                
                # Fail packets that exceeded max retries
                for pkt_id, packet in packets_to_fail:
                    if self.log_event_callback:
                        self.log_event_callback(f"TIMEOUT:packet_id={pkt_id} failed_after_{self.max_retries}_retries")
                    self.pending_acks.pop(pkt_id, None)
                    self._handle_command_failure(packet, pkt_id)

                # Update non-fire auto-abort countdown (if active)
                now = QDateTime.currentMSecsSinceEpoch()
                self._tick_auto_abort_countdown(now)

                time.sleep(0.001)    # Control the pace of this thread to 1ms to prevent it from burning too much CPU
        
        # Start the thread
        # NOTE - Although this is a separate high priority thread, applying a stylesheet or doing other
        #        basic things on the GUI can cause 40-50ms pauses in this thread's execution.
        #        As a result the timing loop is constrained to a precision of that amount to not get an abort
        #        Currently to see an abort, you need to miss 6x 10ms heartbeats (60ms total timeout),
        #        which provides tolerance for brief GUI hiccups while still detecting connection loss quickly.
        self.heartbeat_thread = QThread()
        self.heartbeat_thread.run = heartbeat_loop
        self.heartbeat_thread.start()
        self.heartbeat_thread.setPriority(QThread.TimeCriticalPriority)

    def stop_heartbeat(self):
        self.heartbeat_active = False

    def start_listening(self):
        if self.listening_active:
            return

        def listen_loop():
            buffer = b""  # Binary buffer instead of string
            while self.connected and self.listening_active:
                try:
                    data = self.sock.recv(1024)
                    if not data:
                        self.disconnect("Data is empty")
                        break
                    
                    buffer += data
                    
                    # Process complete packets (need at least 4 bytes for header)
                    while len(buffer) >= 4:
                        try:
                            # Peek at packet length from header
                            header = struct.unpack('>I', buffer[:4])[0]
                            packet_length = header & 0xF
                            total_packet_size = 4 + packet_length
                            
                            # Wait for complete packet
                            if len(buffer) < total_packet_size:
                                break
                            
                            # Extract and decode packet
                            packet_data = buffer[:total_packet_size]
                            buffer = buffer[total_packet_size:]
                            
                            packet = EGCPPacket.decode(packet_data)
                            # Any valid packet proves link liveness.
                            self.heartbeat_last_rx = QDateTime.currentMSecsSinceEpoch()

                            if self.heartbeat_miss_abort_active and not self.heartbeat_miss_recovery_logged:
                                now_ms = QDateTime.currentMSecsSinceEpoch()
                                elapsed_since_abort = now_ms - self.heartbeat_miss_triggered_ms
                                elapsed_since_last_rx = now_ms - self.heartbeat_miss_last_rx_ms
                                packet_kind = "heartbeat packet" if packet.packet_type == EGCPPacket.PKT_HRT else f"packet type {packet.packet_type}"
                                print(
                                    f"[EthernetClient] Next {packet_kind} after miss: "
                                    f"elapsed_since_last_rx={elapsed_since_last_rx} ms "
                                    f"elapsed_since_abort={elapsed_since_abort} ms"
                                )
                                self.heartbeat_miss_recovery_logged = True
                                self.heartbeat_miss_abort_active = False
                            
                            # Handle different packet types
                            if packet.packet_type == EGCPPacket.PKT_STA:
                                # Connection START received - ACK it
                                self._send_ack(packet.packet_id)
                            
                            elif packet.packet_type == EGCPPacket.PKT_HRT:
                                # Reset the heartbeat timer when HRT received
                                # Send ACK for heartbeat
                                self._send_ack(packet.packet_id)
                            
                            elif packet.packet_type == EGCPPacket.PKT_ACK:
                                # ACK received - remove from pending_acks
                                if len(packet.body) >= 3:
                                    acked_id = struct.unpack('>I', b'\x00' + packet.body[:3])[0]
                                    acked_record = self.pending_acks.pop(acked_id, None)
                                else:
                                    # Legacy compatibility: some peers send ACK with no body
                                    # and place the acked packet id in the ACK header packet_id.
                                    acked_record = self.pending_acks.pop(packet.packet_id, None)
                                    
                                # If the ACK was for a valve command, notify the GUI controller it succeeded
                                if acked_record and self.receive_callback:
                                    _, orig_pkt, _ = acked_record
                                    if orig_pkt.packet_type in (EGCPPacket.PKT_VSO, EGCPPacket.PKT_VSC):
                                        if len(orig_pkt.body) >= 1:
                                            valve_id = orig_pkt.body[0]
                                            valve_name = "UNKNOWN"
                                            for name, vid in self.VALVE_MAP.items():
                                                if vid == valve_id:
                                                    valve_name = name
                                                    break
                                            state_str = "1" if orig_pkt.packet_type == EGCPPacket.PKT_VSO else "0"
                                            self.receive_callback(f"0,VALVE_SUCCESS:{valve_name}:{state_str}")
                            
                            elif packet.packet_type == EGCPPacket.PKT_NCK:
                                # NCK received - log error
                                nck_record = None
                                if len(packet.body) >= 3:
                                    nck_id = struct.unpack('>I', b'\x00' + packet.body[:3])[0]
                                    if self.log_event_callback:
                                        self.log_event_callback(f"NCK:packet_id={nck_id}")
                                    nck_record = self.pending_acks.pop(nck_id, None)
                                else:
                                    nck_record = self.pending_acks.pop(packet.packet_id, None)
                                    
                                if nck_record and self.receive_callback:
                                    _, orig_pkt, _ = nck_record
                                    if orig_pkt.packet_type in (EGCPPacket.PKT_VSO, EGCPPacket.PKT_VSC):
                                        if len(orig_pkt.body) >= 1:
                                            valve_id = orig_pkt.body[0]
                                            valve_name = "UNKNOWN"
                                            for name, vid in self.VALVE_MAP.items():
                                                if vid == valve_id:
                                                    valve_name = name
                                                    break
                                            self.receive_callback(f"0,VALVE_FAIL:{valve_name}")
                            
                            elif packet.packet_type == EGCPPacket.PKT_ADC:
                                # ADC reading: 1 byte sensor ID + 4 bytes IEEE 754 float (calibrated value)
                                if len(packet.body) >= 5:
                                    sensor_id = packet.body[0]
                                    # Unpack as big-endian float
                                    raw_value = struct.unpack('>f', packet.body[1:5])[0]
                                    
                                    # Send ACK for ADC packet
                                    self._send_ack(packet.packet_id)
                                    
                                    # Convert to string format for backward compatibility
                                    if self.receive_callback:
                                        sensor_name = self.SENSOR_MAP.get(sensor_id, f"SENSOR_{sensor_id}")
                                        data_str = f"0,{sensor_name}:{raw_value:.2f}"
                                        self.receive_callback(data_str)
                            
                            elif packet.packet_type == EGCPPacket.PKT_SFE:
                                # Safe mode entered - ACK and notify
                                self._send_ack(packet.packet_id)
                                if self.log_event_callback:
                                    self.log_event_callback(f"RX_SFE:packet_id={packet.packet_id}")
                                if self.receive_callback:
                                    self.receive_callback(f"ABORTED:REMOTE_SFE:packet_id={packet.packet_id}")
                        
                        except (ValueError, struct.error) as e:
                            # Bad packet, skip one byte and try again
                            print(f"Packet decode error: {e}")
                            buffer = buffer[1:]
                            break
                    
                except Exception as e:
                    self.disconnect(str(e))
                    break

        self.listening_active = True
        # self.listen_thread = Thread(target=listen_loop, daemon=True)
        self.listen_thread = QThread()
        self.listen_thread.run = listen_loop
        self.listen_thread.start()
        self.listen_thread.setPriority(QThread.TimeCriticalPriority)

    def stop_listening(self):
        self.listening_active = False

    def send_valve_command(self, valve_name, state):
        if self.connected:
            try:
                # Get valve ID from mapping
                valve_id = self.VALVE_MAP.get(valve_name)
                if valve_id is None:
                    if self.log_event_callback:
                        self.log_event_callback(f"VALVE_ERROR:Unknown valve {valve_name}")
                    return
                
                # Create VSO (open) or VSC (close) packet with 1-byte valve ID body
                packet_type = EGCPPacket.PKT_VSO if state else EGCPPacket.PKT_VSC
                body = struct.pack('B', valve_id)  # 1-byte valve ID
                packet = EGCPPacket(self._get_next_tx_id(), packet_type, body)
                
                # Send with ACK tracking for reliability
                self._send_packet(packet, track_ack=True)
                
                if self.log_event_callback:
                    state_str = "OPEN" if state else "CLOSE"
                    self.log_event_callback(f"VALVE_CMD:{valve_name}:{state_str}")
            except Exception as e:
                print(f"Valve command error: {e}")

    def disconnect(self, reason: str):
        # Bounce if we are already disconnected
        if not self.connected:
            return

        print("EthernetClient disconnected: ", reason)
        if self.log_event_callback:
            self.log_event_callback(f"DISCONNECT:{reason}")
        
        self.connected = False
        self.stop_heartbeat()
        self.stop_listening()
        if self.sock:
            self.sock.close()
            self.sock = None
        if self.disconnect_callback:
            self.disconnect_callback(reason)
