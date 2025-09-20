# GUI_CONTROLLER.py
# This file will manage all UI related states, and stores functions that will manipulate them
import csv, os
from ast import Dict
from PyQt5.QtWidgets import QVBoxLayout, QPushButton, QDialog, QLabel, QDialogButtonBox, QCheckBox, QMessageBox, QGroupBox
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QObject, pyqtSignal
from GUI_COMMS import EthernetClient, CommsSignals

# This may be necessary for ongoing refactors but currently has no use
class GuiSignals(QObject):
    test_signal = pyqtSignal()

class GUIController:
    def __init__(self):
        # These signals are functions that will be run when the backend EthernetClient receives new packets
        self.comms_signals = CommsSignals()
        self.comms_signals.data_received.connect(self.process_data_main_thread)
        self.comms_signals.abort_triggered.connect(self.handle_abort)

        # The EthernetClient will connect to the "flight" MCU and listen for packets in a backend thread
        self.ethernet_client = EthernetClient()
        self.ethernet_client.receive_callback = self.handle_received_data
        self.ethernet_client.log_event_callback = self.log_event

        # For file recording
        self.csv_file = None
        self.csv_writer = None

        # These are constants and dictionaries that the UI needs to be tracked
        self.current_sensor_values: Dict[str, float] = {}
        self.abort_active = False
        self.lockout_mode = False
        self.ncs3_opened_due_to_p2 = False
        self.abort_modes: Dict[str, bool] = {}
        self.pre_abort_valve_states: Dict[str, bool]  = {}
        self.manual_valve_buttons: [QPushButton] = {}
        # self.fire_sequence_btn = None
        # self.manual_valve_dialog = None
        # self.p3_p5_violation_start = None
        # self.p4_p6_violation_start = None
        self.abort_check_interval = 50
        self.throttling_enabled = False
        self.gimbaling_enabled = False
        
        # Abort related configuration
        self.init_abort_modes()
        self.setup_abort_monitor()
    
    # ABORT CONTROL ------------------------------------------------------------------------------------------------
    def setup_abort_monitor(self):
        self.abort_timer = QTimer()
        self.abort_timer.timeout.connect(self.check_abort_conditions)
        self.abort_timer.start(self.abort_check_interval)

    def init_abort_modes(self):
        self.abort_modes = {
            "high_upstream_pressure": True,
            "reverse_flow": True,
            "high_chamber_pressure": True,
            "high_p2": True
        }
    
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

    def update_lockout_state(self):
        """Update UI based on lockout state (Req 24)"""
        # Enable/disable control buttons
        self.daq_window.manual_btn.setEnabled(not self.lockout_mode)
        
        # Disable fire sequence button during abort
        if self.fire_sequence_btn:
            self.fire_sequence_btn.setEnabled(not self.lockout_mode)
        
        # Change manual abort button color during lockout
        if self.lockout_mode:
            self.abort_menu.manual_abort_btn.setStyleSheet("""
                background-color: darkred; 
                color: gray; 
                font-weight: bold; 
                font-size: 20pt;
                min-height: 80px;
            """)
        else:
            self.abort_menu.manual_abort_btn.setStyleSheet("""
                background-color: red; 
                color: white; 
                font-weight: bold; 
                font-size: 20pt;
                min-height: 80px;
            """)
        
        # Disable/enable valve state buttons
        for btn in self.daq_window.findChildren(QPushButton):
            if btn.text() in ValveControlWindow.valve_states:
                btn.setEnabled(not self.lockout_mode)

    def confirm_safe_state(self):
        """Confirm system is safe after abort without any dialog"""
        self.abort_active = False
        self.lockout_mode = False
        self.update_lockout_state()
        self.abort_menu.safe_state_btn.setVisible(False)
        
        # Update status
        self.status_label.setText("System in Safe State")
        
        # Log safe state confirmation
        self.log_event("ABORT_RESOLVED", "Operator confirmed safe state")

    def trigger_manual_abort(self):
        """Manual abort button handler (Req 11)"""
        self.comms_signals.abort_triggered.emit(
            "manual_abort", 
            "Operator triggered manual abort"
        )

    def show_abort_control(self):
        """Abort configuration dialog (Req 9)"""
        dialog = QDialog(self.daq_window)
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
            # ("NCS4", False),    # Close NCS4
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
            self.valve_control, # has to bind to a real widget
            "ABORT TRIGGERED", 
            f"Abort Type: {abort_type}\nReason: {reason}"
        )
        
        # Lock out manual control (Req 24)
        self.update_lockout_state()
        
        # Show safe state button
        # self.abort_menu.safe_state_btn.setVisible(True)
        
        # Log abort event
        self.log_event("ABORT", f"{abort_type}:{reason}")


    def update_lockout_state(self):
        """Update UI based on lockout state (Req 24)"""
        # Enable/disable control buttons
        self.daq_window.manual_btn.setEnabled(not self.lockout_mode)
        
        # Disable fire sequence button during abort
        if self.fire_sequence_btn:
            self.fire_sequence_btn.setEnabled(not self.lockout_mode)
        
        # Change manual abort button color during lockout
        if self.lockout_mode:
            self.abort_menu.manual_abort_btn.setStyleSheet("""
                background-color: darkred; 
                color: gray; 
                font-weight: bold; 
                font-size: 20pt;
                min-height: 80px;
            """)
        else:
            self.abort_menu.manual_abort_btn.setStyleSheet("""
                background-color: red; 
                color: white; 
                font-weight: bold; 
                font-size: 20pt;
                min-height: 80px;
            """)
        
        # Disable/enable valve state buttons
        for btn in self.valve_control.findChildren(QPushButton):
            if btn.text() in ValveControlWindow.valve_states:
                btn.setEnabled(not self.lockout_mode)
        self.valve_control.fire_sequence_btn.setEnabled(not self.lockout_mode)
        self.daq_window.throttling_btn.setEnabled(not self.lockout_mode)
        self.daq_window.gimbaling_btn.setEnabled(not self.lockout_mode)

    def confirm_safe_state(self):
        """Confirm system is safe after abort without any dialog"""
        self.abort_active = False
        self.lockout_mode = False
        self.update_lockout_state()
        
        # Log safe state confirmation
        self.log_event("ABORT_RESOLVED", "Operator confirmed safe state")

    # DAQ RECORDING ------------------------------------------------------------------------------------------------
    def log_event(self, event_type, event_details=""):
        """Log an event to CSV (Req 15)"""
        if not self.csv_writer:
            return
            
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
        self.csv_writer.writerow([
            timestamp, "", 
            "ON" if self.throttling_enabled else "OFF",
            "ON" if self.gimbaling_enabled else "OFF",
            "", event_type, event_details
        ])

    def handle_new_data(self, data_str: str):
        """ Parse teensy timestamp (first token) (Req 4) """
        # print("GUIController handling new data: \n\t", data_str)

        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
        
        parts = data_str.split(sep=",",maxsplit=1)
        teensy_ts = parts[0] if len(parts) > 1 else ""
        sensor_data = parts[1] if len(parts) > 1 else data_str

        print("teensy_ts: ", teensy_ts)
        print("sensor_data: ", sensor_data)
        
        if self.csv_writer:
            self.csv_writer.writerow([
                timestamp, teensy_ts, 
                "ON" if self.throttling_enabled else "OFF",
                "ON" if self.gimbaling_enabled else "OFF",
                sensor_data, "", ""
            ])
        
        if self.sensor_grid:
            self.sensor_grid.handle_data_line(sensor_data)
    
    def update_sensor_value(self, sensor, value):
        self.current_sensor_values[sensor] = value

    def handle_received_data(self, data_str):
        self.comms_signals.data_received.emit(data_str)

    def process_data_main_thread(self, data_str):
        self.handle_new_data(data_str)

    # Start recording, returns whether the conditions were fit for recording to start, otherwise returns false
    def start_recording(self, filename: str) -> bool:
        if not filename:
            QMessageBox.warning(self.daq_window, "Invalid Filename", "Please enter a filename")
            return False
            
        if not filename.endswith(".csv"):
            filename += ".csv"
            
        # Check if file exists (Req 12)
        if os.path.exists(filename):
            reply = QMessageBox.question(self.daq_window, "File Exists", 
                                        f"{filename} already exists. Overwrite?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        
        try:
            self.file = open(filename, "w", newline="")
            self.csv_writer = csv.writer(self.file)
            # Add columns for throttling/gimbaling (Req 26) and event logging (Req 15)
            self.csv_writer.writerow([
                "Timestamp", "TeensyTimestamp", "Throttling", "Gimbaling", 
                "SensorData", "EventType", "EventDetails"
            ])
            self.log_event("RECORDING:START")

            return True

        except Exception as e:
            QMessageBox.critical(self.daq_window, "Error", f"Failed to create file: {str(e)}")
            return False

    def stop_recording(self):
        if self.file:
            self.log_event("RECORDING:STOP")

            self.file.close()
            self.file = None
            self.csv_writer = None

    # VALVE CONTROL ------------------------------------------------------------------------------------------------
    def toggle_throttling(self):
        self.throttling_enabled = not self.throttling_enabled

        status = "ENABLED" if self.throttling_enabled else "DISABLED"
        self.log_event(f"THROTTLING:{status}")

    def toggle_gimbaling(self):
        self.gimbaling_enabled = not self.gimbaling_enabled

        status = "ENABLED" if self.gimbaling_enabled else "DISABLED"
        self.log_event(f"GIMBALING:{status}")
    
    def show_fire_sequence_dialog(self):
        if self.lockout_mode:
            QMessageBox.warning(self.daq_window, "Abort Active", "Auto fire sequence cannot be activated during an abort")
            return
            
        # First confirmation dialog
        confirm_dialog = QDialog(self.valve_control)
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
        countdown_dialog = QDialog(self.valve_control)
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

    def show_manual_valve_control(self):
        if self.lockout_mode:
            QMessageBox.warning(self.daq_window, "Lockout Active", "Manual control is disabled during abort")
            return
            
        # Close existing dialog if open
        if self.manual_valve_dialog:
            self.manual_valve_dialog.close()
            
        dialog = QDialog(self.daq_window)
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

    def apply_valve_state(self, operation):
        if self.lockout_mode:
            return
            
        active_valves = ValveControlWindow.valve_states.get(operation, [])
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
