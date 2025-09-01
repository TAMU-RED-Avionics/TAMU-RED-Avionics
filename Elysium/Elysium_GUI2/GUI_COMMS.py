# GUI_COMMS.py
import socket
import threading
import time

class EthernetClient:
    def __init__(self):
        self.sock = None
        self.connected = False
        self.receive_callback = None
        self.log_event_callback = None
        self.heartbeat_active = False
        self.heartbeat_thread = None

    def connect(self, ip, port):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.5)   # 500 milliseconds
            self.sock.connect((ip, port))
            self.connected = True
            threading.Thread(target=self.listen, daemon=True).start()
            return True
        except Exception:
            return False

    def start_heartbeat(self):
        """Start sending heartbeat NOOP signals (Req 25)"""
        if self.heartbeat_active:
            return
            
        self.heartbeat_active = True
        def heartbeat_loop():
            while self.connected and self.heartbeat_active:
                try:
                    self.sock.sendall("NOOP\n".encode())
                    if self.log_event_callback:
                        self.log_event_callback("HEARTBEAT:NOOP")
                except Exception:
                    self.connected = False
                    break
                time.sleep(1)  # Send every second
                
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def stop_heartbeat(self):
        self.heartbeat_active = False

    def listen(self):
        buffer = ""
        while self.connected:
            try:
                data = self.sock.recv(1024)
                if not data:
                    self.connected = False
                    break
                    
                decoded = buffer + data.decode(errors='ignore')
                
                # Split into lines while preserving partial messages
                lines = decoded.split('\n')
                for line in lines[:-1]:
                    if line.strip() and self.receive_callback:
                        self.receive_callback(line.strip())
                buffer = lines[-1]
                
            except Exception:
                self.connected = False
                break

    def send_valve_command(self, valve_name, state):
        if self.connected:
            try:
                message = f"VALVE:{valve_name}:{1 if state else 0}\n"
                self.sock.sendall(message.encode())
                if self.log_event_callback:
                    state_str = "OPEN" if state else "CLOSE"
                    self.log_event_callback(f"VALVE_CMD:{valve_name}:{state_str}")
            except Exception:
                pass

    def disconnect(self):
        self.connected = False
        self.stop_heartbeat()
        if self.sock:
            self.sock.close()
            self.sock = None