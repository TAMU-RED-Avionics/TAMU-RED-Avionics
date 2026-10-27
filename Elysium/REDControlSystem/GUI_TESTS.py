# GUI_TESTS.py
# Tests tab: operator-run hold tests. Right now one type, the leak check: pressurize the
# line first, then Start; the page watches the selected PTs for the test duration and shows
# each one's smoothed trace (raw in grey behind it), the change since the start value and
# the rate of change. No pass/fail yet (TODO: tolerance).
#
# The controller GUI runs and records the test and relays start/stop to viewer GUIs
# (controller.publish_test_event); a viewer follows along from the sensor stream it already
# receives but can't start, stop or reset anything. An abort or a lost link cancels the test.
import csv
import json
import math
import os
import time
from datetime import datetime
from typing import Dict, List

import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QComboBox,
    QDoubleSpinBox, QCheckBox, QScrollArea, QFrame, QSizePolicy,
)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from GUI_GRAPHS import sensor_unit, SERIES_COLORS_DARK, SERIES_COLORS_LIGHT
from GUI_HEALTH import _card
from TEST_ANALYSIS import SeriesTrack, SMOOTH_METHODS, SMOOTH_MEAN

TEST_TYPES = ["Leak check"]
IDLE, RUNNING, DONE = "idle", "running", "done"

TICK_MS    = 100     # countdown / end-of-test check
REFRESH_MS = 500     # re-analyse and redraw the graphs
GRAPH_WINDOWS = [("30 s", 30.0), ("1 min", 60.0), ("2 min", 120.0), ("Whole test", None)]
DATA_DIR = "Data"


def _fmt(x: float, digits: int = 2, signed: bool = False) -> str:
    if x is None or math.isnan(x):
        return "—"
    return f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"


def _clock(seconds: float) -> str:
    s = max(0, int(math.ceil(seconds)))
    return f"{s // 60:02d}:{s % 60:02d}"


