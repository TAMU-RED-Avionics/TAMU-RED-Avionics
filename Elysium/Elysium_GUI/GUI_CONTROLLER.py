# GUI_CONTROLLER.py
# This file will manage all UI related states, and stores functions that will manipulate them
import csv, os
from collections import deque
from ast import Dict, Str
from re import S
from typing import Optional
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QLabel, QDialogButtonBox, QCheckBox, QMessageBox, QGroupBox
from PyQt5.QtCore import QDate, Qt, QTimer, QDateTime
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QObject, pyqtSignal
from GUI_COMMS import EthernetClient
from GUI_WARNING_VALUES import WarningValueConfigWindow

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

    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal()

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

        # Violation timers for debounced abort conditions (keyed by condition name -> start timestamp ms)
        self.violation_timers: dict = {}
        # How long a condition must persist before triggering abort (ms)
        self.VIOLATION_HOLD_MS = 150

        # Keyed by sensor name -> deque of recent raw readings
        self.abort_smooth_window = 5   # number of samples to average
        self.sensor_history: dict = {}

        self.warning_ranges: Dict[str, dict] = {}
        self.load_warning_ranges()

        # Valve Command Reliability
        self.pending_valve_commands = {} # valve_name -> {"state": bool, "last_sent": timestamp, "retries": int}
        self.valve_retry_timeout = 200 # ms
        self.valve_max_retries = 5
        self.retry_timer = QTimer()
        self.retry_timer.timeout.connect(self.check_valve_command_timeouts)
        self.retry_timer.start(100) # Check every 100ms

        # Failed Ignition detection
        # LC_offsets: raw LC values snapshotted at fire commit, used to zero each channel.
        # Index order: [LC1, LC2, LC3]
        # e.g. corrected_LC1 = raw_LC1 + LC_offsets[0]  (offset = -raw_at_zero, so adding it zeroes it)
        self.combustion_achieved = False
        self.ignition_start_time: Optional[int] = None  # ms timestamp of T+0 (Ignition 2 Fire)
        self.LC_offsets: list = []                       # populated at fire-sequence commit

        # Initial valve states: False = closed (red), True = open (green)
        self.valve_states: Dict[str, bool] = {
            "NCS1": False,
            "NCS2": False,
            "NCS3": False,
            "NCS5": False,
            "PA-BV3": False,
            "PA-BV1": False,
            "PA-BV2": False,
            "IGN-1": False,
            "IGN-2": False,
            "GV-1": False,
            "GV-2": False
        }

        # This is a list of the different buttons and the valves that they manipulate
        self.valve_operation_states: Dict(str, [str]) = {
            "Open Oxidizer": ["PA-BV1"],
            "Oxidizer Fill": ["NCS3", "NCS2", "PA-BV1"],
            "Oxidizer Leak Check": ["PA-BV1"],
            "Oxidizer Leak Check Fill": ["NCS1", "PA-BV1"],
            "Close Oxidizer": ["NCS3", "PA-BV1"],
            "Oxidizer Vent": ["GV-1", "NCS2", "NCS3", "PA-BV1"],

            "Open Pressure": ["PA-BV1"],
            "Fuel Fill 1": ["NCS5", "PA-BV3", "PA-BV1"],
            "Fuel Leak Check": ["PA-BV1"],
            "Fuel Leak Check Fill": ["NCS1", "PA-BV1"],
            "Close Pressure 1": ["PA-BV1"],
            "Vent Pressure": ["NCS1", "NCS3", "PA-BV1"],

            "Postfire Purge": ["NCS1", "GV-1", "PA-BV1"],
            "Fuel Fill 2": ["NCS5", "PA-BV1"],
            "Prefire Purge 1": ["GV-1", "PA-BV1"],
            "Prefire Purge 2": ["GV-1", "PA-BV1"],
            "Close Pressure 2": ["NCS3", "PA-BV1"],
            "Power down": [],

            # Auto sequence states
            "Ignition 1": ["PA-BV2", "IGN-1"],
            "Main Valves Open": ["PA-BV2", "IGN-1", "PA-BV1"],
            "Ignition 2 (Fire)": ["PA-BV2", "IGN-1", "PA-BV1", "IGN-2"],
            "Shutdown": [],
        }
        
        # Abort related configuration
        self.init_abort_modes()
        self.setup_abort_monitor()
    
    # ABORT CONTROL ------------------------------------------------------------------------------------------------

    def _summarize_connection_error(self, reason: str) -> str:
        """Map verbose socket diagnostics to concise UI status text."""
        msg = (reason or "").lower()
        if "timed out" in msg:
            return "Connection Timeout"
        if "already in use" in msg:
            return "Port In Use"
        if "network unreachable" in msg:
            return "Network Unreachable"
        if "host" in msg and "unreachable" in msg:
            return "Host Unreachable"
        if "permission denied" in msg:
            return "Permission Denied"
        return "Connection Failed"
    
    def handle_connect(self, success: bool):
        if success:
            self.ethernet_client.set_system_state("CONNECTED")
            self.signals.connected.emit()
        else:
            detailed_reason = self.ethernet_client.last_connection_error or "Connection failed"
            concise_reason = self._summarize_connection_error(detailed_reason)
            self.signals.disconnected.emit(concise_reason)
    
    def setup_abort_monitor(self):
        self.abort_timer = QTimer()
        self.abort_timer.timeout.connect(self.check_abort_conditions)
        self.abort_timer.start(self.abort_check_interval)

    def init_abort_modes(self):
        # Pressure constants
        self.MEOP = 1175
        self.MAWP = 1600

        self.abort_modes = {
            # --- High Pressure ---
            # Any sensor >= MAWP (1600): abort + open NCS3
            "mawp_any":             True,
            # P7 > 700: abort + close all  (SF 1.5 on yield up to 1500°F wall temp)
            "high_pressure_p7":     True,

            # --- Back Pressure (all → close all) ---
            "back_pressure_p3_p1":  True,   # P3 > P1  (oxidiser backflow into supply)
            "back_pressure_p5_p3":  True,   # P5 > P3  (fuel backflow into ox line)
            "back_pressure_p8_p5":  True,   # P8 > P5  (chamber back-driving injector)
            "back_pressure_p7_p8":  True,   # P7 > P8  (line back-driving chamber)
            "back_pressure_p4_p1":  True,   # P4 > P1  (fuel backflow into supply)
            "back_pressure_p6_p4":  True,   # P6 > P4  (downstream back-driving fuel line)
            "back_pressure_p7_p6":  True,   # P7 > P6  (line back-driving fuel downstream)

            # --- Stiffness (→ close all) ---
            # Injector pressure drop too small → risk of backflow through injector face
            "stiffness_p8":         True,   # P8 > 1.2 * P7
            "stiffness_p6":         True,   # P6 > 1.2 * P7

            # --- Failed Ignition (→ close all) ---
            # Total corrected thrust (|LC1|+|LC2|+|LC3|) must reach 200 lbs by T+2s
            "failed_ignition":      True,
        }

    def load_warning_ranges(self):
        """Load warning ranges from CSV"""
        csv_path = "warning_ranges.csv"
        if not os.path.exists(csv_path):
            return
        
        try:
            with open(csv_path, newline="") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    name = row["Name"].strip().upper()
                    self.warning_ranges[name] = {
                        "warn_low": float(row["WarnLow"]),
                        "warn_high": float(row["WarnHigh"]),
                        "cold": float(row["Cold"]),
                        "hot": float(row["Hot"])
                    }
        except Exception as e:
            print(f"Error loading warning ranges: {e}")

    def get_sensor_status(self, name: str, value: float) -> str:
        """Check if a sensor value is in warning, hot, or cold range"""
        if name not in self.warning_ranges:
            return "DEFAULT"
        
        ranges = self.warning_ranges[name]
        
        # Red: Outside Warning Range
        if value < ranges["warn_low"] or value > ranges["warn_high"]:
            return "RED"
        
        # Orange: Above Hot
        if value > ranges["hot"]:
            return "ORANGE"
        
        # Blue: Below Cold
        if value < ranges["cold"]:
            return "BLUE"
            
        return "DEFAULT"

    def _push_sensor_history(self, sensor_name: str, value: float):
        if sensor_name not in self.sensor_history:
            self.sensor_history[sensor_name] = deque(maxlen=self.abort_smooth_window)
        self.sensor_history[sensor_name].append(value)

    def _get_smoothed(self, sensor_name: str, fallback: float = 0.0) -> float:
        history = self.sensor_history.get(sensor_name)
        if history:
            return sum(history) / len(history)
        return self.current_sensor_values.get(sensor_name, fallback)

    def _check_timed_condition(self, key: str, condition: bool, current_time: int) -> bool:
        """
        Debounce helper. Returns True the first time `condition` has been
        continuously True for at least VIOLATION_HOLD_MS milliseconds.
        Clears the timer when the condition is False.
        """
        if condition:
            if key not in self.violation_timers:
                self.violation_timers[key] = current_time
            elif current_time - self.violation_timers[key] >= self.VIOLATION_HOLD_MS:
                return True
        else:
            self.violation_timers.pop(key, None)
        return False

    def _capture_lc_offsets(self):
        """
        Snapshot the current raw LC readings so they can be subtracted as a zero-offset.
        Offset is stored as the negative of the current reading so that:
            corrected = raw + offset  →  zero at the moment of capture.
        Called once at fire-sequence commit, before any ignition commands go out.
        """
        lc1_raw = self.current_sensor_values.get("LC1", 0.0)
        lc2_raw = self.current_sensor_values.get("LC2", 0.0)
        lc3_raw = self.current_sensor_values.get("LC3", 0.0)
        self.LC_offsets = [-lc1_raw, -lc2_raw, -lc3_raw]
        self.log_event("LC_OFFSET_CAPTURE", f"LC1={lc1_raw:.2f}, LC2={lc2_raw:.2f}, LC3={lc3_raw:.2f}")

    def _get_corrected_thrust(self) -> float:
        """
        Return total thrust in lbs using the offsets captured at fire-sequence commit.
        thrust = |LC1 + offset[0]| + |LC2 + offset[1]| + |LC3 + offset[2]|
        Returns 0.0 if offsets haven't been captured yet.
        """
        if len(self.LC_offsets) < 3:
            return 0.0
        lc1 = self.current_sensor_values.get("LC1", 0.0)
        lc2 = self.current_sensor_values.get("LC2", 0.0)
        lc3 = self.current_sensor_values.get("LC3", 0.0)
        return (abs(lc1 + self.LC_offsets[0]) +
                abs(lc2 + self.LC_offsets[1]) +
                abs(lc3 + self.LC_offsets[2]))

    def check_abort_conditions(self):
        if self.lockout:
            return

        if not self.current_sensor_values:
            return

        current_time = QDateTime.currentMSecsSinceEpoch()

        p1 = self._get_smoothed("P1")
        p2 = self._get_smoothed("P2")
        p3 = self._get_smoothed("P3")
        p4 = self._get_smoothed("P4")
        p5 = self._get_smoothed("P5")
        p6 = self._get_smoothed("P6")
        p7 = self._get_smoothed("P7")   # line pressure
        p8 = self._get_smoothed("P8")   # chamber pressure

        all_sensors = {
            "P1": p1,
            "P2": p2,
            "P3": p3,
            "P4": p4,
            "P5": p5,
            "P6": p6,
            "P7": p7,
            "P8": p8,
        }

        # ── HIGH PRESSURE ────────────────────────────────────────────────────

        # Any sensor >= MAWP → immediate abort + open NCS3 (relief path)
        if self.abort_modes["mawp_any"]:
            for sensor_name, value in all_sensors.items():
                if value >= self.MAWP:
                    self.signals.abort_triggered.emit(
                        "mawp_any",
                        f"{sensor_name} = {value:.1f} psi >= MAWP ({self.MAWP} psi)"
                    )
                    # Open NCS3 as relief path before closing everything else
                    self.toggle_valve("NCS3", True)
                    return  # one abort per cycle is sufficient

        # P7 > 700 psi → abort + close all
        if self.abort_modes["high_pressure_p7"]:
            if self._check_timed_condition("high_pressure_p7", p7 > 700, current_time):
                self.signals.abort_triggered.emit(
                    "high_pressure_p7",
                    f"Line pressure P7 = {p7:.1f} psi > 700 psi"
                )
                return

        # ── BACK PRESSURE (close all on abort) ───────────────────────────────

        back_pressure_checks = [
            ("back_pressure_p3_p1", p3 > p1,  f"P3 ({p3:.1f}) > P1 ({p1:.1f})"),
            ("back_pressure_p5_p3", p5 > p3,  f"P5 ({p5:.1f}) > P3 ({p3:.1f})"),
            ("back_pressure_p8_p5", p8 > p5,  f"P8 ({p8:.1f}) > P5 ({p5:.1f})"),
            ("back_pressure_p7_p8", p7 > p8,  f"P7 ({p7:.1f}) > P8 ({p8:.1f})"),
            ("back_pressure_p4_p1", p4 > p1,  f"P4 ({p4:.1f}) > P1 ({p1:.1f})"),
            ("back_pressure_p6_p4", p6 > p4,  f"P6 ({p6:.1f}) > P4 ({p4:.1f})"),
            ("back_pressure_p7_p6", p7 > p6,  f"P7 ({p7:.1f}) > P6 ({p6:.1f})"),
        ]

        for mode_key, condition, message in back_pressure_checks:
            if self.abort_modes[mode_key]:
                if self._check_timed_condition(mode_key, condition, current_time):
                    self.signals.abort_triggered.emit("back_pressure", message)
                    return

        # ── STIFFNESS (close all on abort) ────────────────────────────────────
        # Low injector ΔP means chamber pressure is nearly meeting line pressure,
        # creating backflow risk through the injector face.

        stiffness_checks = [
            ("stiffness_p8", p8 > 1.2 * p7, f"P8 ({p8:.1f}) > 1.2 × P7 ({1.2*p7:.1f})"),
            ("stiffness_p6", p6 > 1.2 * p7, f"P6 ({p6:.1f}) > 1.2 × P7 ({1.2*p7:.1f})"),
        ]

        for mode_key, condition, message in stiffness_checks:
            if self.abort_modes[mode_key]:
                if self._check_timed_condition(mode_key, condition, current_time):
                    self.signals.abort_triggered.emit("low_stiffness", message)
                    return

        # ── FAILED IGNITION (close all on abort) ─────────────────────────────
        # Active only while ignition_start_time is set (i.e. between "Ignition 2 (Fire)"
        # and either combustion_achieved going True or the 2-second deadline expiring).

        if self.abort_modes["failed_ignition"] and self.ignition_start_time is not None:
            thrust = self._get_corrected_thrust()

            if thrust >= 200.0:
                # Combustion confirmed — disarm the check so it never fires again this run
                if not self.combustion_achieved:
                    self.combustion_achieved = True
                    self.ignition_start_time = None     # no longer needed
                    self.log_event("COMBUSTION_ACHIEVED", f"Thrust = {thrust:.1f} lbs")
            else:
                # Still waiting — check if the 2-second window has elapsed
                elapsed_ms = current_time - self.ignition_start_time
                if elapsed_ms >= 2000:
                    self.signals.abort_triggered.emit(
                        "failed_ignition",
                        f"Thrust = {thrust:.1f} lbs < 200 lbs at T+{elapsed_ms/1000:.2f}s"
                    )
                    return

    def trigger_manual_abort(self):
        """Manual abort button handler"""
        self.signals.abort_triggered.emit(
            "manual_abort",
            "Operator triggered manual abort"
        )

    def show_abort_control(self):
        """Abort configuration dialog"""
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Abort Configuration")
        layout = QVBoxLayout(dialog)
        
        mode_group = QGroupBox("Abort Modes")
        mode_layout = QVBoxLayout()
        
        modes = [
            # High Pressure
            ("mawp_any",             f"MAWP: Any sensor >= {self.MAWP} psi → abort + open NCS3"),
            ("high_pressure_p7",     "High Line Pressure: P7 > 700 psi → abort + close all"),
            # Back Pressure
            ("back_pressure_p3_p1",  "Back Pressure: P3 > P1"),
            ("back_pressure_p5_p3",  "Back Pressure: P5 > P3"),
            ("back_pressure_p8_p5",  "Back Pressure: P8 > P5"),
            ("back_pressure_p7_p8",  "Back Pressure: P7 > P8"),
            ("back_pressure_p4_p1",  "Back Pressure: P4 > P1"),
            ("back_pressure_p6_p4",  "Back Pressure: P6 > P4"),
            ("back_pressure_p7_p6",  "Back Pressure: P7 > P6"),
            # Stiffness
            ("stiffness_p8",         "Low Stiffness: P8 > 1.2 × P7"),
            ("stiffness_p6",         "Low Stiffness: P6 > 1.2 × P7"),
            # Failed Ignition
            ("failed_ignition",      "Failed Ignition: total thrust < 200 lbs by T+2s"),
        ]
        
        for mode_id, mode_name in modes:
            check = QCheckBox(mode_name)
            check.setChecked(self.abort_modes.get(mode_id, False))
            check.stateChanged.connect(lambda state, m=mode_id: self.toggle_abort_mode(m, state))
            mode_layout.addWidget(check)
        
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        self.custom_abort_btn = QPushButton("Warning Value Configuration")
        self.custom_abort_btn.clicked.connect(self.open_warning_value_config)
        layout.addWidget(self.custom_abort_btn)
        
        dialog.exec_()

    def open_warning_value_config(self):
        self.warning_valve_config = WarningValueConfigWindow(self, self.parent)
        self.warning_valve_config.exec_()

    def toggle_abort_mode(self, mode, state):
        self.abort_modes[mode] = state == 2
        status = "ENABLED" if state == 2 else "DISABLED"
        self.log_event("ABORT_MODE", f"{mode}:{status}")

    def handle_abort(self, abort_type, reason):
        """
        Handle abort sequence.

        MAWP abort: NCS3 is opened first (relief path) then all valves close.
        All other aborts: close every valve immediately.
        """
        if self.lockout:
            return

        self.ethernet_client.set_system_state("ABORT")
        self.pre_abort_valve_states = self.valve_states.copy()

        # Disarm failed-ignition check — the sequence is over regardless
        self.ignition_start_time = None
        self.combustion_achieved = False

        # For MAWP hits NCS3 was already opened in check_abort_conditions;
        # close everything else (toggle_valve skips NCS3 if already open, which is fine).
        for valve in self.valve_states.keys():
            if abort_type == "mawp_any" and valve == "NCS3":
                continue  # keep NCS3 open as the relief path
            self.toggle_valve(valve, False)

        self.lockout = True
        self._sequence_cancelled = True

        msg_box = QMessageBox(self.parent)
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("ABORT TRIGGERED")
        msg_box.setText(f"Abort Type: {abort_type}\nReason: {reason}")
        msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)
        msg_box.setAttribute(Qt.WA_DeleteOnClose) 
        msg_box.show()

        self.log_event("ABORT", f"{abort_type}:{reason}")

    def confirm_safe_state(self):
        """Confirm system is safe after abort without any dialog"""
        if self.ethernet_client.connected:
            self.ethernet_client.cancel_auto_abort_countdown()
            self.ethernet_client.set_system_state("SAFE")
            self.lockout = False
            self.signals.safe_state.emit()
            self.log_event("SAFE_STATE", "Operator confirmed safe state")


    # DAQ RECORDING -----------------------------------------------------------------------------------------------
    def log_event(self, event_type, event_details=""):
        """Log an event to CSV"""
        # Handle auto-abort countdown events - use signals for thread safety
        if event_type.startswith("AUTO_ABORT_COUNTDOWN:"):
            parts = event_type.split(":")
            if len(parts) >= 2:
                action = parts[1]
                if action == "START" and len(parts) >= 3:
                    initial_seconds = int(parts[2])
                    valve_name = parts[3] if len(parts) >= 4 else "UNKNOWN"
                    cmd_type = parts[4] if len(parts) >= 5 else "COMMAND"
                    self.signals.countdown_start.emit(initial_seconds, valve_name, cmd_type)
                elif action == "REMAINING" and len(parts) >= 3:
                    remaining_seconds = int(parts[2])
                    self.signals.countdown_update.emit(remaining_seconds)
                elif action == "CANCELED":
                    self.signals.countdown_close.emit()
        
        if event_type.startswith("COMMS_AUTO_ABORT:"):
            self.signals.countdown_close.emit()
        
        if event_type.strip().lower() == "heartbeat:hrt":
            return
            
        if not self.csv_writer:
            return
            
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
        row = [
            timestamp, "", 
            "ON" if self.throttling_enabled else "OFF",
            "ON" if self.gimbaling_enabled else "OFF"
        ]
        sensor_names = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", 
                        "TC1", "TC2", "TC3", "LC1", "LC2", "LC3", "B1", "B2"]
        for sensor in sensor_names:
            val = self.current_sensor_values.get(sensor, "")
            if isinstance(val, (int, float)):
                row.append(f"{val:.2f}")
            else:
                row.append(str(val))
        row.extend([event_type, event_details])
        self.csv_writer.writerow(row)

    # WILL BE RUN INSIDE A BACKGROUND THREAD
    def handle_new_data(self, data_str: str):
        """ Parse teensy timestamp (first token) """
        timestamp = QDateTime.currentMSecsSinceEpoch() / 1000.0

        parts = data_str.split(sep=",",maxsplit=1)
        teensy_ts = parts[0] if len(parts) > 1 else ""
        sensor_data = parts[1] if len(parts) > 1 else data_str

        readings = sensor_data.strip().split(sep=",")
        
        event_type = ""
        event_details = ""
        is_heartbeat = False
        
        for reading in readings:
            if "HEARTBEAT:HRT" in reading.upper():
                is_heartbeat = True
            elif "ABORTED" in reading:
                event_type = "ABORTED"
                event_details = reading
                
                if "ABORTED:COMMS:" in reading:
                    reason_part = reading.split("ABORTED:COMMS:", 1)[1] if len(reading.split("ABORTED:COMMS:")) > 1 else "Unknown reason"
                    
                    if reason_part.startswith("countdown_expired:"):
                        reason_part = reason_part.replace("countdown_expired:", "", 1)
                    
                    if "OPEN_" in reason_part or "CLOSE_" in reason_part:
                        parts = reason_part.split("_")
                        if len(parts) >= 2:
                            cmd = parts[0]
                            valve = parts[1].split(":")[0]
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
                    self.signals.abort_triggered.emit("engine_abort", "The engine MCU triggered a local abort")

            elif "VALVE_SUCCESS" in reading:
                event_type = "VALVE_SUCCESS"
                event_details = reading
                
                parts = reading.split(':')
                if len(parts) >= 3:
                    valve_name: str = parts[1]
                    new_state: str = "OPEN" if parts[2] == "1" else "CLOSED"

                    print(f"ACK received for {valve_name}: {reading}")

                    if valve_name in self.pending_valve_commands:
                        del self.pending_valve_commands[valve_name]

                    self.signals.valve_updated.emit(valve_name, new_state)

            elif "VALVE_FAIL" in reading:
                event_type = "VALVE_FAIL"
                event_details = reading
                parts = reading.split(':')
                if len(parts) >= 2:
                    valve_name: str = parts[1]
                    
                    print(f"NAK received for {valve_name}: {reading}")

                    if valve_name in self.pending_valve_commands:
                        del self.pending_valve_commands[valve_name]

                    prev_state = self.valve_states[valve_name]
                    self.signals.valve_updated.emit(valve_name, "OPEN" if prev_state else "CLOSED")

            elif ':' in reading:
                try:
                    parts = reading.split(':', 1)
                    sensor_name = parts[0].strip().upper()
                    value = float(parts[1].strip())
                    self.current_sensor_values[sensor_name] = value
                    self._push_sensor_history(sensor_name, value)
                    self.signals.sensor_updated.emit(sensor_name, value, timestamp)
                except ValueError:
                    pass
        
        if self.csv_writer and not is_heartbeat:
            timestamp_str = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
            row = [
                timestamp_str, 
                "ON" if self.throttling_enabled else "OFF",
                "ON" if self.gimbaling_enabled else "OFF"
            ]
            sensor_names = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", 
                            "TC1", "TC2", "TC3", "LC1", "LC2", "LC3", "B1", "B2"]
            for sensor in sensor_names:
                val = self.current_sensor_values.get(sensor, "")
                if isinstance(val, (int, float)):
                    row.append(f"{val:.2f}")
                else:
                    row.append(str(val))
            row.extend([event_type, event_details])
            self.csv_writer.writerow(row)

    def start_recording(self, filename: str) -> bool:
        if not filename:
            QMessageBox.warning(self.parent, "Invalid Filename", "Please enter a filename")
            return False
            
        if not filename.endswith(".csv"):
            filename += ".csv"
            
        if os.path.exists(filename):
            reply = QMessageBox.question(self.parent, "File Exists", 
                                         f"{filename} already exists. Overwrite?",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        
        try:
            self.csv_file = open(filename, "w", newline="")
            self.csv_writer = csv.writer(self.csv_file)
            self.csv_writer.writerow([
                "Timestamp", "Throttling", "Gimbaling", 
                "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8",
                "TC1", "TC2", "TC3", "LC1", "LC2", "LC3", "B1", "B2",
                "EventType", "EventDetails"
            ])
            self.log_event("RECORDING:START")
            self.signals.recording_started.emit(filename)
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
            self.signals.recording_stopped.emit()

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
        
        if confirm_dialog.exec_() != QDialog.Accepted:
            return

        # ── Capture LC zero-offsets NOW, before any ignition commands go out ──
        # This gives the cleanest pre-ignition baseline with valves still closed.
        self._capture_lc_offsets()

        # Reset ignition state for a clean run
        self.combustion_achieved = False
        self.ignition_start_time = None

        if not self.csv_file:
            data_folder = "Data"
            os.makedirs(data_folder, exist_ok=True)
            date_str = QDateTime.currentDateTime().toString("yyyy-MM-dd")
            filename = f"Elysium2_Hotfire_1_{date_str}.csv"
            full_path = os.path.join(data_folder, filename)

            i = 2
            while os.path.exists(full_path):
                filename = f"Elysium2_Hotfire_{i}_{date_str}.csv"
                full_path = os.path.join(data_folder, filename)
                i += 1

            self.start_recording(full_path)

        countdown_dialog = QDialog(self.parent)
        countdown_dialog.setWindowTitle("Ignition Sequence")
        countdown_dialog.setMinimumSize(300, 150)
        countdown_layout = QVBoxLayout(countdown_dialog)
        
        self.countdown_label = QLabel("Terminal Count: T-10")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        font = self.countdown_label.font()
        font.setPointSize(14)
        font.setBold(True)
        self.countdown_label.setFont(font)
        countdown_layout.addWidget(self.countdown_label)
        
        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setStyleSheet("background-color: red; color: white;")
        countdown_layout.addWidget(cancel_btn)
        
        self.countdown_value = 10.0
        self.countdown_timer = QTimer()
        self.countdown_timer.setInterval(500)
        self._sequence_cancelled = False
        
        def update_countdown():
            self.countdown_value -= .5
            if self.countdown_value > 0 and self.countdown_value.is_integer():
                self.countdown_label.setText(f"Terminal Count: T-{self.countdown_value:.0f}")
            if self.countdown_value == 0.5:
                self.countdown_timer.stop()
                countdown_dialog.accept()

        def cancel_sequence():
            self._sequence_cancelled = True
            self.countdown_timer.stop()
            countdown_dialog.reject()
        
        self.countdown_timer.timeout.connect(update_countdown)
        cancel_btn.clicked.connect(cancel_sequence)
        self.countdown_timer.start()
        
        if countdown_dialog.exec_() != QDialog.Accepted:
            return

        # TERMINAL COUNT | AUTO FIRE SEQUENCE
        # All timings are relative to T-0.5
        # T-0.5s  →  now (t=0 ms offset):     PA-BV2 opens + IGN-1 actuates
        # T+0.0s  →  +500 ms:                 PA-BV1 opens
        # T+0.4s  →  +900 ms:                 IGN-2 actuates
        # T+15.5s →  +16000 ms:               PA-BV1, PA-BV2, NCS1 close

        # T-0.5s: IGN-1 + PA-BV2
        self.log_event("FIRE_SEQUENCE", "T-0.5 Ignition 1")
        self.apply_operation("Ignition 1")

        # T+0.0s: PA-BV1 opens
        QTimer.singleShot(500, lambda: (
            self.apply_operation("Main Valves Open")
            if not self._sequence_cancelled else None
        ))

        # T+0.4s: IGN-2 actuates. IMPORTANT: this is for the combustion check window
        def fire_ignition_2():
            if not self._sequence_cancelled:
                self.apply_operation("Ignition 2 (Fire)")
                # Arm the failed-ignition check from this exact moment
                self.ignition_start_time = QDateTime.currentMSecsSinceEpoch()

        QTimer.singleShot(900, fire_ignition_2)

        # T+5.5s (relative to T-0.5): shutdown
        #QTimer.singleShot(16000, lambda: ( 
        QTimer.singleShot(6000, lambda: (
            self.apply_operation("Shutdown")
            if not self._sequence_cancelled else None
        ))

    def show_abort_countdown_dialog(self, initial_seconds: int, valve_name: str = "UNKNOWN", cmd_type: str = "COMMAND"):
        """Show a non-modal dialog displaying the auto-abort countdown"""
        if self.abort_countdown_dialog is not None:
            self.abort_countdown_dialog.close()
            self.abort_countdown_dialog = None
        
        self.abort_countdown_dialog = QDialog(self.parent)
        self.abort_countdown_dialog.setWindowTitle("AUTO-ABORT WARNING")
        self.abort_countdown_dialog.setMinimumSize(400, 180)
        countdown_layout = QVBoxLayout(self.abort_countdown_dialog)
        
        self.abort_countdown_label = QLabel(f"ABORT IN {initial_seconds} SECONDS")
        self.abort_countdown_label.setAlignment(Qt.AlignCenter)
        font = self.abort_countdown_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.abort_countdown_label.setFont(font)
        countdown_layout.addWidget(self.abort_countdown_label)
        
        warning_label = QLabel(f"Valve {valve_name} {cmd_type} command failed!\nClick button below to cancel abort.")
        warning_label.setAlignment(Qt.AlignCenter)
        countdown_layout.addWidget(warning_label)
        
        cancel_btn = QPushButton("CONFIRM SAFE STATE\n(Cancel Abort)")
        cancel_btn.setStyleSheet("background-color: green; color: white; font-size: 14px; padding: 10px;")
        cancel_btn.clicked.connect(self._cancel_abort_countdown)
        countdown_layout.addWidget(cancel_btn)
        
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
        if new_val == "OPEN":
            self.valve_states[valve_name] = True
        elif new_val == "CLOSED":
            self.valve_states[valve_name] = False

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
        
        if self.manual_valve_dialog:
            self.manual_valve_dialog.close()
        
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Manual Valve Control")
        dialog.setModal(False)
        layout = QVBoxLayout(dialog)
        
        self.manual_valve_dialog = dialog
        
        valve_names = list(self.valve_states.keys())
        
        self.manual_valve_buttons = {}
        for valve in valve_names:
            current_state = self.valve_states[valve]
            btn = QPushButton(valve)
            color = "green" if current_state else "red"
            btn.setStyleSheet(f"background-color: {color}; color: white;")
            self.manual_valve_buttons[valve] = btn
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

        if valve_name in self.valve_states and self.valve_states[valve_name] == new_state:
            return

        self.signals.valve_updated.emit(valve_name, "PENDING")
        
        try:
            self.ethernet_client.send_valve_command(valve_name, new_state)
        except Exception:
            pass

        self.log_event("VALVE_CHANGED", f"{valve_name}:{new_state}")

        self.pending_valve_commands[valve_name] = {
            "state": new_state,
            "last_sent": QDateTime.currentMSecsSinceEpoch(),
            "retries": 0
        }

    def check_valve_command_timeouts(self):
        """Check for valve commands that haven't been acknowledged and retry if necessary"""
        current_time = QDateTime.currentMSecsSinceEpoch()
        valves_to_delete = []

        for valve_name, info in self.pending_valve_commands.items():
            if current_time - info["last_sent"] > self.valve_retry_timeout:
                if info["retries"] < self.valve_max_retries:
                    info["retries"] += 1
                    info["last_sent"] = current_time
                    try:
                        self.ethernet_client.send_valve_command(valve_name, info["state"])
                        self.log_event("VALVE_RETRY", f"{valve_name}:{info['state']} (Attempt {info['retries']})")
                    except Exception:
                        pass
                else:
                    print(f"Timeout: Max retries reached for valve {valve_name}")
                    self.log_event("VALVE_TIMEOUT", f"{valve_name}:{info['state']}")
                    valves_to_delete.append(valve_name)

        for valve_name in valves_to_delete:
            del self.pending_valve_commands[valve_name]

    def apply_operation(self, operation: str):
        if self.lockout:
            return

        self.ethernet_client.set_system_state(operation)

        active_valves = self.valve_operation_states.get(operation, [])
        for name in self.valve_states:
            state = name in active_valves
            self.toggle_valve(name, state)

        self.signals.system_status.emit(operation)

        self.log_event("OPERATION", f"{operation}")