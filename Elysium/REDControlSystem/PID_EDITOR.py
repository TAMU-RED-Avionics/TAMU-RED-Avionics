import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox,
    QSplitter, QMessageBox, QFrame, QSizePolicy, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox,
    QToolButton, QScrollArea,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QFontMetrics

from PID_SCHEMA import (
    PIDProject, Component, PipeLine, LayoutPoint, Connection, HardwareBinding,
    COMPONENT_TYPES, FLUID_COLORS, FLUID_GENERIC,
    COMP_VALVE, COMP_THROTTLE_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_TANK, COMP_INJECTOR, COMP_ORIFICE, COMP_FILTER,
    COMP_REGULATOR, COMP_CHECK_VALVE, COMP_RELIEF_VALVE, COMP_LABEL, COMP_JUNCTION,
    FLUID_OXIDIZER, FLUID_FUEL, FLUID_PRESSURANT, FLUID_PURGE, COMP_BALL_VALVE, COMP_PSV,
    COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_REDUCER, COMP_PRV
)

from PID_CANVAS import PIDCanvas, snap

PALETTE_GROUPS = [
    ("Valves", [
        ("Valve",            COMP_VALVE),
        ("Ball Valve",       COMP_BALL_VALVE),
        ("Solenoid",         COMP_SOLENOID),
        ("Globe Valve",      COMP_GLOBE_VALVE),
        ("Check Valve",      COMP_CHECK_VALVE),
    ]),
    ("Pressure Control", [
        ("PSV",              COMP_PSV),
        ("PRV",              COMP_PRV),
        ("Regulator",        COMP_REGULATOR),
    ]),
    ("Sensors", [
        ("PT",               COMP_PRESSURE),
        ("Thermocouple",     COMP_TEMPERATURE),
        ("Load Cell",        COMP_LOAD_CELL),
    ]),
    ("Plumbing / Misc", [
        ("Reducer",          COMP_REDUCER),
        ("Tank",             COMP_TANK),
        ("Injector",         COMP_INJECTOR),
        ("Junction",         COMP_JUNCTION),
        ("Label",            COMP_LABEL),
    ]),
]


class _PaletteGroup(QWidget):
    def __init__(self, title: str, items: list[tuple[str, str]], on_pick, parent=None):
        super().__init__(parent)
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

        self.title_lbl = QLabel(title)
        self.title_lbl.setObjectName("collapsible_title")

        header_layout.addWidget(self.toggle_btn)
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(6, 4, 6, 6)
        self.content_layout.setSpacing(4)

        self._expanded = True
        self.toggle_btn.clicked.connect(self._toggle)
        header.mousePressEvent = lambda event: self._toggle()

        for label, comp_type in items:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda checked, ct=comp_type: on_pick(ct))
            self.content_layout.addWidget(btn)

        outer.addWidget(header)
        outer.addWidget(self.content)

    def _toggle(self):
        self._expanded = not self._expanded
        self.content.setVisible(self._expanded)
        self.toggle_btn.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)


class PalettePanel(QWidget):
    component_type_selected = pyqtSignal(str)
    line_draw_requested     = pyqtSignal(str) 

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(120)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("COMPONENTS")
        title.setObjectName("panel_section_title")
        layout.addWidget(title)

        for group_title, items in PALETTE_GROUPS:
            layout.addWidget(_PaletteGroup(group_title, items, self.component_type_selected.emit))

        layout.addSpacing(2)
        pipe_title = QLabel("PIPES")
        pipe_title.setObjectName("panel_section_title")
        layout.addWidget(pipe_title)

        for fluid_label, fluid in [
            ("Oxidizer",    FLUID_OXIDIZER),
            ("Fuel",        FLUID_FUEL),
            ("Pressurant",  FLUID_PRESSURANT),
            ("Purge",       FLUID_PURGE),
            ("Generic",     FLUID_GENERIC),
        ]:
            color = FLUID_COLORS[fluid]
            btn = QPushButton(f"● {fluid_label}")
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"color: {color}; text-align: left; padding-left: 6px;")
            btn.clicked.connect(lambda checked, f=fluid: self.line_draw_requested.emit(f))
            layout.addWidget(btn)

        layout.addStretch()
        hint = QLabel("Click pipe colour → click points.\n"
                      "Dbl-click or ↵ to finish.\n"
                      "Middle-click = undo\nlast vertex.\n"
                      "Esc = cancel.\n")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(hint)

        scroll.setWidget(content)
        outer.addWidget(scroll)

