# GUI_HEALTH.py
# System Health page: live sensor health table + a preprogrammed,
# confidence-driven multi-sensor calibration wizard.

import time

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog, QDialogButtonBox, QDoubleSpinBox, QComboBox,
    QListWidget, QMessageBox, QStackedWidget,
)
from PyQt5.QtCore import Qt, QTimer, QDateTime
from PyQt5.QtGui import QColor

# Sensor is STALE when nothing arrived for this long (seconds)
STALE_AFTER_S = 2.0
# FLATLINE when this many consecutive identical samples arrive
FLATLINE_SAMPLES = 10

_STATUS_COLORS = {
    "OK":       "#1e8e3e",
    "STALE":    "#e08700",
    "FLATLINE": "#c9a200",
    "NO DATA":  "#8a8880",
}


def _card(title: str, subtitle: str = ""):
    """Rounded card with a section title, matching the abort config page."""
    frame = QFrame()
    frame.setObjectName("config_card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)

    lbl = QLabel(title)
    lbl.setObjectName("panel_section_title")
    lay.addWidget(lbl)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        sub.setObjectName("sensor_unit_label")
        lay.addWidget(sub)
    return frame, lay


def _linear_fit_r2(xs: list, ys: list):
    """Least-squares gain/offset (expected = gain*wire + offset) plus R²,
    the fraction of variance in the reference values the fit explains.

    R² is meaningless (trivially 1.0) with only 2 points - a line always
    passes exactly through 2 points regardless of how noisy the sensor is -
    so callers must gate on point count separately before trusting it.
    Returns None if all points share the same wire reading (no spread to fit).
    """
    n = len(xs)
    x_mean, y_mean = sum(xs) / n, sum(ys) / n
    var = sum((x - x_mean) ** 2 for x in xs)
    if var < 1e-9:
        return None
    gain = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / var
    offset = y_mean - gain * x_mean
    ss_res = sum((y - (gain * x + offset)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - y_mean) ** 2 for y in ys)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 1.0
    return gain, offset, r2


class SensorCalibrationDialog(QDialog):
    """
    Preprogrammed, confidence-driven calibration wizard.

    Rather than the operator typing an arbitrary "expected value" at every
    step, the wizard computes the checkpoint itself from a known physical
    zero (atmospheric pressure, for PTs) plus the sensor's own full-scale
    rating, and tells the operator exactly what to set up next. After each
    capture (3+ points, since a 2-point fit is always a trivial perfect line)
    it fits gain/offset and reports a confidence (R²); once confidence clears
    the threshold it applies automatically. If confidence isn't there yet, it
    asks for another point from a small pool of extra checkpoints instead of
    just stopping.

    PT calibration is fully wired up (atmospheric pressure is a universal,
    always-available zero point). Load Cell and Thermocouple calibration have
    no defined reference procedure yet - we don't have a settled way to apply
    a known force or temperature - so they're shown as explicit placeholders
    rather than guessing at fake reference points for a flight instrument.
    """

    # Checkpoints in psi-above-atmosphere. Kept deliberately low: pressing up
    # a PT for calibration shouldn't need anywhere near full scale, so the
    # primary sequence stays at/under 100 and the extras only climb toward
    # 200 if the fit still isn't confident (200 is the hard ceiling).
    PRIMARY_TARGETS = [0.0, 50.0, 100.0]
    EXTRA_TARGETS   = [25.0, 75.0, 150.0, 200.0]

    CONFIDENCE_R2_THRESHOLD   = 0.999
    MIN_POINTS_FOR_CONFIDENCE = 3

    TYPE_CHOICES = [
        ("Pressure Transducer", "pt"),
        ("Load Cell",           "lc"),
        ("Thermocouple",        "tc"),
    ]

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Sensor Calibration")
        self.setMinimumWidth(480)

        self._points: list = []       # (expected, wire_avg)
        self._target_queue: list = [] # pending checkpoints, psi above atmosphere
        self._used_targets: list = []
        self._ref0: float = 14.7

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Sensor type:"))
        self._type_combo = QComboBox()
        for text, _ in self.TYPE_CHOICES:
            self._type_combo.addItem(text)
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        type_row.addWidget(self._type_combo)
        type_row.addStretch()
        lay.addLayout(type_row)

        sensor_row = QHBoxLayout()
        sensor_row.addWidget(QLabel("Sensor:"))
        self._sensor_combo = QComboBox()
        self._sensor_combo.currentIndexChanged.connect(self._on_sensor_changed)
        sensor_row.addWidget(self._sensor_combo)
        sensor_row.addStretch()
        lay.addLayout(sensor_row)

        self._stack = QStackedWidget()
        lay.addWidget(self._stack)

        self._stack.addWidget(self._build_unsupported_panel(
            "Load Cell calibration isn't set up yet - there's no agreed-on "
            "way to apply a known reference force to these sensors. Once "
            "there's a fixture (known weights, a calibrated pull, etc.) this "
            "same wizard can drive it the way it already does for PTs."))
        self._stack.addWidget(self._build_unsupported_panel(
            "Thermocouple calibration isn't set up yet - there's no agreed-on "
            "way to apply a known reference temperature to these sensors. "
            "Once there's a fixture (ice bath, calibrated block, etc.) this "
            "same wizard can drive it the way it already does for PTs."))
        self._pt_panel = self._build_pt_panel()
        self._stack.addWidget(self._pt_panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self._apply_now_btn = buttons.addButton("Apply Now", QDialogButtonBox.AcceptRole)
        self._apply_now_btn.setToolTip(
            "Apply the current fit even if confidence hasn't cleared the "
            "auto-complete threshold yet.")
        self._apply_now_btn.setEnabled(False)
        buttons.accepted.connect(self._apply_now)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        self._on_type_changed()

    # ── Per-type panel construction ──────────────────────────────────────

    def _build_unsupported_panel(self, message: str) -> QWidget:
        w = QWidget()
        wl = QVBoxLayout(w)
        lbl = QLabel(message)
        lbl.setWordWrap(True)
        lbl.setObjectName("sensor_unit_label")
        wl.addWidget(lbl)
        wl.addStretch()
        return w

    def _build_pt_panel(self) -> QWidget:
        w = QWidget()
        wl = QVBoxLayout(w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)

        intro = QLabel(
            "The wizard tells you what pressure to set up next - starting "
            "with atmospheric (a free, always-available zero point), then "
            "low-pressure checkpoints (nothing above 200 psi is ever asked "
            "for). Capture at least 3 points; it applies automatically once "
            "the fit is confident, or asks for another point if it isn't. "
            "You can also capture extra points at any pressure of your own "
            "to tighten the fit."
        )
        intro.setWordWrap(True)
        wl.addWidget(intro)

        ref_row = QHBoxLayout()
        ref_row.addWidget(QLabel("Reference:"))
        self._ref_combo = QComboBox()
        self._ref_combo.addItem("Absolute (atmosphere = 14.7 psia)", 14.7)
        self._ref_combo.addItem("Gauge (atmosphere = 0 psig)", 0.0)
        self._ref_combo.currentIndexChanged.connect(self._on_ref_changed)
        ref_row.addWidget(self._ref_combo)
        wl.addLayout(ref_row)

        self._start_btn = QPushButton("Start Calibration")
        self._start_btn.clicked.connect(self._start_sequence)
        wl.addWidget(self._start_btn)

        self._target_lbl = QLabel("")
        self._target_lbl.setObjectName("panel_section_title")
        wl.addWidget(self._target_lbl)

        cap_row = QHBoxLayout()
        self._capture_btn = QPushButton("Capture Point")
        self._capture_btn.setEnabled(False)
        self._capture_btn.clicked.connect(self._capture)
        cap_row.addWidget(self._capture_btn)
        cap_row.addStretch()
        wl.addLayout(cap_row)

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Your own point - actual pressure:"))
        self._custom_spin = QDoubleSpinBox()
        self._custom_spin.setRange(0.0, 100000.0)
        self._custom_spin.setDecimals(2)
        self._custom_spin.setSuffix(" psi")
        custom_row.addWidget(self._custom_spin)
        self._custom_btn = QPushButton("Capture Custom Point")
        self._custom_btn.setToolTip(
            "Capture a point at whatever pressure you actually have applied "
            "right now (enter it in the box) - more points mean a more "
            "confident fit.")
        self._custom_btn.setEnabled(False)
        self._custom_btn.clicked.connect(self._capture_custom)
        custom_row.addWidget(self._custom_btn)
        custom_row.addStretch()
        wl.addLayout(custom_row)

        self._points_list = QListWidget()
        self._points_list.setMaximumHeight(110)
        wl.addWidget(self._points_list)

        self._confidence_lbl = QLabel("No points captured yet.")
        self._confidence_lbl.setObjectName("sensor_unit_label")
        wl.addWidget(self._confidence_lbl)

        return w

    # ── Type / sensor selection ──────────────────────────────────────────

    def _current_type(self) -> str:
        return self.TYPE_CHOICES[self._type_combo.currentIndex()][1]

    def _sensor_keys_for_type(self, t: str) -> list:
        c = self.controller
        return {"pt": c.pt_keys, "lc": c.lc_keys, "tc": c.tc_keys}.get(t, [])

    def _on_type_changed(self):
        t = self._current_type()
        self._sensor_combo.blockSignals(True)
        self._sensor_combo.clear()
        for name in [n.upper() for n in (self._sensor_keys_for_type(t) or [])]:
            self._sensor_combo.addItem(name)
        self._sensor_combo.blockSignals(False)

        panel_index = {"pt": 2, "lc": 0, "tc": 1}[t]
        self._stack.setCurrentIndex(panel_index)
        if t == "pt":
            self._reset_sequence()

    def _on_sensor_changed(self):
        if self._current_type() == "pt":
            self._reset_sequence()

    def _selected_sensor(self) -> str:
        return self._sensor_combo.currentText()

    # ── PT calibration flow ───────────────────────────────────────────────

    def _on_ref_changed(self):
        self._ref0 = self._ref_combo.currentData()
        if not self._points:
            self._reset_sequence()

    def _reset_sequence(self):
        self._points = []
        self._points_list.clear()
        self._ref0 = self._ref_combo.currentData()
        self._target_queue = list(self.PRIMARY_TARGETS)
        self._used_targets = []
        self._apply_now_btn.setEnabled(False)
        self._capture_btn.setEnabled(False)
        if hasattr(self, "_custom_btn"):
            self._custom_btn.setEnabled(False)
        self._confidence_lbl.setText("No points captured yet.")
        self._target_lbl.setText("")

    def _start_sequence(self):
        if not self._selected_sensor():
            QMessageBox.warning(self, "No Project",
                               "Load a project first - it defines which sensors exist.")
            return
        self._reset_sequence()
        self._capture_btn.setEnabled(True)
        self._custom_btn.setEnabled(True)
        self._show_next_target()

    def _current_target(self) -> float:
        return self._ref0 + self._target_queue[0]

    def _show_next_target(self):
        if not self._target_queue:
            self._target_lbl.setText(
                "Checkpoint pool exhausted - add your own points below.")
            self._capture_btn.setEnabled(False)
            return
        gauge = self._target_queue[0]
        setup = "leave it at atmosphere" if gauge == 0 \
            else f"press up to {gauge:g} psi above atmosphere"
        self._target_lbl.setText(
            f"Set {self._selected_sensor()} to {self._current_target():.2f} psi "
            f"({setup})")

    def _read_wire_average(self) -> float:
        """Average of the last few raw wire samples, or None if no data."""
        name = self._selected_sensor()
        recent = self.controller.sensor_recent.get(name)
        if not recent:
            QMessageBox.warning(
                self, "No Data",
                f"No readings received yet for {name} - connect and wait for data.")
            return None
        tail = list(recent)[-5:]
        return sum(tail) / len(tail)

    def _capture(self):
        wire_avg = self._read_wire_average()
        if wire_avg is None:
            return

        expected = self._current_target()
        self._add_point(expected, wire_avg)
        self._used_targets.append(self._target_queue.pop(0))

        self._evaluate_fit()

        if not self._target_queue and not self._confidence_met():
            # Primary checkpoints exhausted and still not confident - pull
            # the next unused extra (they climb gradually, never past 200).
            remaining_extra = [t for t in self.EXTRA_TARGETS
                               if t not in self._used_targets]
            self._target_queue = remaining_extra[:1]

        if self._confidence_met():
            return   # _evaluate_fit already auto-applied
        if self._target_queue:
            self._show_next_target()
        else:
            self._target_lbl.setText(
                "Checkpoint pool exhausted - add your own points below, or "
                "Apply Now to accept the current fit.")
            self._capture_btn.setEnabled(False)

    def _capture_custom(self):
        """Operator-supplied checkpoint: they type the pressure actually
        applied right now and we capture against it. Lets them stack as many
        points as they want to drive confidence up."""
        wire_avg = self._read_wire_average()
        if wire_avg is None:
            return
        self._add_point(self._custom_spin.value(), wire_avg)
        self._evaluate_fit()

    def _add_point(self, expected: float, wire_avg: float):
        self._points.append((expected, wire_avg))
        self._points_list.addItem(f"{expected:.2f} psi   (raw {wire_avg:.3f})")

    def _confidence_met(self) -> bool:
        if len(self._points) < self.MIN_POINTS_FOR_CONFIDENCE:
            return False
        xs = [w for _, w in self._points]
        ys = [e for e, _ in self._points]
        fit = _linear_fit_r2(xs, ys)
        return fit is not None and fit[2] >= self.CONFIDENCE_R2_THRESHOLD

    def _evaluate_fit(self):
        n = len(self._points)
        xs = [w for _, w in self._points]
        ys = [e for e, _ in self._points]
        fit = _linear_fit_r2(xs, ys)

        if fit is None:
            self._confidence_lbl.setText(
                f"{n} point(s) captured - all identical readings so far, "
                "need spread to fit anything.")
            self._apply_now_btn.setEnabled(n >= 2)
            return

        gain, offset, r2 = fit
        self._apply_now_btn.setEnabled(True)

        if n < self.MIN_POINTS_FOR_CONFIDENCE:
            self._confidence_lbl.setText(
                f"{n} point(s) captured. Confidence available once "
                f"{self.MIN_POINTS_FOR_CONFIDENCE}+ points are in "
                f"(a 2-point fit is always a perfect line, so it's not a "
                f"real confidence signal yet).")
            return

        self._confidence_lbl.setText(
            f"{n} points - fit confidence R²={r2:.5f} "
            f"(gain={gain:.6g}, offset={offset:.6g})")

        if r2 >= self.CONFIDENCE_R2_THRESHOLD:
            self._finish(gain, offset, r2, auto=True)

    def _apply_now(self):
        if len(self._points) < 2:
            return
        xs = [w for _, w in self._points]
        ys = [e for e, _ in self._points]
        fit = _linear_fit_r2(xs, ys)
        if fit is None:
            QMessageBox.warning(self, "No Spread",
                               "All captured points had the same reading - "
                               "vary the pressure between captures first.")
            return
        gain, offset, r2 = fit
        self._finish(gain, offset, r2, auto=False)

    def _finish(self, gain: float, offset: float, r2: float, auto: bool):
        name = self._selected_sensor()
        self.controller.set_calibration(name, gain, offset)
        self._store_in_project(name, gain, offset)

        if auto:
            msg = (f"{name} calibrated automatically once confidence cleared "
                  f"the threshold (R²={r2:.5f}).\ngain={gain:.6g}, offset={offset:.6g}")
        else:
            n = len(self._points)
            conf_note = (f"R²={r2:.5f}" if n >= self.MIN_POINTS_FOR_CONFIDENCE
                        else f"only {n} points - confidence not yet meaningful")
            msg = (f"{name} calibrated manually ({conf_note}).\n"
                  f"gain={gain:.6g}, offset={offset:.6g}")
        QMessageBox.information(self, "Calibration Applied", msg)
        self.accept()

    def _store_in_project(self, name: str, gain: float, offset: float):
        """Persist gain/offset into that sensor's component extras + save."""
        project = self.controller.project
        path = self.controller.project_path
        if not project:
            return
        for comp in project.components.values():
            hw_id = str(comp.extras.get("hw_id") or comp.label or comp.id).upper()
            if hw_id == name:
                comp.extras["cal_gain"] = round(gain, 6)
                comp.extras["cal_offset"] = round(offset, 6)
                break
        if path:
            try:
                project.save(path)
            except Exception as e:
                QMessageBox.warning(self, "Save Failed",
                                    f"Calibration applied but project not saved:\n{e}")


class HealthPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setMaximumWidth(1100)
        inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        main = QVBoxLayout(inner)
        main.setContentsMargins(16, 14, 16, 16)
        main.setSpacing(12)

        header = QLabel("System Health")
        header.setObjectName("panel_section_title")
        main.addWidget(header)

        # ── Link card ─────────────────────────────────────────────────────
        link_card, link_lay = _card("LINK")
        self._link_lbl = QLabel("Not connected")
        self._link_lbl.setObjectName("sensor_value_label")
        link_lay.addWidget(self._link_lbl)
        main.addWidget(link_card)

        # ── Sensor health card ────────────────────────────────────────────
        sensor_card, sensor_lay = _card(
            "SENSOR HEALTH",
            "Live status of every sensor in the project: OK = fresh data, "
            "STALE = nothing received recently, FLATLINE = repeating the exact "
            "same value (possible wiring / ADC fault).")
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Sensor", "Value", "Last Data", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setFocusPolicy(Qt.NoFocus)
        sensor_lay.addWidget(self._table)
        main.addWidget(sensor_card)

        # ── Sensor calibration card ───────────────────────────────────────
        cal_card, cal_lay = _card(
            "SENSOR CALIBRATION",
            "Preprogrammed, confidence-driven calibration - the wizard tells "
            "you what checkpoint to set up next and applies automatically "
            "once the fit is confident. Currently wired up for Pressure "
            "Transducers; Load Cell and Thermocouple procedures aren't "
            "defined yet.")
        cal_row = QHBoxLayout()
        self._cal_btn = QPushButton("Start Sensor Calibration…")
        self._cal_btn.clicked.connect(self._open_calibration)
        cal_row.addWidget(self._cal_btn)
        self._cal_clear_btn = QPushButton("Clear Calibrations")
        self._cal_clear_btn.clicked.connect(self._clear_calibrations)
        cal_row.addWidget(self._cal_clear_btn)
        cal_row.addStretch()
        cal_lay.addLayout(cal_row)
        main.addWidget(cal_card)

        main.addStretch()

        wrap = QWidget()
        wrap_lay = QHBoxLayout(wrap)
        wrap_lay.setContentsMargins(0, 0, 0, 0)
        wrap_lay.addStretch(1)
        wrap_lay.addWidget(inner, stretch=4)
        wrap_lay.addStretch(1)
        scroll.setWidget(wrap)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        # Refresh only while the page is visible
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._refresh)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    # ── Sensor health ─────────────────────────────────────────────────────

    def _sensor_names(self):
        c = self.controller
        names = [n.upper() for n in (c.pt_keys + c.tc_keys + c.lc_keys)]
        if not names:
            names = sorted(c.sensor_last_rx.keys())
        return names

    def _refresh(self):
        c = self.controller

        eth = c.ethernet_client
        if getattr(eth, "connected", False):
            hb_age = QDateTime.currentMSecsSinceEpoch() - eth.heartbeat_last_rx
            self._link_lbl.setText(
                f"Connected to {eth.remote_ip}:{eth.remote_port}   ·   "
                f"last packet {hb_age} ms ago   ·   "
                f"{eth.heartbeat_tx_count} heartbeats sent")
            self._link_lbl.setStyleSheet("color: #1e8e3e; font-weight: bold;")
        else:
            self._link_lbl.setText("Not connected")
            self._link_lbl.setStyleSheet("color: #8a8880;")

        names = self._sensor_names()
        now = time.time()
        self._table.setRowCount(len(names))

        for row, name in enumerate(names):
            last_rx = c.sensor_last_rx.get(name)
            recent = c.sensor_recent.get(name)
            value = c.current_sensor_values.get(name)

            if last_rx is None:
                status, age_txt = "NO DATA", "-"
            else:
                age = now - last_rx
                age_txt = f"{age:.1f} s ago"
                if age > STALE_AFTER_S:
                    status = "STALE"
                elif (recent and len(recent) >= FLATLINE_SAMPLES
                        and len(set(list(recent)[-FLATLINE_SAMPLES:])) == 1):
                    status = "FLATLINE"
                else:
                    status = "OK"

            cal_note = "  (cal)" if name in c.calibrations else ""
            cells = [
                name + cal_note,
                f"{value:.2f}" if value is not None else "-",
                age_txt,
                status,
            ]
            for col, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if col == 3:
                    item.setForeground(QColor(_STATUS_COLORS.get(status, "#8a8880")))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                item.setTextAlignment(Qt.AlignCenter if col else
                                      (Qt.AlignLeft | Qt.AlignVCenter))
                self._table.setItem(row, col, item)

        # Keep the table compact: size to contents up to a cap
        header_h = self._table.horizontalHeader().height()
        rows_h = sum(self._table.rowHeight(r) for r in range(self._table.rowCount()))
        self._table.setFixedHeight(min(header_h + rows_h + 4, 420))

    # ── Sensor calibration ────────────────────────────────────────────────

    def _open_calibration(self):
        if not (self.controller.pt_keys or self.controller.lc_keys or self.controller.tc_keys):
            QMessageBox.warning(self, "No Project", "Load a project first.")
            return
        SensorCalibrationDialog(self.controller, self).exec_()
        self._refresh()

    def _clear_calibrations(self):
        reply = QMessageBox.question(
            self, "Clear Calibrations",
            "Remove all in-memory sensor calibrations?\n"
            "(Values saved in the project file are kept until re-saved.)",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            self.controller.clear_calibrations()
            self._refresh()
