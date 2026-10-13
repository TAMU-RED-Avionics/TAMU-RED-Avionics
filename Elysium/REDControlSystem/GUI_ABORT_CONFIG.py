from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox,
    QScrollArea, QFrame, QSizePolicy, QMessageBox,
    QDoubleSpinBox, QComboBox, QToolButton, QInputDialog,
)
from PyQt5.QtCore import Qt, pyqtSignal

from GUI_CONTROLLER import GUIController, GuiMode
from PID_SCHEMA import (
    AbortRule, AbortState, DEFAULT_ABORT_ID,
    COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL,
    COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_THROTTLE_VALVE,
    get_actuator_spec,
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


class _StateCombo(QComboBox):
    """Picks one of the project's named abort states (stored as "" for the default)."""

    def __init__(self, choices: list, current: str = "", parent=None):
        super().__init__(parent)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.set_choices(choices, current)

    def set_choices(self, choices: list, current=None):
        keep = self.state_id() if current is None else current
        self.blockSignals(True)
        self.clear()
        for sid, name in choices:
            self.addItem(name, sid)
        self.setCurrentIndex(max(self.findData(keep or DEFAULT_ABORT_ID), 0))
        self.blockSignals(False)

    def state_id(self) -> str:
        data = self.currentData()
        return "" if data in (None, DEFAULT_ABORT_ID) else data


class _SensorThresholdWidget(QWidget):
    def __init__(self, comp_id: str, comp_label: str, comp_type: str,
                 extras: dict, valve_options: list, state_choices: list, parent=None):
        super().__init__(parent)
        self._extras = extras
        unit = _TYPE_UNIT.get(comp_type, "")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 8)
        outer.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)

        headers = ["Threshold", "Value", "Action", "Target Valve (open_valve)", "Close below",
                   "Abort state (abort)"]
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

            state_combo = _StateCombo(state_choices, th_data.get(f"{band}_state", ""))
            state_combo.setEnabled(action_combo.current_action() == "abort")
            action_combo.currentTextChanged.connect(
                lambda text, sc=state_combo: sc.setEnabled(text == "abort"))
            grid.addWidget(state_combo, row_idx, 5)

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
                "state":       state_combo,
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

    def set_state_choices(self, choices: list):
        for f in self._fields.values():
            f["state"].set_choices(choices)

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
            d[f"{band}_state"]    = f["state"].state_id()
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
            "on any PT at or above System MEOP; a clear-the-area warning at the "
            "level below; and the chosen abort state fires at 95% of System MAWP."
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

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Warn (clear the area) at:"))
        self._prewarn = QDoubleSpinBox()
        self._prewarn.setRange(1, 99)
        self._prewarn.setDecimals(0)
        self._prewarn.setSuffix(" % of MAWP")
        self._prewarn.setToolTip(
            "A dialog warns operators to clear the area at this level, before the system "
            "acts at 95% of MAWP. They can vent early or cancel the auto-action.")
        row2.addWidget(self._prewarn)
        row2.addSpacing(24)
        row2.addWidget(QLabel("At MAWP limit use abort state:"))
        self._mawp_state = _StateCombo([(DEFAULT_ABORT_ID, "Default Abort")])
        row2.addWidget(self._mawp_state)
        row2.addStretch()
        outer.addLayout(row2)

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
        self._prewarn.setValue(getattr(params, "system_prewarn_pct", 90.0))
        self._mawp_state.set_choices(
            [(s.id, s.name) for s in project.abort_states],
            getattr(params, "system_mawp_state", ""))

    def set_state_choices(self, choices: list):
        self._mawp_state.set_choices(choices)

    def flush(self):
        if not self._project:
            return
        self._project.parameters.system_mawp = self._mawp.value()
        self._project.parameters.system_meop = self._meop.value()
        self._project.parameters.system_mawp_message = self._mawp_msg.text().strip()
        self._project.parameters.system_meop_message = self._meop_msg.text().strip()
        self._project.parameters.system_prewarn_pct = float(self._prewarn.value())
        self._project.parameters.system_mawp_state = self._mawp_state.state_id()


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
            if comp.type in _VALVE_TYPES or get_actuator_spec(comp) is not None
        ]

        sensor_comps = [
            (cid, comp)
            for cid, comp in project.components.items()
            if comp.type in _SENSOR_TYPES
        ]

        for cid, comp in sensor_comps:
            block = _CollapsibleBlock(comp.label or cid)
            w = _SensorThresholdWidget(cid, comp.label or cid, comp.type,
                                       comp.extras, valve_options,
                                       [(s.id, s.name) for s in project.abort_states])
            block.add_widget(w)
            self._container_layout.addWidget(block)
            self._widgets[cid] = w

        if not sensor_comps:
            self._container_layout.addWidget(
                QLabel("No pressure / temperature / load-cell sensors found in this project.")
            )

    def set_state_choices(self, choices: list):
        for w in self._widgets.values():
            w.set_state_choices(choices)

    def flush(self):
        for w in self._widgets.values():
            w.flush()

