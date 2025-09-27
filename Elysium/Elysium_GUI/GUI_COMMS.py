from re import I
from socket import socket, SocketKind, AddressFamily
from threading import Thread
import time
from PyQt5.QtCore import QObject, pyqtSignal, QDate, Qt, QTimer, QDateTime, QThread

class EthernetClient:
    def __init__(self, log_event_callback: (str)=None, receive_callback: (str)=None, connect_callback: (bool)=None, disconnect_callback: (str)=None):
        self.log_event_callback: (str) = log_event_callback
        self.receive_callback: (str) = receive_callback
        self.connect_callback: (bool) = connect_callback
        self.disconnect_callback: (str) = disconnect_callback
        
        self.remote_ip: str = None
        self.remote_port: int = None
        self.sock: socket = None
        
        # Declaration of the three threads in this controller
        self.connection_thread: QThread = None
        self.heartbeat_thread: QThread = None
        self.listen_thread: QThread = None

        # State values related to the threads
        self.connecting = False
        self.connected = False
        self.heartbeat_active = False
        self.listening_active = False

        self.heartbeat_tx_cadence: int = 10                 # ms
        self.heartbeat_rx_miss_interval: int = 100           # ms

        self.heartbeat_last_tx: int = 0                     # ms since Jan 1 1970
        self.heartbeat_last_rx: int = 0                     # ms since Jan 1 1970

    # Connects to the MCU over Ethernet in an asynchronous manner to preserve the main thread
    # The callback function is called with the result of the connection attempt
    def connect(self, ip: str, port: int):
        self.remote_ip = ip     # In the future we can probably automatically determine remote_ip when we sniff the first heartbeat packets
        self.remote_port = port

        if self.connecting or self.connected:     # If it is already connecting, just bounce because the command is redundant
            return
        
        self.connecting = True

        # The connection worker is a separate thread that handles the connection attempt
        def connection_worker():
            try:
                # Create the socket
                self.sock = socket(AddressFamily.AF_INET, SocketKind.SOCK_DGRAM)
                self.sock.settimeout(1)   # seconds

                # Tells the socket to connect to the MCU's IP and port
                # host = socket.get
                self.sock.bind(("", port))     # bind to the hardcoded port (should be configurable live in the future
                # self.sock.connect((ip, port))

                # Listen for a packet to come in
                data = self.sock.recv(1024)
                if not data:
                    ConnectionError("No data received in packet")

                # If we reach past this point in execution, it means that we have NOT timed out or encountered some other issue

                self.connected = True
                self.connecting = False

                self.sock.sendto("START\n".encode(), (self.remote_ip, self.remote_port))

                # Start NOOP heartbeat (Req 25)
                self.start_heartbeat()
                
                # Start the listening thread in order to receive telemetry
                self.start_listening()

                if self.connect_callback:
                    self.connect_callback(True)  # Success
            
            # Handle errors, notably timeouts which will be common
            except Exception as e:
                if self.log_event_callback:
                    self.log_event_callback(f"CONNECTION_ERROR:{str(e)}")
                
                self.connecting = False
                self.connected = False

                if self.connect_callback:
                    self.connect_callback(False)  # Failure

                print("Connect ran into exception: ", e)
        
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
                            # self.sock.sendall("NOOP\n".encode())
                            self.sock.sendto("NOOP\n".encode(), (self.remote_ip, self.remote_port))
                            self.heartbeat_last_tx = now

                        if self.log_event_callback:
                            self.log_event_callback("HEARTBEAT:NOOP")
                    except Exception as e:
                        self.disconnect(str(e))
                        break

                # Check on the RX heartbeat
                now = QDateTime.currentMSecsSinceEpoch()
                if (now - self.heartbeat_last_rx) > self.heartbeat_rx_miss_interval:
                    self.heartbeat_active = False
                    self.disconnect("Heartbeat missed")

                time.sleep(0.001)    # Control the pace of this thread to 1ms to prevent it from burning too much CPU
        
        # Start the thread
        # NOTE - Although this is a separate high priority thread, applying a stylesheet or doing other
        #        basic things on the GUI can cause 40-50ms pauses in this thread's execution.
        #        As a result the timing loop is constrained to a precision of that amount to not get an abort
        #        Currently to see an abort, you need to miss 3*30ms intervals (90ms), which has a comfortable 
        #        safety factor under the 3 strikes you are out rule.
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
            buffer = ""
            while self.connected and self.listening_active:
                try:
                    data = self.sock.recv(1024)
                    if not data:
                        self.disconnect("Data is empty")
                        break
                    decoded = buffer + data.decode(errors='ignore')
                    
                    # Split into lines while preserving partial messages
                    lines = decoded.split('\n')
                    for line in lines[:-1]:
                        strip = line.strip()
                        if strip and self.receive_callback:
                            self.heartbeat_last_rx = QDateTime.currentMSecsSinceEpoch()
                            self.receive_callback(strip)
                    buffer = lines[-1]
                    
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
                # "Set this valve to this state"
                message = f"VALVE_SET:{valve_name}:{1 if state else 0}\n"
                self.sock.sendto(message.encode(), (self.remote_ip, self.remote_port))
                if self.log_event_callback:
                    state_str = "OPEN" if state else "CLOSE"
                    self.log_event_callback(f"VALVE_CMD:{valve_name}:{state_str}")
            except Exception:
                pass

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
