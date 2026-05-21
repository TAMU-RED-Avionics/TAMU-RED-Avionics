from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy,
    QStackedWidget, QComboBox, QScrollArea,
    QGridLayout, QSplitter, QToolButton, QMessageBox,
    QLineEdit, QDialog, QDialogButtonBox,
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
from PROJECT_LOADER import discover_projects, load_project, project_summary
from GUI_ABORT_CONFIG import AbortConfigPage, AbortWindow
from GUI_TELEMETRY import TelemetryPage

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

class PTSensorRow(QWidget):
    clicked = pyqtSignal(str)
    
    def __init__(self, name: str, controller: GUIController, parent=None):
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

        self.unit_lbl = QLabel("psi")
        self.unit_lbl.setFixedWidth(40)
        self.unit_lbl.setObjectName("sensor_unit_label")

        self.tare_btn = QPushButton("tare")
        self.tare_btn.setObjectName("tare_btn")
        self.tare_btn.setFixedSize(70, 30)
        self.tare_btn.clicked.connect(self._confirm_tare)

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

    def _confirm_tare(self):
        reply = QMessageBox.question(
            self, "Tare Sensor",
            f"Zero out {self.name}?\n\nThis will offset all future readings by the current value.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            # Hook: controller.tare_sensor(self.name) will go here once implemented
            pass


class SensorPanel(QWidget):
    PT_NAMES = [f"P{i}" for i in range(1, 9)]
    TC_NAMES = [f"TC{i}" for i in range(1, 4)]
    LC_NAMES = [f"LC{i}" for i in range(1, 4)]
    
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

        self.pt_rows: dict[str, PTSensorRow] = {}
        for name in self.PT_NAMES:
            row = PTSensorRow(name, controller)
            row.clicked.connect(self._on_sensor_row_clicked)
            self.pt_rows[name] = row
            inner_layout.addWidget(row)

        inner_layout.addSpacing(6)

        self.tc_section = CollapsibleSection("Thermocouples")
        self.tc_labels: dict[str, QLabel] = {}
        self.tc_row_widgets: dict[str, QWidget] = {}
        for name in self.TC_NAMES:
            row_widget = QWidget()
            row_widget.setCursor(Qt.PointingHandCursor)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            name_lbl = QLabel(f"{name}:")
            name_lbl.setFixedWidth(36)
            val_lbl = QLabel("---")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            unit_lbl = QLabel("°C")
            unit_lbl.setFixedWidth(24)
            row_layout.addWidget(name_lbl)
            row_layout.addWidget(val_lbl, stretch=1)
            row_layout.addWidget(unit_lbl)
            self.tc_labels[name] = val_lbl
            self.tc_row_widgets[name] = row_widget

            row_widget.mousePressEvent = lambda event, n=name: self._on_sensor_row_clicked(n)
            self.tc_section.add_widget(row_widget)

        self.tc_section._toggle()
        inner_layout.addWidget(self.tc_section)

        self.lc_section = CollapsibleSection("Load Cells")
        self.lc_labels: dict[str, QLabel] = {}
        self.lc_row_widgets: dict[str, QWidget] = {}
        for name in self.LC_NAMES:
            row_widget = QWidget()
            row_widget.setCursor(Qt.PointingHandCursor)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)
            name_lbl = QLabel(f"{name}:")
            name_lbl.setFixedWidth(36)
            val_lbl = QLabel("---")
            val_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            unit_lbl = QLabel("lbf")
            unit_lbl.setFixedWidth(28)

            tare_btn = QPushButton("tare")
            tare_btn.setObjectName("tare_btn")
            tare_btn.setFixedSize(40, 22)
            tare_btn.clicked.connect(lambda _, n=name: self._confirm_lc_tare(n))

            row_layout.addWidget(name_lbl)
            row_layout.addWidget(val_lbl, stretch=1)
            row_layout.addWidget(unit_lbl)
            row_layout.addWidget(tare_btn)
            self.lc_labels[name] = val_lbl
            self.lc_row_widgets[name] = row_widget

            row_widget.mousePressEvent = lambda event, n=name: self._on_sensor_row_clicked(n)
            self.lc_section.add_widget(row_widget)


        total_row = QWidget()
        total_layout = QHBoxLayout(total_row)
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
        self.lc_section.add_widget(total_row)

        self.lc_section._toggle()
        inner_layout.addWidget(self.lc_section)

        inner_layout.addStretch()
        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
    
    def _on_sensor_row_clicked(self, sensor_name: str):
        """Handle click on any sensor row - update selection and emit signal."""
        self._selected_sensor = sensor_name

        for name, row in self.pt_rows.items():
            row.set_selected(name == sensor_name)
        
        for name, widget in self.tc_row_widgets.items():
            if name == sensor_name:
                widget.setStyleSheet("background-color: rgba(128, 128, 128, 0.2); border-radius: 4px;")
            else:
                widget.setStyleSheet("")
        
        for name, widget in self.lc_row_widgets.items():
            if name == sensor_name:
                widget.setStyleSheet("background-color: rgba(128, 128, 128, 0.2); border-radius: 4px;")
            else:
                widget.setStyleSheet("")

        self.sensor_selected.emit(sensor_name)

    def _on_sensor_updated(self, name: str, value: float, timestamp: float):
        if name in self.pt_rows:
            status = self.controller.get_sensor_status(name, value)
            self.pt_rows[name].set_value(value, status)

        elif name in self.tc_labels:
            self.tc_labels[name].setText(f"{value:.1f}")

        elif name in self.lc_labels:
            self.lc_labels[name].setText(f"{value:.2f}")

            total = sum(
                self.controller.current_sensor_values.get(n, 0.0)
                for n in self.LC_NAMES
            )
            self.lc_total_lbl.setText(f"{total:.2f}")

    def _confirm_lc_tare(self, name: str):
        reply = QMessageBox.question(
            self, "Tare Load Cell",
            f"Zero out {name}?\n\nThis will offset all future readings by the current value.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            # Hook: controller.tare_sensor(name) once implemented
            pass


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
        
        self.setVisible(True)
    
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


class _StubPage(QWidget):

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size: 18pt; color: #888888;")
        layout.addWidget(lbl)


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
 

class LivePIDPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
 
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
 
        self.view = PIDViewWindow(controller=controller)
        layout.addWidget(self.view)
 
    def load_project(self, project):
        self.view.load_project(project)


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

    def _on_graph_sensor_changed(self, sensor_name: str):
        self.sensor_grid.update_main_graph(sensor_name)

    def show_warnings(self, messages: list):
        self.warning_panel.set_warnings(messages)

    def clear_warnings(self):
        self.warning_panel.clear_warnings()

    def set_dark_mode(self, dark: bool):
        # The live PID canvas uses its own dark background — nothing to switch
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
        abort_menu.setMinimumWidth(180)
        layout.addWidget(abort_menu)

        divider1 = QFrame()
        divider1.setFrameShape(QFrame.VLine)
        layout.addWidget(divider1)

        self.fire_seq_btn = QPushButton("Auto-Fire Sequence")
        self.fire_seq_btn.setObjectName("action_bar_btn")
        self.fire_seq_btn.setEnabled(False)
        self.fire_seq_btn.clicked.connect(controller.show_fire_sequence_dialog)
        layout.addWidget(self.fire_seq_btn)

        self.tare_all_btn = QPushButton("Sensor Tare")
        self.tare_all_btn.setObjectName("action_bar_btn")
        self.tare_all_btn.clicked.connect(self._show_tare_dialog)
        layout.addWidget(self.tare_all_btn)

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

        layout.addStretch()

        self.state_label = QLabel("State: —")
        self.state_label.setObjectName("state_label")
        layout.addWidget(self.state_label)
        controller.signals.system_status.connect(lambda s: self.state_label.setText(f"State: {s}"))

        divider3 = QFrame()
        divider3.setFrameShape(QFrame.VLine)
        layout.addWidget(divider3)

        conn_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        layout.addWidget(conn_widget)

        controller.signals.connected.connect(lambda: self.fire_seq_btn.setEnabled(True))
        controller.signals.disconnected.connect(lambda _: self.fire_seq_btn.setEnabled(False))
        controller.signals.abort_triggered.connect(lambda *_: self.fire_seq_btn.setEnabled(False))

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

    def _show_tare_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Sensor Tare")
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("Select sensor category to tare:"))

        pt_btn = QPushButton("Tare all PT sensors")
        tc_btn = QPushButton("Tare all Thermocouples")
        lc_btn = QPushButton("Tare all Load Cells")

        def _tare(category):
            reply = QMessageBox.question(
                dlg, "Confirm Tare",
                f"Zero out all {category} sensors?",
                QMessageBox.Yes | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if reply == QMessageBox.Yes:
                # Hook: self.controller.tare_category(category) once implemented
                dlg.accept()

        pt_btn.clicked.connect(lambda: _tare("PT"))
        tc_btn.clicked.connect(lambda: _tare("TC"))
        lc_btn.clicked.connect(lambda: _tare("LC"))

        layout.addWidget(pt_btn)
        layout.addWidget(tc_btn)
        layout.addWidget(lc_btn)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        dlg.exec_()

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
        self.text_size = 11

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

        pages = [
            ("Home",          self.home_page),
            ("Abort Config",  self.abort_config_page),
            ("Sequencing",    self.sequencing_page),
            ("New/Edit PID",  self.new_pid_page),
            ("Telemetry",     self.telemetry_page),
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
        self.project_combo.addItem("— select project —")

        for display_name, path in discover_projects():
            self.project_combo.addItem(display_name)
            self._project_paths.append(path)

        self.controller.signals.abort_triggered.connect(
            lambda *_: self.project_combo.setEnabled(False)
        )
        self.controller.signals.safe_state.connect(
            lambda: self.project_combo.setEnabled(True)
        )

        self.project_combo.currentIndexChanged.connect(self._on_project_selected)
        chrome_layout.addWidget(self.project_combo)

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

    def _dispatch_project(self, project):
        # MUST come first — populates pt_keys / tc_keys / lc_keys and reloads abort rules
        self.controller.load_project(project, self.controller.project_path)

        if hasattr(self, "home_page"):
            self.home_page.load_project(project)

        if hasattr(self, "sequencing_page"):
            self.sequencing_page.load_project(project)

        if hasattr(self, "live_pid_page"):
            self.live_pid_page.load_project(project)

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
        self.telemetry_page.panel_a.graph.set_dark_mode(self.dark_mode)
        self.telemetry_page.panel_b.graph.set_dark_mode(self.dark_mode)

    def change_text_size(self):
        cycle = {12: (16, "Small Text"), 16: (8, "Medium Text"), 8: (12, "Large Text")}
        self.text_size, label = cycle.get(self.text_size, (12, "Large Text"))
        self.text_size_btn.setText(label)
        self.apply_stylesheet()

    def apply_stylesheet(self):
        ts = self.text_size
        if self.dark_mode:
            bg       = "#1e1e24"
            bg2      = "#28282f"
            bg3      = "#333340"
            border   = "#44444f"
            text     = "#e8e6e0"
            text2    = "#9b9990"
            accent   = "#8b1a1a"
            tab_act  = "#8b1a1a"
        else:
            bg       = "#f4f2ee"
            bg2      = "#ffffff"
            bg3      = "#ebebeb"
            border   = "#cccccc"
            text     = "#1a1a1a"
            text2    = "#666666"
            accent   = "#7a0000"
            tab_act  = "#7a0000"

        self.setStyleSheet(f"""
            /* ── Root & chrome ── */
            QMainWindow, QWidget {{
                background-color: {bg};
                color: {text};
                font-family: "Courier New", monospace;
                font-size: {ts}pt;
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
                font-family: "Courier New", monospace;
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
                padding: 4px 14px;
                font-size: {ts}pt;
                font-family: "Courier New", monospace;
                font-weight: bold;
            }}
            QPushButton#action_bar_btn:hover  {{ background-color: {bg};  }}
            QPushButton#action_bar_btn:pressed {{ background-color: {border}; }}
            QPushButton#action_bar_btn:disabled {{ color: {text2}; background-color: {bg3}; }}

            /* ── Abort / Safe State (inherited AbortWindow styles take priority for
                   the manual_abort_btn and safe_state_btn by object name) ── */

            /* ── General buttons ── */
            QPushButton {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: {ts}pt;
                font-family: "Courier New", monospace;
                font-weight: bold;
            }}
            QPushButton:hover   {{ background-color: {bg}; }}
            QPushButton:pressed {{ background-color: {border}; }}
            QPushButton:disabled {{ color: {text2}; }}

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

            /* ── Line edits ── */
            QLineEdit {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 6px;
                padding: 2px 8px;
                font-size: {ts}pt;
            }}

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
            QLabel#sensor_name_label  {{ color: {text2}; font-size: {ts}pt; }}
            QLabel#sensor_value_label {{ font-size: {ts + 1}pt; font-weight: bold; }}
            QLabel#sensor_unit_label  {{ color: {text2}; font-size: {max(ts - 1, 7)}pt; }}
            QLabel#state_label        {{ color: {accent}; font-weight: bold; }}
            QLabel#proj_label         {{ color: {text2}; font-size: {max(ts - 1, 7)}pt; }}
            
            /* ── Graph title ── */
            QLabel#graph_title_label {{
                font-size: {ts + 1}pt;
                font-weight: bold;
                color: {accent};
                border-bottom: 1px solid {border};
                padding: 2px 0px;
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

            /* ── Project combo ── */
            QComboBox#project_combo {{
                background-color: {bg3};
                color: {text};
                border: 1px solid {border};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: {ts}pt;
            }}
            QComboBox#project_combo QAbstractItemView {{
                background-color: {bg2};
                color: {text};
                selection-background-color: {accent};
            }}

            /* ── Sensor panel ── */
            QWidget#sensor_panel {{
                border-left: 1px solid {border};
            }}

            /* ── Scroll bars ── */
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 3px;
            }}
        """)

        self.home_page.sensor_grid.set_dark_mode(self.dark_mode)