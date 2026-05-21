from dataclasses import dataclass, field
from typing import List, Dict, Any
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSplitter, QInputDialog, QListWidget, QListWidgetItem, QDoubleSpinBox, QMessageBox
)
from PyQt5.QtCore import Qt

from PID_CANVAS import PIDCanvas
from PID_SCHEMA import COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE

@dataclass
class SequenceStep:
    name: str = "State"
    time_offset: float = 0.0                                  # Seconds from sequence auto-start
    open_valves: List[str] = field(default_factory=list)      # List of component IDs that are OPEN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "time_offset": self.time_offset,
            "open_valves": self.open_valves
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SequenceStep":
        return SequenceStep(
            name=d.get("name", "State"),
            time_offset=float(d.get("time_offset", 0.0)),
            open_valves=d.get("open_valves", [])
        )

class SequenceEditorWindow(QWidget):
    def __init__(self, controller, project, canvas_save_callback=None):
        super().__init__()
        self.controller = controller
        self._project = project
        self.canvas_save_callback = canvas_save_callback
        
        raw_seq = getattr(project, 'sequence', []) if hasattr(project, 'sequence') else []
        self.steps: list[SequenceStep] = []
        for s in (raw_seq or []):
            if isinstance(s, dict):
                self.steps.append(SequenceStep.from_dict(s))
            else:
                self.steps.append(s)
        self.current_step_idx = -1

        self.setWindowTitle("Sequence Configuration")
        self.resize(1200, 700)
        self._build_ui()
        
        if self.steps:
            self._select_step(0)

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

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

        self.btn_finish = QPushButton("FINISH & SAVE SEQUENCE")
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
            if comp.type in [COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE]:
                mock_valve_states[cid] = "OPEN" if cid in step.open_valves else "CLOSED"
        
        self.canvas.live_valve_states = mock_valve_states
        self.canvas.update()
        self._refresh_step_list_ui()

    def _on_canvas_component_clicked(self, cid: str):
        if self.current_step_idx == -1:
            return
        comp = self._project.components.get(cid)
        if not comp or comp.type not in [COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE]:
            return

        step = self.steps[self.current_step_idx]
        if cid in step.open_valves:
            step.open_valves.remove(cid)
        else:
            step.open_valves.append(cid)

        self._select_step(self.current_step_idx)

    def _on_time_changed(self, value):
        if self.current_step_idx != -1:
            self.steps[self.current_step_idx].time_offset = value
            self.steps.sort(key=lambda x: x.time_offset)
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
        self._project.sequence = list(self.steps)

        if self.canvas_save_callback:
            self.canvas_save_callback()

        QMessageBox.information(self, "Success", "Sequence successfully added to project file.")