class _LogicRuleRow(QWidget):
    def __init__(self, rule: AbortRule, on_delete, state_choices: list, parent=None):
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

        self._state_combo = _StateCombo(state_choices, rule.abort_state)
        self._state_combo.setEnabled(rule.action == "abort")
        self._state_combo.currentIndexChanged.connect(
            lambda _i: setattr(self._rule, "abort_state", self._state_combo.state_id()))
        self._action_combo.currentTextChanged.connect(
            lambda t: self._state_combo.setEnabled(t == "abort"))
        top.addWidget(QLabel("Abort state:"))
        top.addWidget(self._state_combo)

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

    def set_state_choices(self, choices: list):
        self._state_combo.set_choices(choices)
        self._rule.abort_state = self._state_combo.state_id()

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

    def _state_choices(self) -> list:
        if self._project is None:
            return [(DEFAULT_ABORT_ID, "Default Abort")]
        return [(s.id, s.name) for s in self._project.abort_states]

    def set_state_choices(self, choices: list):
        for row in self._rows:
            row.set_state_choices(choices)

    def _add_row(self, rule: AbortRule):
        row = _LogicRuleRow(rule, on_delete=self._delete_row, state_choices=self._state_choices())
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

class _AbortStateSection(QWidget):
    """Named abort states: valve configurations the system is driven to on an
    abort. The Default Abort is also the Safe State preset. Each state is
    confirmed separately; until the default one is, abort/safe close ALL valves.
    """
    states_changed = pyqtSignal()       # added / renamed / deleted
    confirmation_changed = pyqtSignal() # a state was edited (un-confirmed) or confirmed

    def __init__(self, on_confirm, parent=None):
        super().__init__(parent)
        self._project = None
        self._on_confirm = on_confirm
        self._boxes: dict = {}
        self._loading = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(_section_title("Abort States"))

        intro = QLabel(
            "Set each valve's position when the system aborts. By default every valve closes; "
            "check a valve to leave it open during an abort. The Default Abort is also the Safe "
            "State. Add named states (e.g. a vent) and choose which one a limit or rule uses below. "
            "Confirm each state when done."
        )
        intro.setWordWrap(True)
        intro.setObjectName("sensor_unit_label")
        lay.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel("State:"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(220)
        self._combo.currentIndexChanged.connect(self._on_state_selected)
        row.addWidget(self._combo)
        self._new_btn = QPushButton("New")
        self._new_btn.clicked.connect(self._new_state)
        self._rename_btn = QPushButton("Rename")
        self._rename_btn.clicked.connect(self._rename_state)
        self._delete_btn = QPushButton("Delete")
        self._delete_btn.clicked.connect(self._delete_state)
        for b in (self._new_btn, self._rename_btn, self._delete_btn):
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

        self._status = QLabel()
        self._status.setWordWrap(True)
        lay.addWidget(self._status)

        self._firmware_note = QLabel()
        self._firmware_note.setWordWrap(True)
        self._firmware_note.setStyleSheet("color: #e37400;")
        lay.addWidget(self._firmware_note)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(24)
        lay.addWidget(self._grid_host)

        row = QHBoxLayout()
        row.addStretch()
        self._confirm_btn = QPushButton("Confirm This State")
        self._confirm_btn.setObjectName("primary_btn")
        self._confirm_btn.setMinimumHeight(30)
        self._confirm_btn.clicked.connect(self._confirm)
        row.addWidget(self._confirm_btn)
        lay.addLayout(row)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _commandable(comp) -> bool:
        return comp.type in _VALVE_TYPES or get_actuator_spec(comp) is not None

    def current_state(self):
        if self._project is None:
            return None
        return self._project.get_abort_state(self._combo.currentData() or "")

    def state_choices(self) -> list:
        """[(id, name)] for rule / limit dropdowns."""
        if self._project is None:
            return [(DEFAULT_ABORT_ID, "Default Abort")]
        return [(s.id, s.name) for s in self._project.abort_states]

    # -- loading -------------------------------------------------------------
    def load_project(self, project, select_id: str = ""):
        self._project = project
        self._loading = True
        self._combo.clear()
        if project is not None:
            for st in project.abort_states:
                self._combo.addItem(st.name, st.id)
            idx = self._combo.findData(select_id or DEFAULT_ABORT_ID)
            self._combo.setCurrentIndex(max(idx, 0))
        self._loading = False
        self._rebuild_grid()

    def _rebuild_grid(self):
        self._loading = True
        self._boxes.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        project, state = self._project, self.current_state()
        valves = []
        if project is not None:
            valves = sorted((c for c in project.components.values() if self._commandable(c)),
                            key=lambda c: ((c.label or "").strip() or c.id))
        cols = 3
        for i, comp in enumerate(valves):
            box = QCheckBox(f"{(comp.label or '').strip() or comp.id}  ({comp.type.replace('_', ' ')})")
            box.setChecked(bool(state.valves.get(comp.id, False)))
            box.toggled.connect(lambda checked, cid=comp.id: self._on_toggled(cid, checked))
            self._grid.addWidget(box, i // cols, i % cols)
            self._boxes[comp.id] = box
        if not valves:
            self._grid.addWidget(QLabel("No commandable valves in this project."), 0, 0)
        is_default = state is not None and state.id == DEFAULT_ABORT_ID
        self._confirm_btn.setEnabled(project is not None)
        self._rename_btn.setEnabled(project is not None and not is_default)
        self._delete_btn.setEnabled(project is not None and not is_default)
        self._new_btn.setEnabled(project is not None)
        self._loading = False
        self.refresh_status()

    def _on_state_selected(self, *_):
        if not self._loading:
            self._rebuild_grid()

    # -- editing -------------------------------------------------------------
    def _on_toggled(self, cid: str, checked: bool):
        state = self.current_state()
        if self._loading or state is None:
            return
        state.valves[cid] = checked
        state.confirmed = False         # any edit needs re-confirming
        self.refresh_status()
        self.confirmation_changed.emit()

    def _confirm(self):
        state = self.current_state()
        if state is not None:
            state.confirmed = True
            self._on_confirm(state)
            self.refresh_status()
            self.confirmation_changed.emit()

    def _new_state(self):
        if self._project is None:
            return
        name, ok = QInputDialog.getText(self, "New Abort State", "Name (e.g. Vent):")
        name = name.strip()
        if not ok or not name:
            return
        existing = {s.id for s in self._project.abort_states}
        n = 1
        while f"state_{n}" in existing:
            n += 1
        self._project.abort_states.append(AbortState(f"state_{n}", name))
        self.load_project(self._project, select_id=f"state_{n}")
        self.states_changed.emit()

    def _rename_state(self):
        state = self.current_state()
        if state is None or state.id == DEFAULT_ABORT_ID:
            return
        name, ok = QInputDialog.getText(self, "Rename Abort State", "Name:", text=state.name)
        if ok and name.strip():
            state.name = name.strip()
            self.load_project(self._project, select_id=state.id)
            self.states_changed.emit()

    def _delete_state(self):
        state = self.current_state()
        if state is None or state.id == DEFAULT_ABORT_ID:
            return
        if QMessageBox.question(
                self, "Delete Abort State",
                f"Delete '{state.name}'? Limits and rules that use it will fall back to the "
                "Default Abort.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._project.abort_states = [s for s in self._project.abort_states if s.id != state.id]
        self.load_project(self._project)
        self.states_changed.emit()

    def refresh_status(self):
        state = self.current_state()
        if state is None:
            self._status.setText("No project loaded.")
            self._firmware_note.setText("")
            return
        n_open = sum(1 for cid, v in state.valves.items() if v and cid in self._boxes)
        label = state.name
        if state.confirmed:
            self._status.setText(f"{label}: CONFIRMED - {n_open} valve(s) open, all others closed.")
            self._status.setStyleSheet("color: #1e8e3e; font-weight: bold;")
        else:
            self._status.setText(
                f"{label}: NOT CONFIRMED - until you review and confirm, this state closes ALL "
                f"valves ({n_open} currently ticked open).")
            self._status.setStyleSheet("color: #e37400; font-weight: bold;")
        if n_open:
            self._firmware_note.setText(
                "Note: the Teensy firmware closes ALL valves on its own aborts (e.g. comms loss), "
                "so it won't match this state there.")
        else:
            self._firmware_note.setText("")


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

        state_card, state_card_layout = _card()
        self._abort_state_section = _AbortStateSection(self._confirm_abort_state)
        self._abort_state_section.states_changed.connect(self._refresh_state_choices)
        self._abort_state_section.confirmation_changed.connect(
            lambda: self._controller and self._controller.refresh_safe_state_warning())
        state_card_layout.addWidget(self._abort_state_section)
        self._main_layout.addWidget(state_card)

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
        self._abort_state_section.load_project(project)
        self._system_limits_section.load_project(project)
        self._sensor_section.load_project(project)
        self._logic_section.load_project(project)

        if self._controller:
            self._controller.reload_abort_rules(project)

    def _refresh_state_choices(self):
        if self._project is None:
            return
        choices = [(s.id, s.name) for s in self._project.abort_states]
        self._system_limits_section.set_state_choices(choices)
        self._sensor_section.set_state_choices(choices)
        self._logic_section.set_state_choices(choices)

    def _confirm_abort_state(self, state):
        if self._project is None:
            QMessageBox.warning(self, "No Project", "No project is currently loaded.")
            return
        path = getattr(self._controller, "project_path", None)
        if not path:
            QMessageBox.warning(
                self, "Confirmed (not saved)",
                f"'{state.name}' is confirmed for this session, but there is no project file "
                "path to save it to. Save the project from the P&ID editor first.")
            return
        try:
            self._project.save(path)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))

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

Mode control panel: the MANUAL ABORT button, the current-mode readout, and a
mode dropdown (Safe / Manual / Locked) with a SEND button. Choosing an entry
does nothing until SEND is pressed (guards against mis-clicks). ABORT is not a
selectable mode - it is entered by the abort button or an automatic abort, and
is left by sending SAFE.

INPUT DEPENDENCIES:
    GUIController.signals.connected() / disconnected(reason)
        Controls are disabled while there is no link.

    GUIController.signals.mode_changed(mode)
        Updates the mode readout and resets the dropdown to the current mode.

OUTPUT DEPENDENCIES:
    GUIController.trigger_manual_abort()
        The abort button is enabled in MANUAL and LOCKED (SAFE is already safe; ABORT already aborted). The controller emits the abort
        signal and enters ABORT.

    GUIController.request_mode(mode)
        SEND asks the controller to change mode; a returned message means the
        change was refused and is shown to the operator.
"""
class AbortWindow(QWidget):
    _MODE_OPTIONS = [("Safe", GuiMode.SAFE), ("Manual", GuiMode.MANUAL), ("Locked", GuiMode.LOCKED)]
    _MODE_COLORS = {
        GuiMode.SAFE:   "#1e8e3e",
        GuiMode.MANUAL: "#1a73e8",
        GuiMode.LOCKED: "#e37400",
        GuiMode.ABORT:  "#c62828",
    }

    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self._connected = False
        self.controller.signals.connected.connect(self.connect_action)
        self.controller.signals.disconnected.connect(self.disconnect_action)
        self.controller.signals.mode_changed.connect(self.mode_changed_action)
        self.controller.signals.safe_status_changed.connect(
            lambda: self.mode_changed_action(self.controller.mode))

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

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
            QPushButton:disabled { background-color: #700000; color: #c9a9a9; }
        """)
        # Emits the abort signal, which the controller handles in any mode
        self.manual_abort_btn.clicked.connect(self.controller.trigger_manual_abort)
        layout.addWidget(self.manual_abort_btn, 3)

        self.mode_label = QLabel()
        self.mode_label.setObjectName("mode_label")
        self.mode_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.mode_label)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("mode_combo")
        for text, mode in self._MODE_OPTIONS:
            self.mode_combo.addItem(text, mode)
        self.mode_combo.currentIndexChanged.connect(self._refresh_send)
        row.addWidget(self.mode_combo, 1)

        self.send_btn = QPushButton("SEND")
        self.send_btn.setObjectName("mode_send_btn")
        self.send_btn.clicked.connect(self._send_mode)
        row.addWidget(self.send_btn)
        layout.addLayout(row)

        self.setLayout(layout)
        self.mode_changed_action(self.controller.mode)

    def _selected_mode(self) -> str:
        return self.mode_combo.currentData()

    def _refresh_send(self, *_):
        c = self.controller
        # SEND is live when the selection differs from the current mode - or for
        # SAFE while it's only assumed (just connected), so it can be applied.
        pending_safe = (self._selected_mode() == GuiMode.SAFE and c.mode == GuiMode.SAFE
                        and not c.safe_applied)
        self.send_btn.setEnabled(self._connected and (self._selected_mode() != c.mode or pending_safe))
        self.mode_combo.setEnabled(self._connected)
        self.manual_abort_btn.setEnabled(
            self._connected and self.controller.mode in (GuiMode.MANUAL, GuiMode.LOCKED))

    def _send_mode(self):
        error = self.controller.request_mode(self._selected_mode())
        if error:
            QMessageBox.warning(self, "Mode Change Refused", error)
        self._refresh_send()

    def connect_action(self):
        self._connected = True
        self.mode_changed_action(self.controller.mode)

    def disconnect_action(self, reason=""):
        self._connected = False
        self.mode_changed_action(self.controller.mode)

    def mode_changed_action(self, mode: str):
        color = self._MODE_COLORS.get(mode, "#555")
        text = f"MODE: {mode}"
        if mode == GuiMode.SAFE and self._connected and not self.controller.safe_applied:
            text, color = "MODE: SAFE (not applied)", "#e37400"
        self.mode_label.setText(text)
        self.mode_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        # Point the dropdown at the active mode (ABORT has no entry; offer SAFE,
        # the only way out of it).
        index = self.mode_combo.findData(mode)
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentIndex(index if index >= 0 else 0)
        self.mode_combo.blockSignals(False)
        self._refresh_send()
