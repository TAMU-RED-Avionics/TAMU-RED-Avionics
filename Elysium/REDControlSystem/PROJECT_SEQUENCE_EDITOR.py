from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QInputDialog, QListWidget, QDoubleSpinBox,
    QCheckBox, QMessageBox, QComboBox,
)
from PyQt5.QtCore import Qt

from PID_CANVAS import PIDCanvas
from PID_SCHEMA import (
    SequenceStep, NamedSequence,
    COMMANDABLE_VALVE_TYPES,
    get_actuator_spec,
)

_STEP_ACTUATOR_TYPES = list(COMMANDABLE_VALVE_TYPES)


def _is_step_actuator(comp) -> bool:
    return comp.type in _STEP_ACTUATOR_TYPES or get_actuator_spec(comp) is not None

def fmt_t(t: float) -> str:
    """A step time as the operator reads it: T-0.5, T+0.0, T+15.0."""
    return f"T{'-' if t < 0 else '+'}{abs(t):.1f}"


class _TimeSpinBox(QDoubleSpinBox):
    """Seconds relative to T-0, always shown with its sign: +0.5 is after T-0, -0.5 before it."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDecimals(2)
        self.setSuffix(" s")

    def textFromValue(self, value: float) -> str:
        return (f"{value:+.2f}").rstrip("0").rstrip(".")


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
        seq = next((s for s in self._project.sequences if s.id == self._current_seq_id), None)
        if seq is None and self._project.sequences:
            seq = self._project.sequences[0]
        return seq

    def _load_sequence(self, seq_id: str):
        seq = next((s for s in self._project.sequences if s.id == seq_id), None)
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
        tc_len_layout.addWidget(QLabel("<b>Terminal Count:</b>"))
        self.tc_length_spin = QDoubleSpinBox()
        self.tc_length_spin.setRange(0.0, 600.0)
        self.tc_length_spin.setDecimals(1)
        self.tc_length_spin.setSuffix(" seconds")
        self.tc_length_spin.setValue(
            getattr(self._project.parameters, "terminal_count_s", 10.0))
        self.tc_length_spin.valueChanged.connect(self._on_tc_length_changed)
        tc_len_layout.addWidget(self.tc_length_spin)
        left_layout.addLayout(tc_len_layout)

        hint = QLabel("Step times are relative to T-0.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a8a8a; font-size: 9pt;")
        left_layout.addWidget(hint)

        self.step_list_widget = QListWidget()
        self.step_list_widget.currentRowChanged.connect(self._select_step)
        left_layout.addWidget(QLabel("Sequence Steps:"))
        left_layout.addWidget(self.step_list_widget)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Time vs T-0:"))
        self.time_spinbox = _TimeSpinBox()
        self.time_spinbox.setRange(-self.tc_length_spin.value(), 3600.0)
        self.time_spinbox.setSingleStep(0.5)
        self.time_spinbox.setToolTip("Seconds after T-0. Type a minus for before T-0, e.g. -0.5")
        self.time_spinbox.valueChanged.connect(self._on_time_changed)
        time_layout.addWidget(self.time_spinbox)
        left_layout.addLayout(time_layout)

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
        self.canvas.actuator_position_requested.connect(self._on_actuator_position)

        splitter.addWidget(left_panel)
        splitter.addWidget(self.canvas)
        splitter.setSizes([350, 850])

        main_layout.addWidget(splitter)
        self._refresh_step_list_ui()

    def _refresh_step_list_ui(self):
        self.step_list_widget.blockSignals(True)
        self.step_list_widget.clear()
        for idx, step in enumerate(self.steps):
            item_text = f"[{fmt_t(step.time_offset):>7}] {step.name} ({len(step.open_valves)} Valves Open)"
            for cid in step.open_valves:
                comp = self._project.components.get(cid)
                spec = get_actuator_spec(comp) if comp else None
                if spec is not None:
                    item_text += f"  {comp.label} {step.positions.get(cid, spec.open_pct):g}{spec.unit}"
            if step.time_offset < -self.tc_length_spin.value() - 1e-9:
                item_text += "  ⚠ before the terminal count starts"
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

        mock_valve_states = {}
        for cid in self._project.components.keys():
            comp = self._project.components[cid]
            if _is_step_actuator(comp):
                mock_valve_states[cid] = "OPEN" if cid in step.open_valves else "CLOSED"
        
        self.canvas.live_valve_states = mock_valve_states
        self.canvas.update()
        self._refresh_step_list_ui()

    def _on_canvas_component_clicked(self, cid: str):
        if self.current_step_idx == -1:
            return
        comp = self._project.components.get(cid)
        if not comp or not _is_step_actuator(comp):
            return

        step = self.steps[self.current_step_idx]
        spec = get_actuator_spec(comp)
        if spec is not None:
            # Servos / the Bray valve: the same slider popup as on the home screen, to pick how far it opens
            pct = step.positions.get(cid, spec.open_pct) if cid in step.open_valves else spec.safe_pct
            anchor = self.canvas._popup_anchor(cid)
            self.canvas._actuator_popup.show_for(
                cid, (comp.label or cid).strip(), spec,
                "OPEN" if cid in step.open_valves else "CLOSED", pct, anchor)
            return
        if cid in step.open_valves:
            step.open_valves.remove(cid)
        else:
            step.open_valves.append(cid)

        self._select_step(self.current_step_idx)

    def _on_actuator_position(self, cid: str, pct: float):
        """The popup picked a position for this step: anywhere off the safe position means the step
        opens the actuator to that position; the safe position means the step leaves it closed."""
        if not (0 <= self.current_step_idx < len(self.steps)):
            return
        comp = self._project.components.get(cid)
        spec = get_actuator_spec(comp) if comp else None
        if spec is None:
            return
        step = self.steps[self.current_step_idx]
        if spec.is_off_safe(pct):
            if cid not in step.open_valves:
                step.open_valves.append(cid)
            step.positions[cid] = float(pct)
        else:
            if cid in step.open_valves:
                step.open_valves.remove(cid)
            step.positions.pop(cid, None)
        self._select_step(self.current_step_idx)
        self.canvas._actuator_popup.update_actuator(
            cid, "OPEN" if cid in step.open_valves else "CLOSED", pct)

    def _on_time_changed(self, value):
        if self.current_step_idx == -1:
            return
        step = self.steps[self.current_step_idx]
        step.time_offset = value
        self.steps.sort(key=lambda x: x.time_offset)
        self.current_step_idx = self.steps.index(step)
        self._refresh_step_list_ui()

    def _on_tc_length_changed(self, value: float):
        self._project.parameters.terminal_count_s = value
        self.time_spinbox.setMinimum(-value)            # a step can't be earlier than the start of the run
        self._refresh_step_list_ui()

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