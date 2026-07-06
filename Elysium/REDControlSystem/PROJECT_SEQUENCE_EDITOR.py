import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QInputDialog, QListWidget, QListWidgetItem, QDoubleSpinBox,
    QCheckBox, QMessageBox, QComboBox,
)
from PyQt5.QtCore import Qt

from PID_CANVAS import PIDCanvas
from PID_SCHEMA import (
    SequenceStep, NamedSequence,
    COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_IGNITER,
)

# Component types that a sequence step can command open/closed (or, for the
# igniter, fire/safe).
_STEP_ACTUATOR_TYPES = [COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_IGNITER]

class SequenceEditorWindow(QWidget):
    def __init__(self, controller, project, canvas_save_callback=None):
        super().__init__()
        self.controller = controller
        self._project = project
        self.canvas_save_callback = canvas_save_callback

        if not getattr(project, "sequences", None):
            project.sequences = [NamedSequence(id="seq_default", name="Default")]
            project.active_sequence_id = "seq_default"

        self._current_seq_id = project.active_sequence_id
        self.steps: list[SequenceStep] = []   # direct reference to the selected NamedSequence.steps
        self.current_step_idx = -1

        self.setWindowTitle("Sequence Configuration")
        self.resize(1200, 700)
        self._build_ui()

        self._load_sequence(self._current_seq_id)

    def _current_sequence(self) -> "NamedSequence | None":
        for seq in self._project.sequences:
            if seq.id == self._current_seq_id:
                return seq
        return self._project.sequences[0] if self._project.sequences else None

    def _load_sequence(self, seq_id: str):
        seq = None
        for s in self._project.sequences:
            if s.id == seq_id:
                seq = s
                break
        if seq is None and self._project.sequences:
            seq = self._project.sequences[0]
        if seq is None:
            self.steps = []
            self.current_step_idx = -1
            return

        self._current_seq_id = seq.id
        self.steps = seq.steps   # live reference - edits below apply immediately
        self.current_step_idx = -1
        self._refresh_seq_combo()
        if self.steps:
            self._select_step(0)
        else:
            self.canvas.live_valve_states = {}
            self.canvas.update()
            self._refresh_step_list_ui()

    def _refresh_seq_combo(self):
        self.seq_combo.blockSignals(True)
        self.seq_combo.clear()
        for seq in self._project.sequences:
            self.seq_combo.addItem(seq.name, seq.id)
        idx = next((i for i in range(self.seq_combo.count())
                    if self.seq_combo.itemData(i) == self._current_seq_id), 0)
        self.seq_combo.setCurrentIndex(idx)
        self.seq_combo.blockSignals(False)

    def _on_sequence_combo_changed(self, index: int):
        seq_id = self.seq_combo.itemData(index)
        if seq_id and seq_id != self._current_seq_id:
            self._load_sequence(seq_id)

    def _on_new_sequence(self):
        name, ok = QInputDialog.getText(self, "New Sequence", "Sequence name:")
        if not ok or not name.strip():
            return
        seq = self._project.add_sequence(name.strip())
        self._load_sequence(seq.id)

    def _on_rename_sequence(self):
        seq = self._current_sequence()
        if not seq:
            return
        name, ok = QInputDialog.getText(self, "Rename Sequence", "Sequence name:", text=seq.name)
        if ok and name.strip():
            seq.name = name.strip()
            self._refresh_seq_combo()

    def _on_delete_sequence(self):
        if len(self._project.sequences) <= 1:
            QMessageBox.warning(self, "Can't Delete", "A project must keep at least one sequence.")
            return
        seq = self._current_sequence()
        if not seq:
            return
        reply = QMessageBox.question(
            self, "Delete Sequence",
            f"Delete sequence '{seq.name}'? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply != QMessageBox.Yes:
            return
        self._project.remove_sequence(seq.id)
        self._load_sequence(self._project.sequences[0].id)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        seq_row = QHBoxLayout()
        seq_row.addWidget(QLabel("Sequence:"))
        self.seq_combo = QComboBox()
        self.seq_combo.currentIndexChanged.connect(self._on_sequence_combo_changed)
        seq_row.addWidget(self.seq_combo, stretch=1)
        left_layout.addLayout(seq_row)

        seq_mgmt_row = QHBoxLayout()
        btn_new_seq = QPushButton("+ New")
        btn_rename_seq = QPushButton("Rename")
        btn_del_seq = QPushButton("Delete")
        btn_new_seq.clicked.connect(self._on_new_sequence)
        btn_rename_seq.clicked.connect(self._on_rename_sequence)
        btn_del_seq.clicked.connect(self._on_delete_sequence)
        seq_mgmt_row.addWidget(btn_new_seq)
        seq_mgmt_row.addWidget(btn_rename_seq)
        seq_mgmt_row.addWidget(btn_del_seq)
        left_layout.addLayout(seq_mgmt_row)

        tc_len_layout = QHBoxLayout()
        tc_len_layout.addWidget(QLabel("Terminal Count Length (s):"))
        self.tc_length_spin = QDoubleSpinBox()
        self.tc_length_spin.setRange(1.0, 600.0)
        self.tc_length_spin.setValue(
            getattr(self._project.parameters, "terminal_count_s", 10.0))
        self.tc_length_spin.valueChanged.connect(self._on_tc_length_changed)
        tc_len_layout.addWidget(self.tc_length_spin)
        left_layout.addLayout(tc_len_layout)

        self.step_list_widget = QListWidget()
        self.step_list_widget.currentRowChanged.connect(self._select_step)
        left_layout.addWidget(QLabel("Sequence Steps:"))
        left_layout.addWidget(self.step_list_widget)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Trigger Time (s):"))
        self.time_spinbox = QDoubleSpinBox()
        self.time_spinbox.setRange(0.0, 3600.0)
        self.time_spinbox.setSingleStep(1.0)
        self.time_spinbox.valueChanged.connect(self._on_time_changed)
        time_layout.addWidget(self.time_spinbox)
        left_layout.addLayout(time_layout)

        self.terminal_cb = QCheckBox("This is the Terminal Count state")
        self.terminal_cb.setToolTip(
            "Required before Auto-Fire Sequence can run. Only one step may "
            "be marked as the terminal-count hold.")
        self.terminal_cb.toggled.connect(self._on_terminal_toggled)
        left_layout.addWidget(self.terminal_cb)

        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("◀ Prev State")
        self.btn_next = QPushButton("Next State ▶")
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        self.btn_next.clicked.connect(lambda: self._navigate(1))
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        left_layout.addLayout(nav_layout)

        mgmt_layout = QHBoxLayout()
        btn_add = QPushButton("+ Add Step")
        btn_del = QPushButton("- Delete Step")
        btn_add.clicked.connect(self._add_new_step)
        btn_del.clicked.connect(self._delete_step)
        mgmt_layout.addWidget(btn_add)
        mgmt_layout.addWidget(btn_del)
        left_layout.addLayout(mgmt_layout)

        self.btn_finish = QPushButton("FINISH && SAVE SEQUENCE")
        self.btn_finish.setStyleSheet("background-color: #007acc; color: white; font-weight: bold; font-size: 11pt;")
        self.btn_finish.clicked.connect(self._finish_sequence)
        left_layout.addWidget(self.btn_finish)

        self.canvas = PIDCanvas()
        self.canvas.project = self._project
        self.canvas.interactive = True
        
        self.canvas.component_clicked.connect(self._on_canvas_component_clicked)

        splitter.addWidget(left_panel)
        splitter.addWidget(self.canvas)
        splitter.setSizes([350, 850])

        main_layout.addWidget(splitter)
        self._refresh_step_list_ui()

    def _refresh_step_list_ui(self):
        self.step_list_widget.blockSignals(True)
        self.step_list_widget.clear()
        for idx, step in enumerate(self.steps):
            item_text = f"[{step.time_offset:5.1f}s] {step.name} ({len(step.open_valves)} Valves Open)"
            if getattr(step, "is_terminal_count", False):
                item_text += "  [TERMINAL COUNT]"
            self.step_list_widget.addItem(item_text)
        if self.current_step_idx >= 0 and self.current_step_idx < len(self.steps):
            self.step_list_widget.setCurrentRow(self.current_step_idx)
        self.step_list_widget.blockSignals(False)

    def _select_step(self, index):
        if index < 0 or index >= len(self.steps):
            return
        self.current_step_idx = index
        step = self.steps[index]
        
        self.time_spinbox.blockSignals(True)
        self.time_spinbox.setValue(step.time_offset)
        self.time_spinbox.blockSignals(False)

        self.terminal_cb.blockSignals(True)
        self.terminal_cb.setChecked(getattr(step, "is_terminal_count", False))
        self.terminal_cb.blockSignals(False)

        mock_valve_states = {}
        for cid in self._project.components.keys():
            comp = self._project.components[cid]
            if comp.type in _STEP_ACTUATOR_TYPES:
                mock_valve_states[cid] = "OPEN" if cid in step.open_valves else "CLOSED"
        
        self.canvas.live_valve_states = mock_valve_states
        self.canvas.update()
        self._refresh_step_list_ui()

    def _on_canvas_component_clicked(self, cid: str):
        if self.current_step_idx == -1:
            return
        comp = self._project.components.get(cid)
        if not comp or comp.type not in _STEP_ACTUATOR_TYPES:
            return

        step = self.steps[self.current_step_idx]
        if cid in step.open_valves:
            step.open_valves.remove(cid)
        else:
            step.open_valves.append(cid)

        self._select_step(self.current_step_idx)

    def _on_time_changed(self, value):
        if self.current_step_idx == -1:
            return
        step = self.steps[self.current_step_idx]
        step.time_offset = value
        self.steps.sort(key=lambda x: x.time_offset)
        self.current_step_idx = self.steps.index(step)
        self._refresh_step_list_ui()

    def _on_terminal_toggled(self, checked: bool):
        if self.current_step_idx == -1:
            return
        # Only one step may be the terminal-count hold.
        for i, step in enumerate(self.steps):
            step.is_terminal_count = checked if i == self.current_step_idx else False
        self._refresh_step_list_ui()

    def _on_tc_length_changed(self, value: float):
        self._project.parameters.terminal_count_s = value

    def _navigate(self, delta):
        target = self.current_step_idx + delta
        if 0 <= target < len(self.steps):
            self._select_step(target)

    def _add_new_step(self):
        name, ok = QInputDialog.getText(self, "Step Properties", "Enter step state identifier label:")
        if not ok or not name:
            name = f"State {len(self.steps) + 1}"
        
        new_time = self.steps[-1].time_offset + 5.0 if self.steps else 0.0
        new_step = SequenceStep(name=name, time_offset=new_time, open_valves=[])
        self.steps.append(new_step)
        self.steps.sort(key=lambda x: x.time_offset)
        self.current_step_idx = self.steps.index(new_step)
        self._select_step(self.current_step_idx)

    def _delete_step(self):
        if len(self.steps) > 0 and self.current_step_idx != -1:
            self.steps.pop(self.current_step_idx)
            self.current_step_idx = max(0, self.current_step_idx - 1) if self.steps else -1
            if self.current_step_idx != -1:
                self._select_step(self.current_step_idx)
            else:
                self.canvas.live_valve_states = {}
                self.canvas.update()
                self._refresh_step_list_ui()

    def _finish_sequence(self):
        # self.steps is a direct reference into the selected NamedSequence,
        # so edits are already applied - this just persists the project.
        if self.canvas_save_callback:
            self.canvas_save_callback()

        QMessageBox.information(self, "Success", "Sequence successfully added to project file.")