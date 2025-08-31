from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QScrollArea, QDialog, QLabel,
    QDialogButtonBox, QHBoxLayout, QLineEdit, QCheckBox, QFrame, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QDateTime
from PyQt5.QtGui import QFont
from GUI_LOGO import LogoWidget
from GUI_DAQ import GUI_DAQ_Window
from GUI_COMMS import EthernetClient
from GUI_VALVE_DIAGRAM import ValveDiagram
from GUI_GRAPHS import SensorLabelGrid
from GUI_VALVE_STATES import valve_states

class CommsSignals(QObject):
    data_received = pyqtSignal(str)
    abort_triggered = pyqtSignal(str, str)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rocket Engine Control Panel")
        self.setGeometry(100, 100, 1000, 800)
        self.dark_mode = False
        self.abort_active = False
        self.lockout_mode = False
        self.ncs3_opened_due_to_p2 = False
        self.current_sensor_values = {}
        self.abort_modes = {}
        self.pre_abort_valve_states = {}
        self.fire_sequence_btn = None
        self.manual_valve_dialog = None
        self.p3_p5_violation_start = None
        self.p4_p6_violation_start = None
        self.abort_check_interval = 50

        self.comms_signals = CommsSignals()
        self.comms_signals.data_received.connect(self.process_data_main_thread)
        self.comms_signals.abort_triggered.connect(self.handle_abort)

        self.ethernet_client = EthernetClient()
        self.ethernet_client.receive_callback = self.handle_received_data
        self.ethernet_client.log_event_callback = self.log_event

        self.sensor_grid = SensorLabelGrid()
        self.sensor_grid.signals.update_signal.connect(self.update_sensor_value)

        self.daq_window = GUI_DAQ_Window(self.sensor_grid)
        self.daq_window.log_event_callback = self.log_event
        self.daq_window.throttling_enabled = False
        self.daq_window.gimbaling_enabled = False

        self.init_abort_modes()
        self.init_ui()
        self.setup_abort_monitor()

    def init_abort_modes(self):
        self.abort_modes = {
            "high_upstream_pressure": True,
            "reverse_flow": True,
            "high_chamber_pressure": True,
            "high_p2": True
        }

    def setup_abort_monitor(self):
        self.abort_timer = QTimer()
        self.abort_timer.timeout.connect(self.check_abort_conditions)
        self.abort_timer.start(self.abort_check_interval)

    def check_abort_conditions(self):
        if not self.current_sensor_values or self.abort_active:
            return
        current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        p3 = self.current_sensor_values.get("P3", 0)
        p4 = self.current_sensor_values.get("P4", 0)
        p5 = self.current_sensor_values.get("P5", 0)
        p6 = self.current_sensor_values.get("P6", 0)
        pc = self.current_sensor_values.get("P8", 0)
        pline = self.current_sensor_values.get("P7", 0)
        p2 = self.current_sensor_values.get("P2", 0)

        if p2 > 1375:
            if not self.diagram.valve_states.get("NCS3", False):
                self.toggle_valve("NCS3", True)
                self.ncs3_opened_due_to_p2 = True
        elif p2 < 1250 and self.ncs3_opened_due_to_p2:
            self.toggle_valve("NCS3", False)
            self.ncs3_opened_due_to_p2 = False

        if pc > 700 and self.abort_modes["high_chamber_pressure"]:
            self.comms_signals.abort_triggered.emit(
                "high_chamber_pressure",
                f"Chamber pressure {pc} psi > 700 psi"
            )

        if pc > pline and self.abort_modes["reverse_flow"]:
            self.comms_signals.abort_triggered.emit(
                "reverse_flow",
                f"Chamber pressure {pc} psi > Line pressure {pline} psi"
            )

        if self.abort_modes["high_upstream_pressure"]:
            if p5 - p3 >= 5:
                if self.p3_p5_violation_start is None:
                    self.p3_p5_violation_start = current_time
                elif current_time - self.p3_p5_violation_start >= 150:
                    self.comms_signals.abort_triggered.emit(
                        "high_upstream_pressure",
                        f"P5 {p5} psi > P3 {p3} psi by 5+ psi for 150ms"
                    )
            else:
                self.p3_p5_violation_start = None

            if p6 - p4 >= 5:
                if self.p4_p6_violation_start is None:
                    self.p4_p6_violation_start = current_time
                elif current_time - self.p4_p6_violation_start >= 150:
                    self.comms_signals.abort_triggered.emit(
                        "high_upstream_pressure",
                        f"P6 {p6} psi > P4 {p4} psi by 5+ psi for 150ms"
                    )
            else:
                self.p4_p6_violation_start = None

    def update_sensor_value(self, sensor, value):
        self.current_sensor_values[sensor] = value

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()

        logo_widget = LogoWidget("RED_logo.png", scale_width=200)
        main_layout.addWidget(logo_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        eth_layout = QHBoxLayout()
        self.ip_input = QLineEdit("192.168.1.174")
        self.port_input = QLineEdit("8888")
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.connect_ethernet)

        self.dark_mode_btn = QPushButton("Dark Mode")
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)
        eth_layout.addWidget(self.dark_mode_btn)
        eth_layout.addWidget(QLabel("IP Address:"))
        eth_layout.addWidget(self.ip_input)
        eth_layout.addWidget(QLabel("Port:"))
        eth_layout.addWidget(self.port_input)
        eth_layout.addWidget(connect_btn)
        scroll_layout.addLayout(eth_layout)

        self.conn_status_label = QLabel("Not connected")
        self.conn_status_label.setAlignment(Qt.AlignCenter)
        self.conn_status_label.setFont(QFont("Arial", 10, QFont.Bold))
        scroll_layout.addWidget(self.conn_status_label)
        scroll_layout.addWidget(self.make_divider())

        scroll_layout.addWidget(self.daq_window.filename_input)
        scroll_layout.addWidget(self.daq_window.start_button)
        scroll_layout.addWidget(self.daq_window.stop_button)

        self.manual_btn = QPushButton("Manual Valve Control")
        self.manual_btn.clicked.connect(self.show_manual_valve_control)
        scroll_layout.addWidget(self.manual_btn)

        self.abort_config_btn = QPushButton("Abort Configuration")
        self.abort_config_btn.clicked.connect(self.show_abort_control)
        scroll_layout.addWidget(self.abort_config_btn)

        throttle_gimbal_layout = QHBoxLayout()
        self.throttling_btn = QPushButton("Enable Throttling")
        self.throttling_btn.clicked.connect(self.toggle_throttling)
        throttle_gimbal_layout.addWidget(self.throttling_btn)
        self.gimbaling_btn = QPushButton("Enable Gimbaling")
        self.gimbaling_btn.clicked.connect(self.toggle_gimbaling)
        throttle_gimbal_layout.addWidget(self.gimbaling_btn)
        scroll_layout.addLayout(throttle_gimbal_layout)

        self.daq_window.throttle_check.stateChanged.connect(
            lambda state: self.throttling_btn.setText("Disable Throttling" if state == 2 else "Enable Throttling")
        )
        self.daq_window.gimbal_check.stateChanged.connect(
            lambda state: self.gimbaling_btn.setText("Disable Gimbaling" if state == 2 else "Enable Gimbaling")
        )

        scroll_layout.addWidget(self.make_divider())

        self.manual_abort_btn = QPushButton("MANUAL ABORT")
        self.manual_abort_btn.setStyleSheet("""background-color: red; color: white; font-weight: bold; font-size: 20pt; min-height: 80px;""")
        self.manual_abort_btn.clicked.connect(self.trigger_manual_abort)
        scroll_layout.addWidget(self.manual_abort_btn)

        scroll_layout.addWidget(self.make_divider())

        self.safe_state_btn = QPushButton("CONFIRM SAFE STATE")
        self.safe_state_btn.setStyleSheet("""background-color: green; color: white; font-weight: bold; font-size: 16pt; min-height: 60px;""")
        self.safe_state_btn.clicked.connect(self.confirm_safe_state)
        self.safe_state_btn.setVisible(False)
        scroll_layout.addWidget(self.safe_state_btn)

        scroll_layout.addWidget(self.make_divider())

        top_layout = QHBoxLayout()
        operations_layout = QVBoxLayout()

        for op in valve_states:
            if op in ["Pressurization", "Fire", "Kill and Vent"]:
                continue
            btn = QPushButton(op)
            btn.setFont(QFont("Arial", 10, QFont.Bold))
            btn.setMinimumHeight(40)
            btn.clicked.connect(lambda checked, o=op: self.apply_valve_state(o))
            operations_layout.addWidget(btn)
            if op == "Oxidizer Fill":
                self.fire_sequence_btn = QPushButton("Auto Fire Sequence")
                self.fire_sequence_btn.setFont(QFont("Arial", 10, QFont.Bold))
                self.fire_sequence_btn.setMinimumHeight(40)
                self.fire_sequence_btn.clicked.connect(self.show_fire_sequence_dialog)
                operations_layout.addWidget(self.fire_sequence_btn)

        top_layout.addLayout(operations_layout)
        self.diagram = ValveDiagram()
        top_layout.addWidget(self.diagram)
        scroll_layout.addLayout(top_layout)

        self.status_label = QLabel("Current State: None")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 14, QFont.Bold))
        scroll_layout.addWidget(self.status_label)
        scroll_layout.addWidget(self.sensor_grid)

        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self.apply_stylesheet()

    def make_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line

    def toggle_throttling(self):
        new_state = not self.daq_window.throttling_enabled
        self.daq_window.throttling_enabled = new_state
        self.throttling_btn.setText("Disable Throttling" if new_state else "Enable Throttling")
        if self.daq_window.log_event_callback:
            status = "ENABLED" if new_state else "DISABLED"
            self.daq_window.log_event_callback(f"THROTTLING:{status}")

    def toggle_gimbaling(self):
        new_state = not self.daq_window.gimbaling_enabled
        self.daq_window.gimbaling_enabled = new_state
        self.gimbaling_btn.setText("Disable Gimbaling" if new_state else "Enable Gimbaling")
        if self.daq_window.log_event_callback:
            status = "ENABLED" if new_state else "DISABLED"
            self.daq_window.log_event_callback(f"GIMBALING:{status}")

    def toggle_dark_mode(self):
        """Toggle between dark and light mode"""
        self.dark_mode = not self.dark_mode
        self.apply_stylesheet()
        self.dark_mode_btn.setText("Light Mode" if self.dark_mode else "Dark Mode")
        # Update sensor grid
        self.sensor_grid.set_dark_mode(self.dark_mode)

    def apply_stylesheet(self):
        """Apply appropriate stylesheet based on current mode"""
        if self.dark_mode:
            dark_stylesheet = """
                QWidget {
                    background-color: #333333;
                    color: #EEEEEE;
                }
                QLabel {
                    color: #EEEEEE;
                }
                QPushButton {
                    background-color: #555555;
                    color: #EEEEEE;
                    border: 1px solid #888888;
                }
                QPushButton:hover {
                    background-color: #666666;
                }
                QPushButton:pressed {
                    background-color: #444444;
                }
                QLineEdit {
                    background-color: #444444;
                    color: #EEEEEE;
                    border: 1px solid #555555;
                }
                QCheckBox {
                    color: #EEEEEE;
                }
                QScrollArea {
                    background-color: #333333;
                }
                QFrame {
                    background-color: #555555;
                }
                QDialog {
                    background-color: #333333;
                }
                /* Valve diagram background */
                ValveDiagram {
                    background-color: #222222;
                }
            """
            self.setStyleSheet(dark_stylesheet)
        else:
            # Light mode - reset to default
            self.setStyleSheet("")

    def toggle_abort_mode(self, mode, state):
        """Enable/disable specific abort mode (Req 9)"""
        self.abort_modes[mode] = state == 2
        status = "ENABLED" if state == 2 else "DISABLED"
        self.log_event("ABORT_MODE", f"{mode}:{status}")


    def handle_abort(self, abort_type, reason):
        """Handle abort sequence (Req 11, 20-24)"""
        if self.abort_active:
            return
            
        self.abort_active = True
        self.lockout_mode = True
        
        # Store current valve states before making changes
        self.pre_abort_valve_states = self.diagram.valve_states.copy()
        
        # Apply abort valve sequence (Req 21-23) and update diagram
        valves_to_set = [
            ("NCS3", True),     # Open NCS3
            ("NCS1", False),    # Close NCS1
            ("NCS2", False),    # Close NCS2
            ("NCS4", False),    # Close NCS4
            ("NCS5", False),    # Close NCS5
            ("NCS6", False),    # Close NCS6
            ("LA-BV1", False),  # Close LA-BV1
            ("GV-1", False),    # Close GV-1
            ("GV-2", False)     # Close GV-2
        ]
        for name, state in valves_to_set:
            self.diagram.set_valve_state(name, state)
            try:
                self.ethernet_client.send_valve_command(name, state)
            except Exception:
                pass
        
        # Show abort popup (Req 20)
        QMessageBox.critical(
            self, 
            "ABORT TRIGGERED", 
            f"Abort Type: {abort_type}\nReason: {reason}"
        )
        
        # Lock out manual control (Req 24)
        self.update_lockout_state()
        
        # Show safe state button
        self.safe_state_btn.setVisible(True)
        
        # Log abort event
        self.log_event("ABORT", f"{abort_type}:{reason}")

    def update_lockout_state(self):
        """Update UI based on lockout state (Req 24)"""
        # Enable/disable control buttons
        self.manual_btn.setEnabled(not self.lockout_mode)
        
        # Disable fire sequence button during abort
        if self.fire_sequence_btn:
            self.fire_sequence_btn.setEnabled(not self.lockout_mode)
        
        # Change manual abort button color during lockout
        if self.lockout_mode:
            self.manual_abort_btn.setStyleSheet("""
                background-color: darkred; 
                color: gray; 
                font-weight: bold; 
                font-size: 20pt;
                min-height: 80px;
            """)
        else:
            self.manual_abort_btn.setStyleSheet("""
                background-color: red; 
                color: white; 
                font-weight: bold; 
                font-size: 20pt;
                min-height: 80px;
            """)
        
        # Disable/enable valve state buttons
        for btn in self.findChildren(QPushButton):
            if btn.text() in valve_states:
                btn.setEnabled(not self.lockout_mode)

    def confirm_safe_state(self):
        """Confirm system is safe after abort without any dialog"""
        self.abort_active = False
        self.lockout_mode = False
        self.update_lockout_state()
        self.safe_state_btn.setVisible(False)
        
        # Update status
        self.status_label.setText("System in Safe State")
        
        # Log safe state confirmation
        self.log_event("ABORT_RESOLVED", "Operator confirmed safe state")

    def log_event(self, event_type, event_details=""):
        """Log event to DAQ system (Req 15)"""
        if not self.daq_window:
            return
        self.daq_window.log_event(event_type, event_details)

    def connect_ethernet(self):
        ip = self.ip_input.text().strip()
        port_text = self.port_input.text().strip()
        if not port_text.isdigit():
            self.conn_status_label.setText("Port must be a number")
            return
        port = int(port_text)

        connected = self.ethernet_client.connect(ip, port)
        if connected:
            self.conn_status_label.setText("Connected successfully")
            # Start NOOP heartbeat (Req 25)
            self.ethernet_client.start_heartbeat()
        else:
            self.conn_status_label.setText("Connection failed")

    def handle_received_data(self, data_str):
        self.comms_signals.data_received.emit(data_str)

    def process_data_main_thread(self, data_str):
        self.daq_window.handle_new_data(data_str)

    def apply_valve_state(self, operation):
        if self.lockout_mode:
            return
            
        active_valves = valve_states.get(operation, [])
        for name in self.diagram.valve_states:
            state = name in active_valves
            self.diagram.set_valve_state(name, state)
            try:
                self.ethernet_client.send_valve_command(name, state)
            except Exception:
                pass
        self.status_label.setText(f"Current State: {operation}")

        if operation == "Pressurization":
            QTimer.singleShot(5000, lambda: self.apply_valve_state("Fire"))
            QTimer.singleShot(20000, lambda: self.apply_valve_state("Kill and Vent"))

    def show_fire_sequence_dialog(self):
        if self.lockout_mode:
            QMessageBox.warning(self, "Abort Active", "Auto fire sequence cannot be activated during an abort")
            return
            
        # First confirmation dialog
        confirm_dialog = QDialog(self)
        confirm_dialog.setWindowTitle("Confirm Ignition")
        layout = QVBoxLayout()
        label = QLabel("Start ignition sequence?")
        layout.addWidget(label)
        buttons = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.Cancel)
        buttons.accepted.connect(confirm_dialog.accept)
        buttons.rejected.connect(confirm_dialog.reject)
        layout.addWidget(buttons)
        confirm_dialog.setLayout(layout)
        
        # Only proceed if user confirms
        if confirm_dialog.exec_() != QDialog.Accepted:
            return

        # Create countdown dialog
        countdown_dialog = QDialog(self)
        countdown_dialog.setWindowTitle("Ignition Sequence")
        countdown_dialog.setMinimumSize(300, 150)
        countdown_layout = QVBoxLayout(countdown_dialog)
        
        # Countdown label
        self.countdown_label = QLabel("Ignition in 10 seconds...")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setFont(QFont("Arial", 14, QFont.Bold))
        countdown_layout.addWidget(self.countdown_label)
        
        # Cancel button
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFont(QFont("Arial", 12, QFont.Bold))
        cancel_btn.setStyleSheet("background-color: red; color: white;")
        countdown_layout.addWidget(cancel_btn)
        
        # Initialize countdown
        self.countdown_value = 10
        self.countdown_timer = QTimer()
        self.countdown_timer.setInterval(1000)  # 1 second interval
        
        # Update countdown display
        def update_countdown():
            self.countdown_value -= 1
            if self.countdown_value > 0:
                self.countdown_label.setText(f"Ignition in {self.countdown_value} seconds...")
            else:
                self.countdown_timer.stop()
                countdown_dialog.accept()  # Close dialog and proceed
        
        # Cancel sequence
        def cancel_sequence():
            self.countdown_timer.stop()
            countdown_dialog.reject()
        
        # Connect signals
        self.countdown_timer.timeout.connect(update_countdown)
        cancel_btn.clicked.connect(cancel_sequence)
        
        # Start countdown
        self.countdown_timer.start()
        
        # Show dialog and handle result
        if countdown_dialog.exec_() == QDialog.Accepted:
            self.apply_valve_state("Pressurization")

    def show_manual_valve_control(self):
        if self.lockout_mode:
            QMessageBox.warning(self, "Lockout Active", "Manual control is disabled during abort")
            return
            
        # Close existing dialog if open
        if self.manual_valve_dialog:
            self.manual_valve_dialog.close()
            
        dialog = QDialog(self)
        dialog.setWindowTitle("Manual Valve Control")
        dialog.setModal(False)  # Allow interaction with main window
        layout = QVBoxLayout(dialog)
        
        # Store reference to dialog
        self.manual_valve_dialog = dialog
        
        # Get actual valve names from diagram
        valve_names = list(self.diagram.valve_states.keys())
        
        # Create buttons and store references
        self.manual_valve_buttons = {}
        for valve in valve_names:
            current_state = self.diagram.valve_states[valve]
            btn = QPushButton(valve)
            color = "green" if current_state else "red"
            btn.setStyleSheet(f"background-color: {color}; color: white;")
            # Store button reference
            self.manual_valve_buttons[valve] = btn
            # Connect click handler with valve name
            btn.clicked.connect(lambda checked, v=valve: self.toggle_valve_and_update_button(v))
            layout.addWidget(btn)
            
        dialog.show()
    
    def toggle_valve_and_update_button(self, valve_name):
        """Toggle valve state and update button color"""
        if self.lockout_mode:
            return
            
        # Toggle current state
        new_state = not self.diagram.valve_states[valve_name]
        self.diagram.set_valve_state(valve_name, new_state)
        
        # Update button color
        if valve_name in self.manual_valve_buttons:
            color = "green" if new_state else "red"
            self.manual_valve_buttons[valve_name].setStyleSheet(
                f"background-color: {color}; color: white;"
            )
        
        # Send command
        try:
            self.ethernet_client.send_valve_command(valve_name, new_state)
        except Exception:
            pass

    def toggle_valve(self, valve_name, state=None):
        if self.lockout_mode:
            return
            
        if state is None:
            # Toggle current state
            new_state = not self.diagram.valve_states[valve_name]
        else:
            new_state = state
            
        self.diagram.set_valve_state(valve_name, new_state)
        
        # Update manual valve button if dialog is open
        if hasattr(self, 'manual_valve_buttons') and valve_name in self.manual_valve_buttons:
            color = "green" if new_state else "red"
            self.manual_valve_buttons[valve_name].setStyleSheet(
                f"background-color: {color}; color: white;"
            )
        
        # Send command
        try:
            self.ethernet_client.send_valve_command(valve_name, new_state)
        except Exception:
            pass

    def trigger_manual_abort(self):
        """Manual abort button handler (Req 11)"""
        self.comms_signals.abort_triggered.emit(
            "manual_abort", 
            "Operator triggered manual abort"
        )

    def show_abort_control(self):
        """Abort configuration dialog (Req 9)"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Abort Configuration")
        layout = QVBoxLayout(dialog)
        
        # Abort mode configuration (Req 9)
        mode_group = QGroupBox("Abort Modes")
        mode_layout = QVBoxLayout()
        
        # Create checkboxes for each abort mode
        modes = [
            ("high_upstream_pressure", "High Upstream Pressure"),
            ("reverse_flow", "Reverse Flow Risk"),
            ("high_chamber_pressure", "High Chamber Pressure"),
            ("high_p2", "High P2 Pressure")
        ]
        
        for mode_id, mode_name in modes:
            check = QCheckBox(mode_name)
            check.setChecked(self.abort_modes.get(mode_id, False))
            check.stateChanged.connect(
                lambda state, m=mode_id: self.toggle_abort_mode(m, state)
            )
            mode_layout.addWidget(check)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        dialog.exec_()