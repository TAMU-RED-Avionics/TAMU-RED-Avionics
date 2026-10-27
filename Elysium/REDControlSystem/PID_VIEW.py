# PID_VIEW.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt

from PID_SCHEMA import (
    PIDProject, get_actuator_spec, COMMANDABLE_VALVE_TYPES,
    COMP_VALVE, COMP_THROTTLE_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_BALL_VALVE, COMP_GLOBE_VALVE, COMP_SOLENOID, COMP_IGNITER,
)
from PID_CANVAS import PIDCanvas
from GUI_CONTROLLER import GuiMode
from GUI_ACTUATION import ActuationPanel

_VALVE_TYPES = COMMANDABLE_VALVE_TYPES


class PIDViewWindow(QWidget):

    def __init__(self, controller, project: PIDProject = None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._project: PIDProject = None
        self._interactive = False 
        self._valve_hw_to_comp: dict = {}
        self._comp_to_valve_hw: dict = {}
        self._sensor_hw_to_comp: dict = {}

        self._build_ui()
        self._connect_signals()

        if project:
            self.load_project(project)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("action_bar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(8, 4, 8, 4)
        tb_layout.setSpacing(6)

        def tb_btn(text, slot):
            b = QPushButton(text)
            b.setObjectName("action_bar_btn")
            b.clicked.connect(slot)
            tb_layout.addWidget(b)
            return b

        # "&&" renders a literal ampersand (a single "&" becomes a mnemonic underline)
        self._open_btn = tb_btn("Open P&&ID…", self._open_project)
        tb_btn("Fit View [F]", self._fit_view)
        zi = tb_btn("+", lambda: self.canvas.zoom_in())
        zo = tb_btn("\u2212", lambda: self.canvas.zoom_out())
        for b, tip in ((zi, "Zoom in"), (zo, "Zoom out")):
            b.setFixedWidth(34)
            b.setToolTip(tip + "  (or mouse wheel / Ctrl or \u2318 + scroll)")
        tb_layout.addWidget(_vsep())

        self._conn_badge = QLabel("● DISCONNECTED")
        self._conn_badge.setStyleSheet("color: #c62828; font-weight: bold;")
        tb_layout.addWidget(self._conn_badge)

        tb_layout.addStretch()

        self._proj_label = QLabel("No project loaded")
        self._proj_label.setStyleSheet("color: #888;")
        tb_layout.addWidget(self._proj_label)

        root.addWidget(toolbar)

        self.canvas = PIDCanvas(interactive=False)
        self.canvas.component_clicked.connect(self._on_comp_clicked)
        self.canvas.valve_open_requested.connect(self._on_valve_open_requested)
        self.canvas.valve_close_requested.connect(self._on_valve_close_requested)
        self.canvas.actuator_position_requested.connect(self._on_actuator_position_requested)
        root.addWidget(self.canvas, stretch=1)

        # Automated actuation: a button in the canvas's bottom-right corner that expands
        # into the plan editor / runner. Follows the controller's project on its own.
        self.actuation = ActuationPanel(self.controller, self.canvas)

        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setContentsMargins(8, 2, 8, 2)
        status_layout.setSpacing(18)
        self._status = QLabel("Open a .red file to display the live P&ID.")
        status_layout.addWidget(self._status)
        status_layout.addStretch()

        root.addWidget(status_row)


    def _connect_signals(self):
        c = self.controller
        c.signals.connected.connect(self._on_connected)
        c.signals.disconnected.connect(self._on_disconnected)
        c.signals.abort_triggered.connect(self._on_abort)
        c.signals.mode_changed.connect(self._on_mode_changed)
        c.signals.view_only_changed.connect(lambda _v: self._on_mode_changed(self.controller.mode))
        c.signals.valve_updated.connect(self._on_valve_updated)
        c.signals.actuator_updated.connect(self._on_actuator_updated)
        c.signals.sensor_updated.connect(self._on_sensor_updated)

        # Same lock rule as the project selector: locked while live (MANUAL /
        # LOCKED) or while any valve is open. See
        # GUIController.project_lock_required().
        c.signals.connected.connect(self._refresh_open_lock)
        c.signals.abort_triggered.connect(lambda *_: self._refresh_open_lock())
        c.signals.mode_changed.connect(lambda *_: self._refresh_open_lock())
        c.signals.disconnected.connect(lambda _: self._refresh_open_lock())
        c.signals.valve_updated.connect(lambda *_: self._refresh_open_lock())

    def _refresh_open_lock(self):
        self._set_open_locked(self.controller.project_lock_required())

    def _set_open_locked(self, locked: bool):
        self._open_btn.setEnabled(not locked)
        self._open_btn.setToolTip(
            "Locked while the system is live (MANUAL/LOCKED) or a valve is open" if locked else "")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open P&ID Project", "",
            "P&ID Project (*.red);;JSON Files (*.json);;All Files (*)"
        )
        if path:
            try:
                proj = PIDProject.load(path)
                self.load_project(proj)
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", str(e))

    def load_project(self, project: PIDProject):
        self._project = project
        self._build_hw_maps()
        self.canvas.set_project(project)
        self._proj_label.setText(project.name)
        self._status.setText(f"Loaded: {project.name}  "
                             f"({len(project.components)} components, "
                             f"{len(project.lines)} pipes)")
        for cid, comp in project.components.items():
            if comp.type in _VALVE_TYPES or get_actuator_spec(comp) is not None:
                self.canvas.update_valve_state(cid, "CLOSED")
            spec = get_actuator_spec(comp)
            if spec is not None:
                hw_id = self._comp_to_valve_hw.get(cid)
                self.canvas.update_throttle(
                    cid, self.controller.actuator_positions.get(hw_id, spec.safe_pct))

    def _build_hw_maps(self):
        """Build comp_id <-> hardware_id lookup tables from the loaded project."""
        self._valve_hw_to_comp.clear()
        self._comp_to_valve_hw.clear()
        self._sensor_hw_to_comp.clear()

        if not self._project:
            return

        for cid, comp in self._project.components.items():
            if comp.type in _VALVE_TYPES or get_actuator_spec(comp) is not None:
                hw_id = comp.extras.get("hw_id", comp.label)
                if hw_id:
                    self._valve_hw_to_comp[hw_id] = cid
                    self._comp_to_valve_hw[cid]   = hw_id

            elif comp.type in (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL):
                hw_id = comp.extras.get("hw_id", comp.label)
                if hw_id:
                    self._sensor_hw_to_comp[hw_id] = cid


    def _on_connected(self):
        # Connecting lands in SAFE: controls stay disabled until MANUAL is sent
        self._conn_badge.setText("● CONNECTED")
        self._conn_badge.setStyleSheet("color: #2e7d32; font-weight: bold;")

    def _on_disconnected(self, reason=""):
        self._interactive = False
        self._conn_badge.setText("● DISCONNECTED")
        self._conn_badge.setStyleSheet("color: #c62828; font-weight: bold;")

    def _on_abort(self, abort_type: str, reason: str):
        self._interactive = False

    def _on_mode_changed(self, mode: str):
        self._interactive = (mode == GuiMode.MANUAL) and not self.controller.view_only

    def _controls_disabled_text(self, what: str) -> str:
        if self.controller.view_only:
            return f"View-only mode - cannot control {what}."
        if not self.controller.ethernet_client.connected:
            return f"Not connected - cannot control {what}."
        return f"Controls disabled in {self.controller.mode} mode - select MANUAL to control {what}."

    def _on_valve_updated(self, hw_name: str, state: str):
        """Translate hardware valve name -> project comp_id -> canvas update."""
        cid = self._valve_hw_to_comp.get(hw_name)
        if cid:
            self.canvas.update_valve_state(cid, state)
        elif hw_name in (self._project.components if self._project else {}):
            self.canvas.update_valve_state(hw_name, state)

    def _on_actuator_updated(self, hw_name: str, pct: float):
        cid = self._valve_hw_to_comp.get(hw_name)
        if cid:
            self.canvas.update_throttle(cid, pct)

    def _on_sensor_updated(self, hw_name: str, value: float, timestamp: float):
        # Total Thrust / Total Mdot / Isp are computed from the project's own
        # CalcChannel formulas (see GUI_PERFORMANCE.py's PerformanceBar / gear
        # icon in the bottom action bar) rather than a hardcoded load-cell sum.
        cid = self._sensor_hw_to_comp.get(hw_name)
        if cid:
            self.canvas.update_sensor_value(cid, value)


    def _on_valve_open_requested(self, cid: str):
        hw_id = self._comp_to_valve_hw.get(cid, cid)
        if not self._interactive:
            self._status.setText(self._controls_disabled_text("valves"))
            return
        self.controller.toggle_valve(hw_id, True)
        self._status.setText(f"Opening valve: {hw_id}")

    def _on_actuator_position_requested(self, cid: str, pct: float):
        hw_id = self._comp_to_valve_hw.get(cid, cid)
        if not self._interactive:
            self._status.setText(self._controls_disabled_text("actuators"))
            return
        self.controller.set_actuator_position(hw_id, pct)
        self._status.setText(f"Setting {hw_id} to {pct:g}")

    def _on_valve_close_requested(self, cid: str):
        hw_id = self._comp_to_valve_hw.get(cid, cid)
        if not self._interactive:
            self._status.setText(self._controls_disabled_text("valves"))
            return
        self.controller.toggle_valve(hw_id, False)
        self._status.setText(f"Closing valve: {hw_id}")

    def _on_comp_clicked(self, cid: str):
        if not self._project:
            return
        comp = self._project.components.get(cid)
        if not comp:
            return
        # Valve / actuator popups are handled directly by the canvas.
        lbl = comp.label or cid
        state = self.canvas.live_valve_states.get(cid, "-")
        self._status.setText(f"{lbl}  |  {state}")

    def _fit_view(self):
        self.canvas.fit_view()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F:
            self._fit_view()
        else:
            super().keyPressEvent(event)


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFrameShadow(QFrame.Sunken)
    return f