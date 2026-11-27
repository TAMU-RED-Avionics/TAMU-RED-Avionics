# GUI_HEALTH.py
# System Health page: live sensor health table + the load cell calibration window
# (LoadCellCalibrationWindow, below). The older confidence-driven PT wizard
# (SensorCalibrationDialog) is still defined here but no longer reachable from the page.

import json
import math
import os
import re
import time
from collections import deque
from decimal import Decimal

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDialog, QDialogButtonBox, QDoubleSpinBox, QComboBox,
    QListWidget, QMessageBox, QStackedWidget, QGridLayout, QProgressBar,
    QApplication, QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, QDateTime, QSettings
from PyQt5.QtGui import QColor, QFont

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


# ══ Load cell calibration ════════════════════════════════════════════════════════════════════
# The Teensy sends load cells as RAW counts. Each cell's slope and intercept (pounds = slope * raw + intercept)
# are saved in the P&ID (cal_gain / cal_offset on the load cell) and applied by the GUI as the data arrives.
# This window finds them, like the loadcell_cal sketch:
#   1. pick a load cell (every cell shows its live raw count, pounds and calibration at all times);
#   2. capture a ZERO point with nothing on it, then add known weights;
#   3. read off the slope and intercept (the same least-squares fit the sketch prints) and save them to the P&ID
#      (or copy them). They take effect immediately and are written to the P&ID file.
# Each point is the middle half of 20 raw counts taken 100 ms apart (the firmware's update rate), lowest and
# highest quarter thrown away, as in the sketch. Points are saved in gui_settings.ini between sessions.

LC_CAL_SAMPLES = 20            # raw counts averaged per point (as in the sketch)
LC_CAL_MAX_POINTS = 12         # per load cell (as in the sketch)
LC_CAL_SPREAD_WARN = 1000      # a point whose readings span more than this many counts had bad samples
LC_CAL_STEADY = 60             # live raw within this many counts over 2 s counts as "steady"
LC_CAL_STALE_S = 1.0           # no data for this long = the cell is not reporting
_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_settings.ini")
_LC_GREEN, _LC_AMBER, _LC_RED, _LC_GREY, _LC_BLUE = "#1e8e3e", "#e08700", "#c62828", "#8a8880", "#4488ff"