class TestGraph(QWidget):
    """Raw (grey, behind) and smoothed (bold) trace against seconds since the test started,
    with the start value as a dashed line. Scrolls with a fixed time window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dark_mode = False
        self.figure = Figure()
        self.figure.set_constrained_layout(True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(170)
        self.ax = self.figure.add_subplot(111)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.canvas)
        self._style()

    def _colors(self):
        if self.dark_mode:
            return "#e8e6e0", "#1e1e24", "#44444f", "#6b6b78", SERIES_COLORS_DARK[0]
        return "#1a1a1a", "#ffffff", "#cccccc", "#b5b5b5", SERIES_COLORS_LIGHT[0]

    def _style(self):
        fg, bg, grid, self._raw_c, self._line_c = self._colors()
        self.figure.set_facecolor(bg)
        self.ax.clear()
        self.ax.set_facecolor(bg)
        self.ax.tick_params(colors=fg, labelsize=8)
        for sp in self.ax.spines.values():
            sp.set_color(grid)
        self.ax.grid(True, color=grid, linewidth=0.5)
        self.ax.set_xlabel("seconds since start", color=fg, fontsize=8)
        (self._raw_ln,) = self.ax.plot([], [], color=self._raw_c, linewidth=0.8, zorder=1)
        (self._sm_ln,) = self.ax.plot([], [], color=self._line_c, linewidth=1.8, zorder=3)
        self._base_ln = self.ax.axhline(math.nan, color=fg, linestyle="--", linewidth=0.8, alpha=0.6, zorder=2)

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        self._style()
        self.canvas.draw_idle()

    def clear(self):
        self._style()
        self.canvas.draw_idle()

    def update_data(self, res, x_window, duration: float, elapsed: float):
        self._raw_ln.set_data(res.t_raw, res.raw)
        self._sm_ln.set_data(res.t_smooth, res.smooth)
        self._base_ln.set_ydata([res.baseline, res.baseline])
        if x_window is None:
            lo, hi = 0.0, max(duration, 10.0)
        else:
            hi = max(elapsed, x_window)
            lo = hi - x_window
        self.ax.set_xlim(lo, hi)
        if len(res.t_raw):
            m = res.t_raw >= lo
            raw, sm = res.raw[m], res.smooth[m]
            if len(raw):
                # Percentiles, not min/max: a single spike shouldn't flatten the real trace.
                y0 = min(np.percentile(raw, 2), sm.min())
                y1 = max(np.percentile(raw, 98), sm.max())
                if not math.isnan(res.baseline):
                    y0, y1 = min(y0, res.baseline), max(y1, res.baseline)
                pad = max((y1 - y0) * 0.1, 0.5)
                self.ax.set_ylim(y0 - pad, y1 + pad)
        self.canvas.draw_idle()


class PTCard(QFrame):
    def __init__(self, key: str, title: str, unit: str, parent=None):
        super().__init__(parent)
        self.key, self.unit = key, unit
        self.setObjectName("config_card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)
        self.title = QLabel(title)
        self.title.setObjectName("panel_section_title")
        lay.addWidget(self.title)
        self.graph = TestGraph()
        lay.addWidget(self.graph, stretch=1)
        self.stats = QLabel("")
        self.stats.setTextFormat(Qt.RichText)
        lay.addWidget(self.stats)
        self.clear()

    def clear(self):
        self.graph.clear()
        self.stats.setText(self._stats_html(None))

    def _stats_html(self, res) -> str:
        u = self.unit
        if res is None:
            start = now = delta = rate = "—"
        else:
            start, now = _fmt(res.baseline, 1), _fmt(res.current, 1)
            delta = f"{_fmt(res.delta, 2, True)} {u}" if not math.isnan(res.delta) else "—"
            rate = (f"{_fmt(res.rate, 2, True)} ± {_fmt(res.rate_err, 2)} {u}/min"
                    if not math.isnan(res.rate) else "—")
        return (f"<table width='100%'><tr>"
                f"<td>Start<br><b>{start}</b></td><td>Now<br><b>{now}</b></td>"
                f"<td>Δ since start<br><b>{delta}</b></td><td>Rate<br><b>{rate}</b></td>"
                f"</tr></table>")

    def update_result(self, res, x_window, duration, elapsed):
        self.graph.update_data(res, x_window, duration, elapsed)
        self.stats.setText(self._stats_html(res))


class TestsPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.state = IDLE
        self.cfg: dict = {}
        self.t0 = 0.0
        self.tracks: Dict[str, SeriesTrack] = {}
        self.cards: Dict[str, PTCard] = {}
        self._boxes: Dict[str, QCheckBox] = {}
        self._end_note = ""
        self._joined_late = False
        self._dark = False

        self._build_ui()

        sig = controller.signals
        sig.sensor_updated.connect(self._on_sensor)
        sig.project_changed.connect(self._on_project_changed)
        sig.abort_triggered.connect(lambda t, r, s: self._cancel(f"abort ({t})"))
        sig.disconnected.connect(lambda reason: self._cancel("connection lost"))
        sig.test_event.connect(self._on_remote_event)
        sig.view_only_changed.connect(lambda *_: self._on_view_only_changed())

        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._refresh = QTimer(self)
        self._refresh.timeout.connect(self._redraw)
        self._refresh.start(REFRESH_MS)

        self._rebuild_pt_list()
        self._sync_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        card, cl = _card("TEST SETUP", "Pressurize the line first, then press Start - the test "
                         "measures the hold from that moment. Smoothing is display-only; raw "
                         "data is always kept and saved.")
        top = QHBoxLayout()
        top.setSpacing(16)
        cl.addLayout(top)

        left = QGridLayout()
        left.setHorizontalSpacing(8)
        left.setVerticalSpacing(6)
        top.addLayout(left, stretch=0)

        def add(row, text, widget, tip=""):
            lbl = QLabel(text)
            lbl.setObjectName("sensor_unit_label")
            if tip:
                widget.setToolTip(tip)
                lbl.setToolTip(tip)
            left.addWidget(lbl, row, 0)
            left.addWidget(widget, row, 1)

        self.type_box = QComboBox()
        self.type_box.addItems(TEST_TYPES)
        add(0, "Test type", self.type_box)

        self.duration_box = QDoubleSpinBox()
        self.duration_box.setRange(0.5, 240.0)
        self.duration_box.setDecimals(1)
        self.duration_box.setValue(5.0)
        self.duration_box.setSuffix(" min")
        add(1, "Duration", self.duration_box)

        self.settle_box = QDoubleSpinBox()
        self.settle_box.setRange(0.0, 3600.0)
        self.settle_box.setDecimals(0)
        self.settle_box.setSuffix(" s")
        add(2, "Settle time", self.settle_box,
            "Ignore this many seconds at the start (e.g. gas cooling after pressurizing). "
            "The start value and the rate are measured after it.")

        self.method_box = QComboBox()
        self.method_box.addItems(SMOOTH_METHODS)
        self.method_box.setCurrentText(SMOOTH_MEAN)
        add(3, "Smoothing", self.method_box)

        self.window_box = QDoubleSpinBox()
        self.window_box.setRange(0.5, 60.0)
        self.window_box.setDecimals(1)
        self.window_box.setValue(3.0)
        self.window_box.setSuffix(" s")
        add(4, "Smoothing window", self.window_box,
            "Trailing window. Longer = smoother but the trace lags the pressure by about "
            "half of it.")

        self.xwin_box = QComboBox()
        for label, _ in GRAPH_WINDOWS:
            self.xwin_box.addItem(label)
        self.xwin_box.setCurrentText("Whole test")
        add(5, "Graph window", self.xwin_box)

        # PT selection
        right = QVBoxLayout()
        top.addLayout(right, stretch=1)
        hdr = QHBoxLayout()
        lbl = QLabel("Pressure transducers")
        lbl.setObjectName("sensor_unit_label")
        hdr.addWidget(lbl)
        hdr.addStretch()
        self.all_btn = QPushButton("All")
        self.none_btn = QPushButton("None")
        for b in (self.all_btn, self.none_btn):
            b.setObjectName("small_btn")
            hdr.addWidget(b)
        self.all_btn.clicked.connect(lambda: self._set_all(True))
        self.none_btn.clicked.connect(lambda: self._set_all(False))
        right.addLayout(hdr)
        self.pt_area = QScrollArea()
        self.pt_area.setWidgetResizable(True)
        self.pt_area.setFrameShape(QFrame.NoFrame)
        self.pt_area.setFixedHeight(120)
        self.pt_host = QWidget()
        self.pt_grid = QGridLayout(self.pt_host)
        self.pt_grid.setContentsMargins(0, 0, 0, 0)
        self.pt_area.setWidget(self.pt_host)
        right.addWidget(self.pt_area)
        outer.addWidget(card)

        # run bar
        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.reset_btn = QPushButton("Reset")
        for b in (self.start_btn, self.stop_btn, self.reset_btn):
            b.setMinimumHeight(34)
            bar.addWidget(b)
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        bar.addSpacing(16)
        self.clock_lbl = QLabel("--:--")
        self.clock_lbl.setStyleSheet("font-size: 28pt; font-weight: bold;")
        bar.addWidget(self.clock_lbl)
        bar.addSpacing(12)
        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        self.status_lbl.setObjectName("sensor_unit_label")
        bar.addWidget(self.status_lbl, stretch=1)
        outer.addLayout(bar)

        # graphs
        self.cards_host = QWidget()
        self.cards_grid = QGridLayout(self.cards_host)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.cards_host)
        outer.addWidget(scroll, stretch=1)

        for w in (self.method_box, self.window_box, self.xwin_box):
            sig = w.currentTextChanged if isinstance(w, QComboBox) else w.valueChanged
            sig.connect(lambda *_: self._redraw())

    # ------------------------------------------------------------ PT list
    def _rebuild_pt_list(self):
        keep = {k for k, b in self._boxes.items() if b.isChecked()}
        while self.pt_grid.count():
            item = self.pt_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._boxes = {}
        for i, key in enumerate(self.controller.pt_keys):
            box = QCheckBox(self.controller.sensor_display_name(key))
            box.setChecked(key in keep)
            box.toggled.connect(lambda *_: self._sync_ui())
            self._boxes[key] = box
            self.pt_grid.addWidget(box, i // 4, i % 4)
        self._sync_ui()

    def _set_all(self, on: bool):
        for b in self._boxes.values():
            b.setChecked(on)

    def _selected(self) -> List[str]:
        return [k for k, b in self._boxes.items() if b.isChecked()]

    def _on_project_changed(self):
        if self.state == RUNNING:
            self._cancel("project changed")
        if self.state != RUNNING:
            self._rebuild_pt_list()

    # -------------------------------------------------------------- state
    def _is_viewer(self) -> bool:
        return bool(self.controller.view_only)

    def _on_view_only_changed(self):
        if self.state == RUNNING:
            self._cancel("GUI mode changed")
        self._sync_ui()

    def _sync_ui(self):
        running = self.state == RUNNING
        viewer = self._is_viewer()
        locked = running or viewer
        for w in (self.type_box, self.duration_box, self.settle_box, self.all_btn, self.none_btn):
            w.setEnabled(not locked)
        for b in self._boxes.values():
            b.setEnabled(not locked)
        self.start_btn.setEnabled(self.state == IDLE and not viewer and bool(self._selected()))
        self.stop_btn.setEnabled(running and not viewer)
        self.reset_btn.setEnabled(self.state == DONE and not viewer)
        tip = "Viewers can watch a test but only the controller GUI can run one." if viewer else ""
        for b in (self.start_btn, self.stop_btn, self.reset_btn):
            b.setToolTip(tip)
        if self.state == IDLE:
            self.clock_lbl.setText(_clock(self.duration_box.value() * 60))
            self.status_lbl.setText(
                "Viewing: waiting for the controller to start a test." if viewer else
                ("Select at least one PT." if not self._selected() else "Ready."))

    def _on_start_clicked(self):
        if self._is_viewer() or self.state != IDLE or not self._selected():
            return
        if not self.controller.ethernet_client.connected:
            self.status_lbl.setText("Not connected to the Teensy - no data to test with.")
            return
        cfg = {"type": self.type_box.currentText(), "sensors": self._selected(),
               "duration": self.duration_box.value() * 60.0, "settle": self.settle_box.value()}
        self._begin(cfg, elapsed=0.0)
        self.controller.publish_test_event({"op": "start", "elapsed": 0.0, **cfg})

    def _begin(self, cfg: dict, elapsed: float):
        self.cfg = cfg
        self.t0 = time.time() - elapsed
        self._joined_late = elapsed > 1.0
        self.tracks = {k: SeriesTrack() for k in cfg["sensors"]}
        self._end_note = ""
        self.state = RUNNING
        self._build_cards(cfg["sensors"])
        self.duration_box.setValue(cfg["duration"] / 60.0)
        self.settle_box.setValue(cfg.get("settle", 0.0))
        self._tick.start(TICK_MS)
        self._sync_ui()
        self.status_lbl.setText("Joined mid-test: start value unavailable, rate and trend shown from now."
                                if self._joined_late else "Running.")

    def _build_cards(self, keys: List[str]):
        for c in self.cards.values():
            c.setParent(None)
            c.deleteLater()
        self.cards = {}
        for i, key in enumerate(keys):
            card = PTCard(key, self.controller.sensor_display_name(key), sensor_unit(key) or "psi")
            card.graph.set_dark_mode(self._dark)
            self.cards[key] = card
            self.cards_grid.addWidget(card, i // 2, i % 2)

    def _elapsed(self) -> float:
        return time.time() - self.t0

    def _on_sensor(self, name: str, value: float, _ts: float):
        if self.state != RUNNING:
            return
        tr = self.tracks.get(name)
        if tr is not None:
            tr.add(self._elapsed(), value)

    def _on_tick(self):
        if self.state != RUNNING:
            return
        el = self._elapsed()
        left = self.cfg["duration"] - el
        self.clock_lbl.setText(_clock(left))
        if self.controller.active_test is not None and not self._is_viewer():
            self.controller.active_test["elapsed"] = el      # for a viewer that joins mid-test
        if left <= 0 and not self._is_viewer():
            self._end("finish", "Finished.")

    def _on_stop_clicked(self):
        if self.state == RUNNING and not self._is_viewer():
            self._end("stop", "Stopped by operator.")

    def _on_reset_clicked(self):
        if self._is_viewer() or self.state != DONE:
            return
        self._reset()
        self.controller.publish_test_event({"op": "reset"})

    def _reset(self):
        self.state = IDLE
        self.tracks = {}
        for c in self.cards.values():
            c.setParent(None)
            c.deleteLater()
        self.cards = {}
        self._tick.stop()
        self._sync_ui()

    def _cancel(self, reason: str):
        """An abort or lost link ends the test; whatever was recorded is kept."""
        if self.state != RUNNING:
            return
        if self._is_viewer():
            self._finish_local("cancel", f"Cancelled: {reason}.")
        else:
            self._end("cancel", f"Cancelled: {reason}.")

    def _end(self, op: str, note: str):
        """Controller side: close the test, save it, tell viewers."""
        saved = self._finish_local(op, note)
        self.controller.publish_test_event({"op": op, "note": note})
        if saved:
            self.status_lbl.setText(f"{note} Saved {saved}")

    def _finish_local(self, op: str, note: str):
        el = min(self._elapsed(), self.cfg.get("duration", 0.0)) if op == "finish" else self._elapsed()
        self._tick.stop()
        self.state = DONE
        self._end_note = note
        self._redraw(final_elapsed=el)
        self.clock_lbl.setText("Done" if op == "finish" else ("Stopped" if op == "stop" else "Cancelled"))
        self.status_lbl.setText(note)
        self._sync_ui()
        if self._is_viewer():
            return None
        try:
            return self._save(op, note, el)
        except OSError as e:
            self.status_lbl.setText(f"{note} Could not save results: {e}")
            return None

    def _on_remote_event(self, msg: dict):
        """Viewer GUI: follow the controller's test."""
        if not self._is_viewer():
            return
        op = msg.get("op")
        if op == "start":
            if self.state == RUNNING:
                return
            if self.state == DONE:
                self._reset()
            cfg = {k: msg[k] for k in ("type", "sensors", "duration", "settle") if k in msg}
            self._begin(cfg, elapsed=float(msg.get("elapsed", 0.0)))
        elif op in ("stop", "finish", "cancel"):
            if self.state == RUNNING:
                self._finish_local(op, msg.get("note", ""))
        elif op == "reset":
            if self.state != RUNNING:
                self._reset()

    # ------------------------------------------------------------ drawing
    def _x_window(self):
        return GRAPH_WINDOWS[self.xwin_box.currentIndex()][1]

    def _redraw(self, final_elapsed: float = None):
        if self.state == IDLE or not self.tracks:
            return
        el = final_elapsed if final_elapsed is not None else self._elapsed()
        for key, card in self.cards.items():
            res = self.tracks[key].analyze(self.method_box.currentText(), self.window_box.value(),
                                           self.cfg.get("settle", 0.0))
            card.update_result(res, self._x_window(), self.cfg["duration"], el)

    def set_dark_mode(self, dark: bool):
        self._dark = dark
        for c in self.cards.values():
            c.graph.set_dark_mode(dark)

    # ------------------------------------------------------------- saving
    def _save(self, op: str, note: str, elapsed: float) -> str:
        proj = self.controller.project
        base = f"{getattr(proj, 'name', 'DAQ')}{getattr(proj, 'version', '') or ''}" if proj else "DAQ"
        base = f"LeakTest_{base}_{datetime.now().strftime('%m%d%Y')}".replace(" ", "_")
        os.makedirs(DATA_DIR, exist_ok=True)
        n = 1
        while os.path.exists(os.path.join(DATA_DIR, f"{base}_test{n}.csv")):
            n += 1
        stem = os.path.join(DATA_DIR, f"{base}_test{n}")

        with open(stem + ".csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_s", "sensor", "value"])
            for key, tr in self.tracks.items():
                t, v = tr.raw_arrays()
                for a, b in zip(t, v):
                    w.writerow([f"{a:.4f}", key, f"{b:.4f}"])

        method, window, settle = self.method_box.currentText(), self.window_box.value(), self.cfg.get("settle", 0.0)
        summary = {
            "test": self.cfg.get("type"), "result": op, "note": note,
            "started": datetime.fromtimestamp(self.t0).isoformat(timespec="seconds"),
            "planned_duration_s": self.cfg["duration"], "elapsed_s": round(elapsed, 2),
            "settle_s": settle, "smoothing": method, "smoothing_window_s": window,
            "sensors": {k: {"label": self.controller.sensor_display_name(k),
                            **tr.summary(method, window, settle)} for k, tr in self.tracks.items()},
        }
        with open(stem + ".json", "w") as f:
            json.dump(summary, f, indent=2)
        return stem + ".csv"
