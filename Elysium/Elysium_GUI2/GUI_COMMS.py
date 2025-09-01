# GUI_COMMS.py
import socket
import threading
import time

class EthernetClient:
    def __init__(self):
        self.sock = None
        self.connecting = False
        self.connected = False
        self.receive_callback = None
        self.log_event_callback = None
        self.heartbeat_active = False
        self.heartbeat_thread = None
        self.listening_active = False
        self.listen_thread = None

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

    def listen_loop(self):
        buffer = ""
        while self.connected and self.listening_active:
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

    def start_listening(self):
        if self.listening_active:
            return

        self.listening_active = True
        self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True)
        self.listen_thread.start()

    def stop_listening(self):
        self.listening_active = False

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
        self.stop_listening()
        if self.sock:
            self.sock.close()
            self.sock = None

    # Connects to the MCU over Ethernet in an asynchronous manner to preserve the main thread
    # The callback function is called with the result of the connection attempt
    def connect(self, ip, port, callback):
        if self.connecting:     # If it is already connecting, just bounce because the command is redundant
            return
        elif self.connected:    # If it is connected already, return true so that the UI adjusts its text back to "Connected"
            callback(True)
            return
        
        # The connection worker is a separate thread that handles the connection attempt
        def connection_worker():
            try:
                # Create the socket
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3.0)   # 3 seconds

                # Tells the socket to connect to the MCU's IP and port
                self.sock.connect((ip, port))
                self.connected = True
                
                self.connecting = False
                callback(True)  # Success
            
            # Handle errors, notably timeouts which will be common
            except Exception as e:
                if self.log_event_callback:
                    self.log_event_callback(f"CONNECTION_ERROR:{str(e)}")
                
                self.connecting = False
                callback(False)  # Failure

        self.connecting = True
        
        # Start connection in the separate thread
        connection_thread = threading.Thread(target=connection_worker, daemon=True)
        connection_thread.start()