def lc_trimmed_middle_mean(samples):
    """Sort, drop the lowest and highest quarter, average the middle half (the sketch's averageRaw).
    Returns (average, min, median, max, number used)."""
    s = sorted(samples)
    n = len(s)
    cut = n // 4
    mid = s[cut:n - cut] or s
    return sum(mid) / len(mid), s[0], s[n // 2], s[-1], len(mid)


def lc_fit_line(points):
    """Least-squares weight = slope * raw + intercept over [(weight, raw), ...] - the sketch's
    updateCalibration. Returns dict(slope, intercept, r2, max_err, errors), or None when it can't be
    fitted (fewer than 2 points, or no change in the raw counts)."""
    n = len(points)
    if n < 2:
        return None
    xs = [float(p[1]) for p in points]
    ys = [float(p[0]) for p in points]
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-9:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    errors = [slope * x + intercept - y for x, y in zip(xs, ys)]
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum(e * e for e in errors)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0
    return {"slope": slope, "intercept": intercept, "r2": r2,
            "max_err": max(abs(e) for e in errors), "errors": errors}


def lc_plain(x: float) -> str:
    """A float as a plain decimal at full precision (no 2.5e-05), ready to paste anywhere."""
    return format(Decimal(repr(float(x))), "f")


def lc_decode_location(info: int) -> str:
    """'JLC1 · VIN2 · shared chip' from the hardware info byte the firmware sends with each raw count."""
    jlc, vin, shared = (info >> 4) & 0xF, (info >> 1) & 0x7, info & 1
    return f"JLC{jlc} · VIN{vin}" + (" · shared chip" if shared else "")


def _lc_card(title: str, subtitle: str = ""):
    frame = QFrame()
    frame.setObjectName("config_card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 12, 16, 14)
    lay.setSpacing(8)
    t = QLabel(title)
    t.setObjectName("panel_section_title")
    lay.addWidget(t)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        sub.setObjectName("sensor_unit_label")
        lay.addWidget(sub)
    return frame, lay


def _lc_big(label: QLabel, pt: int = 16):
    f = QFont()
    f.setPointSize(pt)
    f.setBold(True)
    f.setFamily("Consolas")
    label.setFont(f)


class _LcCard(QFrame):
    """One load cell in the left column: name, live values and calibration status. Click to select."""

    def __init__(self, key: str, on_click):
        super().__init__()
        self.key = key
        self._on_click = on_click
        self.setObjectName("lc_card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)

        top = QHBoxLayout()
        self.dot = QLabel("●")
        self.name = QLabel(key)
        self.name.setStyleSheet("font-weight: bold; font-size: 13pt;")
        self.loc = QLabel("")
        self.loc.setObjectName("sensor_unit_label")
        top.addWidget(self.dot)
        top.addWidget(self.name)
        top.addStretch()
        top.addWidget(self.loc)
        lay.addLayout(top)

        mid = QHBoxLayout()
        self.raw = QLabel("--")
        _lc_big(self.raw, 14)
        self.lbf = QLabel("")
        self.lbf.setStyleSheet("font-weight: bold;")
        mid.addWidget(self.raw)
        mid.addStretch()
        mid.addWidget(self.lbf)
        lay.addLayout(mid)

        self.pid = QLabel("")
        self.pid.setObjectName("sensor_unit_label")
        self.pid.setWordWrap(True)
        lay.addWidget(self.pid)
        self.fit = QLabel("")
        self.fit.setObjectName("sensor_unit_label")
        self.fit.setWordWrap(True)
        lay.addWidget(self.fit)
        self.set_selected(False)

    def mousePressEvent(self, event):
        self._on_click(self.key)

    def set_selected(self, sel: bool):
        self.setStyleSheet(
            f"QFrame#lc_card {{ border: 2px solid {_LC_BLUE if sel else 'rgba(128,128,128,0.35)'}; "
            f"border-radius: 8px; background-color: {'rgba(68,136,255,0.10)' if sel else 'rgba(128,128,128,0.06)'}; }}")


class LoadCellCalibrationWindow(QDialog):
    def __init__(self, controller, parent=None, settings_path=_SETTINGS_PATH):
        super().__init__(parent)
        self.controller = controller
        self._settings_path = settings_path
        self.setWindowTitle("Load Cell Calibration")
        self.resize(1240, 940)
        self.setModal(False)

        self.keys = [str(k).upper() for k in controller.lc_keys]
        self.selected = self.keys[0] if self.keys else ""
        self.points = self._load_points()              # "LC3" -> [(weight, raw, pounds shown then), ...]
        self._hist = {k: deque(maxlen=40) for k in self.keys}     # (time, live raw) for the steady check
        self._capture = None
        self._cap_timer = QTimer(self)
        self._cap_timer.setInterval(100)               # the firmware recomputes load cells at 10 Hz
        self._cap_timer.timeout.connect(self._cap_tick)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("Load Cell Calibration")
        title.setObjectName("panel_section_title")
        head.addWidget(title)
        head.addStretch()
        self.banner = QLabel("")
        self.banner.setStyleSheet("font-weight: bold;")
        head.addWidget(self.banner)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        # ── left: every load cell, live ────────────────────────────────────────────────
        left = QVBoxLayout()
        left.setSpacing(8)
        hint = QLabel("Click a load cell to calibrate it. Every cell keeps showing its live value, so you can "
                      "watch the others while you work.")
        hint.setObjectName("sensor_unit_label")
        hint.setWordWrap(True)
        left.addWidget(hint)
        self.cards = {}
        for k in self.keys:
            card = _LcCard(k, self.select)
            self.cards[k] = card
            left.addWidget(card)
        left.addStretch()
        left_w = QWidget()
        left_w.setLayout(left)
        left_scroll = QScrollArea()                    # scrolls instead of squeezing on a small screen
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setWidget(left_w)
        left_scroll.setFixedWidth(352)
        body.addWidget(left_scroll)

        # ── right: workflow + factors ───────────────────────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(10)
        right_w = QWidget()
        right_w.setLayout(right)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setWidget(right_w)
        body.addWidget(right_scroll, 1)

        work, wl = _lc_card("CALIBRATE")
        self.work_title = QLabel("")
        self.work_title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        wl.addWidget(self.work_title)

        live = QHBoxLayout()
        self.live_raw = QLabel("--")
        _lc_big(self.live_raw, 22)
        self.live_lbf = QLabel("")
        _lc_big(self.live_lbf, 14)
        self.live_state = QLabel("")
        live.addWidget(QLabel("Raw count"))
        live.addWidget(self.live_raw)
        live.addSpacing(20)
        live.addWidget(self.live_lbf)
        live.addStretch()
        live.addWidget(self.live_state)
        wl.addLayout(live)

        steps = QGridLayout()
        steps.setHorizontalSpacing(10)
        steps.addWidget(self._step_label("1"), 0, 0)
        self.zero_btn = QPushButton("Capture ZERO  (nothing on the load cell)")
        self.zero_btn.clicked.connect(self._capture_zero)
        steps.addWidget(self.zero_btn, 0, 1, 1, 3)
        steps.addWidget(self._step_label("2"), 1, 0)
        steps.addWidget(QLabel("Put a KNOWN weight on it:"), 1, 1)
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0.01, 100000.0)
        self.weight.setDecimals(2)
        self.weight.setValue(10.0)
        self.weight.setSuffix(" lbf")
        self.weight.setMinimumWidth(130)
        steps.addWidget(self.weight, 1, 2)
        self.point_btn = QPushButton("Capture point")
        self.point_btn.clicked.connect(self._capture_point)
        steps.addWidget(self.point_btn, 1, 3)
        steps.setColumnStretch(1, 1)
        wl.addLayout(steps)

        self.progress = QProgressBar()
        self.progress.setRange(0, LC_CAL_SAMPLES)
        self.progress.setTextVisible(True)
        self.progress.setVisible(False)
        wl.addWidget(self.progress)
        self.msg = QLabel("")
        self.msg.setWordWrap(True)
        wl.addWidget(self.msg)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["#", "Weight (lbf)", "Raw count", "Showed (lbf)", "Fit error (lbf)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setMinimumHeight(170)
        wl.addWidget(self.table)

        row = QHBoxLayout()
        self.del_btn = QPushButton("Delete selected point")
        self.del_btn.clicked.connect(self._delete_point)
        self.clear_btn = QPushButton("Clear all points for this load cell")
        self.clear_btn.clicked.connect(self._clear_points)
        row.addWidget(self.del_btn)
        row.addWidget(self.clear_btn)
        row.addStretch()
        wl.addLayout(row)

        # the new fit
        self.res_line = QLabel("")
        self.res_line.setObjectName("sensor_unit_label")
        self.res_line.setWordWrap(True)
        wl.addWidget(self.res_line)
        res = QGridLayout()
        self.slope_val, self.int_val = QLabel("--"), QLabel("--")
        for lab in (self.slope_val, self.int_val):
            _lc_big(lab, 13)
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.slope_copy = QPushButton("Copy slope")
        self.int_copy = QPushButton("Copy intercept")
        self.save_fit = QPushButton("Save to P&&ID")
        self.save_fit.setToolTip("Write this slope and intercept into the load cell's entry in the P&ID file "
                                 "and start using them now")
        self.save_fit.setStyleSheet(f"background-color: {_LC_BLUE}; color: white; font-weight: bold;")
        self.slope_copy.clicked.connect(lambda: self._copy(self._fit_text("slope")))
        self.int_copy.clicked.connect(lambda: self._copy(self._fit_text("intercept")))
        self.save_fit.clicked.connect(self._save_fit_to_pid)
        res.addWidget(QLabel("NEW SLOPE"), 0, 0)
        res.addWidget(self.slope_val, 0, 1)
        res.addWidget(self.slope_copy, 0, 2)
        res.addWidget(QLabel("NEW INTERCEPT"), 1, 0)
        res.addWidget(self.int_val, 1, 1)
        res.addWidget(self.int_copy, 1, 2)
        res.addWidget(self.save_fit, 0, 3, 2, 1)
        res.setColumnStretch(1, 1)
        wl.addLayout(res)

        # what is in the P&ID now (editable by hand)
        pid = QHBoxLayout()
        pid.addWidget(QLabel("<b>In the P&ID now:</b>  slope"))
        self.pid_slope = QLineEdit()
        self.pid_slope.setPlaceholderText("none")
        pid.addWidget(self.pid_slope, 1)
        pid.addWidget(QLabel("intercept"))
        self.pid_int = QLineEdit()
        self.pid_int.setPlaceholderText("none")
        pid.addWidget(self.pid_int, 1)
        self.pid_save = QPushButton("Save typed values")
        self.pid_save.clicked.connect(self._save_typed_to_pid)
        pid.addWidget(self.pid_save)
        for ed in (self.pid_slope, self.pid_int):
            ed.setFont(QFont("Consolas", 9))
        wl.addLayout(pid)
        right.addWidget(work)

        fac, fl = _lc_card("CALIBRATION FACTORS - ALL LOAD CELLS",
                           "Always here, whichever cell you are working on: the new fit from your points next to "
                           "what the P&ID has now. Save any cell's fit to the P&ID, or copy it.")
        self.factors = QTableWidget(len(self.keys), 9)
        self.factors.setHorizontalHeaderLabels(["Load cell", "Points", "New slope", "New intercept", "R²",
                                                "P&ID slope", "P&ID intercept", "", ""])
        self.factors.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.factors.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.factors.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.factors.verticalHeader().setVisible(False)
        self.factors.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.factors.setSelectionMode(QAbstractItemView.NoSelection)
        self.factors.setFocusPolicy(Qt.NoFocus)
        self.factors.setFixedHeight(min(40 + 34 * max(len(self.keys), 1), 260))
        self._copy_btns, self._save_btns = {}, {}        # one pair of buttons per row, created once
        for r, k in enumerate(self.keys):
            cb, sb = QPushButton("Copy"), QPushButton("Save")
            for b in (cb, sb):
                b.setEnabled(False)
            cb.clicked.connect(lambda _=False, kk=k: self._copy(self._lines_for(kk)))
            sb.clicked.connect(lambda _=False, kk=k: self._save_fit_to_pid(kk))
            sb.setToolTip("Save this cell's new fit to the P&ID")
            self.factors.setCellWidget(r, 7, cb)
            self.factors.setCellWidget(r, 8, sb)
            self.factors.setRowHeight(r, 34)
            self._copy_btns[k], self._save_btns[k] = cb, sb
        fl.addWidget(self.factors)
        frow = QHBoxLayout()
        self.copy_all = QPushButton("Copy all new fits")
        self.copy_all.clicked.connect(lambda: self._copy(self._all_lines()))
        self.save_all = QPushButton("Save all new fits to the P&&ID")
        self.save_all.clicked.connect(self._save_all_to_pid)
        frow.addWidget(self.copy_all)
        frow.addWidget(self.save_all)
        frow.addStretch()
        fl.addLayout(frow)
        right.addWidget(fac)

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._tick)
        self.select(self.selected, force=True)
        self._timer.start()

    # ── small helpers ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _step_label(n: str) -> QLabel:
        lab = QLabel(n)
        lab.setAlignment(Qt.AlignCenter)
        lab.setFixedSize(26, 26)
        lab.setStyleSheet(f"background-color: {_LC_BLUE}; color: white; border-radius: 13px; font-weight: bold;")
        return lab

    def _name(self, key: str) -> str:
        try:
            return self.controller.sensor_display_name(key)
        except Exception:
            return key

    def _copy(self, text: str):
        QApplication.clipboard().setText(text)
        self._say("Copied to the clipboard.", _LC_GREEN)

    def _say(self, text: str, colour: str = ""):
        self.msg.setText(text)
        self.msg.setStyleSheet(f"color: {colour};" if colour else "")

    def _pts(self, key=None):
        return self.points.setdefault(key or self.selected, [])

    def _fit(self, key=None):
        return lc_fit_line([(p[0], p[1]) for p in self._pts(key)])

    def _fit_text(self, what: str) -> str:
        f = self._fit()
        return lc_plain(f[what]) if f else ""

    def _lines_for(self, key: str) -> str:
        f = self._fit(key)
        if not f:
            return ""
        return (f"// {key} ({self._name(key)}): pounds = slope * raw + intercept\n"
                f"slope     = {lc_plain(f['slope'])}\nintercept = {lc_plain(f['intercept'])}")

    def _all_lines(self) -> str:
        blocks = [b for b in (self._lines_for(k) for k in self.keys) if b]
        return "\n\n".join(blocks) if blocks else "No load cell has two or more calibration points yet."

    # ── saved points (gui_settings.ini) ────────────────────────────────────────────────────
    def _qs(self):
        return QSettings(self._settings_path, QSettings.IniFormat)

    def _load_points(self) -> dict:
        qs, out = self._qs(), {}
        for k in self.keys:
            try:
                v = qs.value(f"lc_cal/points_{k}", "[]") or "[]"
                if isinstance(v, (list, tuple)):          # QSettings may split a value containing commas
                    v = ",".join(v)
                out[k] = [tuple(p) for p in json.loads(str(v))]
            except (ValueError, TypeError):
                out[k] = []
        return out

    def _save_points(self):
        qs = self._qs()
        for k in self.keys:
            qs.setValue(f"lc_cal/points_{k}", json.dumps([list(p) for p in self.points.get(k, [])]))
        qs.sync()

    # ── the P&ID ───────────────────────────────────────────────────────────────────────────
    def _pid_cal(self, key):
        """(slope, intercept) the GUI is using for this cell (loaded from / saved to the P&ID), or None."""
        return self.controller.calibrations.get(key)

    def _component(self, key):
        project = self.controller.project
        if project is None:
            return None
        for comp in project.components.values():
            if str(comp.extras.get("hw_id") or comp.label or comp.id).upper() == key:
                return comp
        return None

    def _write_pid(self, key, slope: float, intercept: float) -> bool:
        """Put slope / intercept (full precision) on the load cell in the P&ID, use them now, save the file."""
        comp = self._component(key)
        if comp is None or not (slope and math.isfinite(slope) and math.isfinite(intercept)):
            self._say(f"Could not save {key}: not found in the P&ID, or the numbers are not valid.", _LC_RED)
            return False
        comp.extras["cal_gain"] = float(slope)
        comp.extras["cal_offset"] = float(intercept)
        self.controller.set_calibration(key, float(slope), float(intercept))
        path = self.controller.project_path
        if not path:
            self._say(f"{key}: in use now, but this project has no file path, so it was not saved to disk.", _LC_AMBER)
            return True
        try:
            self.controller.project.save(path)
        except Exception as e:
            QMessageBox.warning(self, "Save Failed", f"{key} is in use now, but the P&ID file could not be saved:\n{e}")
            return False
        return True

    def _save_fit_to_pid(self, key=None):
        key = key if isinstance(key, str) else self.selected
        f = self._fit(key)
        if f and self._write_pid(key, f["slope"], f["intercept"]):
            self._say(f"{key}: saved to the P&ID and in use now (slope {f['slope']:.6g}, intercept {f['intercept']:.6g}).",
                      _LC_GREEN)
        self._tick()
        self._refresh_work()

    def _save_all_to_pid(self):
        done = [k for k in self.keys if self._fit(k) and self._write_pid(k, *(self._fit(k)[x] for x in ("slope", "intercept")))]
        self._say(f"Saved to the P&ID: {', '.join(done)}." if done else "No load cell has a fit to save yet.",
                  _LC_GREEN if done else _LC_AMBER)
        self._tick()
        self._refresh_work()

    def _save_typed_to_pid(self):
        try:
            a, b = float(self.pid_slope.text()), float(self.pid_int.text())
        except ValueError:
            self._say("Type a number in both the slope and intercept boxes.", _LC_RED)
            return
        if self._write_pid(self.selected, a, b):
            self._say(f"{self.selected}: typed values saved to the P&ID and in use now.", _LC_GREEN)
        self._tick()
        self._refresh_work()

    def _show_pid_fields(self):
        cal = self._pid_cal(self.selected)
        for ed, v in ((self.pid_slope, None if not cal else cal[0]), (self.pid_int, None if not cal else cal[1])):
            ed.setText("" if v is None else lc_plain(v))

    # ── live values ────────────────────────────────────────────────────────────────────────
    def _wire(self, key):
        """The latest raw count the Teensy sent for this cell, or None."""
        recent = self.controller.sensor_recent.get(key)
        if not recent:
            return None
        w = recent[-1]
        return None if (w != w) else float(w)

    def _fresh(self, key) -> bool:
        t = self.controller.sensor_last_rx.get(key)
        return t is not None and time.time() - t < LC_CAL_STALE_S

    def _is_raw(self, key) -> bool:
        return key in self.controller.raw_sensor_names

    def _location(self, key) -> str:
        info = getattr(self.controller.ethernet_client, "lc_info", {}).get(key)
        return lc_decode_location(info) if info is not None else ""

    # ── selection / updates ────────────────────────────────────────────────────────────────
    def select(self, key: str, force: bool = False):
        if not key or (key == self.selected and not force):
            return
        if self._capture is not None:
            self._say("Wait for the capture in progress to finish first.", _LC_AMBER)
            return
        self.selected = key
        for k, c in self.cards.items():
            c.set_selected(k == key)
        self._say("")
        self._show_pid_fields()
        self._refresh_work()

    def _tick(self):
        c = self.controller
        now = time.monotonic()
        any_fresh, any_pounds = False, False
        for k, card in self.cards.items():
            raw = self._wire(k)
            lbf = c.current_sensor_values.get(k)
            fresh = self._fresh(k)
            sending_raw = self._is_raw(k)
            any_fresh = any_fresh or fresh
            any_pounds = any_pounds or (fresh and not sending_raw)
            if raw is not None and fresh and sending_raw:
                self._hist[k].append((now, raw))
            cal = self._pid_cal(k)
            if raw is None:
                card.raw.setText("--")
            else:
                card.raw.setText(f"{raw:,.0f}" if sending_raw else f"{raw:,.2f} lbf")
            card.lbf.setText("" if (lbf is None or not sending_raw or not cal) else f"= {lbf:,.2f} lbf")
            card.loc.setText(self._location(k))
            card.dot.setStyleSheet(f"color: {_LC_GREEN if fresh else _LC_GREY};")
            card.pid.setText(f"P&ID: slope {cal[0]:.6g} · intercept {cal[1]:.6g}" if cal else "no calibration in the P&ID yet")
            card.pid.setStyleSheet("" if cal else f"color: {_LC_AMBER};")
            f = self._fit(k)
            n = len(self.points.get(k, []))
            card.fit.setText(f"new fit: {n} points · R² {f['r2']:.5f}" if f
                             else (f"{n} point{'s' if n != 1 else ''} - need 2 to fit" if n else ""))
        if not self.keys:
            self.banner.setText("This project has no load cells")
            self.banner.setStyleSheet(f"color: {_LC_AMBER}; font-weight: bold;")
        elif not c.ethernet_client.connected:
            self.banner.setText("Not connected to the Teensy")
            self.banner.setStyleSheet(f"color: {_LC_AMBER}; font-weight: bold;")
        elif not any_fresh:
            self.banner.setText("Connected, but no load cell data is arriving")
            self.banner.setStyleSheet(f"color: {_LC_RED}; font-weight: bold;")
        elif any_pounds:
            self.banner.setText("A load cell is sending pounds, not raw counts - flash the new firmware")
            self.banner.setStyleSheet(f"color: {_LC_RED}; font-weight: bold;")
        else:
            self.banner.setText("Receiving live raw counts from the Teensy")
            self.banner.setStyleSheet(f"color: {_LC_GREEN}; font-weight: bold;")
        self._refresh_live()

    def _refresh_live(self):
        k = self.selected
        if not k:
            return
        raw = self._wire(k)
        lbf = self.controller.current_sensor_values.get(k)
        sending_raw = self._is_raw(k)
        cal = self._pid_cal(k)
        self.live_raw.setText("--" if raw is None else (f"{raw:,.0f}" if sending_raw else f"{raw:,.2f}"))
        self.live_lbf.setText("" if (lbf is None or not cal or not sending_raw) else f"= {lbf:,.2f} lbf")
        recent = [r for (t, r) in self._hist.get(k, ()) if time.monotonic() - t <= 2.0]
        if raw is None or not self._fresh(k):
            self.live_state.setText("no data")
            self.live_state.setStyleSheet(f"color: {_LC_GREY}; font-weight: bold;")
        elif not sending_raw:
            self.live_state.setText("sending pounds - needs the new firmware")
            self.live_state.setStyleSheet(f"color: {_LC_RED}; font-weight: bold;")
        elif len(recent) >= 5 and max(recent) - min(recent) > LC_CAL_STEADY:
            self.live_state.setText("settling")
            self.live_state.setToolTip(f"{max(recent) - min(recent):,.0f} counts of movement in the last 2 s")
            self.live_state.setStyleSheet(f"color: {_LC_AMBER}; font-weight: bold;")
        else:
            self.live_state.setText("steady  ✓")
            self.live_state.setStyleSheet(f"color: {_LC_GREEN}; font-weight: bold;")

    # ── capture ────────────────────────────────────────────────────────────────────────────
    def _start_capture(self, weight: float, label: str):
        k = self.selected
        if not k or self._capture is not None:
            return
        if len(self._pts()) >= LC_CAL_MAX_POINTS and not (weight == 0.0 and any(p[0] == 0.0 for p in self._pts())):
            QMessageBox.information(self, "Maximum points", f"{LC_CAL_MAX_POINTS} points per load cell is the "
                                    "maximum (delete one first).")
            return
        if not self._fresh(k) or self._wire(k) is None:
            self._say(f"No data from {k}. Is the Teensy connected and sending this load cell?", _LC_RED)
            return
        if not self._is_raw(k):
            self._say(f"{k} is sending pounds, not raw counts. Flash the new E2_Teensy firmware first.", _LC_RED)
            return
        self._capture = {"key": k, "weight": weight, "raw": [], "lbf": [], "ticks": 0}
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self._say(f"{label}: taking {LC_CAL_SAMPLES} readings (about {LC_CAL_SAMPLES // 10} s) - keep it still...")
        self._set_buttons()
        self._cap_timer.start()

    def _cap_tick(self):
        cap = self._capture
        if cap is None:
            self._cap_timer.stop()
            return
        cap["ticks"] += 1
        w = self._wire(cap["key"]) if self._fresh(cap["key"]) else None
        if w is not None:
            cap["raw"].append(w)
            lbf = self.controller.current_sensor_values.get(cap["key"])
            if lbf is not None:
                cap["lbf"].append(lbf)
            self.progress.setValue(len(cap["raw"]))
        if len(cap["raw"]) >= LC_CAL_SAMPLES:
            self._cap_timer.stop()
            self._finish_capture()
        elif cap["ticks"] > LC_CAL_SAMPLES * 4:
            self._cap_timer.stop()
            self._capture = None
            self.progress.setVisible(False)
            self._say("Capture timed out: the Teensy stopped sending this load cell.", _LC_RED)
            self._set_buttons()

    def _capture_zero(self):
        self._start_capture(0.0, "Zero")

    def _capture_point(self):
        self._start_capture(float(self.weight.value()), f"{self.weight.value():g} lbf")

    def _finish_capture(self):
        cap, self._capture = self._capture, None
        self.progress.setVisible(False)
        avg, lo, med, hi, used = lc_trimmed_middle_mean(cap["raw"])
        raw = int(round(avg))
        lbf = sum(cap["lbf"]) / len(cap["lbf"]) if cap["lbf"] else float("nan")
        pts = self._pts(cap["key"])
        if cap["weight"] == 0.0:                       # the zero point replaces an earlier zero
            pts[:] = [p for p in pts if p[0] != 0.0]
        pts.append((cap["weight"], raw, lbf))
        pts.sort(key=lambda p: p[0])
        self._save_points()
        note = (f"Saved: {cap['weight']:g} lbf = raw {raw:,}  (readings {lo:,.0f} / {med:,.0f} / {hi:,.0f} "
                "min / median / max)")
        if hi - lo > LC_CAL_SPREAD_WARN:
            note += f"  ⚠ large spread: some readings were bad and were ignored (used the middle {used})"
            self._say(note, _LC_AMBER)
        else:
            self._say(note, _LC_GREEN)
        self._refresh_work()

    # ── points ─────────────────────────────────────────────────────────────────────────────
    def _delete_point(self):
        r = self.table.currentRow()
        pts = self._pts()
        if 0 <= r < len(pts):
            pts.pop(r)
            self._save_points()
            self._refresh_work()

    def _clear_points(self):
        if not self._pts():
            return
        if QMessageBox.question(self, "Clear points", f"Delete all {len(self._pts())} calibration points for "
                                f"{self.selected}?", QMessageBox.Yes | QMessageBox.Cancel,
                                QMessageBox.Cancel) == QMessageBox.Yes:
            self.points[self.selected] = []
            self._save_points()
            self._refresh_work()

    # ── drawing the selected cell ──────────────────────────────────────────────────────────
    def _set_buttons(self):
        busy = self._capture is not None
        has_zero = any(p[0] == 0.0 for p in self._pts())
        self.zero_btn.setEnabled(not busy and bool(self.selected))
        self.point_btn.setEnabled(not busy and bool(self.selected))
        self.zero_btn.setText("Re-capture ZERO  (nothing on the load cell)" if has_zero
                              else "Capture ZERO  (nothing on the load cell)")
        self.del_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)

    def _refresh_work(self):
        k = self.selected
        nm = self._name(k) if k else ""
        self.work_title.setText((f"{k}  ·  {nm}" if nm and nm != k else k) if k else "No load cell selected")
        pts = self._pts() if k else []
        f = self._fit() if k else None
        self.table.setRowCount(len(pts))
        for i, p in enumerate(pts):
            vals = [str(i + 1), f"{p[0]:g}", f"{p[1]:,}",
                    "--" if p[2] != p[2] else f"{p[2]:,.2f}",
                    "--" if not f else f"{f['errors'][i]:+.3f}"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, c, it)
        if f:
            self.slope_val.setText(lc_plain(f["slope"]))
            self.int_val.setText(lc_plain(f["intercept"]))
            quality = "excellent" if f["max_err"] < 0.1 else "good" if f["max_err"] < 0.5 else "check the points"
            self.res_line.setText(f"{len(pts)} points · R² {f['r2']:.6f} · worst point is off by "
                                  f"{f['max_err']:.3f} lbf ({quality})")
        else:
            self.slope_val.setText("--")
            self.int_val.setText("--")
            need = ("capture a zero, then at least one known weight" if len(pts) < 2
                    else "the points show no change in raw count")
            self.res_line.setText(f"Not enough yet: {need}.")
        for b in (self.slope_copy, self.int_copy, self.save_fit):
            b.setEnabled(bool(f))
        self._show_pid_fields()
        self._set_buttons()
        self._refresh_factors()

    def _refresh_factors(self):
        for r, k in enumerate(self.keys):
            f = self._fit(k)
            cal = self._pid_cal(k)
            n = len(self.points.get(k, []))
            nm = self._name(k)
            full = [None, None, f["slope"] if f else None, f["intercept"] if f else None, None,
                    cal[0] if cal else None, cal[1] if cal else None]      # full-precision numbers for the tooltips
            cells = [f"{k}  {nm}" if nm != k else k, str(n),
                     f"{f['slope']:.7g}" if f else "—", f"{f['intercept']:.7g}" if f else "—",
                     f"{f['r2']:.5f}" if f else "—",
                     f"{cal[0]:.7g}" if cal else "—", f"{cal[1]:.7g}" if cal else "—"]
            for c, v in enumerate(cells):
                it = QTableWidgetItem(v)
                if full[c] is not None:
                    it.setToolTip(lc_plain(full[c]))
                it.setTextAlignment(Qt.AlignCenter if c else Qt.AlignLeft | Qt.AlignVCenter)
                if k == self.selected:
                    it.setBackground(self.palette().alternateBase())
                self.factors.setItem(r, c, it)
            self._copy_btns[k].setEnabled(bool(f))
            self._save_btns[k].setEnabled(bool(f))

    def closeEvent(self, event):
        self._timer.stop()
        self._cap_timer.stop()
        event.accept()


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
            "LOAD CELL CALIBRATION",
            "Calibrate the load cells: pick a cell, capture a zero, add known weights, and save the "
            "slope and intercept to the P&ID.")
        cal_row = QHBoxLayout()
        self._cal_btn = QPushButton("Open Load Cell Calibration…")
        self._cal_btn.clicked.connect(self._open_calibration)
        cal_row.addWidget(self._cal_btn)
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
        if not self.controller.lc_keys:
            QMessageBox.warning(self, "No Load Cells", "Load a project that has load cells first.")
            return
        win = getattr(self, "_lc_cal_window", None)
        if win is not None and win.isVisible():
            win.raise_()
            win.activateWindow()
            return
        self._lc_cal_window = LoadCellCalibrationWindow(self.controller, self)
        self._lc_cal_window.show()
