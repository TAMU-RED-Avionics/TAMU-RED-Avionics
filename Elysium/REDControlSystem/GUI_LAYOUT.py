from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy,
    QStackedWidget, QComboBox, QScrollArea,
    QGridLayout, QSplitter, QToolButton, QMessageBox,
    QLineEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QFont

from GUI_LOGO import LogoWindow
from GUI_CONNECT import ConnectionWindow
from GUI_DAQ import DAQWindow
from GUI_GRAPHS import SensorGridWindow, SensorGraph
from GUI_CONTROLLER import GUIController
from PID_EDITOR import PIDEditorWindow
from PID_VIEW   import PIDViewWindow
from PROJECT_SEQUENCE_EDITOR import SequenceEditorWindow
from GUI_PERFORMANCE import PerformanceBar
from PROJECT_LOADER import discover_projects, load_project, project_summary
from GUI_ABORT_CONFIG import AbortConfigPage, AbortWindow
from GUI_TELEMETRY import TelemetryPage
from GUI_HEALTH import HealthPage

class CollapsibleSection(QWidget):

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._expanded = True

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("collapsible_header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 4, 6, 4)

        self.toggle_btn = QToolButton()
        self.toggle_btn.setArrowType(Qt.DownArrow)
        self.toggle_btn.setFixedSize(16, 16)
        self.toggle_btn.clicked.connect(self._toggle)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("collapsible_title")

        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(4, 4, 4, 4)
        self.content_layout.setSpacing(4)

        outer.addWidget(header)
        outer.addWidget(self.content)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.toggle_btn.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

class TareDialog(QDialog):
    """Tare a sensor so its current reading displays as a chosen value.
    PTs default to 14.7 (ambient); everything else defaults to 0."""

    def __init__(self, sensor_name: str, controller: GUIController, parent=None):
        super().__init__(parent)
        self.sensor_name = sensor_name
        self.controller = controller
        self.setWindowTitle(f"Tare {sensor_name}")

        default_target = 14.7 if self._is_pt(sensor_name) else 0.0

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        current = controller.current_sensor_values.get(sensor_name.upper())
        current_txt = f"{current:.2f}" if current is not None else "-"
        layout.addWidget(QLabel(
            f"Set the current {sensor_name} reading ({current_txt}) to:"))

        self.target_spin = QDoubleSpinBox()
        self.target_spin.setRange(-99999, 99999)
        self.target_spin.setDecimals(2)
        self.target_spin.setValue(default_target)
        layout.addWidget(self.target_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Tare")
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

        if sensor_name.upper() in controller.tare_offsets:
            clear_btn = buttons.addButton("Clear Tare", QDialogButtonBox.ResetRole)
            clear_btn.clicked.connect(self._clear)

        layout.addWidget(buttons)

    @staticmethod
    def _is_pt(name: str) -> bool:
        n = name.upper()
        return n.startswith("P") and not n.startswith("PU")  # P1…P8 / PT_x

    def _apply(self):
        if self.controller.tare_sensor(self.sensor_name, self.target_spin.value()):
            self.accept()
        else:
            QMessageBox.information(
                self, "No Reading",
                f"No reading has been received for {self.sensor_name} yet - "
                "connect and wait for data before taring.")

    def _clear(self):
        self.controller.clear_tare(self.sensor_name)
        self.accept()


class SensorRow(QWidget):
    """One sensor line in the right sidebar: name, live value, unit, tare."""
    clicked = pyqtSignal(str)

    def __init__(self, name: str, unit: str, controller: GUIController, parent=None):
        super().__init__(parent)
        self.name = name
        self.controller = controller

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(10)

        self.name_lbl = QLabel(f"{name}:")
        self.name_lbl.setFixedWidth(52)
        self.name_lbl.setObjectName("sensor_name_label")

        self.value_lbl = QLabel("---")
        self.value_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_lbl.setObjectName("sensor_value_label")
        self.value_lbl.setMinimumWidth(90)

        self.unit_lbl = QLabel(unit)
        self.unit_lbl.setFixedWidth(40)
        self.unit_lbl.setObjectName("sensor_unit_label")

        self.tare_btn = QPushButton("tare")
        self.tare_btn.setObjectName("tare_btn")
        self.tare_btn.setFixedSize(52, 26)
        self.tare_btn.clicked.connect(self._open_tare_dialog)

        layout.addWidget(self.name_lbl)
        layout.addWidget(self.value_lbl, stretch=1)
        layout.addWidget(self.unit_lbl)
        layout.addWidget(self.tare_btn)

        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        """Emit clicked signal with sensor name when row is clicked."""
        self.clicked.emit(self.name)
        super().mousePressEvent(event)

    def set_value(self, val: float, status: str = ""):
        self.value_lbl.setText(f"{val:.2f}")
        if status == "RED":
            self.value_lbl.setStyleSheet("color: #cc2222; font-weight: bold;")
        elif status == "ORANGE":
            self.value_lbl.setStyleSheet("color: #cc7700; font-weight: bold;")
        elif status == "BLUE":
            self.value_lbl.setStyleSheet("color: #4488ff; font-weight: bold;")
        else:
            self.value_lbl.setStyleSheet("")

    def set_selected(self, selected: bool):
        """Highlight this row when it's the selected sensor for graphing."""
        if selected:
            self.setStyleSheet("background-color: rgba(128, 128, 128, 0.2); border-radius: 4px;")
        else:
            self.setStyleSheet("")

    def _open_tare_dialog(self):
        TareDialog(self.name, self.controller, self).exec_()


class SensorPanel(QWidget):
    """Right-hand sensor sidebar. Rows are built entirely from whatever the
    loaded project defines (controller.pt_keys / tc_keys / lc_keys, rebuilt
    per-project in GUIController._rebuild_sensor_keys) - there is no fixed
    P1-P8 / TC1-3 / LC1-3 assumption, so a project with 4 PTs and no load
    cells shows exactly that."""

    sensor_selected = pyqtSignal(str)

    def __init__(self, controller: GUIController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.controller.signals.sensor_updated.connect(self._on_sensor_updated)

        self._selected_sensor = None

        self.setObjectName("sensor_panel")
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(6, 6, 6, 6)
        inner_layout.setSpacing(8)

        pt_title = QLabel("PT Sensors")
        pt_title.setObjectName("panel_section_title")
        inner_layout.addWidget(pt_title)

        pt_divider = QFrame()
        pt_divider.setFrameShape(QFrame.HLine)
        inner_layout.addWidget(pt_divider)

        self._pt_layout = QVBoxLayout()
        self._pt_layout.setContentsMargins(0, 0, 0, 0)
        self._pt_layout.setSpacing(4)
        inner_layout.addLayout(self._pt_layout)

        self._pt_empty_lbl = QLabel("No pressure transducers in this project.")
        self._pt_empty_lbl.setObjectName("sensor_unit_label")
        self._pt_empty_lbl.setWordWrap(True)
        inner_layout.addWidget(self._pt_empty_lbl)

        inner_layout.addSpacing(6)

        self.tc_section = CollapsibleSection("Thermocouples")
        self._tc_empty_lbl = QLabel("No thermocouples in this project.")
        self._tc_empty_lbl.setObjectName("sensor_unit_label")
        self._tc_empty_lbl.setWordWrap(True)
        self.tc_section.add_widget(self._tc_empty_lbl)
        self.tc_section._toggle()
        inner_layout.addWidget(self.tc_section)

        self.lc_section = CollapsibleSection("Load Cells")
        self._lc_empty_lbl = QLabel("No load cells in this project.")
        self._lc_empty_lbl.setObjectName("sensor_unit_label")
        self._lc_empty_lbl.setWordWrap(True)
        self.lc_section.add_widget(self._lc_empty_lbl)

        self._lc_total_row = QWidget()
        total_layout = QHBoxLayout(self._lc_total_row)
        total_layout.setContentsMargins(0, 4, 0, 0)
        total_lbl = QLabel("Total:")
        total_lbl.setObjectName("sensor_name_label")
        self.lc_total_lbl = QLabel("---")
        self.lc_total_lbl.setObjectName("sensor_value_label")
        self.lc_total_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        total_unit = QLabel("lbf")
        total_unit.setFixedWidth(28)
        total_layout.addWidget(total_lbl)
        total_layout.addWidget(self.lc_total_lbl, stretch=1)
        total_layout.addWidget(total_unit)
        self.lc_section.add_widget(self._lc_total_row)
        self._lc_total_row.setVisible(False)

        self.lc_section._toggle()
        inner_layout.addWidget(self.lc_section)

        self.pt_rows: dict[str, SensorRow] = {}
        self.tc_rows: dict[str, SensorRow] = {}
        self.lc_rows: dict[str, SensorRow] = {}

        inner_layout.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.refresh_sensors()

    def load_project(self, project):
        self.refresh_sensors()

    def refresh_sensors(self):
        """Rebuild every row from the controller's current per-project
        sensor key lists. Safe to call any time (project switch, refresh)."""
        c = self.controller
        self._rebuild_rows(self._pt_layout, self.pt_rows, c.pt_keys, "psi")
        self._pt_empty_lbl.setVisible(not c.pt_keys)

        self._rebuild_rows(self.tc_section.content_layout, self.tc_rows, c.tc_keys, "°C",
                          keep_widgets=(self._tc_empty_lbl,))
        self._tc_empty_lbl.setVisible(not c.tc_keys)

        self._rebuild_rows(self.lc_section.content_layout, self.lc_rows, c.lc_keys, "lbf",
                          keep_widgets=(self._lc_empty_lbl, self._lc_total_row))
        self._lc_empty_lbl.setVisible(not c.lc_keys)
        self._lc_total_row.setVisible(bool(c.lc_keys))

        self._update_lc_total()

    def _rebuild_rows(self, layout, rows_dict: dict, keys: list, unit: str,
                     keep_widgets: tuple = ()):
        """Clear out any previously-built SensorRow widgets from `layout`
        (leaving `keep_widgets` - e.g. the empty-state label / total row -
        untouched) and rebuild fresh rows for the current `keys` list."""
        for row in rows_dict.values():
            layout.removeWidget(row)
            row.deleteLater()
        rows_dict.clear()

        insert_at = 0
        for name in keys:
            row = SensorRow(name, unit, self.controller)
            row.clicked.connect(self._on_sensor_row_clicked)
            rows_dict[name] = row
            layout.insertWidget(insert_at, row)
            insert_at += 1

    def _all_rows(self) -> dict:
        return {**self.pt_rows, **self.tc_rows, **self.lc_rows}

    def _on_sensor_row_clicked(self, sensor_name: str):
        """Handle click on any sensor row - update selection and emit signal."""
        self._selected_sensor = sensor_name

        for name, row in self._all_rows().items():
            row.set_selected(name == sensor_name)

        self.sensor_selected.emit(sensor_name)

    def _on_sensor_updated(self, name: str, value: float, timestamp: float):
        if name in self.pt_rows:
            status = self.controller.get_sensor_status(name, value)
            self.pt_rows[name].set_value(value, status)

        elif name in self.tc_rows:
            self.tc_rows[name].set_value(value)

        elif name in self.lc_rows:
            self.lc_rows[name].set_value(value)
            self._update_lc_total()

    def _update_lc_total(self):
        total = sum(
            self.controller.current_sensor_values.get(n, 0.0)
            for n in self.controller.lc_keys
        )
        self.lc_total_lbl.setText(f"{total:.2f}")


class WarningPanel(QWidget):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("warning_panel")
        self.setMaximumHeight(100)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        header_layout = QHBoxLayout()
        self.warning_title = QLabel("Warnings")
        self.warning_title.setObjectName("warning_title")
        header_layout.addWidget(self.warning_title)
        header_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("clear_warnings_btn")
        self.clear_btn.setFixedSize(60, 24)
        self.clear_btn.clicked.connect(self.clear_warnings)
        header_layout.addWidget(self.clear_btn)
        
        layout.addLayout(header_layout)
        
        self.warning_text = QLabel("No active warnings")
        self.warning_text.setObjectName("warning_message")
        self.warning_text.setWordWrap(True)
        layout.addWidget(self.warning_text)

        # Hidden until the first warning arrives
        self.setVisible(False)
    
    def set_warnings(self, messages: list[str]):
        if not messages:
            self.clear_warnings()
            return
        
        self.setVisible(True)
        self.warning_text.setText("\n".join(f"• {msg}" for msg in messages))

        if any("CRITICAL" in msg.upper() for msg in messages):
            self.setStyleSheet("""
                QWidget#warning_panel {
                    background-color: #cc2222;
                    border: 1px solid #991111;
                    border-radius: 6px;
                }
            """)
        else:
            self.setStyleSheet("""
                QWidget#warning_panel {
                    background-color: #cc7700;
                    border: 1px solid #995500;
                    border-radius: 6px;
                }
            """)
    
    def clear_warnings(self):
        self.setVisible(False)
        self.warning_text.setText("No active warnings")
        self.setStyleSheet("")


class SequencingPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.seq_editor = None

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.placeholder_widget = QWidget()
        ph_layout = QVBoxLayout(self.placeholder_widget)
        
        self.lbl = QLabel(
            "No P&ID project active.\n\n"
            "Please open or create a valid P&ID configuration project "
            "from the main dashboard file menu to configure automated sequences."
        )
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet("font-size: 13pt; color: #888888;")
        ph_layout.addWidget(self.lbl)
        
        self.main_layout.addWidget(self.placeholder_widget)

    def load_project(self, project):
        if not project:
            return
            
        if self.seq_editor:
            self.seq_editor.setParent(None)
            self.seq_editor.deleteLater()
            
        self.placeholder_widget.setVisible(False)

        self.seq_editor = SequenceEditorWindow(
            controller=self.controller,
            project=project,
            canvas_save_callback=lambda: self.controller.project.save(self.controller.project_path)
        )

        self.main_layout.addWidget(self.seq_editor)
        self.seq_editor.setVisible(True)
 
 
class NewPIDPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
 
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
 
        self.editor = PIDEditorWindow()
        layout.addWidget(self.editor)
    
    def load_project(self, project):
        if not project:
            return

        project_path = getattr(self.controller, "project_path", "")
        self.editor.load_project_path(project_path)


class HomePage(QWidget):
    def __init__(self, controller: GUIController, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Live P&ID canvas (replaces static ValveDiagramWindow) ─────────────
        self.live_pid = PIDViewWindow(controller=controller)
        self.live_pid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ── Right column: sensor readouts + graph ──────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)

        self.sensor_panel = SensorPanel(controller)

        self.warning_panel = WarningPanel()

        self.sensor_panel.sensor_selected.connect(self._on_graph_sensor_changed)
        self.controller.signals.warnings_changed.connect(self._on_warnings_changed)

        self.sensor_grid = SensorGridWindow(controller)
        self.sensor_grid.setVisible(False)
        self.sensor_grid.main_graph.setMinimumHeight(160)
        self.sensor_grid.main_graph.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right_layout.addWidget(self.sensor_panel, stretch=3)
        right_layout.addWidget(self.warning_panel)
        right_layout.addWidget(self.sensor_grid.main_graph, stretch=2)

        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setObjectName("panel_divider")

        layout.addWidget(self.live_pid, stretch=3)
        layout.addWidget(divider)
        layout.addWidget(right_widget, stretch=1)

    def load_project(self, project):
        """Called by MainWindow when a project file is selected."""
        self.live_pid.load_project(project)
        self.sensor_panel.refresh_sensors()
        self.sensor_grid.refresh_sensors()
        self.clear_warnings()

    def _on_graph_sensor_changed(self, sensor_name: str):
        self.sensor_grid.update_main_graph(sensor_name)

    def show_warnings(self, messages: list):
        self.warning_panel.set_warnings(messages)

    def clear_warnings(self):
        self.warning_panel.clear_warnings()

    def _on_warnings_changed(self, messages: list):
        if messages:
            self.show_warnings(messages)
        else:
            self.clear_warnings()

    def set_dark_mode(self, dark: bool):
        # The live PID canvas uses its own dark background - nothing to switch
        self.sensor_grid.set_dark_mode(dark)

class ActionBar(QWidget):
    def __init__(self, controller: GUIController,
                 conn_widget: ConnectionWindow,
                 daq_window: DAQWindow,
                 abort_menu: AbortWindow,
                 parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        abort_menu.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        abort_menu.setMinimumWidth(230)
        layout.addWidget(abort_menu)

        divider1 = QFrame()
        divider1.setFrameShape(QFrame.VLine)
        layout.addWidget(divider1)

        self.active_seq_combo = QComboBox()
        self.active_seq_combo.setObjectName("action_bar_combo")
        self.active_seq_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.active_seq_combo.setMinimumWidth(150)
        self.active_seq_combo.currentIndexChanged.connect(self._on_sequence_changed)
        layout.addWidget(self.active_seq_combo)

        self.fire_seq_btn = QPushButton("Auto-Fire Sequence")
        self.fire_seq_btn.setObjectName("action_bar_btn")
        self.fire_seq_btn.setEnabled(False)
        self.fire_seq_btn.clicked.connect(controller.show_fire_sequence_dialog)
        layout.addWidget(self.fire_seq_btn)

        self.fully_closed_btn = QPushButton("Fully Closed")
        self.fully_closed_btn.setObjectName("action_bar_btn")
        self.fully_closed_btn.setToolTip(
            "Close every open valve without aborting.\n"
            "Locked while the system is already fully closed.")
        self.fully_closed_btn.setEnabled(False)
        self.fully_closed_btn.clicked.connect(controller.close_all_valves)
        layout.addWidget(self.fully_closed_btn)

        divider2 = QFrame()
        divider2.setFrameShape(QFrame.VLine)
        layout.addWidget(divider2)

        self.start_rec_btn = QPushButton("▶  Start Recording")
        self.start_rec_btn.setObjectName("action_bar_btn")
        self.start_rec_btn.clicked.connect(self._on_start_recording)
        layout.addWidget(self.start_rec_btn)

        self.stop_rec_btn = QPushButton("■  Stop Recording")
        self.stop_rec_btn.setObjectName("action_bar_btn")
        self.stop_rec_btn.setEnabled(False)
        self.stop_rec_btn.clicked.connect(self._on_stop_recording)
        layout.addWidget(self.stop_rec_btn)

        # Keep a reference to daq_window so our handlers can call it
        self._daq_window = daq_window

        divider_perf = QFrame()
        divider_perf.setFrameShape(QFrame.VLine)
        layout.addWidget(divider_perf)

        self.performance_bar = PerformanceBar(controller)
        layout.addWidget(self.performance_bar)

        layout.addStretch()

        self.state_label = QLabel("State: Fully Closed")
        self.state_label.setObjectName("state_label")
        layout.addWidget(self.state_label)
        self._last_status = ""
        controller.signals.system_status.connect(self._on_system_status)
        # Belt-and-suspenders: a fresh connection always clears stale status
        # text (e.g. "Disconnected (safe)" surviving a reconnect).
        controller.signals.connected.connect(self._on_reconnected)

        controller.signals.connected.connect(self.sync_fire_sequence_state)
        controller.signals.disconnected.connect(lambda _: self.sync_fire_sequence_state())
        controller.signals.abort_triggered.connect(lambda *_: self.sync_fire_sequence_state())
        controller.signals.safe_state.connect(self.sync_fire_sequence_state)

        # "Fully Closed" unlocks whenever any valve is open
        controller.signals.valve_updated.connect(lambda *_: self.sync_fully_closed_state())
        controller.signals.connected.connect(self.sync_fully_closed_state)
        controller.signals.disconnected.connect(lambda _: self.sync_fully_closed_state())

        divider3 = QFrame()
        divider3.setFrameShape(QFrame.VLine)
        layout.addWidget(divider3)

        conn_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(conn_widget)

        self.sync_fire_sequence_state()

    def sync_fire_sequence_state(self):
        project = getattr(self.controller, "project", None)
        
        self.active_seq_combo.blockSignals(True)
        self.active_seq_combo.clear()
        
        has_sequence = False
        if project:
            named_sequences = getattr(project, "sequences", [])
            legacy_steps    = getattr(project, "sequence", [])
            
            if named_sequences:
                has_sequence = True
                active_id = getattr(project, "active_sequence_id", "")
                for ns in named_sequences:
                    self.active_seq_combo.addItem(ns.name, ns.id)
                
                # Pre-select active sequence
                for i in range(self.active_seq_combo.count()):
                    if self.active_seq_combo.itemData(i) == active_id:
                        self.active_seq_combo.setCurrentIndex(i)
                        break
            elif legacy_steps:
                has_sequence = True
                self.active_seq_combo.addItem("Legacy Sequence", "legacy")
                self.active_seq_combo.setCurrentIndex(0)
                
        self.active_seq_combo.blockSignals(False)
        self.active_seq_combo.setEnabled(has_sequence)

        connected = bool(getattr(self.controller.ethernet_client, "connected", False))
        enabled = connected and has_sequence and not self.controller.lockout
        self.fire_seq_btn.setEnabled(enabled)
        self.sync_fully_closed_state()

    def _on_sequence_changed(self, index):
        project = getattr(self.controller, "project", None)
        if project and index >= 0:
            seq_id = self.active_seq_combo.itemData(index)
            if seq_id != "legacy":
                project.active_sequence_id = seq_id

    def sync_fully_closed_state(self):
        """Enabled only while at least one valve is open."""
        any_open = any(self.controller.valve_states.values())
        self.fully_closed_btn.setEnabled(any_open)
        self._refresh_state_label()

    def _on_system_status(self, status: str):
        self._last_status = status
        self._refresh_state_label()

    def _on_reconnected(self):
        self._last_status = ""
        self._refresh_state_label()

    def _refresh_state_label(self):
        open_count = sum(1 for is_open in self.controller.valve_states.values() if is_open)
        valve_txt = (f"{open_count} Valve{'s' if open_count != 1 else ''} Open"
                     if open_count else "Fully Closed")
        s = (self._last_status or "").strip()
        if s and s.upper() not in ("-", "CONNECTED", "NONE", "SAFE"):
            self.state_label.setText(f"State: {s} · {valve_txt}")
        else:
            self.state_label.setText(f"State: {valve_txt}")

    def _on_start_recording(self):
        """Start recording and update button states in the action bar."""
        if self._daq_window.controller.start_recording():
            fname = self._daq_window.controller._xlsx_path
            short = fname.replace("\\", "/").split("/")[-1]
            self._daq_window.filename_preview.setText(short)
            self.start_rec_btn.setEnabled(False)
            self.stop_rec_btn.setEnabled(True)

    def _on_stop_recording(self):
        """Stop recording and update button states in the action bar."""
        self._daq_window.controller.stop_recording()
        self.start_rec_btn.setEnabled(True)
        self.stop_rec_btn.setEnabled(False)
        self._daq_window.filename_preview.setText(self._daq_window._get_preview())

class TabBar(QWidget):

    def __init__(self, pages: list[tuple[str, QWidget]], stack: QStackedWidget, parent=None):
        super().__init__(parent)
        self.buttons: list[QPushButton] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i, (label, _) in enumerate(pages):
            btn = QPushButton(label)
            btn.setObjectName("tab_btn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, idx=i: self._select(idx, stack))
            layout.addWidget(btn)
            self.buttons.append(btn)

        layout.addStretch()
        self._select(0, stack)

    def _select(self, idx: int, stack: QStackedWidget):
        stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == idx)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RED Control System")
        self.setGeometry(10, 10, 1400, 820)

        self.dark_mode = True # change to False if you want to start in light mode
        self.text_size = 12   # must be one of the sizes in the change_text_size cycle

        self.controller = GUIController(self)

        self.controller.project = None
        self.controller.project_path = None

        self.conn_widget = ConnectionWindow(self.controller)
        self.daq_window = DAQWindow(self.controller)
        self.daq_window.setVisible(False)
        self.abort_menu = AbortWindow(self.controller)
        self._build_ui()
        self.apply_stylesheet()

    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        chrome = QWidget()
        chrome.setObjectName("top_chrome")
        chrome_layout = QHBoxLayout(chrome)
        chrome_layout.setContentsMargins(8, 4, 8, 0)
        chrome_layout.setSpacing(12)

        self.logo = LogoWindow(scale_width=90)
        chrome_layout.addWidget(self.logo)

        logo_div = QFrame()
        logo_div.setFrameShape(QFrame.VLine)
        logo_div.setObjectName("chrome_divider")
        chrome_layout.addWidget(logo_div)

        self.stack = QStackedWidget()

        self.home_page = HomePage(self.controller)
        self.abort_config_page = AbortConfigPage(self.controller)
        self.sequencing_page = SequencingPage(self.controller)
        self.new_pid_page = NewPIDPage(self.controller)
        self.telemetry_page = TelemetryPage(self)
        self.health_page = HealthPage(self.controller)

        pages = [
            ("Home",          self.home_page),
            ("Abort Config",  self.abort_config_page),
            ("Sequencing",    self.sequencing_page),
            ("New/Edit PID",  self.new_pid_page),
            ("Telemetry",     self.telemetry_page),
            ("Health",        self.health_page),
        ]
        for _, page in pages:
            self.stack.addWidget(page)

        self.tab_bar = TabBar(pages, self.stack)
        chrome_layout.addWidget(self.tab_bar, stretch=1)

        proj_label = QLabel("Project:")
        proj_label.setObjectName("proj_label")
        chrome_layout.addWidget(proj_label)

        self.project_combo = QComboBox()
        self.project_combo.setObjectName("project_combo")
        self.project_combo.setMinimumWidth(150)

        self._project_paths: list[str | None] = [None]
        self.project_combo.addItem("Choose project")

        for display_name, path in discover_projects():
            self.project_combo.addItem(display_name)
            self._project_paths.append(path)

        self.refresh_project_btn = QPushButton("Refresh")
        self.refresh_project_btn.setObjectName("small_btn")
        self.refresh_project_btn.setFixedHeight(26)
        self.refresh_project_btn.clicked.connect(self.refresh_current_project)

        # Project is locked once the operator confirms safe state (system
        # live) or while any valve is open; unlocked while not-yet-confirmed
        # and fully closed. See GUIController.project_lock_required().
        self.controller.signals.connected.connect(self._refresh_project_lock)
        self.controller.signals.abort_triggered.connect(lambda *_: self._refresh_project_lock())
        self.controller.signals.safe_state.connect(self._refresh_project_lock)
        self.controller.signals.disconnected.connect(lambda _: self._refresh_project_lock())
        self.controller.signals.valve_updated.connect(lambda *_: self._refresh_project_lock())

        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        chrome_layout.addWidget(self.project_combo)
        chrome_layout.addWidget(self.refresh_project_btn)

        self.proj_version_label = QLabel("")
        self.proj_version_label.setObjectName("proj_label")
        chrome_layout.addWidget(self.proj_version_label)


        self.dark_mode_btn = QPushButton("Light Mode") if self.dark_mode else QPushButton("Dark Mode")
        self.dark_mode_btn.setObjectName("small_btn")
        self.dark_mode_btn.setFixedHeight(26)
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)
        chrome_layout.addWidget(self.dark_mode_btn)

        self.text_size_btn = QPushButton("Large Text")
        self.text_size_btn.setObjectName("small_btn")
        self.text_size_btn.setFixedHeight(26)
        self.text_size_btn.clicked.connect(self.change_text_size)
        chrome_layout.addWidget(self.text_size_btn)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("tab_separator")

        self.action_bar = ActionBar(
            self.controller,
            self.conn_widget,
            self.daq_window,
            self.abort_menu,
        )
        self.action_bar.setObjectName("action_bar")
        self.action_bar.setFixedHeight(72)

        action_sep = QFrame()
        action_sep.setFrameShape(QFrame.HLine)
        action_sep.setObjectName("action_separator")

        root.addWidget(chrome)
        root.addWidget(sep)
        root.addWidget(self.stack, stretch=1)
        root.addWidget(action_sep)
        root.addWidget(self.action_bar)

        self.setCentralWidget(central)

    def _refresh_project_lock(self):
        self._set_project_locked(self.controller.project_lock_required())

    def _set_project_locked(self, locked: bool):
        self.project_combo.setEnabled(not locked)
        self.refresh_project_btn.setEnabled(not locked)
        tip = ("Project is locked while the system is live or a valve is open"
              if locked else "")
        self.project_combo.setToolTip(tip)

    def _on_project_selected(self, index: int):
        """Called whenever the user picks a different item in the project combo."""
        if index <= 0:
            self.proj_version_label.setText("")
            return

        path = self._project_paths[index]
        if path is None:
            return

        project = load_project(path)
        if project is None:
            QMessageBox.critical(
                self,
                "Project Load Failed",
                f"Could not load project file:\n{path}\n\nCheck the console for details.",
            )
            self.project_combo.blockSignals(True)
            self.project_combo.setCurrentIndex(0)
            self.project_combo.blockSignals(False)
            self.proj_version_label.setText("")
            return

        self.controller.project = project
        self.controller.project_path = path

        self.proj_version_label.setText(f"v{project.version}")
        self.proj_version_label.setToolTip(project_summary(project))

        self._dispatch_project(project)

    def refresh_current_project(self):
        """Reload the currently loaded project from disk."""
        path = self.controller.project_path
        if not path and 0 < self.project_combo.currentIndex() < len(self._project_paths):
            path = self._project_paths[self.project_combo.currentIndex()]

        if not path:
            return

        project = load_project(path)
        if project is None:
            QMessageBox.critical(
                self,
                "Project Load Failed",
                f"Could not reload project file:\n{path}\n\nCheck the console for details.",
            )
            return

        self.controller.project = project
        self.controller.project_path = path

        if path in self._project_paths:
            idx = self._project_paths.index(path)
            if idx > 0 and self.project_combo.currentIndex() != idx:
                self.project_combo.blockSignals(True)
                self.project_combo.setCurrentIndex(idx)
                self.project_combo.blockSignals(False)

        self.proj_version_label.setText(f"v{project.version}")
        self.proj_version_label.setToolTip(project_summary(project))

        self._dispatch_project(project)

    def _dispatch_project(self, project):
        # MUST come first - populates pt_keys / tc_keys / lc_keys and reloads abort rules
        self.controller.load_project(project, self.controller.project_path)

        if hasattr(self, "home_page"):
            self.home_page.load_project(project)

        if hasattr(self, "sequencing_page"):
            self.sequencing_page.load_project(project)

        if hasattr(self, "new_pid_page") and hasattr(self.new_pid_page, "editor"):
            try:
                self.new_pid_page.load_project(project)
            except AttributeError:
                pass

        if hasattr(self, "abort_config_page"):
            self.abort_config_page.load_project(project)

        # Refresh DAQ filename preview now that sensor keys are populated
        if hasattr(self, "daq_window"):
            self.daq_window.filename_preview.setText(self.daq_window._get_preview())

        if hasattr(self, "action_bar"):
            self.action_bar.sync_fire_sequence_state()
            self.action_bar.performance_bar.refresh_channels()
        

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        self.apply_stylesheet()
        self.home_page.set_dark_mode(self.dark_mode)
        self.dark_mode_btn.setText("Light Mode" if self.dark_mode else "Dark Mode")
        if self.dark_mode:
            self.logo.set_dark_image()
            self.conn_widget.spinner.color = QColor(255, 255, 255)
        else:
            self.logo.set_light_image()
            self.conn_widget.spinner.color = QColor(0, 0, 0)
        
        self.telemetry_page.panel_a.table._apply_theme()
        self.telemetry_page.panel_b.table._apply_theme()
        if hasattr(self.telemetry_page.panel_a.graph, "set_dark_mode"):
            self.telemetry_page.panel_a.graph.set_dark_mode(self.dark_mode)
        if hasattr(self.telemetry_page.panel_b.graph, "set_dark_mode"):
            self.telemetry_page.panel_b.graph.set_dark_mode(self.dark_mode)

    def change_text_size(self):
        cycle = {12: (16, "Small Text"), 16: (8, "Medium Text"), 8: (12, "Large Text")}
        self.text_size, label = cycle.get(self.text_size, (12, "Large Text"))
        self.text_size_btn.setText(label)
        self.apply_stylesheet()

    def apply_stylesheet(self):
        ts = self.text_size
        if self.dark_mode:
            bg       = "#1e1e24"   # window background
            bg2      = "#26262e"   # raised surfaces (chrome, cards, toolbars)
            bg3      = "#33333e"   # controls (buttons, inputs)
            bg4      = "#3d3d4a"   # control hover
            border   = "#44444f"
            border2  = "#5a5a68"   # hover / focus border
            text     = "#e8e6e0"
            text2    = "#9b9990"
            accent   = "#b03a3a"   # brighter maroon reads better on dark
            accent2  = "#8b1a1a"
            sel_text = "#ffffff"
        else:
            bg       = "#f4f2ee"
            bg2      = "#ffffff"
            bg3      = "#eceae5"
            bg4      = "#e0ded8"
            border   = "#d4d2cc"
            border2  = "#aaa8a2"
            text     = "#1a1a1a"
            text2    = "#6b6963"
            accent   = "#7a0000"
            accent2  = "#7a0000"
            sel_text = "#ffffff"

        # Sans for UI chrome; mono reserved for data (values, tables, files)
        sans = '"Segoe UI", "Inter", "SF Pro Text", "Ubuntu", "Noto Sans", sans-serif'
        mono = '"Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Courier New", monospace'

        self.setStyleSheet(f"""
            /* ── Root & chrome ── */
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {text};
                font-family: {sans};
                font-size: {ts}pt;
            }}

            QToolTip {{
                background-color: {bg2};
                color: {text};
                border: 1px solid {border2};
                padding: 4px 8px;
                font-size: {max(ts - 2, 7)}pt;
            }}

            QWidget#top_chrome {{
                background-color: {bg2};
                border-bottom: 1px solid {border};
            }}

            QFrame#tab_separator, QFrame#action_separator, QFrame#panel_divider {{
                color: {border};
                max-height: 1px;
                min-height: 1px;
            }}

            /* ── Tab buttons ── */
            QPushButton#tab_btn {{
                background-color: transparent;
                color: {text2};
                border: none;
                border-bottom: 3px solid transparent;
                border-radius: 0px;
                padding: 8px 20px 6px 20px;
                font-size: {ts}pt;
                font-weight: bold;
            }}
            QPushButton#tab_btn:hover {{
                color: {text};
                background-color: {bg3};
            }}
            QPushButton#tab_btn:checked {{
                color: {accent};
                border-bottom: 3px solid {accent};
            }}

            /* ── Action bar ── */
            QWidget#action_bar {{
                background-color: {bg2};
                border-top: 1px solid {border};
            }}
            QPushButton#action_bar_btn {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 5px 14px;
                font-size: {ts}pt;
                font-weight: 600;
            }}
            QPushButton#action_bar_btn:hover    {{ background-color: {bg4}; border-color: {border2}; }}
            QPushButton#action_bar_btn:pressed  {{ background-color: {border}; }}
            QPushButton#action_bar_btn:disabled {{ color: {text2}; background-color: {bg3}; border-color: {border}; }}
            QPushButton#action_bar_btn:checked  {{
                background-color: {accent};
                border-color: {accent};
                color: {sel_text};
            }}

            /* ── General buttons ── */
            QPushButton {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: {ts}pt;
                font-weight: 600;
            }}
            QPushButton:hover    {{ background-color: {bg4}; border-color: {border2}; }}
            QPushButton:pressed  {{ background-color: {border}; }}
            QPushButton:disabled {{ color: {text2}; }}

            QPushButton#primary_btn {{
                background-color: {accent};
                border: 1px solid {accent};
                color: {sel_text};
            }}
            QPushButton#primary_btn:hover   {{ background-color: {accent2}; border-color: {accent2}; }}
            QPushButton#primary_btn:pressed {{ background-color: {accent2}; }}

            QPushButton#small_btn {{
                font-size: {max(ts - 2, 7)}pt;
                padding: 2px 8px;
            }}

            QPushButton#tare_btn {{
                font-size: {max(ts - 2, 7)}pt;
                padding: 1px 4px;
                font-weight: normal;
                border-radius: 3px;
            }}

            QPushButton#clear_warnings_btn {{
                background-color: transparent;
                color: {text};
                border: 1px solid {text};
                border-radius: 3px;
                font-size: {max(ts - 2, 7)}pt;
                padding: 1px 6px;
            }}
            QPushButton#clear_warnings_btn:hover {{
                background-color: rgba(255, 255, 255, 0.2);
            }}

            QToolButton {{
                background-color: transparent;
                color: {text2};
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 2px;
            }}
            QToolButton:hover {{
                background-color: {bg3};
                color: {text};
                border-color: {border};
            }}
            QToolButton#graph_gear_btn {{
                font-size: {ts + 2}pt;
                padding: 0px 6px;
            }}

            /* ── Inputs ── */
            QLineEdit, QDoubleSpinBox, QSpinBox {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 2px 8px;
                font-size: {ts}pt;
                selection-background-color: {accent};
                selection-color: {sel_text};
            }}
            QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
                border: 1px solid {accent};
            }}
            QLineEdit:read-only {{
                background-color: transparent;
                color: {text2};
                border: 1px solid {border};
            }}
            QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {{
                color: {text2};
                background-color: {bg};
            }}
            QDoubleSpinBox::up-button, QSpinBox::up-button,
            QDoubleSpinBox::down-button, QSpinBox::down-button {{
                background-color: {bg4};
                border: none;
                width: 16px;
            }}

            QComboBox {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 5px;
                padding: 2px 8px;
                font-size: {ts}pt;
            }}
            QComboBox:hover {{ border-color: {border2}; }}
            QComboBox::drop-down {{ border: none; width: 18px; }}
            QComboBox QAbstractItemView {{
                background-color: {bg2};
                color: {text};
                border: 1px solid {border};
                selection-background-color: {accent};
                selection-color: {sel_text};
            }}

            QCheckBox {{
                background-color: transparent;
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {border2};
                border-radius: 3px;
                background-color: {bg3};
            }}
            QCheckBox::indicator:checked {{
                background-color: {accent};
                border-color: {accent};
            }}
            QCheckBox:disabled {{ color: {text2}; }}
            QCheckBox::indicator:disabled {{ border-color: {border}; background-color: {bg}; }}

            /* ── Labels ── */
            QLabel {{
                background-color: transparent;
                color: {text};
                font-size: {ts}pt;
            }}
            QLabel#panel_section_title {{
                font-size: {ts + 1}pt;
                font-weight: bold;
                color: {accent};
                letter-spacing: 1px;
            }}
            QLabel#sensor_name_label  {{ color: {text2}; font-size: {ts}pt; font-family: {mono}; }}
            QLabel#sensor_value_label {{ font-size: {ts + 1}pt; font-weight: bold; font-family: {mono}; }}
            QLabel#sensor_unit_label  {{ color: {text2}; font-size: {max(ts - 1, 7)}pt; }}
            QLabel#state_label        {{ color: {accent}; font-weight: bold; font-family: {mono}; }}
            QLabel#proj_label         {{ color: {text2}; font-size: {max(ts - 1, 7)}pt; }}

            /* ── Graph header ── */
            QLabel#graph_title_label {{
                font-size: {ts}pt;
                font-weight: bold;
                color: {accent};
                padding: 2px 0px;
            }}
            QWidget#sensor_picker {{
                background-color: {bg2};
                border: 1px solid {border2};
                border-radius: 8px;
            }}

            /* ── Warning panel ── */
            QWidget#warning_panel {{
                background-color: #cc7700;
                border: 1px solid #995500;
                border-radius: 6px;
            }}
            QLabel#warning_title {{
                font-size: {ts}pt;
                font-weight: bold;
                color: {text};
            }}
            QLabel#warning_message {{
                font-size: {max(ts - 1, 7)}pt;
                color: {text};
                padding: 2px 20px;
            }}

            /* ── Collapsible section header ── */
            QWidget#collapsible_header {{ background-color: {bg3}; border-radius: 4px; }}
            QLabel#collapsible_title   {{ font-size: {ts}pt; font-weight: bold; color: {text2}; }}

            /* ── Cards (abort config, settings groups) ── */
            QFrame#config_card {{
                background-color: {bg2};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QFrame#config_card QWidget {{ background-color: transparent; }}
            QFrame#config_card QLineEdit, QFrame#config_card QDoubleSpinBox,
            QFrame#config_card QSpinBox, QFrame#config_card QComboBox {{
                background-color: {bg3};
            }}
            QFrame#config_card QComboBox QAbstractItemView {{ background-color: {bg2}; }}
            QFrame#config_card QWidget#collapsible_header {{ background-color: {bg3}; }}

            /* ── Project combo ── */
            QComboBox#project_combo {{ min-width: 150px; }}

            /* ── Sensor panel ── */
            QWidget#sensor_panel {{
                border-left: 1px solid {border};
            }}

            /* ── Item views (lists, trees, tables) ── */
            QListWidget, QTreeWidget {{
                background-color: {bg2};
                border: 1px solid {border};
                border-radius: 5px;
                outline: none;
            }}
            QTableWidget, QTableView, QTreeWidget#browser_tree {{
                font-family: {mono};
            }}
            QListWidget::item, QTreeWidget::item {{
                padding: 2px 4px;
            }}
            QListWidget::item:hover, QTreeWidget::item:hover {{
                background-color: {bg3};
            }}
            QListWidget::item:selected, QTreeWidget::item:selected {{
                background-color: {accent};
                color: {sel_text};
            }}
            QHeaderView::section {{
                background-color: {bg3};
                color: {text};
                border: none;
                border-right: 1px solid {border};
                border-bottom: 1px solid {border};
                padding: 3px 6px;
                font-weight: bold;
            }}

            /* ── Telemetry page ── */
            QWidget#telemetry_toolbar, QWidget#file_panel_toolbar, QWidget#browser_header {{
                background-color: {bg2};
            }}
            QLabel#browser_title, QLabel#panel_label {{
                font-weight: bold;
                color: {accent};
                letter-spacing: 1px;
            }}
            QLabel#file_path_label {{ color: {text}; }}
            QLabel#stats_label     {{ color: {text2}; font-size: {max(ts - 1, 7)}pt; }}
            QLineEdit#browser_search {{
                border-radius: 0px;
                border-left: none; border-right: none;
            }}
            QTreeWidget#browser_tree {{
                border: none;
                border-radius: 0px;
            }}

            /* ── Dialogs ── */
            QDialog {{ background-color: {bg}; }}

            /* ── Splitters ── */
            QSplitter::handle {{ background-color: {border}; }}
            QSplitter::handle:hover {{ background-color: {accent}; }}

            /* ── Scroll bars ── */
            QScrollBar:vertical {{
                width: 8px;
                background: transparent;
                margin: 0px;
            }}
            QScrollBar:horizontal {{
                height: 8px;
                background: transparent;
                margin: 0px;
            }}
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
                background: {border};
                border-radius: 4px;
                min-height: 24px;
                min-width: 24px;
            }}
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {{
                background: {border2};
            }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
            QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
        """)

        self.home_page.sensor_grid.set_dark_mode(self.dark_mode)