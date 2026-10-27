import re
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt

from GUI_CONTROLLER import GUIController
from PID_SCHEMA import COMMANDABLE_VALVE_TYPES, COMP_IGNITER, get_actuator_spec


def _natural_key(text: str):
    """Alphabetical, with digit runs compared as numbers (NV-1104 < NV-1105 < NV-11010)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


class ValveControlPanel(QWidget):
    """Open / Close buttons for every relay-bound valve and pump in the project, sorted
    alphabetically then numerically. Position-commanded actuators (servos, the Bray
    valve) open to 100 % and close to 0 %. Igniters are left out on purpose, and so are
    passive parts (PRVs, check valves) and manual valves, which have no binding."""

    def __init__(self, controller: GUIController, parent=None):
        super().__init__(parent)
        self.controller = controller
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        outer.addWidget(self._hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._body = QWidget()
        self._grid = QGridLayout(self._body)
        self._grid.setColumnStretch(1, 1)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

        self._rows = {}         # hw_id -> (state label, open btn, close btn)

        s = controller.signals
        s.valve_updated.connect(self._on_valve_updated)
        s.actuator_updated.connect(self._on_actuator_updated)
        s.mode_changed.connect(self._refresh_enabled)
        s.view_only_changed.connect(lambda *_: self._refresh_enabled())
        s.project_changed.connect(self.rebuild)
        self.rebuild()

    def rebuild(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        project = self.controller.project
        entries = []
        if project is not None:
            for cid, comp in project.components.items():
                if comp.type not in COMMANDABLE_VALVE_TYPES or comp.type == COMP_IGNITER:
                    continue
                if comp.hardware.relay is None:
                    continue
                hw_id = comp.extras.get("hw_id") or comp.label
                if not hw_id or hw_id not in self.controller.valve_states:
                    continue
                entries.append((comp.label or hw_id, hw_id))
        entries.sort(key=lambda e: _natural_key(e[0]))

        for row, (label, hw_id) in enumerate(entries):
            name = QLabel(label)
            name.setStyleSheet("font-weight: bold;")
            state = QLabel("---")
            state.setMinimumWidth(70)
            open_btn = QPushButton("Open")
            close_btn = QPushButton("Close")
            open_btn.clicked.connect(lambda _=False, h=hw_id: self._command(h, True))
            close_btn.clicked.connect(lambda _=False, h=hw_id: self._command(h, False))
            self._grid.addWidget(name, row, 0)
            self._grid.addWidget(state, row, 1)
            self._grid.addWidget(open_btn, row, 2)
            self._grid.addWidget(close_btn, row, 3)
            self._rows[hw_id] = (state, open_btn, close_btn)
            self._show_state(hw_id)
        self._grid.setRowStretch(len(entries), 1)
        self._refresh_enabled()

    def _command(self, hw_id: str, want_open: bool):
        c = self.controller
        spec = c.actuator_specs.get(hw_id)
        if spec is not None:
            c.set_actuator_position(hw_id, 100.0 if want_open else 0.0)
        else:
            c.toggle_valve(hw_id, want_open)

    def _show_state(self, hw_id: str, state: str = None):
        row = self._rows.get(hw_id)
        if row is None:
            return
        c = self.controller
        if state is None:
            state = "OPEN" if c.valve_states.get(hw_id) else "CLOSED"
        text = state
        if hw_id in c.actuator_specs and state != "PENDING":
            text = f"{c.actuator_positions.get(hw_id, 0.0):g} %"
        row[0].setText(text)
        color = {"OPEN": "#2e7d32", "PENDING": "#e37400"}.get(state, "")
        row[0].setStyleSheet(f"color: {color}; font-weight: bold;" if color else "")

    def _on_valve_updated(self, hw_id: str, state: str):
        self._show_state(hw_id, state)

    def _on_actuator_updated(self, hw_id: str, pct: float):
        self._show_state(hw_id)

    def _refresh_enabled(self, *_):
        locked = self.controller.lockout
        for _state, open_btn, close_btn in self._rows.values():
            open_btn.setEnabled(not locked)
            close_btn.setEnabled(not locked)
        if self.controller.view_only:
            self._hint.setText("Valves can not be commanded in view-only mode.")
        elif locked:
            self._hint.setText(f"Controls disabled in {self.controller.mode} mode.")
        else:
            self._hint.setText("")
