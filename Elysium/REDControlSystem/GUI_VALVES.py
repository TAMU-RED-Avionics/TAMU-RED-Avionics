import re
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QFrame,
)
from PyQt5.QtCore import Qt, QPoint

from GUI_CONTROLLER import GUIController
from GUI_WIDGETS import DragHandle, RenameLabel, ask_new_name
from PID_SCHEMA import COMMANDABLE_VALVE_TYPES, COMP_IGNITER, get_actuator_spec


_VALVE_MIME = "application/x-red-valve-row"


def _natural_key(text: str):
    """Alphabetical, with digit runs compared as numbers (NV-1104 < NV-1105 < NV-11010)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


class ValveControlPanel(QWidget):
    """Open / Close buttons for every relay-bound valve and pump in the project. Position-
    commanded actuators (the Bray valve) open to 100 % and close to 0 %. Igniters are
    left out on purpose, and so are passive parts (PRVs, check valves) and manual valves,
    which have no binding.

    Rows start sorted alphabetically then numerically. Drag a row's grip (the dots on its
    left) to reorder, and double-click a name to rename it. Both are for this session only:
    nothing is saved, so a restart brings back the original order and names."""

    def __init__(self, controller: GUIController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setAcceptDrops(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        outer.addWidget(self._hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._body = QWidget()
        self._list = QVBoxLayout(self._body)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.setSpacing(4)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

        self._drop_line = QFrame(self)              # insertion marker shown while dragging a row
        self._drop_line.setStyleSheet("background-color: #4488ff; border-radius: 1px;")
        self._drop_line.hide()

        self._rows = {}         # hw_id -> (state label, open btn, close btn, row widget, name label)
        self._order = []        # session-only row order (hw_ids)

        s = controller.signals
        s.valve_updated.connect(self._on_valve_updated)
        s.actuator_updated.connect(self._on_actuator_updated)
        s.mode_changed.connect(self._refresh_enabled)
        s.view_only_changed.connect(lambda *_: self._refresh_enabled())
        s.project_changed.connect(self.rebuild)
        s.names_changed.connect(self._refresh_names)
        self.rebuild()

    def rebuild(self):
        while self._list.count():
            item = self._list.takeAt(0)
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
        # Alphabetical/numerical by default; anything the operator already dragged keeps its place
        known = {h: i for i, h in enumerate(self._order)}
        entries.sort(key=lambda e: (0, known[e[1]], []) if e[1] in known else (1, 0, _natural_key(e[0])))
        self._order = [h for _l, h in entries]

        for _label, hw_id in entries:
            row = QWidget()
            lay = QHBoxLayout(row)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(8)
            handle = DragHandle(hw_id, _VALVE_MIME)
            name = RenameLabel(self.controller.valve_display_name(hw_id))
            name.setStyleSheet("font-weight: bold;")
            name.setMinimumWidth(110)
            name.rename_requested.connect(lambda h=hw_id: self._rename(h))
            state = QLabel("---")
            state.setMinimumWidth(70)
            open_btn = QPushButton("Open")
            close_btn = QPushButton("Close")
            open_btn.clicked.connect(lambda _=False, h=hw_id: self._command(h, True))
            close_btn.clicked.connect(lambda _=False, h=hw_id: self._command(h, False))
            lay.addWidget(handle)
            lay.addWidget(name)
            lay.addWidget(state, 1)
            lay.addWidget(open_btn)
            lay.addWidget(close_btn)
            self._list.addWidget(row)
            self._rows[hw_id] = (state, open_btn, close_btn, row, name)
            self._show_state(hw_id)
        self._list.addStretch(1)
        self._refresh_enabled()

    # --- renaming (session only) ---------------------------------------------------
    def _rename(self, hw_id: str):
        c = self.controller
        new = ask_new_name(self, c.valve_display_name(hw_id), c.original_name(hw_id))
        if new is not None:
            c.rename_item(hw_id, new)

    def _refresh_names(self):
        for hw_id, row in self._rows.items():
            row[4].setText(self.controller.valve_display_name(hw_id))

    # --- drag-and-drop reordering (session only) -----------------------------------
    def _drop_target(self, event):
        """(dragged hw_id, new index, line y, line x, line width) for a drag over the panel."""
        if not event.mimeData().hasFormat(_VALVE_MIME):
            return None
        key = bytes(event.mimeData().data(_VALVE_MIME)).decode()
        if key not in self._rows:
            return None
        row = self._rows[key][3]
        others = [self._rows[h][3] for h in self._order if h != key]
        if not others:
            return None
        cursor_y = event.pos().y()
        new = sum(1 for r in others
                  if self.mapFromGlobal(r.mapToGlobal(QPoint(0, r.height() // 2))).y() < cursor_y)
        if new == 0:
            line_y = self.mapFromGlobal(others[0].mapToGlobal(QPoint(0, 0))).y()
        else:
            ref = others[new - 1]
            line_y = self.mapFromGlobal(ref.mapToGlobal(QPoint(0, ref.height()))).y()
        x = self.mapFromGlobal(others[0].mapToGlobal(QPoint(0, 0))).x()
        return key, new, line_y, x, others[0].width()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_VALVE_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        t = self._drop_target(event)
        if t is None:
            self._drop_line.hide()
        else:
            _key, _new, y, x, w = t
            self._drop_line.setGeometry(x, y - 1, w, 3)
            self._drop_line.show()
            self._drop_line.raise_()
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._drop_line.hide()

    def dropEvent(self, event):
        self._drop_line.hide()
        t = self._drop_target(event)
        event.acceptProposedAction()
        if t is None:
            return
        key, new, *_ = t
        self._order.remove(key)
        self._order.insert(new, key)
        row = self._rows[key][3]
        self._list.removeWidget(row)
        self._list.insertWidget(new, row)

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
        for _state, open_btn, close_btn, _row, _name in self._rows.values():
            open_btn.setEnabled(not locked)
            close_btn.setEnabled(not locked)
        if self.controller.view_only:
            self._hint.setText("Valves can not be commanded in view-only mode.")
        elif locked:
            self._hint.setText(f"Controls disabled in {self.controller.mode} mode.")
        else:
            self._hint.setText("")
