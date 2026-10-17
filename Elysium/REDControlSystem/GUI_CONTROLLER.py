import os
import re
import math
from collections import deque
from datetime import datetime
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QLabel, QDialogButtonBox, QMessageBox
from PyQt5.QtCore import Qt, QTimer, QDateTime, QObject, pyqtSignal
from GUI_COMMS import EthernetClient
from PID_SCHEMA import DEFAULT_ABORT_ID
from GUI_SHARE import ShareServer, ViewerClient, DEFAULT_SHARE_PORT

try:
    from CoolProp.CoolProp import PropsSI as _PropsSI
except ImportError:
    _PropsSI = None

_TEMPLATE_TOKEN_RE = re.compile(r"\{([A-Za-z0-9_]+)\}")


def render_message_template(template: str, context: dict) -> str:
    def _repl(m: "re.Match") -> str:
        key = m.group(1)
        value = context.get(key)
        if value is None:
            value = context.get(key.upper())
        if value is None:
            return m.group(0)
        return f"{value:.2f}" if isinstance(value, float) else str(value)

    return _TEMPLATE_TOKEN_RE.sub(_repl, template)


class GuiMode:
    """Operating mode of the GUI. SAFE/MANUAL/LOCKED are operator-selectable;
    ABORT is entered only by an abort (button, rule, comms failure) and is left
    only by sending SAFE."""
    SAFE   = "SAFE"     # nothing commandable; all valves closed. Default on connect.
    MANUAL = "MANUAL"   # operator may command valves, sequences, throttling
    LOCKED = "LOCKED"   # keeps current valve configuration, commands disabled
    ABORT  = "ABORT"    # abort configuration applied, commands disabled


class Signals(QObject):
    abort_triggered = pyqtSignal(str, str, str)   # abort_type, reason, abort state id ("" = default)
    mode_changed = pyqtSignal(str)          # new GuiMode value
    safe_status_changed = pyqtSignal()      # safe_applied flipped (SAFE assumed vs applied)

    # Read-only sharing (see GUI_SHARE): abort_notice fires once per abort with the abort
    # type / reason / state name (relayed to viewers); project_changed when a project is
    # (re)loaded; project_received carries a project dict streamed from a controller GUI;
    # view_only_changed when the GUI is switched between controller and viewer.
    abort_notice = pyqtSignal(str, str, str)
    project_changed = pyqtSignal()
    project_received = pyqtSignal(dict)
    view_only_changed = pyqtSignal(bool)
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)
    warnings_changed = pyqtSignal(list)
    
    valve_updated = pyqtSignal(str, str)     # can be open, closed, or pending a response from the MCU
    actuator_updated = pyqtSignal(str, float)  # proportional actuator hw_id, confirmed position (%)
    command_sent = pyqtSignal(str, float, float)  # hw_id, commanded value (valve: 1 open / 0 closed; actuator: %), timestamp (s)
    sensor_updated = pyqtSignal(str, float, float)      # sensor_name, val, timestamp
    system_status = pyqtSignal(str)

    # Calculated performance channels (Mdot, Thrust, ...) recomputed whenever
    # a sensor value changes. Payload is {channel_id: value_or_None} plus the
    # two synthesized totals under the reserved keys "__mdot_total__" and
    # "__isp__".
    calc_values_changed = pyqtSignal(dict)

    # Auto-abort countdown signals (for thread-safe dialog creation)
    countdown_start = pyqtSignal(int, str, str)  # initial_seconds, valve_name, cmd_type
    countdown_update = pyqtSignal(int)  # remaining_seconds
    countdown_close = pyqtSignal()


