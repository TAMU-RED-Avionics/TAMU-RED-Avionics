import socket
import threading
import time
from PyQt5.QtCore import QObject, pyqtSignal

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
        self.ack_enabled = {} # component_name -> bool

        self.sensor_data = {
            "P1": 0.0, "P2": 0.0, "P3": 0.0, "P4": 0.0, "P5": 0.0, "P6": 0.0, "P7": 0.0, "P8": 0.0,
            "TC1": 0.0, "TC2": 0.0, "TC3": 0.0,
            "LC1": 0.0, "LC2": 0.0, "LC3": 0.0,
            "B1": 0.0, "B2": 0.0
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
                message = data.decode('utf-8').strip()
                
                if self.auto_reply:
                    if self.last_addr != addr:
                         print(f"New client connected: {addr}")
                         self.log_signal.emit(f"New client connected: {addr}")
                         self.connected_signal.emit(f"{addr[0]}:{addr[1]}")
                    self.last_addr = addr

                # Handle commands
                if message == "NOOP":
                    pass # Heartbeat
                elif message == "START":
                    print("Received START command")
                    self.log_signal.emit("Received START command")
                elif message.startswith("VALVE_SET"):
                    # VALVE_SET:NAME:STATE
                    parts = message.split(':')
                    if len(parts) == 3:
                        valve = parts[1]
                        state = parts[2] == '1'
                        self.valve_update_signal.emit(valve, state)
                        if self.ack_enabled.get(valve, True):
                            self.send_valve_response(valve, state)
                        self.log_signal.emit(f"Command: {valve} -> {'OPEN' if state else 'CLOSED'}")
                else:
                    print(f"Received: {message}")
                    self.log_signal.emit(f"Received: {message}")

            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                    self.log_signal.emit(f"Receive error: {e}")

    def set_heartbeat_enabled(self, enabled):
        self.heartbeat_enabled = enabled
        self.log_signal.emit(f"Heartbeat {'enabled' if enabled else 'disabled'}")

    def set_ack_enabled(self, name, enabled):
        self.ack_enabled[name] = enabled
        self.log_signal.emit(f"ACK for {name} {'enabled' if enabled else 'disabled'}")

    def heartbeat_loop(self):
        last_sensor_time = 0
        while self.running:
            try:
                current_time = time.time()
                
                # Send NOOP every 10ms (approx) if enabled
                if self.heartbeat_enabled:
                    self.send_udp("NOOP\n")
                
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
        msg = f"VALVE_SUCCESS:{valve}:{1 if state else 0}\n"
        self.send_udp(msg)

    def send_sensors(self):
        # Format: t:TIMESTAMP,P1:VAL,P2:VAL...
        current_time = (time.time() - self.start_time) * 1000000 # microseconds
        
        msg = f"t:{current_time:.0f}"
        for key, value in self.sensor_data.items():
            if isinstance(value, str):
                msg += f",{key}:{value}"
            else:
                msg += f",{key}:{value:.2f}"
            
        # P7 and P8 might not be in the map if initialized old way, check logic
        
        msg += "\n"
        
        self.send_udp(msg)

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

