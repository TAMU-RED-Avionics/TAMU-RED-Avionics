import uuid

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit,
    QComboBox, QCheckBox, QDialog, QDialogButtonBox, QScrollArea, QFrame,
    QToolButton, QMessageBox,
)

from PID_SCHEMA import CalcChannel

ROLE_CHOICES = [
    ("Mdot - Fuel",     "mdot_fuel"),
    ("Mdot - Oxidizer", "mdot_ox"),
    ("Thrust",          "thrust"),
    ("Custom",          "custom"),
]
ROLE_LABELS = {v: k for k, v in ROLE_CHOICES}


def _parse_constants(text: str) -> dict:
    """Parse a 'NAME=1.0, OTHER=2.5' string into {name: float}. Silently
    skips malformed entries rather than raising, so a typo doesn't block
    saving the rest of the channel."""
    out = {}
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, val = part.partition("=")
        name = name.strip()
        if not name:
            continue
        try:
            out[name] = float(val.strip())
        except ValueError:
            continue
    return out


def _format_constants(constants: dict) -> str:
    return ", ".join(f"{k}={v:g}" for k, v in constants.items())


class _ChannelCard(QFrame):
    def __init__(self, channel: CalcChannel, on_remove, parent=None):
        super().__init__(parent)
        self.channel = channel
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("calc_channel_card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        top_row = QHBoxLayout()
        self.label_edit = QLineEdit(channel.label)
        self.label_edit.setPlaceholderText("Label, e.g. Fuel Mdot")
        top_row.addWidget(self.label_edit, stretch=2)

        self.role_combo = QComboBox()
        for text, _ in ROLE_CHOICES:
            self.role_combo.addItem(text)
        self.role_combo.setCurrentText(ROLE_LABELS.get(channel.role, "Custom"))
        top_row.addWidget(self.role_combo, stretch=1)

        self.unit_edit = QLineEdit(channel.unit)
        self.unit_edit.setPlaceholderText("unit, e.g. lbm/s")
        self.unit_edit.setFixedWidth(90)
        top_row.addWidget(self.unit_edit)

        self.enabled_cb = QCheckBox("On")
        self.enabled_cb.setChecked(channel.enabled)
        top_row.addWidget(self.enabled_cb)

        del_btn = QToolButton()
        del_btn.setText("✕")
        del_btn.setToolTip("Remove this channel")
        del_btn.clicked.connect(lambda: on_remove(self))
        top_row.addWidget(del_btn)

        outer.addLayout(top_row)

        self.expr_edit = QLineEdit(channel.expression)
        self.expr_edit.setPlaceholderText(
            "Expression - sensor names (P1, P8, TC1, LC1...), your constants below, "
            "sqrt/abs/min/max/pow/G0, and PropsSI(output, in1, val1, in2, val2, fluid) for "
            "CoolProp fluid properties. e.g. 500 * CV * sqrt((P1 - P2) * SG) or "
            "LC1 * PropsSI('D','T',TC1+273.15,'P',P1*6894.76+101325,'N2O')")
        outer.addWidget(self.expr_edit)

        const_row = QHBoxLayout()
        const_row.addWidget(QLabel("Constants:"))
        self.const_edit = QLineEdit(_format_constants(channel.constants))
        self.const_edit.setPlaceholderText("NAME=value, e.g. CV=4.2, SG=1.14")
        const_row.addWidget(self.const_edit)
        outer.addLayout(const_row)

    def flush(self) -> CalcChannel:
        self.channel.label = self.label_edit.text().strip() or "Channel"
        self.channel.role = dict(ROLE_CHOICES)[self.role_combo.currentText()]
        self.channel.unit = self.unit_edit.text().strip()
        self.channel.enabled = self.enabled_cb.isChecked()
        self.channel.expression = self.expr_edit.text().strip()
        self.channel.constants = _parse_constants(self.const_edit.text())
        return self.channel


class CalcChannelsDialog(QDialog):
    """Settings-gear editor for the project's Mdot/Thrust calculated
    channels - same spirit as the abort-config condition builder, but for
    computed performance values instead of trigger logic."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculated Channels")
        self.resize(640, 520)
        self._project = project
        self._cards: list = []

        outer = QVBoxLayout(self)

        hint = QLabel(
            "Define how variables are computed for this system. Each channel "
            "is a formula using sensor names, your own constants, and helpers "
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 9pt;")
        outer.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._card_container = QWidget()
        self._card_layout = QVBoxLayout(self._card_container)
        self._card_layout.setSpacing(8)
        self._card_layout.addStretch()
        scroll.setWidget(self._card_container)
        outer.addWidget(scroll, stretch=1)

        for ch in project.calc_channels:
            self._add_card(ch)

        add_btn = QPushButton("+ Add Channel")
        add_btn.clicked.connect(self._on_add_channel)
        outer.addWidget(add_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _add_card(self, channel: CalcChannel):
        card = _ChannelCard(channel, self._remove_card, self)
        self._cards.append(card)
        self._card_layout.insertWidget(self._card_layout.count() - 1, card)

    def _remove_card(self, card: "_ChannelCard"):
        self._cards.remove(card)
        card.setParent(None)
        card.deleteLater()

    def _on_add_channel(self):
        ch = CalcChannel(id=f"calc_{uuid.uuid4().hex[:8]}", label="New Channel")
        self._add_card(ch)

    def _on_save(self):
        seen_ids = set()
        channels = []
        for card in self._cards:
            ch = card.flush()
            if not ch.id or ch.id in seen_ids:
                ch.id = f"calc_{uuid.uuid4().hex[:8]}"
            seen_ids.add(ch.id)
            channels.append(ch)
        self._project.calc_channels = channels
        self.accept()


class PerformanceBar(QWidget):
    """Compact bottom-bar readout: one label per configured channel, plus
    Total Mdot and Isp, and a gear button that opens CalcChannelsDialog."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._channel_labels: dict = {}   # channel_id -> QLabel
        self._row_layout = QHBoxLayout()
        self._row_layout.setSpacing(10)
        layout.addLayout(self._row_layout)

        self.total_mdot_label = QLabel("Total ṅ: -")
        self.total_mdot_label.setObjectName("perf_readout")
        layout.addWidget(self.total_mdot_label)

        self.isp_label = QLabel("Isp: -")
        self.isp_label.setObjectName("perf_readout")
        layout.addWidget(self.isp_label)

        self.gear_btn = QToolButton()
        self.gear_btn.setText("⚙")
        self.gear_btn.setToolTip("Configure calculated channels")
        self.gear_btn.clicked.connect(self._open_settings)
        layout.addWidget(self.gear_btn)

        controller.signals.calc_values_changed.connect(self._on_values_changed)
        self.refresh_channels()

    def refresh_channels(self):
        """Rebuild the per-channel labels to match the current project's
        channel list (called after a project load or a settings edit)."""
        for lbl in self._channel_labels.values():
            lbl.setParent(None)
            lbl.deleteLater()
        self._channel_labels.clear()

        project = getattr(self.controller, "project", None)
        channels = list(getattr(project, "calc_channels", []) or [])
        for ch in channels:
            if not ch.enabled:
                continue
            lbl = QLabel(f"{ch.label}: -")
            lbl.setObjectName("perf_readout")
            self._row_layout.addWidget(lbl)
            self._channel_labels[ch.id] = lbl

        self._apply_values(getattr(self.controller, "calc_values", {}) or {})

    def _open_settings(self):
        project = getattr(self.controller, "project", None)
        if not project:
            QMessageBox.warning(self, "No Project", "Load a project before configuring calculated channels.")
            return
        dlg = CalcChannelsDialog(project, self)
        if dlg.exec_() == QDialog.Accepted:
            self.controller._recompute_calc_channels()
            self.refresh_channels()
            path = getattr(self.controller, "project_path", None)
            if path:
                project.save(path)

    def _on_values_changed(self, values: dict):
        self._apply_values(values)

    def _apply_values(self, values: dict):
        project = getattr(self.controller, "project", None)
        channels = {ch.id: ch for ch in getattr(project, "calc_channels", []) or []}

        for cid, lbl in self._channel_labels.items():
            ch = channels.get(cid)
            v = values.get(cid)
            unit = (ch.unit if ch else "") or ""
            label_text = ch.label if ch else cid
            lbl.setText(f"{label_text}: {v:.3f} {unit}".rstrip() if v is not None else f"{label_text}: -")

        mdot = values.get("__mdot_total__")
        self.total_mdot_label.setText(f"Total ṅ: {mdot:.3f}" if mdot is not None else "Total ṅ: -")

        isp = values.get("__isp__")
        self.isp_label.setText(f"Isp: {isp:.1f} s" if isp is not None else "Isp: -")