"""
GUI CONTROLLER

Central state manager / backend for the entire GUI. It emits signals driven
both by data arriving from the EthernetClient and by the action functions the
windows connect to their buttons.

Every window takes this controller as an initializer object: each connects
the signals here to its internal update actions and wires its buttons to the
action functions here.
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
        

        # The ethernet client calls the disconnect_callback in a separate
        # thread, so a signal is used to hop back onto the main thread before
        # touching any UI state.
        self.signals.disconnected.connect(self._on_disconnected)
        self.signals.connected.connect(self._on_connected)
        self.signals.abort_triggered.connect(self.handle_abort)
        self.signals.valve_updated.connect(self.update_valve_state)
        
        # Connect countdown signals for thread-safe dialog creation
        self.signals.countdown_start.connect(self.show_abort_countdown_dialog)
        self.signals.countdown_update.connect(self.update_abort_countdown_dialog)
        self.signals.countdown_close.connect(self.close_abort_countdown_dialog)

        # For file recording (xlsx)
        self._wb: Optional["Workbook"] = None       # openpyxl Workbook
        self._ws = None                              # active Sheet
        self._xlsx_path: str = ""                   # full path of open file

        # Sensor columns - rebuilt from project on load_project(); fallback to empty lists
        self.pt_keys:    list = []   # pressure transducers
        self.tc_keys:    list = []   # thermocouples
        self.lc_keys:    list = []   # load cells

        self.current_batch_sensors: set = set()
        self.latest_teensy_ts = ""

        # Sensor pipeline:  wire value → calibration (gain·x + offset) → tare.
        # raw_sensor_values holds calibrated-but-untared values (tare math
        # works on top of calibration).
        self.raw_sensor_values: dict = {}
        self.tare_offsets: dict = {}
        self.calibrations: dict = {}        # name -> (gain, offset)
        self.sensor_labels: dict = {}       # sensor key (hw_id) -> P&ID label, for display

        # Health tracking: last receive time + recent uncalibrated samples
        # (used for stale / flatline detection and the calibration wizard)
        self.sensor_last_rx: dict = {}      # name -> unix seconds
        self.sensor_recent: dict = {}       # name -> deque of wire values

        # These are constants and dictionaries that the UI needs to be tracked
        self.mode = GuiMode.SAFE                # SAFE until connected, and again on every connect
        # SAFE on connect is only *assumed* (nothing is commanded on connect);
        # it becomes applied when the operator sends SAFE.
        self.safe_applied = False
        # View-only (viewer) GUIs mirror a controller GUI's stream and can command nothing
        self.view_only = False
        # Abort states already driven to during the current ABORT episode
        self._applied_abort_states: set = set()
        # System-MAWP pre-warning dialog state (see _check_system_pressure_limits)
        self._prewarn_dialog = None
        self._prewarn_shown = False
        self._vent_inhibited = False

        self.pre_abort_valve_states: dict = {}
        self.current_sensor_values: dict = {}
        self.manual_valve_buttons: dict = {}
        self.abort_check_interval = 10  # ms
        self.throttling_enabled = False
        self.gimbaling_enabled = False
        self.manual_valve_dialog: QDialog = None
        self.recording = False

        # Abort countdown dialog tracking
        self.abort_countdown_dialog: Optional[QDialog] = None
        self.abort_countdown_label: Optional[QLabel] = None

        # Project / rule engine state
        self.project = None       # PIDProject set by MainWindow via load_project()
        self.project_path = None  # str path to .red file

        # Rule engine runtime state
        self._rule_violation_start: dict = {}  # rule_id -> ms timestamp when violation started
        self._rule_valve_open: dict = {}       # rule_id -> bool, tracks auto-opened valves
        self._sensor_rules: list = []          # compiled from component thresholds
        self._logic_rules: list = []           # AbortRule expression type
        self._active_warnings: dict[str, str] = {}

        # Valve Command Reliability
        self.pending_valve_commands = {} # valve_name -> {"state": bool, "last_sent": timestamp, "retries": int}
        self.valve_retry_timeout = 200 # ms
        self.valve_max_retries = 5
        self.retry_timer = QTimer()
        self.retry_timer.timeout.connect(self.check_valve_command_timeouts)
        self.retry_timer.start(100) # Check every 100ms

        # Initial valve states: False = closed (red), True = open (green)
        self.valve_states: dict[str, bool] = {
            "NCS1": False,
            "NCS2": False,
            "NCS3": False,
            "NCS5": False,
            "NCS6": False,
            "LA-BV1": False,
            "GV-1": False,
            "GV-2": False
        }

        # Proportional actuators (modulating valves, RC servos, ...): hw_id ->
        # ActuatorSpec, rebuilt from the project's component extras["actuator"]
        # on every load_project. actuator_positions holds the last position the
        # MCU confirmed (%). Actuators also live in valve_states (True = off its
        # safe position) so abort / sequences / lockout treat them like valves.
        self.actuator_specs: dict = {}
        self.actuator_positions: dict[str, float] = {}

        # hw_ids that are igniters, not valves - kept out of any automated
        # cycling (health-check valve checkout). They still live in
        # valve_states (so "Fully Closed" can safe one left firing).
        self.igniter_hw_ids: set = set()

        # Sequence execution runtime state
        self._sequence_timers: list[QTimer] = []   # kept alive during a fire sequence run

        # Calculated performance channels (Mdot, Thrust, Isp, ...). Recomputing
        # runs eval() per channel, so it's throttled to 10 Hz instead of
        # running per sample - at wire rate that was hundreds of evals/sec of
        # GUI-thread time for readouts nobody can read that fast.
        self.calc_values: dict = {}
        self._calc_dirty = False
        self.signals.sensor_updated.connect(self._mark_calc_dirty)
        self._calc_timer = QTimer()
        self._calc_timer.timeout.connect(self._flush_calc_channels)
        self._calc_timer.start(100)

        # Read-only sharing: the controller GUI serves viewers; a viewer GUI consumes it
        self.share_server = ShareServer(self._share_snapshot, parent=self.signals)
        self.viewer = ViewerClient(parent=self.signals)
        self.viewer.message.connect(self._on_viewer_message)
        self.viewer.linked.connect(lambda: self.signals.connected.emit())
        self.viewer.failed.connect(lambda reason: self.signals.disconnected.emit(reason))
        self.viewer.stale_changed.connect(self._on_viewer_stale)
        self.share_token = ""       # shared secret: required of viewers (controller) / presented (viewer)

        self.setup_abort_monitor()
    

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
    
    def _on_disconnected(self, reason: str):
        """A dropped link while live (MANUAL/LOCKED) is treated as an abort; an
        operator-requested disconnect just returns to SAFE. Nothing is live in
        SAFE/ABORT, so a failed connection attempt or a drop there is not an
        abort."""
        if self.view_only:
            # Viewer link to a controller GUI dropped: nothing to protect or abort here
            self.signals.system_status.emit(f"Viewer disconnected: {reason}" if reason else "Viewer disconnected")
            return
        if self.ethernet_client.intentional_disconnect:
            self.ethernet_client.intentional_disconnect = False
            self._cancel_sequence()
            self._set_safe_applied(False)
            self._set_mode(GuiMode.SAFE, "operator disconnect")
            self.signals.system_status.emit("Disconnected (safe)")
            return
        if self.mode in (GuiMode.SAFE, GuiMode.ABORT):
            return
        self.signals.abort_triggered.emit("DISCONNECTED", reason, "")

    def _on_connected(self):
        """Every (re)connect lands in SAFE and the Safe State preset is applied
        straight away (valves to their safe positions, actuators to safe_pct)."""
        if self.view_only:
            return              # the viewer link's hello message carries the controller's mode
        self.enter_safe_state("connected")

    # READ-ONLY SHARING --------------------------------------------------------------
    # The controller GUI (holding the Teensy link) streams to viewer GUIs via
    # GUI_SHARE.ShareServer; a viewer GUI (view_only) mirrors that stream and can
    # command nothing. See GUI_SHARE for the wire format.

    def set_view_only(self, view_only: bool):
        """Switch this GUI between controller (normal) and viewer (read-only)."""
        view_only = bool(view_only)
        if view_only == self.view_only:
            return
        if view_only:
            self.stop_sharing()
        else:
            self.viewer.disconnect_from_controller()
        self.view_only = view_only
        self.signals.view_only_changed.emit(view_only)
        self.signals.mode_changed.emit(self.mode)       # refresh anything mode-dependent

    def start_sharing(self, port: int = DEFAULT_SHARE_PORT) -> bool:
        """Start streaming to viewers (controller GUIs only). False if the port is taken."""
        if self.view_only or not self.share_server.start(port):
            return False
        s = self.signals
        self._share_links = [
            (s.sensor_updated,      self._share_sensor),
            (s.valve_updated,       self._share_valve),
            (s.actuator_updated,    self._share_actuator),
            (s.command_sent,        self._share_command),
            (s.mode_changed,        self._share_mode),
            (s.safe_status_changed, self._share_safe_status),
            (s.warnings_changed,    self._share_warnings),
            (s.system_status,       self._share_status),
            (s.abort_notice,        self._share_abort),
            (s.project_changed,     self._share_project),
            (s.connected,           self._share_link_up),
            (s.disconnected,        self._share_link_down),
        ]
        for sig, slot in self._share_links:
            sig.connect(slot)
        return True

    def stop_sharing(self):
        for sig, slot in getattr(self, "_share_links", []):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass
        self._share_links = []
        self.share_server.stop()

    def _share_snapshot(self) -> dict:
        """The hello message a newly connected viewer gets: everything needed to draw the
        current state."""
        return {
            "t": "hello", "v": 1,
            "project": self.project.to_dict() if self.project is not None else None,
            "mode": self.mode, "safe_applied": self.safe_applied,
            "link": bool(self.ethernet_client.connected),
            "valves": dict(self.valve_states),
            "actuators": dict(self.actuator_positions),
            "sensors": dict(self.current_sensor_values),
            "warnings": sorted(self._active_warnings.values()),
        }

    def _share_sensor(self, name, value, _ts):
        self.share_server.publish_sensor(name, value)

    def _share_valve(self, name, state):
        self.share_server.broadcast({"t": "v", "n": name, "s": state})

    def _share_actuator(self, name, pct):
        self.share_server.broadcast({"t": "a", "n": name, "p": pct})

    def _share_command(self, name, value, _ts):
        self.share_server.broadcast({"t": "c", "n": name, "v": value})

    def _share_mode(self, mode):
        self.share_server.broadcast({"t": "m", "mode": mode, "sa": self.safe_applied})

    def _share_safe_status(self):
        self.share_server.broadcast({"t": "m", "mode": self.mode, "sa": self.safe_applied})

    def _share_warnings(self, messages):
        self.share_server.broadcast({"t": "w", "d": list(messages)})

    def _share_status(self, text):
        self.share_server.broadcast({"t": "st", "d": text})

    def _share_abort(self, abort_type, reason, state_name):
        self.share_server.broadcast({"t": "ab", "type": abort_type, "reason": reason, "state": state_name})

    def _share_project(self):
        if self.project is not None:
            self.share_server.broadcast({"t": "project", "project": self.project.to_dict()})

    def _share_link_up(self):
        self.share_server.broadcast({"t": "link", "up": True})

    def _share_link_down(self, reason=""):
        self.share_server.broadcast({"t": "link", "up": False, "reason": reason})

    # -- viewer side ---------------------------------------------------------
    def _on_viewer_message(self, msg: dict):
        if not self.view_only:
            return
        t = msg.get("t")
        if t in ("hello", "project") and msg.get("project"):
            self.signals.project_received.emit(msg["project"])      # the main window loads it
        if t == "hello":
            for name, is_open in msg.get("valves", {}).items():
                self.signals.valve_updated.emit(name, "OPEN" if is_open else "CLOSED")
            for name, pct in msg.get("actuators", {}).items():
                self._apply_actuator_position(name, pct)
            for name, value in msg.get("sensors", {}).items():
                self.apply_remote_sensor(name, value)
            self.signals.warnings_changed.emit(list(msg.get("warnings", [])))
            self.apply_remote_mode(msg.get("mode", GuiMode.SAFE), msg.get("safe_applied", False))
            if not msg.get("link", True):
                self.signals.system_status.emit("Controller GUI is not connected to the Teensy")
        elif t == "s":
            for name, value in msg.get("d", []):
                self.apply_remote_sensor(name, value)
        elif t == "v":
            self.signals.valve_updated.emit(msg.get("n", ""), msg.get("s", "CLOSED"))
        elif t == "a":
            self._apply_actuator_position(msg.get("n", ""), float(msg.get("p", 0.0)))
        elif t == "c":      # stamped on arrival: the two laptops' clocks are not synchronised
            self.signals.command_sent.emit(msg.get("n", ""), float(msg.get("v", 0.0)),
                                           QDateTime.currentMSecsSinceEpoch() / 1000.0)
        elif t == "m":
            self.apply_remote_mode(msg.get("mode", GuiMode.SAFE), msg.get("sa", False))
        elif t == "w":
            self.signals.warnings_changed.emit(list(msg.get("d", [])))
        elif t == "st":
            self.signals.system_status.emit(msg.get("d", ""))
        elif t == "ab":
            self.show_remote_abort(msg.get("type", ""), msg.get("reason", ""), msg.get("state", ""))
        elif t == "link":
            self.signals.system_status.emit(
                "Controller GUI reconnected to the Teensy" if msg.get("up")
                else f"Controller GUI lost its Teensy link: {msg.get('reason', '')}".rstrip(": "))

    def _on_viewer_stale(self, stale: bool, why: str):
        self.signals.system_status.emit(
            f"VIEWER DATA STALE: {why}" if stale else "Viewer link live again")

    def apply_remote_sensor(self, name: str, value: float):
        """A sensor value streamed from the controller (already calibrated / tared there)."""
        now = QDateTime.currentMSecsSinceEpoch() / 1000.0
        self.raw_sensor_values[name] = value
        self.current_sensor_values[name] = value
        self.sensor_last_rx[name] = now
        self.signals.sensor_updated.emit(name, value, now)

    def apply_remote_mode(self, mode: str, safe_applied: bool):
        self.mode = mode
        self.safe_applied = bool(safe_applied)
        self.signals.mode_changed.emit(mode)
        self.signals.safe_status_changed.emit()

    def show_remote_abort(self, abort_type: str, reason: str, state_name: str):
        """Abort alert on a viewer: a banner window that doesn't block the screen."""
        box = QMessageBox(
            QMessageBox.Critical, "ABORT (controller)",
            f"The controller aborted.\n\nAbort Type: {abort_type}\nReason: {reason}\n"
            f"Abort State: {state_name}", QMessageBox.Ok, self.parent)
        box.setWindowModality(Qt.NonModal)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.show()

    # MODES --------------------------------------------------------------------------------------------------------

    @property
    def lockout(self) -> bool:
        """True whenever the operator may not command valves (everything but MANUAL)."""
        return self.view_only or self.mode != GuiMode.MANUAL

    @property
    def sequence_running(self) -> bool:
        return any(t.isActive() for t in self._sequence_timers)

    def _set_mode(self, mode: str, reason: str = ""):
        if mode == self.mode:
            return
        previous = self.mode
        self.mode = mode
        self.log_event("MODE_CHANGE", f"{previous}->{mode}" + (f" ({reason})" if reason else ""))
        self.signals.mode_changed.emit(mode)

    def request_mode(self, mode: str) -> Optional[str]:
        """Operator mode change (dropdown + SEND). Returns an error message if
        the change is refused, else None."""
        if self.view_only:
            return "This GUI is in view-only mode and cannot change modes."
        if not self.ethernet_client.connected:
            return "Connect to the system before changing modes."
        if mode == GuiMode.SAFE:
            if self.mode == GuiMode.SAFE and self.safe_applied:
                return None
            self.enter_safe_state("operator")
            return None
        if mode == self.mode:
            return None
        if self.mode == GuiMode.ABORT:
            return "The system is in ABORT. Send SAFE before selecting another mode."
        if mode == GuiMode.LOCKED:
            if self.sequence_running:
                return "A sequence is running. It cannot be locked - use ABORT to stop it."
            self._set_mode(GuiMode.LOCKED, "operator")
        elif mode == GuiMode.MANUAL:
            if self.project is not None and not self.abort_state_confirmed:
                return ("The Safe State has not been defined for this P&ID. Go to the 'Abort Config' "
                        "tab > Abort States, set the 'Default Abort' valve positions (this is the "
                        "Safe State) and press 'Confirm This State' before using MANUAL.")
            if self.mode == GuiMode.SAFE:
                self.ethernet_client.set_system_state("MANUAL")
            self._set_mode(GuiMode.MANUAL, "operator")
        return None

    def _abandon_pending_commands(self) -> set:
        """Drop in-flight valve commands/retries and any failure countdown, since
        the SAFE/ABORT configuration is about to supersede them. Returns the
        valves that had a command in flight: their local state can't be trusted
        (the MCU may have acted on it), so the caller re-commands them."""
        in_flight = set(self.pending_valve_commands)
        self.pending_valve_commands.clear()
        self.ethernet_client.cancel_auto_abort_countdown()
        self.close_abort_countdown_dialog()
        return in_flight

    def _apply_valve_config(self, targets: dict, force: set):
        """Drive valves to {hw_id: open?}, ignoring the lockout gate."""
        for valve, want_open in targets.items():
            self._drive_valve(valve, want_open, force=valve in force)

    def _set_safe_applied(self, applied: bool):
        if self.safe_applied != applied:
            self.safe_applied = applied
            self.signals.safe_status_changed.emit()

    def abort_valve_targets(self, state_id: str = "") -> dict:
        """{hw_id: open?} for every valve in the given named abort state ("" =
        default). Valves the state doesn't list - or everything, if there is no
        project / nothing configured - are closed."""
        targets = {v: False for v in self.valve_states}
        project = self.project
        if project is not None:
            for cid, want_open in project.get_abort_state(state_id).valves.items():
                comp = project.components.get(cid)
                if comp is None:
                    continue
                hw_id = comp.extras.get("hw_id") or comp.label
                if hw_id in targets and hw_id not in self.igniter_hw_ids:
                    targets[hw_id] = bool(want_open)
        return targets

    def refresh_safe_state_warning(self):
        """Persistent warning while the project's Safe State (default abort state) is
        not confirmed; cleared as soon as it is."""
        if self.view_only:
            return              # warnings come from the controller's stream
        if self.project is not None and not self.abort_state_confirmed:
            self._set_warning(
                "safe_state_undefined",
                "SAFE STATE NOT DEFINED - set and confirm the Default Abort in Abort Config "
                "(MANUAL is blocked until then)")
        else:
            self._clear_warning("safe_state_undefined")

    @property
    def abort_state_confirmed(self) -> bool:
        """Whether the default abort state (= the Safe State preset) is confirmed."""
        return bool(self.project is not None and self.project.default_abort_state().confirmed)

    def enter_safe_state(self, reason: str = ""):
        """SAFE mode: drive to the Safe State preset (the project's default abort
        state; all closed if none is defined), nothing commandable."""
        self._cancel_sequence()
        in_flight = self._abandon_pending_commands()
        self.ethernet_client.set_system_state("SAFE")
        self._applied_abort_states.clear()
        self._set_mode(GuiMode.SAFE, reason)
        targets = self.abort_valve_targets("")
        self._apply_valve_config(targets, in_flight)
        self._set_safe_applied(True)
        opened = [v for v, o in targets.items() if o]
        self.log_event("SAFE_STATE", "applied" + (f"; open: {', '.join(opened)}" if opened else ""))

    def request_safe_disconnect(self):
        """Operator disconnect: notify the MCU (SFE) and tear the link down
        without the abort path firing."""
        self.log_event("OPERATOR_DISCONNECT", "Safe disconnect requested")
        self.ethernet_client.graceful_disconnect()

    def handle_connect(self, success: bool):
        if success:
            self.ethernet_client.set_system_state("CONNECTED")
            # Clear any stale status text left over from a prior disconnect
            # (e.g. "Disconnected (safe)") so it doesn't linger after reconnect.
            self.signals.system_status.emit("")
            self.signals.connected.emit()
        else:
            detailed_reason = self.ethernet_client.last_connection_error or "Connection failed"
            concise_reason = self._summarize_connection_error(detailed_reason)
            self.signals.disconnected.emit(concise_reason)
    
    def setup_abort_monitor(self):
        self.abort_timer = QTimer()
        self.abort_timer.timeout.connect(self.check_abort_conditions)
        self.abort_timer.start(self.abort_check_interval)

    def load_project(self, project, path: str = None):
        self.project = project
        if path:
            self.project_path = path
        self._rebuild_sensor_keys(project)
        self._rebuild_valve_states(project)
        self._rebuild_actuators(project)
        self.load_calibrations_from_project(project)
        self.reload_abort_rules(project)
        self.ethernet_client.load_project_maps(project)
        self.refresh_safe_state_warning()
        self._emit_warnings()
        self.signals.project_changed.emit()
        self._recompute_calc_channels()

    def _rebuild_valve_states(self, project):
        """Rebuild valve_states from project valve components (hw_id -> bool).
        Existing states are preserved for valves that carry over; new valves start closed."""
        from PID_SCHEMA import (
            COMP_VALVE, COMP_THROTTLE_VALVE, COMP_BALL_VALVE, COMP_GLOBE_VALVE,
            COMP_SOLENOID, COMP_IGNITER, get_actuator_spec,
        )
        VALVE_TYPES = (COMP_VALVE, COMP_THROTTLE_VALVE, COMP_BALL_VALVE,
                       COMP_GLOBE_VALVE, COMP_SOLENOID, COMP_IGNITER)

        if not project:
            return

        new_states: dict[str, bool] = {}
        new_igniters: set = set()
        for comp in project.components.values():
            # Anything carrying an actuator spec (e.g. an ep_throttle_valve or a
            # servo-driven ball valve) is commandable even if its type isn't listed.
            if comp.type not in VALVE_TYPES and get_actuator_spec(comp) is None:
                continue
            hw_id = comp.extras.get("hw_id") or comp.label
            if not hw_id:
                continue
            # Preserve state if valve was already known, default to closed
            new_states[hw_id] = self.valve_states.get(hw_id, False)
            if comp.type == COMP_IGNITER:
                new_igniters.add(hw_id)

        self.valve_states = new_states
        self.igniter_hw_ids = new_igniters

    def _rebuild_actuators(self, project):
        """Rebuild actuator_specs from the project (see PID_SCHEMA.get_actuator_spec).
        Positions carry over for actuators that survive a reload; new ones
        start at their safe position."""
        from PID_SCHEMA import get_actuator_spec

        specs: dict = {}
        if project:
            for comp in project.components.values():
                spec = get_actuator_spec(comp)
                hw_id = comp.extras.get("hw_id") or comp.label
                if spec is not None and hw_id and hw_id in self.valve_states:
                    specs[hw_id] = spec

        self.actuator_specs = specs
        self.actuator_positions = {
            hw: self.actuator_positions.get(hw, spec.safe_pct) for hw, spec in specs.items()}

    def sensor_display_name(self, key: str) -> str:
        """Name shown to the operator for a sensor key: the P&ID label (e.g.
        OPT-1301) when the key is a separate internal hw_id (e.g. P2)."""
        return self.sensor_labels.get(key, key)

    def _rebuild_sensor_keys(self, project):
        from PID_SCHEMA import COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL
        pt, tc, lc = [], [], []
        self.sensor_labels = {}
        if project:
            for comp in project.components.values():
                hw_id = comp.extras.get("hw_id", comp.label) or comp.label
                if not hw_id:
                    continue
                if comp.type in (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL) and comp.label:
                    self.sensor_labels[hw_id] = comp.label
                if comp.type == COMP_PRESSURE:
                    pt.append(hw_id)
                elif comp.type == COMP_TEMPERATURE:
                    tc.append(hw_id)
                elif comp.type == COMP_LOAD_CELL:
                    lc.append(hw_id)
        self.pt_keys = sorted(set(pt), key=lambda x: (len(x), x))
        self.tc_keys = sorted(set(tc), key=lambda x: (len(x), x))
        self.lc_keys = sorted(set(lc), key=lambda x: (len(x), x))

    def _generate_filename(self) -> str:
        """
        Auto-generate a filename following the convention:
            {ProjectName}{Version}_{MMDDYYYY}_test{N}.xlsx
        The test number increments so existing files are never overwritten.
        If no project is loaded, falls back to 'DAQ_{date}_test{N}.xlsx'.
        """
        if self.project:
            raw_version = getattr(self.project, "version", "") or ""
            proj_part = f"{self.project.name}{raw_version}"
        else:
            proj_part = "DAQ"

        date_part = datetime.now().strftime("%m%d%Y")
        base = f"{proj_part}_{date_part}"

        data_dir = "Data"
        os.makedirs(data_dir, exist_ok=True)

        n = 1
        while True:
            name = f"{base}_test{n}.xlsx"
            if not os.path.exists(os.path.join(data_dir, name)):
                return name
            n += 1

    def reload_abort_rules(self, project):
        self._sensor_rules = []
        self._logic_rules  = []
        self._rule_violation_start.clear()
        self._rule_valve_open.clear()
        self._active_warnings.clear()

        if project is None:
            return

        from PID_SCHEMA import (
            COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL,
            SensorThresholds,
        )
        SENSOR_TYPES = (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL)

        for cid, comp in project.components.items():
            if comp.type not in SENSOR_TYPES:
                continue

            th_dict = comp.extras.get("thresholds")
            if not th_dict:
                continue

            th = SensorThresholds.from_dict(th_dict)
            hw_id = comp.extras.get("hw_id", comp.label) or cid

            bands = [
                ("mawp",    th.mawp,    th.mawp_action,   None,                                                          None),
                ("meop",    th.meop,    th.meop_action,   th_dict.get("meop_target",   th.target_valve),                  th_dict.get("meop_close_below",   th.close_valve_below)),
                ("relief",  th.relief,  th.relief_action, th_dict.get("relief_target", th.target_valve),                  th_dict.get("relief_close_below", th.close_valve_below)),
            ]

            for band, threshold, action, target, close_below in bands:
                if threshold is None:
                    continue
                rule_id = f"{cid}__{band}"
                self._sensor_rules.append({
                    "id":           rule_id,
                    "hw_id":        hw_id,
                    "band":         band,
                    "threshold":    threshold,
                    "action":       action,
                    "target_valve": target or "",
                    "close_below":  close_below,
                    "soak_ms":      th.soak_ms,
                    "above":        True,
                    # Optional custom {TOKEN} message template for this band -
                    # blank means fall back to the built-in default wording.
                    "message":      th_dict.get(f"{band}_message", ""),
                    "abort_state":  getattr(th, f"{band}_state", ""),
                })

        for rule in project.rules:
            if rule.condition_type == "expression" and rule.enabled and rule.expression.strip():
                self._logic_rules.append(rule)

        self._emit_warnings()

    def _emit_warnings(self):
        messages = sorted(self._active_warnings.values())
        self.signals.warnings_changed.emit(messages)

    def _set_warning(self, warning_id: str, message: str):
        if self._active_warnings.get(warning_id) == message:
            return
        self._active_warnings[warning_id] = message
        self._emit_warnings()

    def _clear_warning(self, warning_id: str):
        if warning_id in self._active_warnings:
            del self._active_warnings[warning_id]
            self._emit_warnings()

    def get_sensor_status(self, hw_name: str, value: float) -> str:
        mawp_val   = None
        meop_val   = None
        relief_val = None
        for sr in self._sensor_rules:
            if sr["hw_id"].upper() != hw_name.upper():
                continue
            if sr["band"] == "mawp":
                mawp_val = sr["threshold"]
            elif sr["band"] == "meop":
                meop_val = sr["threshold"]
            elif sr["band"] == "relief":
                relief_val = sr["threshold"]

        if mawp_val   is not None and value >= mawp_val:
            return "RED"
        if meop_val   is not None and value >= meop_val:
            return "ORANGE"
        if relief_val is not None and value >= relief_val:
            return "BLUE"
        return "DEFAULT"

    # ── Calculated performance channels (Mdot / Thrust / Isp) ──────────────
    # Standard gravity, used for Isp(s) = Thrust(lbf) / (Mdot(lbm/s) * G0).
    # Exposed inside channel expressions too (as G0) for anyone writing a
    # custom formula that needs it.
    G0 = 32.174

    _CALC_SAFE_FUNCS = {
        "sqrt": math.sqrt, "abs": abs, "min": min, "max": max, "pow": pow,
        "G0": G0,
    }
    if _PropsSI is not None:
        # CoolProp fluid property lookup, e.g. PropsSI('D','T',TC1+273.15,'P',P1*6894.76,'N2O')
        # to get temperature/pressure-corrected density instead of a fixed SG constant.
        _CALC_SAFE_FUNCS["PropsSI"] = _PropsSI

    def _mark_calc_dirty(self, *_args):
        self._calc_dirty = True

    def _flush_calc_channels(self):
        if not self._calc_dirty:
            return
        self._calc_dirty = False
        self._recompute_calc_channels()

    def _recompute_calc_channels(self):
        """Evaluate every CalcChannel against the current sensor values and
        each channel's own constants, the same Python-safe-expression
        approach already used for abort-rule expressions. Also synthesizes
        Total Mdot (sum of mdot_fuel + mdot_ox roles) and Isp
        (thrust / (total_mdot * G0))."""
        values: dict = {}
        channels = list(getattr(self.project, "calc_channels", []) or []) if self.project else []

        for ch in channels:
            if not ch.enabled or not ch.expression.strip():
                values[ch.id] = None
                continue
            ctx = dict(self._CALC_SAFE_FUNCS)
            ctx.update(self.current_sensor_values)
            ctx.update(ch.constants)
            try:
                values[ch.id] = float(eval(ch.expression, {"__builtins__": {}}, ctx))
            except Exception:
                values[ch.id] = None

        mdot_total = 0.0
        have_mdot = False
        thrust_total = 0.0
        have_thrust = False
        for ch in channels:
            v = values.get(ch.id)
            if v is None:
                continue
            if ch.role in ("mdot_fuel", "mdot_ox"):
                mdot_total += v
                have_mdot = True
            elif ch.role == "thrust":
                thrust_total += v
                have_thrust = True

        values["__mdot_total__"] = mdot_total if have_mdot else None
        values["__thrust_total__"] = thrust_total if have_thrust else None
        if have_thrust and have_mdot and mdot_total > 0:
            values["__isp__"] = thrust_total / (mdot_total * self.G0)
        else:
            values["__isp__"] = None

        self.calc_values = values
        self.signals.calc_values_changed.emit(values)


    def check_abort_conditions(self):
        if self.view_only:
            return              # the controller GUI evaluates limits and rules
        if not self.current_sensor_values:
            return

        locked_out = self.lockout

        current_time = QDateTime.currentMSecsSinceEpoch()

        self._check_system_pressure_limits(locked_out)

        for sr in self._sensor_rules:
            hw_id = sr["hw_id"].upper()
            value = self.current_sensor_values.get(hw_id)
            if value is None:
                self._rule_violation_start.pop(sr["id"], None)
                continue

            threshold = sr["threshold"]
            violated  = (value >= threshold) if sr["above"] else (value <= threshold)

            if not violated:
                # Clear soak timer
                self._rule_violation_start.pop(sr["id"], None)
                self._clear_warning(sr["id"])
                # Close auto-opened valve if below hysteresis close threshold
                if sr["action"] == "open_valve" and self._rule_valve_open.get(sr["id"]):
                    close_below = sr["close_below"]
                    if close_below is not None and value < close_below:
                        if sr["target_valve"] and sr["target_valve"] in self.valve_states:
                            self.toggle_valve(sr["target_valve"], False)
                        self._rule_valve_open[sr["id"]] = False
                continue

            # Violation detected - handle soak time
            soak = sr["soak_ms"]
            if soak > 0:
                if sr["id"] not in self._rule_violation_start:
                    self._rule_violation_start[sr["id"]] = current_time
                    continue
                elif current_time - self._rule_violation_start[sr["id"]] < soak:
                    continue

            self._fire_sensor_rule(sr, hw_id, value, locked_out)

        for rule in self._logic_rules:
            self._check_logic_rule(rule, current_time, locked_out)

    # Per-sensor threshold band -> display word. Internal dict keys/extras
    # stay "mawp" for backward file compatibility; only the shown text changed.
    _BAND_DISPLAY = {"mawp": "HIGH", "meop": "MEOP", "relief": "RELIEF"}

    def _abort_suppressed(self, state_id: str = "") -> bool:
        """Whether a rule-driven abort for this state should be skipped: with no
        link (stale values), when it's already been applied this abort (would
        re-fire every tick), when the default abort would override a state already
        applied, or when the default abort fires in SAFE (already safe). A named
        non-default state (e.g. a vent) still fires in SAFE."""
        if not self.ethernet_client.connected:
            return True
        sid = state_id or DEFAULT_ABORT_ID
        if self.mode == GuiMode.ABORT:
            return sid in self._applied_abort_states or (
                sid == DEFAULT_ABORT_ID and bool(self._applied_abort_states))
        return self.mode == GuiMode.SAFE and sid == DEFAULT_ABORT_ID

    def _check_system_pressure_limits(self, locked_out: bool):
        """System-wide backstop across all PTs, independent of (and in addition to)
        the per-sensor thresholds: warn above system MEOP; a clear-the-area dialog
        at the pre-warn level (system_prewarn_pct of MAWP); and the configured
        abort state at 95% of system MAWP. The operator can cancel the auto-action
        from the dialog; it re-arms once pressure falls back below the pre-warn
        level."""
        params = getattr(self.project, "parameters", None) if self.project else None
        if not params:
            return

        mawp = getattr(params, "system_mawp", None)
        meop = getattr(params, "system_meop", None)
        if mawp is None and meop is None:
            return

        abort_limit = 0.95 * mawp if mawp is not None else None
        prewarn_pct = float(getattr(params, "system_prewarn_pct", 90.0) or 0.0)
        prewarn_level = (mawp * prewarn_pct / 100.0
                         if mawp is not None and 0.0 < prewarn_pct < 95.0 else None)
        state_id = getattr(params, "system_mawp_state", "")

        peak_key, peak = None, None
        for hw_id in self.pt_keys:
            v = self.current_sensor_values.get(hw_id.upper())
            if v is not None and (peak is None or v > peak):
                peak_key, peak = hw_id.upper(), v

        # Pre-warn dialog / inhibit bookkeeping (one state machine for the system)
        if prewarn_level is None or peak is None or peak < prewarn_level:
            self._rearm_system_vent()
        elif (not self._prewarn_shown and not self._abort_suppressed(state_id)
              and abort_limit is not None):
            self._prewarn_shown = True
            self._show_prewarn_dialog(peak_key, peak, prewarn_level, abort_limit, mawp, state_id)

        for hw_id in self.pt_keys:
            key = hw_id.upper()
            value = self.current_sensor_values.get(key)
            if value is None:
                continue

            if abort_limit is not None and value >= abort_limit:
                self._clear_warning(f"system_meop__{key}")
                if not self._abort_suppressed(state_id) and not self._vent_inhibited:
                    ctx = self._sensor_message_context(value=value, threshold=abort_limit,
                                                       limit=abort_limit, mawp=mawp)
                    template = (params.system_mawp_message.strip() if params.system_mawp_message
                               else f"{key} ({{{key}}}) exceeds 95% of system MAWP "
                                    "({mawp} psi -> limit {limit} psi)")
                    detail = render_message_template(template, ctx)
                    self._close_prewarn_dialog()
                    self.signals.abort_triggered.emit("system_mawp", detail, state_id)
                continue

            if meop is not None and value >= meop:
                ctx = self._sensor_message_context(value=value, threshold=meop, limit=meop)
                template = (params.system_meop_message.strip() if params.system_meop_message
                           else f"{key} ({{{key}}}) is above system MEOP (limit {{limit}} psi)")
                self._set_warning(f"system_meop__{key}", render_message_template(template, ctx))
            else:
                self._clear_warning(f"system_meop__{key}")

    # System-MAWP pre-warning -------------------------------------------------------

    def _rearm_system_vent(self):
        if self._vent_inhibited:
            self._clear_warning("system_vent_inhibited")
            self.log_event("VENT_REARMED", "pressure back below the pre-warn level")
        self._vent_inhibited = False
        self._prewarn_shown = False
        self._close_prewarn_dialog()

    def _close_prewarn_dialog(self):
        if self._prewarn_dialog is not None:
            self._prewarn_dialog.close()
            self._prewarn_dialog = None

    def _show_prewarn_dialog(self, key, value, level, limit, mawp, state_id):
        state = self.project.get_abort_state(state_id)
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("SYSTEM APPROACHING MAWP")
        dlg.setModal(False)
        dlg.setMinimumWidth(460)
        lay = QVBoxLayout(dlg)

        head = QLabel("SYSTEM APPROACHING MAWP\nCLEAR THE AREA")
        head.setAlignment(Qt.AlignCenter)
        f = head.font(); f.setPointSize(16); f.setBold(True); head.setFont(f)
        head.setStyleSheet("color: #c62828;")
        lay.addWidget(head)

        body = QLabel(
            f"{key} is at {value:.0f} psi (warning level {level:.0f} psi, MAWP {mawp:.0f} psi).\n\n"
            f"The system will automatically apply '{state.name}' and lock down at {limit:.0f} psi.")
        body.setWordWrap(True)
        lay.addWidget(body)

        now_btn = QPushButton(f"APPLY '{state.name.upper()}' NOW")
        now_btn.setStyleSheet("background-color: #c62828; color: white; font-size: 14px; padding: 10px;")
        cancel_btn = QPushButton("CANCEL AUTO-ACTION\n(I'll decide - re-arms when pressure drops)")
        cancel_btn.setStyleSheet("background-color: #555; color: white; font-size: 13px; padding: 10px;")
        lay.addWidget(now_btn)
        lay.addWidget(cancel_btn)

        def apply_now():
            self._close_prewarn_dialog()
            self.log_event("VENT_NOW", f"operator applied '{state.name}' early at {value:.0f} psi")
            self.signals.abort_triggered.emit(
                "system_mawp", f"Operator applied '{state.name}' early ({key} at {value:.0f} psi)",
                state_id)

        def cancel_auto():
            self._vent_inhibited = True
            self._close_prewarn_dialog()
            self._set_warning(
                "system_vent_inhibited",
                f"AUTO-ACTION INHIBITED: '{state.name}' will not fire at {limit:.0f} psi until "
                f"pressure drops below {level:.0f} psi")
            self.log_event("VENT_INHIBITED", f"operator cancelled auto-action ({key} at {value:.0f} psi)")

        now_btn.clicked.connect(apply_now)
        cancel_btn.clicked.connect(cancel_auto)
        self._prewarn_dialog = dlg
        self.log_event("PREWARN_SHOWN", f"{key} at {value:.0f} psi")
        dlg.show()
        dlg.raise_()

    def _sensor_message_context(self, **extra) -> dict:
        """Base context for message templates: every live sensor value plus
        whatever special keywords (value/threshold/soak_ms/...) the caller
        supplies for this specific rule."""
        ctx = dict(self.current_sensor_values)
        ctx.update(extra)
        return ctx

    def _fire_sensor_rule(self, sr: dict, hw_id: str, value: float, locked_out: bool = False):
        action  = sr["action"]
        band    = sr["band"]
        rule_id = sr["id"]
        band_disp = self._BAND_DISPLAY.get(band, band.upper())

        ctx = self._sensor_message_context(
            value=value, threshold=sr["threshold"], soak_ms=sr["soak_ms"],
            hw_id=hw_id, band=band_disp,
        )
        template = sr["message"].strip() if sr.get("message") else (
            "{hw_id} {band} threshold exceeded: {value} (limit {threshold})")
        message = render_message_template(template, ctx)

        if action == "abort":
            if self._abort_suppressed(sr.get("abort_state", "")):
                return
            # Show "P1 HIGH" (derived from the sensor's own hw_id/band), never
            # the internal rule_id ("PT_1__mawp") - nothing here is hardcoded,
            # it's built from this sensor's own configuration.
            self.signals.abort_triggered.emit(f"{hw_id} {band_disp}", message, sr.get("abort_state", ""))

        elif action == "warn":
            # Keep a persistent UI warning without escalating to abort.
            self._set_warning(rule_id, message)
            self.log_event("WARN", message)
            self.signals.system_status.emit(f"WARNING: {message}")

        elif action == "open_valve":
            if locked_out:
                return
            target = sr["target_valve"]
            if target and not self._rule_valve_open.get(rule_id):
                if target in self.valve_states:
                    self.toggle_valve(target, True)
                self._rule_valve_open[rule_id] = True
                self.log_event("AUTO_VALVE_OPEN",
                               f"Rule {rule_id}: opened {target} ({hw_id}={value:.2f})")

    def _check_logic_rule(self, rule, current_time: int, locked_out: bool = False):
        try:
            result = bool(eval(rule.expression, {"__builtins__": {}},
                               self.current_sensor_values))
        except Exception:
            return

        rule_id = rule.id
        if not result:
            self._rule_violation_start.pop(rule_id, None)
            self._clear_warning(rule_id)
            # Close valve if hysteresis met
            if rule.action == "open_valve" and self._rule_valve_open.get(rule_id):
                if rule.close_valve_below is not None:
                    # Can't check a sensor value without knowing which one for generic expressions;
                    # use the inverse of the expression result as the close condition instead.
                    self._rule_valve_open[rule_id] = False
                    if rule.target_valve and rule.target_valve in self.valve_states:
                        self.toggle_valve(rule.target_valve, False)
            return

        soak = rule.soak_ms
        if soak > 0:
            if rule_id not in self._rule_violation_start:
                self._rule_violation_start[rule_id] = current_time
                return
            elif current_time - self._rule_violation_start[rule_id] < soak:
                return

        if rule.action == "abort":
            if self._abort_suppressed(rule.abort_state):
                return
            message = self._render_logic_rule_message(rule)
            # Show the rule's own description ("high chamber pressure"), set
            # by the operator in Abort Config - never the auto-generated
            # rule_id ("logic_rule_3"). Falls back to the expression, then
            # the id, only if the operator left description blank.
            label = rule.description.strip() or rule.expression.strip() or rule_id
            self.signals.abort_triggered.emit(label, message, rule.abort_state)
        elif rule.action == "open_valve":
            if locked_out:
                return
            if not self._rule_valve_open.get(rule_id):
                if rule.target_valve and rule.target_valve in self.valve_states:
                    self.toggle_valve(rule.target_valve, True)
                self._rule_valve_open[rule_id] = True
                self.log_event("AUTO_VALVE_OPEN",
                               f"Rule {rule_id}: opened {rule.target_valve}")
        elif rule.action == "warn":
            msg = self._render_logic_rule_message(rule)
            self._set_warning(rule_id, msg)
            self.log_event("WARN", f"Rule {rule_id}: {msg}")

    def _auto_template_from_expression(self, expression: str) -> str:
        """Best-effort default template for a logic rule with no custom
        message: wraps each referenced sensor name with its live value, e.g.
        'P5 > P3' -> 'P5 ({P5}) > P3 ({P3})'."""
        def _repl(m: "re.Match") -> str:
            name = m.group(0)
            return f"{name} ({{{name}}})" if name in self.current_sensor_values else name
        return re.sub(r"[A-Za-z_][A-Za-z0-9_]*", _repl, expression)

    def _render_logic_rule_message(self, rule) -> str:
        """Custom {TOKEN} message_template if the user configured one in Abort
        Config, else an auto-generated 'P5 (600) > P3 (595) for 150ms'-style
        message from the expression - never a blanket dump of every sensor."""
        ctx = self._sensor_message_context(soak_ms=rule.soak_ms, expression=rule.expression)
        template = rule.message_template.strip()
        if not template:
            template = rule.description.strip() or self._auto_template_from_expression(rule.expression)
            if rule.soak_ms > 0 and "{soak_ms}" not in template:
                template += " for {soak_ms}ms"
        return render_message_template(template, ctx)

    def trigger_manual_abort(self):
        """Manual abort button handler (Req 11)"""
        if self.view_only:
            return
        self.signals.abort_triggered.emit(
            "manual_abort",
            "Operator triggered manual abort",
            ""
        )

    def show_abort_control(self):
        """Redirects to the Abort Config tab in the main window if possible."""
        # The AbortConfigPage is now a full tab, so just log / no-op.
        # If called from a button in DAQWindow, we emit a signal or show a message.
        QMessageBox.information(
            self.parent,
            "Abort Configuration",
            "Use the 'Abort Config' tab to configure abort thresholds and rules."
        )

    def handle_abort(self, abort_type, reason, state_id=""):
        """Abort sequence (Req 11, 20-24): stop any sequence, drive the valves to
        the named abort state ("" = the default one), and lock the system down
        (ABORT mode) so operators can assess before anything else happens.

        Works in MANUAL and LOCKED, bypassing the operator lockout gate. Ignored
        in SAFE for the default abort (already safe) - but a named state such as
        a vent still fires there. While already in ABORT, only a state not yet
        applied this episode is run (an escalation, e.g. a vent after a default
        abort); the default abort never overrides a state already applied."""
        if self.view_only:
            return
        sid = state_id or DEFAULT_ABORT_ID
        if self.mode == GuiMode.ABORT and (
                sid in self._applied_abort_states
                or (sid == DEFAULT_ABORT_ID and self._applied_abort_states)):
            return

        # SAFE already is the Safe State preset with nothing live, so the default
        # abort (comms fault, rule, button) must not run there.
        if self.mode == GuiMode.SAFE and sid == DEFAULT_ABORT_ID:
            self.log_event("ABORT_IGNORED_IN_SAFE", f"{abort_type}:{reason}")
            self.signals.system_status.emit(f"WARNING: {abort_type} in SAFE ({reason}) - holding SAFE")
            return

        # Stop any running auto-fire sequence immediately
        self._cancel_sequence()
        in_flight = self._abandon_pending_commands()

        self.ethernet_client.set_system_state("ABORT")
        self.pre_abort_valve_states = self.valve_states.copy()

        # Enter ABORT before anything modal: the abort monitor keeps ticking
        # while the dialog below is open and must not re-fire.
        self._applied_abort_states.add(sid)
        self._set_mode(GuiMode.ABORT, abort_type)

        state = self.project.get_abort_state(sid) if self.project is not None else None
        state_name = state.name if state is not None else "Default Abort"
        targets = self.abort_valve_targets(sid)
        self._apply_valve_config(targets, in_flight)
        opened = [v for v, o in targets.items() if o]
        self.log_event("ABORT_STATE", f"{state_name}" + (f"; open: {', '.join(opened)}" if opened else "; all closed"))

        # `reason` is already a specific, relevant message by this point -
        # sensor-threshold and logic-rule aborts render it from a (customizable,
        # see Abort Config) {TOKEN} template naming exactly the sensors
        # involved, e.g. "P5 (600.00) > P3 (595.00) for 150ms". Triggers with
        # no sensor context (manual abort, comms loss, disconnect) just show
        # their reason as-is. Dumping every PT's value on every abort regardless
        # of relevance was more noise than signal, so that's gone.
        self.log_event("ABORT", f"{abort_type}:{reason}")
        self.signals.abort_notice.emit(abort_type, reason, state_name)
        QMessageBox.critical(
            self.parent, # has to bind to a real widget
            "ABORT TRIGGERED",
            f"Abort Type: {abort_type}\nReason: {reason}\nAbort State: {state_name}"
        )
        self._return_to_safe_after_abort()

    def _return_to_safe_after_abort(self):
        """Once the operator has acknowledged an abort, fall back to SAFE on their
        behalf (no manual SAFE send needed). If only the default abort ran, its
        valve config *is* the Safe State, so apply it; if an escalated state (e.g.
        a vent) ran, switch the mode but leave its valves as they are - SAFE then
        shows as not applied until the operator sends it."""
        if self.view_only or self.mode != GuiMode.ABORT:
            return
        if self._applied_abort_states <= {DEFAULT_ABORT_ID} and self.ethernet_client.connected:
            self.enter_safe_state("abort acknowledged")
        else:
            self.ethernet_client.set_system_state("SAFE")
            self._applied_abort_states.clear()
            self._set_safe_applied(False)
            self._set_mode(GuiMode.SAFE, "abort acknowledged")


    # DAQ RECORDING ------------------------------------------------------------------------------------------------

    def log_event(self, event_type, event_details=""):
        """Log an event to the xlsx file (Req 15)"""
        if "HEARTBEAT" in event_type:
            return

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

        if not self._ws:
            return

        self._write_daq_row(teensy_ts=self.latest_teensy_ts, event_type=event_type, event_details=event_details)

    def _write_daq_row(self, teensy_ts="", event_type="", event_details=""):
        """Write one data row to the xlsx worksheet.

        Column layout:
            Local Time (24-hr + date) | Teensy Timestamp | [blank] |
            <pressure sensors...>     | [blank]          |
            <thermocouples...>        | [blank]          |
            <load cells...>           | [blank]          |
            Control State             | Event Type       | Event Details
        """
        if not self._ws:
            return

        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Local time, 24-hr + date
            teensy_ts,
            "",
        ]

        for keys in (self.pt_keys, self.tc_keys, self.lc_keys):
            for key in keys:
                val = self.current_sensor_values.get(key.upper(), "")
                row.append(round(val, 4) if isinstance(val, float) else val)
            row.append("")

        current_state = getattr(self.ethernet_client, "system_state", "UNKNOWN")
        row.extend([current_state, event_type, event_details])

        self._ws.append(row)

    def get_next_filename(self) -> str:
        return self._generate_filename()

    def start_recording(self) -> bool:
        if not self.project:
            QMessageBox.warning(self.parent, "No Project",
                "Please select a project from the dropdown before recording."
                "The project defines which sensors to log.")
            return False

        filename = self._generate_filename()
        data_dir = "Data"
        os.makedirs(data_dir, exist_ok=True)
        file_path = os.path.join(data_dir, filename)

        try:
            wb = Workbook()
            ws = wb.active
            ws.title = "DAQ"

            # ---- Header row ----
            header = [
                "Local Time (YYYY-MM-DD HH:mm:ss)",
                "Teensy Timestamp (µs from boot)",
                "",
            ]
            header += self.pt_keys + [""]
            header += self.tc_keys + [""]
            header += self.lc_keys + [""]
            header += ["Control State", "Event Type", "Event Details"]

            ws.append(header)

            # Style: bold + light-grey fill on header row
            header_fill = PatternFill("solid", fgColor="D9D9D9")
            header_font = Font(bold=True)
            for cell in ws[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")

            self._wb = wb
            self._ws = ws
            self._xlsx_path = file_path

            # Clear batch tracker
            self.current_batch_sensors.clear()

            self.log_event("RECORDING:START")
            self.recording = True

            return True

        except Exception as e:
            QMessageBox.critical(self.parent, "Error", f"Failed to create file: {str(e)}")
            return False

    def stop_recording(self):
        if self._wb:
            self.log_event("RECORDING:STOP")
            try:
                self._wb.save(self._xlsx_path)
            except Exception as e:
                QMessageBox.warning(self.parent, "Save Warning", f"Could not save file:\n{str(e)}")
            self._wb = None
            self._ws = None
            self._xlsx_path = ""
            self.recording = False

    def handle_new_data(self, data_str: str):
        """ Parse teensy timestamp (first token) (Req 4) """
        timestamp = QDateTime.currentMSecsSinceEpoch() / 1000.0     # seconds, but at a precision of 1 ms
        
        parts = data_str.split(sep=",",maxsplit=1)
        teensy_ts = parts[0] if len(parts) > 1 else ""
        sensor_data = parts[1] if len(parts) > 1 else data_str

        readings = sensor_data.strip().split(sep=",")
        for reading in readings:
            if "ABORTED" in reading:
                if "ABORTED:COMMS:" in reading:
                    reason = reading.split("ABORTED:COMMS:", 1)[1] or "Unknown reason"
                    if reason.startswith("countdown_expired:"):
                        reason = reason[len("countdown_expired:"):]
                    if reason.startswith("SET_") and "_timeout" in reason:
                        # e.g. "SET_MV-1_timeout:packet_id=5"
                        actuator = reason[len("SET_"):reason.index("_timeout")]
                        reason = f"Actuator {actuator} position command failed (timeout)"
                    elif "OPEN_" in reason or "CLOSE_" in reason:
                        # e.g. "OPEN_NCS1_timeout:packet_id=5"
                        cmd, _, rest = reason.partition("_")
                        valve = rest.split("_")[0].split(":")[0]
                        if valve:
                            reason = f"Valve {valve} {cmd} command failed (timeout)"
                    self.signals.abort_triggered.emit("comms_auto_abort", reason, "")
                elif "ABORTED:REMOTE_SFE:" in reading:
                    sfe_reason = reading.split("ABORTED:REMOTE_SFE:", 1)[1] or "unknown packet"
                    self.signals.abort_triggered.emit("remote_safe_mode", f"Received SFE from MCU ({sfe_reason})", "")
                else:
                    # Engine MCU triggered abort
                    self.signals.abort_triggered.emit("engine_abort", "The engine MCU triggered a local abort", "")

            # Proportional actuator responses
            elif "ACTUATOR_SUCCESS" in reading or "ACTUATOR_POS" in reading:
                parts = reading.split(':')
                if len(parts) >= 3:
                    name = parts[1]
                    try:
                        pct = float(parts[2])
                    except ValueError:
                        continue
                    if "ACTUATOR_SUCCESS" in reading:
                        self.pending_valve_commands.pop(name, None)
                    elif name in self.pending_valve_commands:
                        continue    # MCU position report racing our own command; its ACK will follow
                    self._apply_actuator_position(name, pct)

            elif "ACTUATOR_FAIL" in reading:
                parts = reading.split(':')
                if len(parts) >= 2:
                    name = parts[1]
                    self.pending_valve_commands.pop(name, None)
                    # Revert the PENDING display to the last confirmed position
                    self._apply_actuator_position(
                        name, self.actuator_positions.get(name, 0.0))

            # Valve command responses
            elif "VALVE_SUCCESS" in reading:
                parts = reading.split(':')
                if len(parts) >= 3:
                    valve_name = parts[1]
                    self.pending_valve_commands.pop(valve_name, None)
                    self.signals.valve_updated.emit(
                        valve_name, "OPEN" if parts[2] == "1" else "CLOSED")

            elif "VALVE_FAIL" in reading:
                parts = reading.split(':')
                if len(parts) >= 2:
                    valve_name = parts[1]
                    self.pending_valve_commands.pop(valve_name, None)
                    # Revert the PENDING display to the last confirmed state
                    prev_state = self.valve_states.get(valve_name, False)
                    self.signals.valve_updated.emit(valve_name, "OPEN" if prev_state else "CLOSED")

            # Sensor data
            elif ':' in reading:
                try:
                    parts = reading.split(':', 1)
                    sensor_name = parts[0].strip().upper()
                    wire = float(parts[1].strip())

                    self.sensor_last_rx[sensor_name] = timestamp
                    recent = self.sensor_recent.get(sensor_name)
                    if recent is None:
                        recent = self.sensor_recent[sensor_name] = deque(maxlen=20)
                    recent.append(wire)

                    gain, offset = self.calibrations.get(sensor_name, (1.0, 0.0))
                    raw = wire * gain + offset
                    self.raw_sensor_values[sensor_name] = raw
                    value = raw - self.tare_offsets.get(sensor_name, 0.0)
                    self.current_sensor_values[sensor_name] = value
                    self.signals.sensor_updated.emit(sensor_name, value, timestamp)
                    
                    # Batch sensor updates
                    if sensor_name in self.current_batch_sensors:
                        # We've seen this sensor in the current batch -> flush the row
                        if self._ws:
                            self._write_daq_row(teensy_ts=self.latest_teensy_ts)
                        self.current_batch_sensors.clear()
                    
                    self.current_batch_sensors.add(sensor_name)
                    
                except ValueError:
                    pass
        
        if teensy_ts:
            self.latest_teensy_ts = teensy_ts

    def tare_sensor(self, sensor_name: str, target: float) -> bool:
        """Tare so the sensor's current raw reading displays as `target`.
        Returns False when no reading has been received yet."""
        name = sensor_name.upper()
        raw = self.raw_sensor_values.get(name)
        if raw is None:
            return False
        self.tare_offsets[name] = raw - target
        self.current_sensor_values[name] = target
        timestamp = QDateTime.currentMSecsSinceEpoch() / 1000.0
        self.signals.sensor_updated.emit(name, target, timestamp)
        self.log_event("TARE", f"{name}:{target:g} (offset {raw - target:+.4f})")
        return True

    def clear_tare(self, sensor_name: str):
        name = sensor_name.upper()
        if name not in self.tare_offsets:
            return
        del self.tare_offsets[name]
        raw = self.raw_sensor_values.get(name)
        if raw is not None:
            self.current_sensor_values[name] = raw
            timestamp = QDateTime.currentMSecsSinceEpoch() / 1000.0
            self.signals.sensor_updated.emit(name, raw, timestamp)
        self.log_event("TARE_CLEARED", name)

    # TEMPORARY (test setup): until each PT has its own calibration, the calibration
    # of this PT is applied to EVERY pressure transducer. Calibrating (or loading a
    # saved calibration for) the source PT copies it to all other PTs, overwriting
    # whatever they had. Set to None to go back to fully independent per-PT calibration.
    SHARED_PT_CAL_SOURCE = "P1"

    def _refresh_calibrated_value(self, name: str, gain: float, offset: float):
        """Recompute a sensor's displayed value from its latest wire sample."""
        recent = self.sensor_recent.get(name)
        if recent:
            raw = recent[-1] * gain + offset
            self.raw_sensor_values[name] = raw
            value = raw - self.tare_offsets.get(name, 0.0)
            self.current_sensor_values[name] = value
            self.signals.sensor_updated.emit(
                name, value, QDateTime.currentMSecsSinceEpoch() / 1000.0)

    def _share_pt_calibration(self):
        """Copy the shared-source PT's calibration (if it has one) to every other PT."""
        src = (self.SHARED_PT_CAL_SOURCE or "").upper()
        cal = self.calibrations.get(src)
        if not src or cal is None:
            return
        for key in self.pt_keys:
            name = str(key).upper()
            if name != src:
                self.calibrations[name] = cal
                self._refresh_calibrated_value(name, *cal)

    def set_calibration(self, sensor_name: str, gain: float, offset: float):
        """Install a linear calibration (display = gain·wire + offset) and
        refresh the sensor's displayed value from its latest wire sample."""
        name = sensor_name.upper()
        self.calibrations[name] = (gain, offset)
        self._refresh_calibrated_value(name, gain, offset)
        self.log_event("CALIBRATION", f"{name}: gain={gain:.6g} offset={offset:.6g}")
        if name == (self.SHARED_PT_CAL_SOURCE or "").upper():
            self._share_pt_calibration()
            self.log_event("CALIBRATION", f"{name} calibration applied to all PTs (shared, temporary)")

    def clear_calibrations(self):
        self.calibrations.clear()
        self.log_event("CALIBRATION", "All calibrations cleared")

    def load_calibrations_from_project(self, project):
        """Pick up per-sensor cal_gain / cal_offset stored in component extras."""
        if not project:
            return
        for comp in project.components.values():
            hw_id = (comp.extras.get("hw_id") or comp.label or comp.id)
            try:
                gain = float(comp.extras["cal_gain"])
                offset = float(comp.extras.get("cal_offset", 0.0))
            except (KeyError, TypeError, ValueError):
                continue
            self.calibrations[str(hw_id).upper()] = (gain, offset)
        self._share_pt_calibration()

    def project_lock_required(self) -> bool:
        """Whether project selection / Open P&ID should be locked right now.

        Locked while the system is live (MANUAL or LOCKED) or while any valve
        is open. Unlocked in SAFE/ABORT once everything has actually closed.
        """
        return (self.view_only or self.mode in (GuiMode.MANUAL, GuiMode.LOCKED)
                or any(self.valve_states.values()))

    def close_all_valves(self):
        """Return the system to fully closed without aborting."""
        open_valves = [v for v, is_open in self.valve_states.items() if is_open]
        for v in open_valves:
            self.toggle_valve(v, False)
        if open_valves:
            self.log_event("FULLY_CLOSED", f"Closed: {', '.join(open_valves)}")

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
            QMessageBox.warning(self.parent, "Not In Manual Mode",
                                f"Auto fire sequence requires MANUAL mode (currently {self.mode}).")
            return

        # ── Resolve available sequences ──────────────────────────────────────
        named_sequences = getattr(self.project, "sequences", []) if self.project else []
        legacy_steps    = getattr(self.project, "sequence",  []) if self.project else []

        if not named_sequences and not legacy_steps:
            QMessageBox.warning(
                self.parent, "No Sequence",
                "The loaded project has no auto-fire sequence defined.\n"
                "Use the Sequencing tab to build one first."
            )
            return

        # ── Confirmation dialog ──────────────────────────────────────────────
        confirm_dialog = QDialog(self.parent)
        confirm_dialog.setWindowTitle("Confirm Auto-Fire Sequence")
        c_layout = QVBoxLayout(confirm_dialog)

        # Resolve the active sequence steps and name
        steps = legacy_steps
        seq_name = "Legacy Sequence"
        active_id = getattr(self.project, "active_sequence_id", "")
        if named_sequences and active_id:
            for ns in named_sequences:
                if ns.id == active_id:
                    steps = ns.steps
                    seq_name = ns.name
                    break
        elif named_sequences:
            steps = named_sequences[0].steps
            seq_name = named_sequences[0].name

        if not steps:
            QMessageBox.warning(self.parent, "Empty Sequence", "The selected sequence has no steps.")
            return

        info_label = QLabel(
            f"Execute auto-fire sequence: {seq_name}?\n\n"
            f"Steps: {len(steps)}\n"
            f"Total duration: {steps[-1].time_offset:.1f} s"
        )
        c_layout.addWidget(info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.Cancel)
        buttons.accepted.connect(confirm_dialog.accept)
        buttons.rejected.connect(confirm_dialog.reject)
        c_layout.addWidget(buttons)
        if confirm_dialog.exec_() != QDialog.Accepted:
            return

        if not any(getattr(s, "is_terminal_count", False) for s in steps):
            QMessageBox.warning(
                self.parent, "No Terminal Count State",
                "The sequence must include a state marked as 'Terminal Count' "
                "before it can be auto-fired.\n\n"
                "Open the Sequencing tab, select the hold state, and check "
                "'This is the Terminal Count state'."
            )
            return

        # ── Schedule each sequence step as a QTimer shot ────────────────────
        # No artificial pre-delay here: the terminal-count hold IS one of the
        # steps below, scheduled at its own time_offset like any other step.
        # A live "TERMINAL COUNT" overlay (see _execute_sequence_step) shows
        # its countdown in real time instead of blocking beforehand - so the
        # operator sees exactly one countdown, not a generic wait stacked on
        # top of the step's own hold.
        self._cancel_sequence()

        for step in steps:
            delay_ms = int(step.time_offset * 1000)
            t = QTimer()
            t.setSingleShot(True)
            t.timeout.connect(lambda s=step: self._execute_sequence_step(s))
            t.start(delay_ms)
            self._sequence_timers.append(t)

        self.log_event("SEQUENCE:START", f"{len(steps)} steps ({seq_name})")


    def _execute_sequence_step(self, step):
        """Apply one sequence step: set every known valve to its desired state.
        
        step.open_valves contains component IDs (cid). These must be translated
        to hardware IDs (hw_id) before calling toggle_valve, which works in hw space.
        """
        if self.lockout:
            return

        # Build a set of hw_ids that should be OPEN for this step
        open_hw_ids: set[str] = set()
        if self.project:
            for cid in step.open_valves:
                comp = self.project.components.get(cid)
                if comp:
                    hw_id = comp.extras.get("hw_id") or comp.label
                    if hw_id:
                        open_hw_ids.add(hw_id)

        # Set every valve in hw space to its desired state
        for hw_id in list(self.valve_states.keys()):
            self.toggle_valve(hw_id, hw_id in open_hw_ids)

        self.ethernet_client.set_system_state(step.name)
        self.signals.system_status.emit(step.name)
        self.log_event("SEQUENCE:STEP", step.name)

        if getattr(step, "is_terminal_count", False):
            tc_length = getattr(self.project.parameters, "terminal_count_s", 10.0)
            self._show_terminal_count_overlay(step.name, tc_length)

    def _show_terminal_count_overlay(self, step_name: str, seconds: float):
        """Live, non-blocking T-minus display for the terminal-count hold.

        This is purely a visual/cancel affordance - it does not delay or
        reschedule anything. The step's own position in the sequence (its
        time_offset relative to the next step) is what actually determines
        how long the hold lasts; this overlay just counts down alongside it.
        """
        length = max(int(round(seconds)), 1)

        dlg = QDialog(self.parent)
        dlg.setWindowTitle("Terminal Count")
        dlg.setMinimumSize(300, 150)
        dlg.setModal(False)
        lay = QVBoxLayout(dlg)

        label = QLabel(f"{step_name}\nT-{length}")
        label.setAlignment(Qt.AlignCenter)
        font = label.font(); font.setPointSize(14); font.setBold(True)
        label.setFont(font)
        lay.addWidget(label)

        cancel_btn = QPushButton("CANCEL SEQUENCE")
        cancel_btn.setStyleSheet("background-color: red; color: white;")
        lay.addWidget(cancel_btn)

        remaining = [length]
        timer = QTimer(dlg)
        timer.setInterval(1000)

        def tick():
            remaining[0] -= 1
            if remaining[0] <= 0:
                timer.stop()
                dlg.close()
            else:
                label.setText(f"{step_name}\nT-{remaining[0]}")

        def do_cancel():
            timer.stop()
            self._cancel_sequence()
            self.close_all_valves()
            self.log_event("SEQUENCE:CANCELED", f"Canceled during terminal count ({step_name})")
            dlg.close()

        timer.timeout.connect(tick)
        cancel_btn.clicked.connect(do_cancel)
        timer.start()
        dlg.show()

    def _cancel_sequence(self):
        """Stop all pending sequence timers."""
        for t in self._sequence_timers:
            t.stop()
        self._sequence_timers.clear()

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
        warning_label = QLabel(f"Valve {valve_name} {cmd_type} command failed!\n"
                               "Ignore to continue operating, or abort now. "
                               "The system aborts automatically when this reaches zero.")
        warning_label.setAlignment(Qt.AlignCenter)
        countdown_layout.addWidget(warning_label)
        
        # Cancel button
        cancel_btn = QPushButton("IGNORE & CONTINUE\n(Cancel Countdown)")
        cancel_btn.setStyleSheet("background-color: green; color: white; font-size: 14px; padding: 10px;")
        cancel_btn.clicked.connect(self._cancel_abort_countdown)
        countdown_layout.addWidget(cancel_btn)

        abort_now_btn = QPushButton("ABORT NOW")
        abort_now_btn.setStyleSheet("background-color: #c62828; color: white; font-size: 14px; padding: 10px;")
        abort_now_btn.clicked.connect(self._abort_from_countdown)
        countdown_layout.addWidget(abort_now_btn)
        
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
        """Operator chose to ignore the failed valve command: stop the countdown
        and carry on in the current mode (no mode or valve change)."""
        self.ethernet_client.cancel_auto_abort_countdown()
        self.close_abort_countdown_dialog()
        self.log_event("COUNTDOWN_IGNORED", "Operator ignored failed valve command")

    def _abort_from_countdown(self):
        self.close_abort_countdown_dialog()
        self.signals.abort_triggered.emit("valve_failure", "Operator aborted after a failed valve command", "")

    def update_valve_state(self, valve_name: str, new_val: str):        
        # Only update the internal state if it was confirmed open or closed
        if new_val == "OPEN":
            self.valve_states[valve_name] = True
        elif new_val == "CLOSED":
            self.valve_states[valve_name] = False

        # Update the manual valve buttons
        btn = self.manual_valve_buttons.get(valve_name)
        if btn is not None:
            color = {"OPEN": "green", "CLOSED": "red", "PENDING": "gray"}.get(new_val)
            if color:
                btn.setStyleSheet(f"background-color: {color}; color: white;")

    def show_manual_valve_control(self):
        if self.lockout:
            QMessageBox.warning(self.parent, "Not In Manual Mode",
                                f"Manual valve control requires MANUAL mode (currently {self.mode}).")
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

    def _apply_actuator_position(self, name: str, pct: float):
        """Record an MCU-confirmed position and fan it out to the UI. 'Open' for
        the rest of the app (valve_states, lockout, abort) means 'off its safe
        position'."""
        spec = self.actuator_specs.get(name)
        if spec is None:
            return
        self.actuator_positions[name] = pct
        self.signals.actuator_updated.emit(name, pct)
        self.signals.valve_updated.emit(name, "OPEN" if spec.is_off_safe(pct) else "CLOSED")

    def set_actuator_position(self, name: str, pct: float):
        """Command a proportional actuator to a position (%), clamped to its range."""
        if self.lockout:
            return
        self._drive_actuator(name, pct)

    def _drive_actuator(self, name: str, pct: float, force: bool = False):
        """set_actuator_position without the lockout gate (used by SAFE/ABORT).
        force re-sends even if the actuator is already (or about to be) there."""
        spec = self.actuator_specs.get(name)
        if spec is None:
            return

        target = spec.clamp(pct)
        pending = self.pending_valve_commands.get(name)
        current = pending["pct"] if pending and "pct" in pending else self.actuator_positions.get(name)
        if not force and current is not None and abs(current - target) < 0.005:
            return      # already there (or already on its way); sequences re-issue every step

        self.signals.valve_updated.emit(name, "PENDING")
        self.signals.command_sent.emit(name, float(target), QDateTime.currentMSecsSinceEpoch() / 1000.0)
        try:
            self.ethernet_client.send_actuator_command(name, target)
        except Exception:
            pass

        self.log_event("ACTUATOR_SET", f"{name}:{target:.2f}")
        self.pending_valve_commands[name] = {
            "state": spec.is_off_safe(target),
            "pct": target,
            "last_sent": QDateTime.currentMSecsSinceEpoch(),
            "retries": 0,
        }

    def set_throttle(self, name: str, fraction: float):
        """0.0-1.0 of the actuator's travel (min..max), for callers that think in fractions."""
        spec = self.actuator_specs.get(name)
        if spec is not None:
            self.set_actuator_position(
                name, spec.min_pct + (spec.max_pct - spec.min_pct) * float(fraction))

    def toggle_valve(self, valve_name: str, state: bool=None):
        if self.lockout:
            return
        self._drive_valve(valve_name, state)

    def _drive_valve(self, valve_name: str, state: bool=None, force: bool=False):
        """toggle_valve without the lockout gate (used by SAFE/ABORT). force
        re-sends even if the valve already looks to be in the requested state."""
        # Proportional actuators: open/close map onto the spec's open/safe positions
        spec = self.actuator_specs.get(valve_name)
        if spec is not None:
            if state is None:
                state = not self.valve_states.get(valve_name, False)
            self._drive_actuator(valve_name, spec.open_pct if state else spec.safe_pct, force=force)
            return

        new_state = (not self.valve_states[valve_name]) if state is None else state

        # Only send a command if the valve state is actually changing
        if not force and valve_name in self.valve_states and self.valve_states[valve_name] == new_state:
            return

        # Internal state updates only once the MCU confirms; show PENDING until then
        self.signals.valve_updated.emit(valve_name, "PENDING")
        self.signals.command_sent.emit(valve_name, 1.0 if new_state else 0.0,
                                       QDateTime.currentMSecsSinceEpoch() / 1000.0)

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
        current_time = QDateTime.currentMSecsSinceEpoch()
        valves_to_delete = []

        # The comms thread pops entries on ACK/NCK while this timer runs on the GUI
        # thread, so iterate over a snapshot (iterating the live dict could raise
        # "dictionary changed size during iteration", and PyQt aborts the app on an
        # uncaught exception in a slot).
        for valve_name, info in list(self.pending_valve_commands.items()):
            if current_time - info["last_sent"] > self.valve_retry_timeout:
                if info["retries"] < self.valve_max_retries:

                    info["retries"] += 1
                    info["last_sent"] = current_time
                    try:
                        if "pct" in info:
                            self.ethernet_client.send_actuator_command(valve_name, info["pct"])
                        else:
                            self.ethernet_client.send_valve_command(valve_name, info["state"])
                        self.log_event("VALVE_RETRY", f"{valve_name}:{info['state']} (Attempt {info['retries']})")
                    except Exception:
                        pass
                else:
                    self.log_event("VALVE_TIMEOUT", f"{valve_name}:{info['state']}")
                    valves_to_delete.append(valve_name)

        for valve_name in valves_to_delete:
            self.pending_valve_commands.pop(valve_name, None)


    def apply_operation(self, operation: str):
        if self.lockout:
            return

        self.ethernet_client.set_system_state(operation)
        self.signals.system_status.emit(operation)
        self.log_event("OPERATION", operation)

        if self.project and getattr(self.project, "sequence", None):
            step = next(
                (s for s in self.project.sequence if s.name == operation),
                None
            )
            if step is not None:
                open_hw_ids: set[str] = set()
                for cid in step.open_valves:
                    comp = self.project.components.get(cid)
                    if comp:
                        hw_id = comp.extras.get("hw_id") or comp.label
                        if hw_id:
                            open_hw_ids.add(hw_id)
                for hw_id in list(self.valve_states.keys()):
                    self.toggle_valve(hw_id, hw_id in open_hw_ids)
                return

        self.log_event("OPERATION:WARN", f"No sequence step named '{operation}' in project")