# GUI_CONTROLLER.py
# This file will manage all UI related states, and stores functions that will manipulate them
import csv, os
from ast import Dict, Str
from re import S
from typing import Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QLabel, QDialogButtonBox, QCheckBox, QMessageBox, QGroupBox
from PyQt5.QtCore import QDate, Qt, QTimer, QDateTime
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QObject, pyqtSignal
from GUI_COMMS import EthernetClient

# This may be necessary for ongoing refactors but currently has no use
class Signals(QObject):
    abort_triggered = pyqtSignal(str, str)
    safe_state = pyqtSignal()
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)
    
    valve_updated = pyqtSignal(str, str)     # can be open, closed, or pending a response from the MCU
    sensor_updated = pyqtSignal(str, float, float)      # sensor_name, val, timestamp
    system_status = pyqtSignal(str)
    
    # Auto-abort countdown signals (for thread-safe dialog creation)
    countdown_start = pyqtSignal(int, str, str)  # initial_seconds, valve_name, cmd_type
    countdown_update = pyqtSignal(int)  # remaining_seconds
    countdown_close = pyqtSignal()


"""
GUI CONTROLLER

This class object is the daddy of the entire GUI. It is intended to manage state. All actions that 
are called by the windows which cant be contained locally are functions within this object. This 
controller will shit out signals depending on both information it retrieves from the EthernetClient
as well as the action functions connected to different buttons.

Think of it as the entire backend managed in one spot.

The rest of the windows are configured to take in this controller as an initializer object. Each
one of them will connect different signals inside here to their internal update actions, and will
connect functions here to their buttons in order to configure connections.

"""
class GUIController:
    def __init__(self, parent: QWidget):
        self.parent = parent

        # Create signals FIRST before EthernetClient (which references them in callbacks)
        self.signals = Signals()
        
        # The EthernetClient will connect to the "flight" MCU and listen for packets in a backend thread
        self.ethernet_client = EthernetClient(
            receive_callback = self.handle_new_data,
            log_event_callback = self.log_event,
            connect_callback = self.handle_connect,
            disconnect_callback = lambda reason: self.signals.disconnected.emit(reason)
        )
        

        # Explaining the disconnect loop - the ethernet client calls the disconnect_callback
        # in a separate thread, therefore we must use a signal that pops out of it and back in here
        # to safely change things in the main thread as a result
        # self.signals.connected.connect(self.handle_connect)
        self.signals.disconnected.connect(lambda reason: self.signals.abort_triggered.emit("DISCONNECTED", reason))
        self.signals.abort_triggered.connect(self.handle_abort)
        self.signals.valve_updated.connect(self.update_valve_state)
        
        # Connect countdown signals for thread-safe dialog creation
        self.signals.countdown_start.connect(self.show_abort_countdown_dialog)
        self.signals.countdown_update.connect(self.update_abort_countdown_dialog)
        self.signals.countdown_close.connect(self.close_abort_countdown_dialog)

        # For file recording
        self.csv_file = None
        self.csv_writer = None

        # These are constants and dictionaries that the UI needs to be tracked
        self.lockout = True                     # default to lockout until a connection starts

        self.ncs3_opened_due_to_p2 = False
        self.abort_modes: Dict[str, bool] = {}
        self.pre_abort_valve_states: Dict[str, bool]  = {}
        self.current_sensor_values: Dict[str, float] = {}
        self.manual_valve_buttons: Dict[str, QPushButton] = {}
        self.abort_check_interval = 10  # ms
        self.throttling_enabled = False
        self.gimbaling_enabled = False
        self.manual_valve_dialog: QDialog = None

        # Abort countdown dialog tracking
        self.abort_countdown_dialog: Optional[QDialog] = None
        self.abort_countdown_label: Optional[QLabel] = None

        self.p3_p5_violation_start = None
        self.p4_p6_violation_start = None

        # Initial valve states: False = closed (red), True = open (green)
        self.valve_states: Dict[str, bool] = {
            "NCS1": False,
            "NCS2": False,
            "NCS3": False,
            "NCS5": False,
            "NCS6": False,
            "LA-BV1": False,
            "GV-1": False,
            "GV-2": False
        }

        # This is a list of the different buttons and the valves that they manipulate
        self.valve_operation_states: Dict(str, [str]) = {
            "Open Oxidizer": ["LA-BV1"],
            "Oxidizer Fill": ["NCS3", "NCS2", "LA-BV1"],
            "Oxidizer Leak Check": ["LA-BV1"],
            "Oxidizer Leak Check Fill": ["NCS1", "LA-BV1"],
            "Close Oxidizer": ["NCS3", "LA-BV1"],
            "Oxidizer Vent": ["GV-1", "NCS2", "NCS3", "LA-BV1"],


            "Open Pressure": ["LA-BV1"],
            "Fuel Fill 1": ["NCS5", "NCS6", "LA-BV1"],
            "Fuel Leak Check": ["LA-BV1"],
            "Fuel Leak Check Fill": ["NCS1", "LA-BV1"],
            "Close Pressure 1": ["LA-BV1"],
            "Vent Pressure": ["NCS1", "NCS3", "LA-BV1"],
            
            
            "Postfire Purge": ["NCS1", "GV-1", "LA-BV1"],
            "Fuel Fill 2": ["NCS5", "LA-BV1"],
            "Prefire Purge 1": ["GV-1", "LA-BV1"],
            "Prefire Purge 2": ["GV-1", "LA-BV1"],
            "Close Pressure 2": ["NCS3", "LA-BV1"],
            "Power down": [],

            "Fire": ["GV-1", "GV-2", "NCS1", "LA-BV1"],
            "Kill and Vent": ["NCS3", "GV-1", "GV-2", "LA-BV1"],
        }
        
        # Abort related configuration
        self.init_abort_modes()
        self.setup_abort_monitor()
    
    # ABORT CONTROL ------------------------------------------------------------------------------------------------
    
    def handle_connect(self, success: bool):
        if success:
            self.ethernet_client.set_system_state("CONNECTED")
            self.signals.connected.emit()
        else:
            self.signals.disconnected.emit("Connection failed")
    
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
        if self.lockout:
            return

        # Beyond this point we shouldn't check for abort conditions if there is no data
        if not self.current_sensor_values:
            return

        current_time = QDateTime.currentMSecsSinceEpoch()
        p3 = self.current_sensor_values.get("P3", 0)
        p4 = self.current_sensor_values.get("P4", 0)
        p5 = self.current_sensor_values.get("P5", 0)
        p6 = self.current_sensor_values.get("P6", 0)
        pc = self.current_sensor_values.get("P8", 0)
        pline = self.current_sensor_values.get("P7", 0)
        p2 = self.current_sensor_values.get("P2", 0)

        if p2 > 1375:
            if not self.valve_states.get("NCS3", False):
                self.toggle_valve("NCS3", True)
                self.ncs3_opened_due_to_p2 = True
        elif p2 < 1250 and self.ncs3_opened_due_to_p2:
            self.toggle_valve("NCS3", False)
            self.ncs3_opened_due_to_p2 = False

        if pc > 700 and self.abort_modes["high_chamber_pressure"]:
            self.signals.abort_triggered.emit(
                "high_chamber_pressure",
                f"Chamber pressure {pc} psi > 700 psi"
            )

        if pc > pline and self.abort_modes["reverse_flow"]:
            self.signals.abort_triggered.emit(
                "reverse_flow",
                f"Chamber pressure {pc} psi > Line pressure {pline} psi"
            )

        if self.abort_modes["high_upstream_pressure"]:
            if p5 - p3 >= 5:
                if self.p3_p5_violation_start is None:
                    self.p3_p5_violation_start = current_time
                elif current_time - self.p3_p5_violation_start >= 150:
                    self.signals.abort_triggered.emit(
                        "high_upstream_pressure",
                        f"P5 {p5} psi > P3 {p3} psi by 5+ psi for 150ms"
                    )
            else:
                self.p3_p5_violation_start = None

            if p6 - p4 >= 5:
                if self.p4_p6_violation_start is None:
                    self.p4_p6_violation_start = current_time
                elif current_time - self.p4_p6_violation_start >= 150:
                    self.signals.abort_triggered.emit(
                        "high_upstream_pressure",
                        f"P6 {p6} psi > P4 {p4} psi by 5+ psi for 150ms"
                    )
            else:
                self.p4_p6_violation_start = None

    def trigger_manual_abort(self):
        """Manual abort button handler (Req 11)"""
        self.signals.abort_triggered.emit(
            "manual_abort", 
            "Operator triggered manual abort"
        )

    def show_abort_control(self):
        """Abort configuration dialog (Req 9)"""
        dialog = QDialog(self.parent)
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
            check.stateChanged.connect(lambda state, m=mode_id: self.toggle_abort_mode(m, state))
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
        if self.lockout:
            return

        self.ethernet_client.set_system_state("ABORT")

        self.pre_abort_valve_states = self.valve_states.copy()

        # Disable all valves
        for valve in self.valve_states.keys():
            self.toggle_valve(valve, False)

        # Show abort popup (Req 20)
        QMessageBox.critical(
            self.parent, # has to bind to a real widget
            "ABORT TRIGGERED", 
            f"Abort Type: {abort_type}\nReason: {reason}"
        )

        self.lockout = True

        # Log abort event
        self.log_event("ABORT", f"{abort_type}:{reason}")

    def confirm_safe_state(self):
        """Confirm system is safe after abort without any dialog"""
        if self.ethernet_client.connected:
            self.ethernet_client.cancel_auto_abort_countdown()
            self.ethernet_client.set_system_state("SAFE")
            self.lockout = False
            # self.abort_state = False
            self.signals.safe_state.emit()
        
            # Log safe state confirmation
            self.log_event("SAFE_STATE", "Operator confirmed safe state")


    # DAQ RECORDING ------------------------------------------------------------------------------------------------

    def log_event(self, event_type, event_details=""):
        """Log an event to CSV (Req 15)"""
        # Handle auto-abort countdown events - use signals for thread safety
        if event_type.startswith("AUTO_ABORT_COUNTDOWN:"):
            parts = event_type.split(":")
            if len(parts) >= 2:
                action = parts[1]
                if action == "START" and len(parts) >= 3:
                    # Parse: AUTO_ABORT_COUNTDOWN:START:seconds:valve_name:cmd_type
                    initial_seconds = int(parts[2])
                    valve_name = parts[3] if len(parts) >= 4 else "UNKNOWN"
                    cmd_type = parts[4] if len(parts) >= 5 else "COMMAND"
                    self.signals.countdown_start.emit(initial_seconds, valve_name, cmd_type)
                elif action == "REMAINING" and len(parts) >= 3:
                    # Update the countdown display via signal
                    remaining_seconds = int(parts[2])
                    self.signals.countdown_update.emit(remaining_seconds)
                elif action == "CANCELED":
                    # Close the dialog via signal
                    self.signals.countdown_close.emit()
        
        # Close countdown dialog when abort actually triggers
        if event_type.startswith("COMMS_AUTO_ABORT:"):
            self.signals.countdown_close.emit()
        
        if not self.csv_writer:
            return
            
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
        self.csv_writer.writerow([
            timestamp, "", 
            "ON" if self.throttling_enabled else "OFF",
            "ON" if self.gimbaling_enabled else "OFF",
            "", event_type, event_details
        ])


    # WILL BE RUN INSIDE A BACKGROUND THREAD
    def handle_new_data(self, data_str: str):
        """ Parse teensy timestamp (first token) (Req 4) """
        timestamp = QDateTime.currentMSecsSinceEpoch() / 1000.0     # seconds, but at a precision of 1 ms
        
        parts = data_str.split(sep=",",maxsplit=1)
        teensy_ts = parts[0] if len(parts) > 1 else ""
        sensor_data = parts[1] if len(parts) > 1 else data_str

        readings = sensor_data.strip().split(sep=",")
        for reading in readings:
            if "ABORTED" in reading:
                # Parse abort reason if available
                if "ABORTED:COMMS:" in reading:
                    # Extract reason after ABORTED:COMMS:
                    reason_part = reading.split("ABORTED:COMMS:", 1)[1] if len(reading.split("ABORTED:COMMS:")) > 1 else "Unknown reason"
                    
                    # Strip countdown_expired: prefix if present
                    if reason_part.startswith("countdown_expired:"):
                        reason_part = reason_part.replace("countdown_expired:", "", 1)
                    
                    # Format the reason for display
                    if "OPEN_" in reason_part or "CLOSE_" in reason_part:
                        # Parse: OPEN_NCS1_timeout:packet_id=123 or CLOSE_LA-BV1_timeout:packet_id=456
                        parts = reason_part.split("_")
                        if len(parts) >= 2:
                            cmd = parts[0]  # OPEN or CLOSE
                            valve = parts[1].split(":")[0]  # NCS1 or LA-BV1
                            display_reason = f"Valve {valve} {cmd} command failed (timeout)"
                        else:
                            display_reason = reason_part
                    else:
                        display_reason = reason_part
                    self.signals.abort_triggered.emit("comms_auto_abort", display_reason)
                elif "ABORTED:REMOTE_SFE:" in reading:
                    sfe_reason = reading.split("ABORTED:REMOTE_SFE:", 1)[1] if len(reading.split("ABORTED:REMOTE_SFE:")) > 1 else "unknown packet"
                    self.signals.abort_triggered.emit("remote_safe_mode", f"Received SFE from MCU ({sfe_reason})")
                else:
                    # Engine MCU triggered abort
                    self.signals.abort_triggered.emit("engine_abort", "The engine MCU triggered a local abort")

            # Valve command responses
            elif "VALVE_SUCCESS" in reading:
                
                parts = reading.split(':')
                if len(parts) >= 3:
                    valve_name: str = parts[1]
                    new_state: str = "OPEN" if parts[2] == "1" else "CLOSED"

                    self.signals.valve_updated.emit(valve_name, new_state)
                

            elif "VALVE_FAIL" in reading:
                parts = reading.split(':')
                if len(parts) >= 2:
                    valve_name: str = parts[1]
                    prev_state = self.valve_states[valve_name]

                    self.signals.valve_updated.emit(valve_name, "OPEN" if prev_state else "CLOSED")

            # Sensor data
            elif ':' in reading:
                try:
                    parts = reading.split(':', 1)
                    sensor_name = parts[0].strip().upper()
                    value = float(parts[1].strip())
                    self.current_sensor_values[sensor_name] = value
                    self.signals.sensor_updated.emit(sensor_name, value, timestamp)
                except ValueError:
                    pass
        
        if self.csv_writer:
            timestamp_str = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
            self.csv_writer.writerow([
                timestamp_str, teensy_ts, 
                "ON" if self.throttling_enabled else "OFF",
                "ON" if self.gimbaling_enabled else "OFF",
                sensor_data, "", ""
            ])

    # Start recording, returns whether the conditions were fit for recording to start, otherwise returns false
    def start_recording(self, filename: str) -> bool:
        if not filename:
            QMessageBox.warning(self.parent, "Invalid Filename", "Please enter a filename")
            return False
            
        if not filename.endswith(".csv"):
            filename += ".csv"
            
        # Check if file exists (Req 12)
        if os.path.exists(filename):
            reply = QMessageBox.question(self.parent, "File Exists", 
                                        f"{filename} already exists. Overwrite?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        
        try:
            self.csv_file = open(filename, "w", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            # Add columns for throttling/gimbaling (Req 26) and event logging (Req 15)
            self.csv_writer.writerow([
                "Timestamp", "TeensyTimestamp", "Throttling", "Gimbaling", 
                "SensorData", "EventType", "EventDetails"
            ])
            self.log_event("RECORDING:START")

            return True

        except Exception as e:
            QMessageBox.critical(self.parent, "Error", f"Failed to create file: {str(e)}")
            return False

    def stop_recording(self):
        if self.csv_file:
            self.log_event("RECORDING:STOP")

            self.csv_file.close()
            self.csv_file = None
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
        if self.lockout:
            QMessageBox.warning(self.parent, "Abort Active", "Auto fire sequence cannot be activated during an abort")
            return
            
        # First confirmation dialog
        confirm_dialog = QDialog(self.parent)
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
        countdown_dialog = QDialog(self.parent)
        countdown_dialog.setWindowTitle("Ignition Sequence")
        countdown_dialog.setMinimumSize(300, 150)
        countdown_layout = QVBoxLayout(countdown_dialog)
        
        # Countdown label
        self.countdown_label = QLabel("Ignition in 10 seconds...")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        countdown_layout.addWidget(self.countdown_label)
        
        # Cancel button
        cancel_btn = QPushButton("CANCEL")
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
            self.apply_operation("Pressurization")

    def show_abort_countdown_dialog(self, initial_seconds: int, valve_name: str = "UNKNOWN", cmd_type: str = "COMMAND"):
        """Show a non-modal dialog displaying the auto-abort countdown"""
        # Close any existing countdown dialog
        if self.abort_countdown_dialog is not None:
            self.abort_countdown_dialog.close()
            self.abort_countdown_dialog = None
        
        # Create countdown dialog
        self.abort_countdown_dialog = QDialog(self.parent)
        self.abort_countdown_dialog.setWindowTitle("AUTO-ABORT WARNING")
        self.abort_countdown_dialog.setMinimumSize(400, 180)
        countdown_layout = QVBoxLayout(self.abort_countdown_dialog)
        
        # Countdown label
        self.abort_countdown_label = QLabel(f"ABORT IN {initial_seconds} SECONDS")
        self.abort_countdown_label.setAlignment(Qt.AlignCenter)
        font = self.abort_countdown_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.abort_countdown_label.setFont(font)
        countdown_layout.addWidget(self.abort_countdown_label)
        
        # Warning message with valve details
        warning_label = QLabel(f"Valve {valve_name} {cmd_type} command failed!\nClick button below to cancel abort.")
        warning_label.setAlignment(Qt.AlignCenter)
        countdown_layout.addWidget(warning_label)
        
        # Cancel button
        cancel_btn = QPushButton("CONFIRM SAFE STATE\n(Cancel Abort)")
        cancel_btn.setStyleSheet("background-color: green; color: white; font-size: 14px; padding: 10px;")
        cancel_btn.clicked.connect(self._cancel_abort_countdown)
        countdown_layout.addWidget(cancel_btn)
        
        # Show dialog non-modally
        self.abort_countdown_dialog.show()
    
    def update_abort_countdown_dialog(self, remaining_seconds: int):
        """Update the countdown display"""
        if self.abort_countdown_dialog is not None and self.abort_countdown_label is not None:
            self.abort_countdown_label.setText(f"ABORT IN {remaining_seconds} SECONDS")
    
    def close_abort_countdown_dialog(self):
        """Close the abort countdown dialog"""
        if self.abort_countdown_dialog is not None:
            self.abort_countdown_dialog.close()
            self.abort_countdown_dialog = None
            self.abort_countdown_label = None
    
    def _cancel_abort_countdown(self):
        """Called when user clicks the cancel button in the countdown dialog"""
        self.confirm_safe_state()
        self.close_abort_countdown_dialog()

    def update_valve_state(self, valve_name: str, new_val: str):        
        # Only update the internal state if it was confirmed open or closed
        if new_val == "OPEN":
            self.valve_states[valve_name] = True
        elif new_val == "CLOSED":
            self.valve_states[valve_name] = False

        # Update the manual valve buttons
        if valve_name in self.manual_valve_buttons:
            if new_val == "OPEN":
                self.manual_valve_buttons[valve_name].setStyleSheet(f"background-color: green; color: white;")
            elif new_val == "CLOSED":
                self.manual_valve_buttons[valve_name].setStyleSheet(f"background-color: red; color: white;")
            elif new_val == "PENDING":
                self.manual_valve_buttons[valve_name].setStyleSheet(f"background-color: gray; color: white;")

    def show_manual_valve_control(self):
        if self.lockout:
            QMessageBox.warning(self.parent, "Lockout Active", "Manual control is disabled during abort")
            return
        
        # Close existing dialog if open
        if self.manual_valve_dialog:
            self.manual_valve_dialog.close()
        
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Manual Valve Control")
        dialog.setModal(False)  # Allow interaction with main window
        layout = QVBoxLayout(dialog)
        
        # Store reference to dialog
        self.manual_valve_dialog = dialog
        
        # Get actual valve names from diagram
        valve_names = list(self.valve_states.keys())
        
        # Create buttons and store references
        self.manual_valve_buttons = {}
        for valve in valve_names:
            current_state = self.valve_states[valve]
            btn = QPushButton(valve)
            color = "green" if current_state else "red"
            btn.setStyleSheet(f"background-color: {color}; color: white;")
            # Store button reference
            self.manual_valve_buttons[valve] = btn
            # Connect click handler with valve name
            btn.clicked.connect(lambda checked, v=valve: self.toggle_valve(v))
            layout.addWidget(btn)
            
        dialog.show()

    def toggle_valve(self, valve_name: str, state: bool=None):
        if self.lockout:
            return

        if state is None:
            new_state = not self.valve_states[valve_name]
        else:
            new_state = state

        # Only send command if valve state is actually changing
        if valve_name in self.valve_states and self.valve_states[valve_name] == new_state:
            # Valve already in desired state, no need to send command
            return

        # self.valve_states[valve_name] = new_state     # needs to update when we get a response
        self.signals.valve_updated.emit(valve_name, "PENDING")
        
        # Update manual valve button if dialog is open
        # if valve_name in self.manual_valve_buttons:
        #     # color = "green" if new_state else "red"
        #     self.manual_valve_buttons[valve_name].setStyleSheet(
        #         f"background-color: gray; color: white;"
        #     )
        
        try:
            # Send command
            self.ethernet_client.send_valve_command(valve_name, new_state)
        except Exception:
            pass

        self.log_event("VALVE_CHANGED", f"{valve_name}:{new_state}")


    def apply_operation(self, operation: str):
        if self.lockout:
            return

        self.ethernet_client.set_system_state(operation)

        active_valves = self.valve_operation_states.get(operation, [])
        for name in self.valve_states:
            state = name in active_valves
            self.toggle_valve(name, state)

        self.signals.system_status.emit(operation)

        # self.status_label.setText(f"Current State: {operation}")

        self.log_event("OPERATION", f"{operation}")

        if operation == "Pressurization":
            QTimer.singleShot(5000, lambda: self.apply_operation("Fire"))
            QTimer.singleShot(20000, lambda: self.apply_operation("Kill and Vent"))
