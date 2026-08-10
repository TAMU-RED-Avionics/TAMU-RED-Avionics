from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox,
    QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QDoubleSpinBox, QComboBox, QToolButton,
)
from PyQt5.QtCore import Qt

from GUI_CONTROLLER import GUIController
from PID_SCHEMA import (
    AbortRule,
    COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL,
    COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_THROTTLE_VALVE,
)


def _hsep():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def _card() -> tuple:
    f = QFrame()
    f.setObjectName("config_card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)
    return f, lay


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("panel_section_title")
    return lbl


_SENSOR_TYPES = (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL)
_VALVE_TYPES  = (COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_THROTTLE_VALVE)

_TYPE_UNIT = {
    COMP_PRESSURE:    "psi",
    COMP_TEMPERATURE: "°C",
    COMP_LOAD_CELL:   "lbf",
}

_ACTIONS = ["abort", "warn", "open_valve"]


class _CollapsibleBlock(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget()
        header.setObjectName("collapsible_header")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(6, 4, 6, 4)

        self._toggle_btn = QToolButton()
        self._toggle_btn.setArrowType(Qt.RightArrow)
        self._toggle_btn.setFixedSize(16, 16)
        self._toggle_btn.clicked.connect(self._toggle)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("collapsible_title")

        hl.addWidget(self._toggle_btn)
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(8, 4, 4, 4)
        self._content_layout.setSpacing(6)

        outer.addWidget(header)
        outer.addWidget(self._content)
        self._expanded = False
        self._content.setVisible(False)

    def _toggle(self):
        self._expanded = not self._expanded
        self._content.setVisible(self._expanded)
        self._toggle_btn.setArrowType(Qt.DownArrow if self._expanded else Qt.RightArrow)

    def add_widget(self, w: QWidget):
        self._content_layout.addWidget(w)

    def content_layout(self):
        return self._content_layout

class _OptionalSpinBox(QWidget):
    def __init__(self, suffix: str = "", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._cb = QCheckBox()
        self._sb = QDoubleSpinBox()
        self._sb.setRange(-99999, 99999)
        self._sb.setDecimals(2)
        self._sb.setSingleStep(10)
        self._sb.setSuffix(f" {suffix}" if suffix else "")
        self._sb.setMinimumWidth(100)

        lay.addWidget(self._cb)
        lay.addWidget(self._sb)

        self._cb.stateChanged.connect(lambda s: self._sb.setEnabled(s == Qt.Checked))
        self._sb.setEnabled(False)

    def value(self):
        return self._sb.value() if self._cb.isChecked() else None

    def set_value(self, v):
        if v is None:
            self._cb.setChecked(False)
            self._sb.setEnabled(False)
        else:
            self._cb.setChecked(True)
            self._sb.setEnabled(True)
            self._sb.setValue(float(v))


class _ActionCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.addItems(_ACTIONS)

    def current_action(self) -> str:
        return self.currentText()

    def set_action(self, action: str):
        idx = self.findText(action)
        self.setCurrentIndex(idx if idx >= 0 else 0)


class _SensorThresholdWidget(QWidget):
    def __init__(self, comp_id: str, comp_label: str, comp_type: str,
                 extras: dict, valve_options: list, parent=None):
        super().__init__(parent)
        self._extras = extras
        unit = _TYPE_UNIT.get(comp_type, "")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 8)
        outer.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        headers = ["Threshold", "Value", "Action", "Target Valve (open_valve)", "Close below"]
        for col, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setObjectName("sensor_unit_label")
            grid.addWidget(lbl, 0, col)

        rows = [
            ("mawp",   "High   (abort limit)",    "mawp_action"),
            ("meop",   "MEOP   (expected max)",    "meop_action"),
            ("relief", "Relief (auto-vent limit)", "relief_action"),
        ]

        th_data = extras.get("thresholds", {})

        self._fields = {}   # band_name -> {val, action, target, close_below}

        for row_idx, (band, label, action_key) in enumerate(rows, start=1):
            grid.addWidget(QLabel(label), row_idx, 0)

            val_widget = _OptionalSpinBox(unit)
            val_widget.set_value(th_data.get(band))
            grid.addWidget(val_widget, row_idx, 1)

            action_combo = _ActionCombo()

            action_combo.set_action(th_data.get(action_key, "abort" if band == "mawp" else "open_valve"))
            grid.addWidget(action_combo, row_idx, 2)

            target_combo = QComboBox()
            target_combo.addItem("- none -", "")
            for vid, vlabel in valve_options:
                target_combo.addItem(vlabel, vid)

            current_tv = th_data.get(f"{band}_target", th_data.get("target_valve", ""))
            idx = next((i for i in range(target_combo.count()) if target_combo.itemData(i) == current_tv), 0)
            target_combo.setCurrentIndex(idx)
            grid.addWidget(target_combo, row_idx, 3)

            close_widget = _OptionalSpinBox(unit)
            close_widget.set_value(th_data.get(f"{band}_close_below"))
            grid.addWidget(close_widget, row_idx, 4)

            msg_edit = QLineEdit(th_data.get(f"{band}_message", ""))
            msg_edit.setPlaceholderText(
                f"Default wording. Customize with {{{comp_label or comp_id}}} "
                "for its value, plus {value} {threshold} {soak_ms} {hw_id} - "
                'e.g. "{hw_id} over {threshold} for {soak_ms}ms"')

            self._fields[band] = {
                "val":         val_widget,
                "action":      action_combo,
                "target":      target_combo,
                "close_below": close_widget,
                "action_key":  action_key,
                "message":     msg_edit,
            }

        soak_row = QHBoxLayout()
        soak_row.addWidget(QLabel("Soak time (ms):"))
        self._soak_sb = QDoubleSpinBox()
        self._soak_sb.setRange(0, 60000)
        self._soak_sb.setDecimals(0)
        self._soak_sb.setValue(th_data.get("soak_ms", 0))
        soak_row.addWidget(self._soak_sb)
        soak_row.addStretch()

        outer.addLayout(grid)
        outer.addLayout(soak_row)

        msg_form = QGridLayout()
        msg_form.setSpacing(4)
        msg_form.setContentsMargins(0, 4, 0, 0)
        for row_idx, (band, label, _) in enumerate(rows):
            tag = QLabel(f"{label.split()[0]} message:")
            tag.setObjectName("sensor_unit_label")
            msg_form.addWidget(tag, row_idx, 0)
            msg_form.addWidget(self._fields[band]["message"], row_idx, 1)
        outer.addLayout(msg_form)

    def flush(self):
        d = {}
        for band, f in self._fields.items():
            d[band]               = f["val"].value()
            d[f"{band}_action"]   = f["action"].current_action()
            d[f"{band}_message"]  = f["message"].text().strip()
            target = f["target"].currentData()
            d[f"{band}_target"]   = target or ""
            close_val = f["close_below"].value()
            d[f"{band}_close_below"] = close_val
        d["soak_ms"] = int(self._soak_sb.value())
        self._extras["thresholds"] = d


class _SystemLimitsSection(QWidget):
    """System-wide pressure backstop, independent of the per-sensor
    thresholds below: applies across every PT at once."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        outer.addWidget(_section_title("SYSTEM PRESSURE LIMITS"))
        outer.addWidget(_hsep())

        desc = QLabel(
            "Optional system-wide backstop applied across all PT sensors, "
            "independent of the per-sensor thresholds above. A warning fires "
            "on any PT at or above System MEOP; an abort fires at 95% of "
            "System MAWP."
        )
        desc.setWordWrap(True)
        desc.setObjectName("sensor_unit_label")
        outer.addWidget(desc)

        row = QHBoxLayout()
        row.addWidget(QLabel("System MAWP:"))
        self._mawp = _OptionalSpinBox("psi")
        row.addWidget(self._mawp)
        row.addSpacing(24)
        row.addWidget(QLabel("System MEOP:"))
        self._meop = _OptionalSpinBox("psi")
        row.addWidget(self._meop)
        row.addStretch()
        outer.addLayout(row)

        msg_grid = QGridLayout()
        msg_grid.setSpacing(4)
        msg_grid.setContentsMargins(0, 4, 0, 0)
        msg_grid.addWidget(QLabel("MAWP message:"), 0, 0)
        self._mawp_msg = QLineEdit()
        self._mawp_msg.setPlaceholderText(
            'Blank = auto. Use {SENSOR} for its value, {mawp} {limit} for the '
            'configured limits - e.g. "{P1} over 95% of MAWP ({mawp} psi)"')
        msg_grid.addWidget(self._mawp_msg, 0, 1)
        msg_grid.addWidget(QLabel("MEOP message:"), 1, 0)
        self._meop_msg = QLineEdit()
        self._meop_msg.setPlaceholderText(
            'Blank = auto. Use {SENSOR} for its value, {limit} for the MEOP '
            'value - e.g. "{P1} above MEOP ({limit} psi)"')
        msg_grid.addWidget(self._meop_msg, 1, 1)
        outer.addLayout(msg_grid)

    def load_project(self, project):
        self._project = project
        if project is None:
            return
        params = project.parameters
        self._mawp.set_value(getattr(params, "system_mawp", None))
        self._meop.set_value(getattr(params, "system_meop", None))
        self._mawp_msg.setText(getattr(params, "system_mawp_message", ""))
        self._meop_msg.setText(getattr(params, "system_meop_message", ""))

    def flush(self):
        if not self._project:
            return
        self._project.parameters.system_mawp = self._mawp.value()
        self._project.parameters.system_meop = self._meop.value()
        self._project.parameters.system_mawp_message = self._mawp_msg.text().strip()
        self._project.parameters.system_meop_message = self._meop_msg.text().strip()


class _SensorThresholdsSection(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._widgets: dict = {}   # comp_id -> _SensorThresholdWidget

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        outer.addWidget(_section_title("SENSOR THRESHOLDS"))
        outer.addWidget(_hsep())

        desc = QLabel(
            "Configure per-sensor threshold bands. Each sensor has its own MAWP, MEOP, "
            "and Relief values. For open_valve actions, choose which "
            "valve to open and the hysteresis value at which it will be re-closed."
        )
        desc.setWordWrap(True)
        desc.setObjectName("sensor_unit_label")
        outer.addWidget(desc)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 4, 0, 0)
        self._container_layout.setSpacing(4)
        outer.addWidget(self._container)

    def _clear(self):
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._widgets.clear()

    def load_project(self, project):
        self._project = project
        self._clear()
        if project is None:
            return

        valve_options = [
            (cid, comp.label or cid)
            for cid, comp in project.components.items()
            if comp.type in _VALVE_TYPES
        ]

        sensor_comps = [
            (cid, comp)
            for cid, comp in project.components.items()
            if comp.type in _SENSOR_TYPES
        ]

        for cid, comp in sensor_comps:
            block = _CollapsibleBlock(comp.label or cid)
            w = _SensorThresholdWidget(cid, comp.label or cid, comp.type,
                                       comp.extras, valve_options)
            block.add_widget(w)
            self._container_layout.addWidget(block)
            self._widgets[cid] = w

        if not sensor_comps:
            self._container_layout.addWidget(
                QLabel("No pressure / temperature / load-cell sensors found in this project.")
            )

    def flush(self):
        for w in self._widgets.values():
            w.flush()

class _LogicRuleRow(QWidget):
    def __init__(self, rule: AbortRule, on_delete, parent=None):
        super().__init__(parent)
        self._rule = rule

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        top = QHBoxLayout()

        self._enabled_cb = QCheckBox()
        self._enabled_cb.setChecked(rule.enabled)
        self._enabled_cb.stateChanged.connect(lambda s: setattr(self._rule, "enabled", s == Qt.Checked))
        top.addWidget(self._enabled_cb)

        self._id_lbl = QLabel(f"<b>{rule.id}</b>")
        top.addWidget(self._id_lbl)

        top.addStretch()

        self._action_combo = _ActionCombo()
        self._action_combo.set_action(rule.action)
        self._action_combo.currentTextChanged.connect(lambda t: setattr(self._rule, "action", t))
        top.addWidget(QLabel("Action:"))
        top.addWidget(self._action_combo)

        del_btn = QPushButton("✕")
        del_btn.setFixedWidth(28)
        del_btn.clicked.connect(lambda: on_delete(self))
        top.addWidget(del_btn)

        outer.addLayout(top)

        desc_row = QHBoxLayout()
        desc_row.addWidget(QLabel("Description:"))
        self._desc_edit = QLineEdit(rule.description)
        self._desc_edit.setPlaceholderText("Human-readable label")
        self._desc_edit.textChanged.connect(lambda t: setattr(self._rule, "description", t))
        desc_row.addWidget(self._desc_edit)
        outer.addLayout(desc_row)

        expr_row = QHBoxLayout()
        expr_row.addWidget(QLabel("Expression:"))
        self._expr_edit = QLineEdit(rule.expression)
        self._expr_edit.setPlaceholderText('e.g.  P8 > P7   or   P5 - P3 >= 5')
        self._expr_edit.textChanged.connect(lambda t: setattr(self._rule, "expression", t))
        expr_row.addWidget(self._expr_edit)
        outer.addLayout(expr_row)

        msg_row = QHBoxLayout()
        msg_row.addWidget(QLabel("Message:"))
        self._message_edit = QLineEdit(rule.message_template)
        self._message_edit.setPlaceholderText(
            'Blank = auto (e.g. "P5 (600.00) > P3 (595.00) for 150ms"). '
            'Customize with {SENSOR} for its value, {soak_ms} for the soak - '
            'e.g. "P5 ({P5}) > P3 ({P3}) for {soak_ms}ms"')
        self._message_edit.textChanged.connect(
            lambda t: setattr(self._rule, "message_template", t))
        msg_row.addWidget(self._message_edit)
        outer.addLayout(msg_row)

        extra_row = QHBoxLayout()
        extra_row.addWidget(QLabel("Target valve (open_valve):"))
        self._target_edit = QLineEdit(rule.target_valve)
        self._target_edit.setFixedWidth(100)
        self._target_edit.setPlaceholderText("valve id")
        self._target_edit.textChanged.connect(lambda t: setattr(self._rule, "target_valve", t))
        extra_row.addWidget(self._target_edit)

        extra_row.addWidget(QLabel("Close below:"))
        self._close_sb = _OptionalSpinBox()
        self._close_sb.set_value(rule.close_valve_below)
        extra_row.addWidget(self._close_sb)

        extra_row.addWidget(QLabel("Soak (ms):"))
        self._soak_sb = QDoubleSpinBox()
        self._soak_sb.setRange(0, 60000)
        self._soak_sb.setDecimals(0)
        self._soak_sb.setValue(rule.soak_ms)
        self._soak_sb.setFixedWidth(80)
        self._soak_sb.valueChanged.connect(lambda v: setattr(self._rule, "soak_ms", int(v)))
        extra_row.addWidget(self._soak_sb)

        extra_row.addStretch()
        outer.addLayout(extra_row)

    def flush(self):
        self._rule.close_valve_below = self._close_sb.value()
        self._rule.soak_ms = int(self._soak_sb.value())


class _LogicRulesSection(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._project = None
        self._rows: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        outer.addWidget(_section_title("LOGIC / EXPRESSION RULES"))
        outer.addWidget(_hsep())

        desc = QLabel(
            "These rules evaluate arbitrary cross-sensor conditions each cycle. "
            "Use sensor names (P1…P8, TC1…, LC1…) in expressions. "
            "Example:  P8 > P7   .  "
            "All rules here replace the previously hardcoded abort conditions."
        )
        desc.setWordWrap(True)
        desc.setObjectName("sensor_unit_label")
        outer.addWidget(desc)

        self._rows_container = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 4, 0, 0)
        self._rows_layout.setSpacing(4)
        outer.addWidget(self._rows_container)

        add_btn = QPushButton("+ Add Logic Rule")
        add_btn.setFixedWidth(180)
        add_btn.clicked.connect(self._add_rule)
        outer.addWidget(add_btn)

    def _clear(self):
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

    def load_project(self, project):
        self._project = project
        self._clear()
        if project is None:
            return

        for rule in project.rules:
            if rule.condition_type == "expression":
                self._add_row(rule)

        if not self._rows:
            self._rows_layout.addWidget(QLabel("No logic rules defined yet. Click '+ Add Logic Rule' to create one."))

    def _add_row(self, rule: AbortRule):
        row = _LogicRuleRow(rule, on_delete=self._delete_row)
        self._rows.append(row)
        self._rows_layout.addWidget(row)

    def _add_rule(self):
        if self._project is None:
            QMessageBox.warning(self, "No Project", "Load a project before adding rules.")
            return

        if self._rows_layout.count() == 1:
            item = self._rows_layout.itemAt(0)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                item.widget().deleteLater()
                self._rows_layout.takeAt(0)

        rule_id = f"logic_rule_{len(self._project.rules) + 1}"
        new_rule = AbortRule(
            id             = rule_id,
            condition_type = "expression",
            action         = "abort",
            enabled        = True,
            expression     = "",
            description    = "",
        )
        self._project.rules.append(new_rule)
        self._add_row(new_rule)

    def _delete_row(self, row_widget: "_LogicRuleRow"):
        rule = row_widget._rule
        if self._project and rule in self._project.rules:
            self._project.rules.remove(rule)
        if row_widget in self._rows:
            self._rows.remove(row_widget)

        idx = self._rows_layout.indexOf(row_widget)
        if idx >= 0:
            self._rows_layout.takeAt(idx).widget().deleteLater()

    def flush(self):
        for row in self._rows:
            row.flush()

class AbortConfigPage(QWidget):

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self._controller = controller
        self._project = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setMaximumWidth(1100)
        inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._main_layout = QVBoxLayout(inner)
        self._main_layout.setContentsMargins(16, 14, 16, 16)
        self._main_layout.setSpacing(12)

        header = QLabel("Abort Configuration")
        header.setObjectName("panel_section_title")
        self._main_layout.addWidget(header)

        intro = QLabel(
            "Tune sensor thresholds and expression rules used by the abort logic. "
            "Changes are saved back into the active project."
        )
        intro.setWordWrap(True)
        intro.setObjectName("sensor_unit_label")
        self._main_layout.addWidget(intro)

        limits_card, limits_card_layout = _card()
        self._system_limits_section = _SystemLimitsSection()
        limits_card_layout.addWidget(self._system_limits_section)
        self._main_layout.addWidget(limits_card)

        sensor_card, sensor_card_layout = _card()
        self._sensor_section = _SensorThresholdsSection()
        sensor_card_layout.addWidget(self._sensor_section)
        self._main_layout.addWidget(sensor_card)

        logic_card, logic_card_layout = _card()
        self._logic_section = _LogicRulesSection()
        logic_card_layout.addWidget(self._logic_section)
        self._main_layout.addWidget(logic_card)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_btn = QPushButton("Save Abort Configuration to Project")
        self._save_btn.setObjectName("primary_btn")
        self._save_btn.setMinimumHeight(34)
        self._save_btn.clicked.connect(self._save_all)
        save_row.addWidget(self._save_btn)
        self._main_layout.addLayout(save_row)

        self._main_layout.addStretch()

        # Centre the capped-width column in the scroll viewport
        wrap = QWidget()
        wrap_layout = QHBoxLayout(wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addStretch(1)
        wrap_layout.addWidget(inner, stretch=4)
        wrap_layout.addStretch(1)
        scroll.setWidget(wrap)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

    def load_project(self, project):
        self._project = project
        self._system_limits_section.load_project(project)
        self._sensor_section.load_project(project)
        self._logic_section.load_project(project)

        if self._controller:
            self._controller.reload_abort_rules(project)

    def _save_all(self):
        if self._project is None:
            QMessageBox.warning(self, "No Project", "No project is currently loaded.")
            return

        self._system_limits_section.flush()
        self._sensor_section.flush()
        self._logic_section.flush()

        if self._controller:
            self._controller.reload_abort_rules(self._project)

        path = getattr(self._controller, "project_path", None)
        if not path:
            QMessageBox.warning(
                self, "No Save Path",
                "Cannot determine project file path. "
                "Please save the project from the P&ID editor first."
            )
            return

        try:
            self._project.save(path)
            QMessageBox.information(
                self, "Saved",
                f"Abort configuration saved to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

"""
AbortWindow

This window will display a massive abort button which will will trigger the engine system to stop fire
and close valves. It must update the GUI state with the controller when a manual abort or safe state is triggered
as well as update itself based on whether the engine automatically aborts itself

INPUT DEPENDENCIES:
    GUIController.signals.connected()
        When we connect to the MCU, we need to enable the safe state button from its is initially
        disabled state.

    GUIController.signals.disconnected(reason)
        When we disconnect from the MCU for any reason, we need to disable the safe state button.
        Note that an auto disconnect will also trigger an abort, so both disconnected and abort_triggered
        signals will emit. The callbacks play nicely with each other here, the abort flips wich button is 
        visible and this signal determines whether the safe state button is enabled, order of operations will
        not matter thankfully.

    GUIController.signals.abort_triggered(abort_type, reason)
        Aborts can be caused by either the button in this window being pressed as well as 
        the engine automatically hitting an abort state, therefore this window must update the buttons
        based on this signal, rather than a local function attached to the button.
    
    GUIController.signals.safe_state()
        When the system enters a safe state, the button shown in this window must switch from being the abort
        button to the safe state button.

OUTPUT DEPENDENCIES:
    GUIController.trigger_manual_abort()
        When the abort button in this window is updated, the state within the   controller must update 
        accordingly. The controller emits the abort signal, which this window will receive and update to.
    
    GUIController.confirm_safe_state()
        When the safe state button is pressed, it must update the state of the controller accordingly
        Unlike the abort condition, a safe state is only confirmed by the local button in this window,
        so there is no need for an input dependency back from the controller
    
"""
class AbortWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.connected.connect(self.connect_action)
        self.controller.signals.disconnected.connect(self.disconnect_action)
        self.controller.signals.abort_triggered.connect(self.abort_action)
        self.controller.signals.safe_state.connect(self.safe_state_action)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.manual_abort_btn = QPushButton("MANUAL ABORT")
        self.manual_abort_btn.setObjectName("manual_abort_btn")
        self.manual_abort_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.manual_abort_btn.setStyleSheet("""
            QPushButton {
                background-color: #c62828;
                color: white;
                border: 1px solid #8e0000;
                border-radius: 8px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover { background-color: #e53935; }
            QPushButton:pressed { background-color: #8e0000; }
            QPushButton:disabled { background-color: #700000; }
        """)

        # This will trigger the signal, which will spin around and trigger self.abort_action here
        self.manual_abort_btn.clicked.connect(self.controller.trigger_manual_abort)
        self.manual_abort_btn.setVisible(False)
        layout.addWidget(self.manual_abort_btn)

        self.safe_state_btn = QPushButton("CONFIRM SAFE STATE")
        self.safe_state_btn.setObjectName("safe_state_btn")
        self.safe_state_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.safe_state_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e8e3e;
                color: white;
                border: 1px solid #0d652d;
                border-radius: 8px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover { background-color: #28a24a; }
            QPushButton:pressed { background-color: #0d652d; }
            QPushButton:disabled { background-color: #145c2c; color: #a9c9b2; }
        """)

        self.safe_state_btn.clicked.connect(self.controller.confirm_safe_state)
        self.safe_state_btn.setEnabled(False)
        layout.addWidget(self.safe_state_btn)

        self.setLayout(layout)

    def connect_action(self):
        self.safe_state_btn.setEnabled(True)

    def disconnect_action(self, reason=""):
        self.safe_state_btn.setEnabled(False)

    def abort_action(self, abort_type, reason):
        self.manual_abort_btn.setVisible(False)
        self.safe_state_btn.setVisible(True)

    # Updates the controller and the local window when a safe state is commanded
    def safe_state_action(self):            
        self.safe_state_btn.setVisible(False)
        self.manual_abort_btn.setVisible(True)