class PropertyPanel(QWidget):
    property_changed = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(140)
        self._comp_id = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        title = QLabel("PROPERTIES")
        title.setObjectName("panel_section_title")
        layout.addWidget(title)

        self.form = QFormLayout()
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(5)
        layout.addLayout(self.form)

        self.comp_specific_widgets = {}
        self._line_id = None

        layout.addStretch()
        self._fields = {}
        self.hide_lbl_cb = None

    def _add_scale_field(self, label: str, key: str, value):
        le = QLineEdit(str(value))
        le.setPlaceholderText("1.0")
        le.editingFinished.connect(lambda k=key, w=le: self.property_changed.emit(k, w.text()))
        self.form.addRow(label + ":", le)
        self._fields[key] = le

    def show_component(self, comp_id: str, comp: Component):
        self._comp_id = comp_id
        self._clear()
        self._add("ID", comp.id, readonly=True)
        self._add("Label", comp.label, key="label")
        self._add("Type", comp.type, readonly=True)

        self._add_scale_field("Width Scale", "extra_scale_x", comp.extras.get("scale_x", 1.0))
        self._add_scale_field("Height Scale", "extra_scale_y", comp.extras.get("scale_y", 1.0))

        self._add_component_specific_fields(comp)

        if comp.type == COMP_PRESSURE:
            self._add("Linked Line ID", comp.extras.get("line_id", ""), key="extra_line_id")
            self._add("Color Max (psi)", comp.extras.get("line_pressure_max", "50"), key="extra_line_pressure_max")

        self._add("Relay", str(comp.hardware.relay) if comp.hardware.relay is not None else "", key="relay")
        self._add("ADC ch", str(comp.hardware.adc) if comp.hardware.adc is not None else "", key="adc")

        if comp.type in [COMP_BALL_VALVE, COMP_GLOBE_VALVE, COMP_SOLENOID]:
            self._add("Normally", comp.extras.get("normally", "closed"), key="extra_normally")
            self._add("Actuation", comp.extras.get("actuation", "manual"), key="extra_actuation")

        if comp.type in [COMP_PSV, COMP_PRV]:
            self._add("Set Pressure (psi)", comp.extras.get("set_pressure", ""), key="extra_set_pressure")
            self._add("Size", comp.extras.get("size", ""), key="extra_size")

        if comp.type == COMP_REDUCER:
            self._add("Inlet Size", comp.extras.get("inlet_size", ""), key="extra_inlet_size")
            self._add("Outlet Size", comp.extras.get("outlet_size", ""), key="extra_outlet_size")
            self._add("Reduction Ratio", comp.extras.get("reduction_ratio", ""), key="extra_reduction_ratio")

        ignored_keys = {
            "scale_x", "scale_y",
            "normally", "actuation", "set_pressure", "size",
            "inlet_size", "outlet_size", "reduction_ratio",
        }
        for k, v in comp.extras.items():
            if k not in ignored_keys:
                self._add(k, v, key=f"extra_{k}")

        self.hide_lbl_cb = QCheckBox("Hide Label")
        self.hide_lbl_cb.setChecked(getattr(comp, "hide_lbl", False))
        self.hide_lbl_cb.toggled.connect(lambda checked: self.property_changed.emit("hide_lbl", checked))
        self.form.addRow(self.hide_lbl_cb)

    def _add_component_specific_fields(self, comp):
        if comp.type == COMP_BALL_VALVE:
            self._add_section_header("Ball Valve Properties")
        elif comp.type == COMP_GLOBE_VALVE:
            self._add_section_header("Globe Valve Properties")
        elif comp.type == COMP_SOLENOID:
            self._add_section_header("Solenoid Properties")
        elif comp.type == COMP_PSV:
            self._add_section_header("Pressure Safety Valve Properties")
        elif comp.type == COMP_PRV:
            self._add_section_header("Pressure Relief Valve Properties")
        elif comp.type == COMP_REDUCER:
            self._add_section_header("Reducer Properties")

    def _add_section_header(self, text):
        header = QLabel(text)
        header.setStyleSheet("font-weight: bold; margin-top: 5px; color: #555;")
        header.setAlignment(Qt.AlignLeft)
        self.form.addRow(header)

    def clear(self):
        self._comp_id = None
        self._line_id = None
        self._clear()

    def show_line(self, line_id: str, line):
        """Populate the panel with properties for a selected pipe/line."""
        self._comp_id = None
        self._line_id = line_id
        self._clear()

        hdr = QLabel("PIPE PROPERTIES")
        hdr.setObjectName("panel_section_title")
        self.form.addRow(hdr)

        id_le = QLineEdit(line_id)
        id_le.setReadOnly(True)
        self.form.addRow("ID:", id_le)

        fluid_le = QLineEdit(line.fluid)
        fluid_le.setReadOnly(True)
        self.form.addRow("Fluid:", fluid_le)

        pts_le = QLineEdit(str(len(line.points)))
        pts_le.setReadOnly(True)
        self.form.addRow("Points:", pts_le)

        self._dotted_cb = QCheckBox()
        self._dotted_cb.setChecked(getattr(line, 'dotted', False))
        self._dotted_cb.stateChanged.connect(
            lambda state, lid=line_id: self.property_changed.emit("line_dotted", (lid, bool(state)))
        )
        self.form.addRow("Dotted:", self._dotted_cb)

    def _clear(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self._fields.clear()
        self.comp_specific_widgets.clear()
        self.hide_lbl_cb = None

    def _add(self, label, value, key=None, readonly=False):
        le = QLineEdit(str(value) if value is not None else "")
        le.setReadOnly(readonly)
        le.setPlaceholderText("—")
        if key:
            le.editingFinished.connect(lambda k=key, w=le: self.property_changed.emit(k, w.text()))
        self.form.addRow(label + ":", le)
        self._fields[key or label] = le

    def _on_changed(self, key, value):
        self.property_changed.emit(key, value)

class PIDEditorWindow(QWidget):
    project_saved = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project: PIDProject = None
        self._current_path: str   = None
        self._pending_comp_type: str  = None
        self._pending_line_fluid: str = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        toolbar = QWidget()
        toolbar.setObjectName("action_bar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(1)

        def tbtn(text, slot):
            b = QPushButton(text); b.setObjectName("action_bar_btn")
            b.clicked.connect(slot); tb.addWidget(b); return b

        tbtn("New",          self._new_project)
        tbtn("Open…",        self._open_project)
        tbtn("Save",         self._save_project)
        tbtn("Save As…",     self._save_as_project)
        tb.addWidget(_vsep())
        tbtn("Fit [F]",      lambda: self.canvas.fit_view())
        tbtn("Delete [Del]", self._delete_selected)
        tbtn("Rotate [R]", self._rotate_selected)
        tb.addWidget(_vsep())

        self._mode_label = QLabel("MODE: select")
        self._mode_label.setStyleSheet("color: #ffd600; font-weight: bold;")
        tb.addWidget(self._mode_label)

        tb.addSpacing(4)

        self._proj_name_edit = QLineEdit("Untitled Project")
        self._proj_name_edit.setFixedWidth(120)
        self._proj_name_edit.textChanged.connect(
            lambda t: self._project and setattr(self._project, "name", t))
        tb.addWidget(self._proj_name_edit)

        root.addWidget(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self.palette = PalettePanel()
        self.palette.component_type_selected.connect(self._on_palette_comp)
        self.palette.line_draw_requested.connect(self._on_palette_line)
        splitter.addWidget(self.palette)

        self.canvas = PIDCanvas(interactive=True)
        self.canvas.component_clicked.connect(self._on_comp_clicked)
        self.canvas.component_moved.connect(lambda cid, x, y: self._status.setText(f"Moved {cid} → ({x:.0f}, {y:.0f})"))
        self.canvas.canvas_clicked.connect(self._on_canvas_clicked)
        self.canvas.line_clicked.connect(self._on_line_clicked)
        self.canvas.line_finished.connect(self._on_line_finished)
        splitter.addWidget(self.canvas)

        self.prop_panel = PropertyPanel()
        self.prop_panel.property_changed.connect(self._on_prop_changed)
        splitter.addWidget(self.prop_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([120, 1080, 140])
        splitter.setHandleWidth(4)
        root.addWidget(splitter)

        self._status = QLabel("Ready.  Open or create a project.")
        self._status.setFixedHeight(14)
        self._status.setStyleSheet("padding: 0px 2px; color: #777; font-size: 8pt;")
        root.addWidget(self._status)

        self._new_project()

    def _new_project(self):
        self._project      = PIDProject.new_empty("New Project")
        self._current_path = None
        self._proj_name_edit.setText(self._project.name)
        self.canvas.set_project(self._project)
        self._status.setText("New project created.")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open P&ID Project", "PIDs",
            "P&ID Project (*.red);;JSON Files (*.json);;All Files (*)")
        if not path:
            return
        try:
            self._project      = PIDProject.load(path)
            self._current_path = path
            self._proj_name_edit.setText(self._project.name)
            self.canvas.set_project(self._project)
            self._status.setText(f"Opened: {os.path.basename(path)}")
        except Exception as e:
            QMessageBox.critical(self, "Open Failed", str(e))

    def _save_project(self):
        if not self._current_path:
            self._save_as_project()
        else:
            self._do_save(self._current_path)

    def _save_as_project(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save P&ID Project", "PIDs",
            "P&ID Project (*.red);;JSON Files (*.json)")
        if not path:
            return
        if not path.endswith(".red"):
            path += ".red"
        self._do_save(path)

    def _do_save(self, path):
        if not self._project:
            return
        self._project.name = self._proj_name_edit.text().strip() or "Untitled"
        try:
            self._project.save(path)
            self._current_path = path
            self._status.setText(f"Saved: {os.path.basename(path)}")
            self.project_saved.emit(path)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

    def load_project_path(self, path: str):
        try:
            self._project      = PIDProject.load(path)
            self._current_path = path
            self._proj_name_edit.setText(self._project.name)
            self.canvas.set_project(self._project)
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))

    def _delete_selected(self):
        if not self._project:
            return
        for cid in list(self.canvas._selected_comps):
            self._project.remove_component(cid)
        self.canvas._selected_comps.clear()
        self.canvas.update()

    def _rotate_selected(self):
        selected_ids = self.canvas._selected_comps
        if not selected_ids:
            return
        for cid in selected_ids:
            comp = self._project.components.get(cid)
            if comp:
                current_rot = getattr(comp, 'rotation', 0)
                comp.rotation = (current_rot + 90) % 360

        self.canvas.update()

    def _on_palette_comp(self, comp_type: str):
        self._pending_comp_type  = comp_type
        self._pending_line_fluid = None
        self.canvas.cancel_line_draw()
        self._mode_label.setText(f"MODE: place {comp_type}")
        self.canvas.setCursor(Qt.CrossCursor)

    def _on_palette_line(self, fluid: str):
        self._pending_comp_type  = None
        self._pending_line_fluid = fluid
        self.canvas.start_line_draw(fluid)
        self._mode_label.setText(f"MODE: draw pipe ({fluid})")

    def _on_canvas_clicked(self, wx: float, wy: float):
        if not self._project:
            return
        if self._pending_comp_type:
            sx, sy = snap(wx, wy)
            ctype  = self._pending_comp_type
            count  = sum(1 for c in self._project.components.values() if c.type == ctype)

            type_to_prefix = {
                COMP_BALL_VALVE: "BV",
                COMP_SOLENOID: "SV",
                COMP_GLOBE_VALVE: "GV",
                COMP_CHECK_VALVE: "CV",
                COMP_THROTTLE_VALVE: "TV",
                COMP_PSV: "PSV",
                COMP_PRV: "PRV",
                COMP_REGULATOR: "REG",
                COMP_PRESSURE: "PT",
                COMP_TEMPERATURE: "TC",
                COMP_REDUCER: "RED",
                COMP_TANK: "TK",
            }
            
            prefix = type_to_prefix.get(ctype, ctype[:3].upper())
            cid = f"{prefix}_{count + 1}"
            
            comp   = Component(id=cid, type=ctype, label=cid)
            self._project.add_component(comp, sx, sy)
            self.canvas.update()
            self._status.setText(f"Placed '{cid}' at ({sx:.0f}, {sy:.0f})")
            self._pending_comp_type = None 
            self._mode_label.setText("MODE: select")

    def _on_comp_clicked(self, cid: str):
        if not self._project:
            return
        comp = self._project.components.get(cid)
        if comp:
            self.prop_panel.show_component(cid, comp)
            self._status.setText(f"Selected: {cid}  ({comp.type})")
    
    def _on_line_clicked(self, lid: str):
        if self._project:
            line = next((l for l in self._project.lines if l.id == lid), None)
            if line:
                self._status.setText(f"Selected pipe: {lid} (fluid: {line.fluid}, dotted: {getattr(line, 'dotted', False)})")
                self.prop_panel.show_line(lid, line)

    def _on_line_finished(self, line: PipeLine):
        if self._project:
            self._project.add_line(line)
            self.canvas.update()
            self._mode_label.setText("MODE: select")
            self._pending_line_fluid = None
            self._status.setText(
                f"Pipe '{line.id}' ({line.fluid}, {len(line.points)} pts) added.")

    def _on_prop_changed(self, key: str, value):
        if not self._project:
            return

        if key == "line_dotted":
            lid, dotted = value
            line = next((l for l in self._project.lines if l.id == lid), None)
            if line:
                line.dotted = dotted
                self._status.setText(f"Pipe '{lid}' dotted: {dotted}")
                self.canvas.update()
            return

        selected = list(self.canvas._selected_comps)
        if not selected:
            return
        cid = selected[0]
        comp = self._project.components.get(cid)
        if not comp:
            return

        if key == "label":
            comp.label = value
        elif key == "relay":
            try:
                comp.hardware.relay = int(value, 0)  # 0x hex, decimal, 0o octal
            except (ValueError, TypeError):
                comp.hardware.relay = None
        elif key == "adc":
            try:
                comp.hardware.adc = int(value, 0)    # 0x hex, decimal, 0o octal
            except (ValueError, TypeError):
                comp.hardware.adc = None
        elif key.startswith("extra_"):
            comp.extras[key[6:]] = value
        elif key in ["set_pressure", "size", "inlet_size", "outlet_size",
                     "reduction_ratio", "normally", "actuation"]:
            comp.extras[key] = value
        elif key in ["extra_scale_x", "extra_scale_y"]:
            try:
                comp.extras[key[6:]] = max(0.2, float(value))
            except (ValueError, TypeError):
                comp.extras[key[6:]] = 1.0
        elif key == "hide_lbl":
            comp.hide_lbl = value

        self.canvas.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._pending_comp_type  = None
            self._pending_line_fluid = None
            self.canvas.cancel_line_draw()
            self._mode_label.setText("MODE: select")
            self.canvas.setCursor(Qt.ArrowCursor)
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self.canvas._drawing_line:
                self.canvas.finish_line_draw()
        elif event.key() == Qt.Key_R:
            selected_ids = self.canvas._selected_comps
            if selected_ids:
                for cid in selected_ids:
                    comp = self._project.components.get(cid)
                    if comp:
                        comp.rotation = (comp.rotation + 90) % 360
                self.canvas.update()
        else:
            super().keyPressEvent(event)


def _vsep():
    f = QFrame(); f.setFrameShape(QFrame.VLine); f.setFrameShadow(QFrame.Sunken)
    return f