# GUI_LIVEDATA.py
# Live Data tab: a full-size live plot of any mix of sensors and commanded
# signals, with drag-to-zoom, hover readout and a second (right-hand) y axis.
#
#   * Sensors come from controller.signals.sensor_updated.
#   * Commanded signals (what the GUI sent to a valve / actuator) come from
#     controller.signals.command_sent and are drawn as step traces.
#   * Every series sits on axis A (left) or B (right) - flip it with the A/B
#     button on its row - so psi and degrees (or a 0/1 command) can share a
#     plot without one being squashed flat.
#   * The view follows live data until you pause or drag-zoom; Back /
#     Ctrl+Z / right-click undoes a zoom, Home / Esc returns to the live view.
#
# The page only needs the controller's signals and its sensor / valve key
# lists, so it can be fed by any controller-shaped object (e.g. a read-only
# viewer controller).
from array import array
from bisect import bisect_left, bisect_right
from typing import Dict, List, Optional

import numpy as np
from PyQt5.QtCore import Qt, QDateTime, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QShortcut, QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.widgets import RectangleSelector

from GUI_GRAPHS import SERIES_COLORS_DARK, SERIES_COLORS_LIGHT, sensor_unit

WINDOWS = [("10 s", 10.0), ("30 s", 30.0), ("1 min", 60.0), ("5 min", 300.0), ("All", None)]
MAX_POINTS = 200_000          # per series; oldest trimmed beyond this (~30 min at 100 Hz)
TRIM_CHUNK = 50_000
RENDER_MS = 100
MAX_PLOT_POINTS = 3000        # per line; denser windows are min/max-decimated
HOVER_PX = 14
CMD_SUFFIX = " cmd"


class _Series:
    """Append-only (time, value) history in compact arrays."""
    __slots__ = ("ts", "val", "unit", "step")

    def __init__(self, unit: str = "", step: bool = False):
        self.ts = array("d")
        self.val = array("d")
        self.unit = unit
        self.step = step        # commanded signals hold their value between commands

    def append(self, t: float, v: float):
        self.ts.append(t)
        self.val.append(v)
        if len(self.ts) > MAX_POINTS:
            del self.ts[:TRIM_CHUNK]
            del self.val[:TRIM_CHUNK]

    def window(self, a0: float, a1: float):
        """Samples covering [a0, a1] plus one neighbour either side, as numpy copies."""
        n = len(self.ts)
        if n == 0:
            return np.empty(0), np.empty(0)
        i0 = max(bisect_left(self.ts, a0) - 1, 0)
        i1 = min(bisect_right(self.ts, a1) + 1, n)
        return np.array(self.ts[i0:i1]), np.array(self.val[i0:i1])


def _decimate(t: np.ndarray, v: np.ndarray):
    """Min/max bucket decimation: keeps spikes visible when a window holds far
    more samples than pixels."""
    n = len(t)
    if n <= MAX_PLOT_POINTS:
        return t, v
    k = n // (MAX_PLOT_POINTS // 2)
    m = n // k * k
    tt, vv = t[:m].reshape(-1, k), v[:m].reshape(-1, k)
    rows = np.arange(len(tt))
    imin, imax = vv.argmin(1), vv.argmax(1)
    t_lo, t_hi = tt[rows, imin], tt[rows, imax]
    v_lo, v_hi = vv[rows, imin], vv[rows, imax]
    first_is_min = t_lo <= t_hi
    ts = np.empty(2 * len(rows))
    vs = np.empty(2 * len(rows))
    ts[0::2] = np.where(first_is_min, t_lo, t_hi)
    vs[0::2] = np.where(first_is_min, v_lo, v_hi)
    ts[1::2] = np.where(first_is_min, t_hi, t_lo)
    vs[1::2] = np.where(first_is_min, v_hi, v_lo)
    return ts, vs


class _SeriesRow(QWidget):
    """Checkbox + A/B axis button for one plottable series."""

    def __init__(self, key: str, label: str, on_change, on_axis):
        super().__init__()
        self.key = key
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(4)
        self.check = QCheckBox(label)
        self.check.toggled.connect(lambda _c: on_change())
        lay.addWidget(self.check, stretch=1)
        self.axis_btn = QToolButton()
        self.axis_btn.setText("A")
        self.axis_btn.setFixedWidth(26)
        self.axis_btn.setToolTip("Axis: A = left y axis, B = right y axis (click to switch)")
        self.axis_btn.clicked.connect(lambda: on_axis(key))
        lay.addWidget(self.axis_btn)


class LiveDataPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = True

        self._series: Dict[str, _Series] = {}
        self._t0: Optional[float] = None
        self._rows: Dict[str, _SeriesRow] = {}
        self._axis_choice: Dict[str, str] = {}      # key -> "A" | "B" (user override)
        self._color_idx: Dict[str, int] = {}
        self._lines: dict = {}

        # View state. Following = x window tracks "now"; otherwise the view is
        # frozen at _manual_view. _zoom_stack holds views zoomed away from
        # (the string "LIVE" stands for the following view).
        self._following = True
        self._manual_view: Optional[dict] = None
        self._zoom_stack: list = []
        self._dirty = True

        self._build_ui()
        self._build_plot()
        self._connect_controller()
        self.refresh_series()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # UI -----------------------------------------------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QWidget()
        side.setFixedWidth(250)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(6, 6, 6, 6)
        title = QLabel("SERIES")
        title.setObjectName("browser_title")
        side_lay.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._list_host = QWidget()
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(2)
        scroll.setWidget(self._list_host)
        side_lay.addWidget(scroll, stretch=1)
        root.addWidget(side)

        div = QFrame()
        div.setFrameShape(QFrame.VLine)
        root.addWidget(div)

        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        bar = QWidget()
        bar_lay = QHBoxLayout(bar)
        bar_lay.setContentsMargins(8, 4, 8, 4)
        bar_lay.setSpacing(8)
        bar_lay.addWidget(QLabel("Window:"))
        self.window_combo = QComboBox()
        for label, secs in WINDOWS:
            self.window_combo.addItem(label, secs)
        self.window_combo.setCurrentIndex(1)
        self.window_combo.currentIndexChanged.connect(self._mark_dirty)
        bar_lay.addWidget(self.window_combo)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Freeze the view (data keeps recording). Resume = Home.")
        self.pause_btn.clicked.connect(self._toggle_pause)
        bar_lay.addWidget(self.pause_btn)
        self.back_btn = QPushButton("Back")
        self.back_btn.setToolTip("Undo the last zoom (Backspace / Ctrl+Z / right-click)")
        self.back_btn.clicked.connect(self.zoom_back)
        bar_lay.addWidget(self.back_btn)
        self.home_btn = QPushButton("Live View")
        self.home_btn.setToolTip("Clear zoom and follow live data again (Home / Esc)")
        self.home_btn.clicked.connect(self.zoom_home)
        bar_lay.addWidget(self.home_btn)
        self.clear_btn = QPushButton("Clear Data")
        self.clear_btn.setToolTip("Discard the plotted history and restart the time axis at 0")
        self.clear_btn.clicked.connect(self.clear_data)
        bar_lay.addWidget(self.clear_btn)
        bar_lay.addStretch()
        self.status_lbl = QLabel("")
        bar_lay.addWidget(self.status_lbl)
        right_lay.addWidget(bar)

        self.fig = Figure()
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_lay.addWidget(self.canvas, stretch=1)

        hint = QLabel("Drag on the plot to zoom to that box  ·  Back / Ctrl+Z / right-click: undo zoom"
                      "  ·  Home / Esc: live view  ·  A/B button on a series: choose its y axis")
        hint.setContentsMargins(8, 2, 8, 2)
        right_lay.addWidget(hint)
        root.addWidget(right, stretch=1)

        for keys, slot in (
            (("Backspace", "Ctrl+Z", "Alt+Left"), self.zoom_back),
            (("Home", "Esc"), self.zoom_home),
        ):
            for key in keys:
                sc = QShortcut(QKeySequence(key), self)
                sc.setContext(Qt.WidgetWithChildrenShortcut)
                sc.activated.connect(slot)

    def _build_plot(self):
        self.fig.clear()
        self.ax_a = self.fig.add_subplot(111)
        self.ax_b = self.ax_a.twinx()          # topmost axes: receives mouse events
        self.fig.subplots_adjust(left=0.07, right=0.93, top=0.95, bottom=0.11)
        self._apply_theme()
        self._annot = self.ax_b.annotate(
            "", xy=(0, 0), xytext=(14, 14), textcoords="offset points", fontsize=10,
            fontfamily="monospace", zorder=30,
            bbox=dict(boxstyle="round,pad=0.6", fc="#2a2a38", ec="#8b1a1a", lw=1.6, alpha=0.97))
        self._annot.set_visible(False)
        self._lines.clear()
        self._selector = RectangleSelector(
            self.ax_b, self._on_zoom_select, useblit=False, button=[1],
            minspanx=6, minspany=6, spancoords="pixels", interactive=False,
            props=dict(facecolor="#3b82f6", edgecolor="#3b82f6", alpha=0.25))
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self._rebuild_lines()

    def _theme(self):
        if self.dark_mode:
            return "#e8e6e0", "#1e1e24", "#44444f", "#2a2a38"
        return "#1a1a1a", "#ffffff", "#cccccc", "#ffffff"

    def _apply_theme(self):
        fg, bg, grid, _ = self._theme()
        self.fig.set_facecolor(bg)
        for ax in (self.ax_a, self.ax_b):
            ax.set_facecolor(bg if ax is self.ax_a else "none")
            ax.tick_params(colors=fg, labelsize=9)
            for sp in ax.spines.values():
                sp.set_color(grid)
        self.ax_a.grid(True, color=grid, linestyle="--", linewidth=0.5, alpha=0.7)
        self.ax_a.set_xlabel("Time (s)", color=fg, fontsize=10, fontfamily="monospace")

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        self._apply_theme()
        fg, bg, grid, annot_bg = self._theme()
        self._annot.get_bbox_patch().set_facecolor(annot_bg)
        self._annot.set_color(fg)
        self._rebuild_lines()

    # CONTROLLER ---------------------------------------------------------------------------------------------------

    def _connect_controller(self):
        sig = self.controller.signals
        sig.sensor_updated.connect(self._on_sensor)
        cmd = getattr(sig, "command_sent", None)
        if cmd is not None:
            cmd.connect(self._on_command)

    def _ensure_series(self, key: str, unit: str, step: bool) -> _Series:
        s = self._series.get(key)
        if s is None:
            s = self._series[key] = _Series(unit, step)
        return s

    def _on_sensor(self, name: str, value: float, timestamp: float):
        if self._t0 is None:
            self._t0 = timestamp
        self._ensure_series(name, sensor_unit(name), False).append(timestamp, value)

    def _on_command(self, name: str, value: float, timestamp: float):
        if self._t0 is None:
            self._t0 = timestamp
        key = name + CMD_SUFFIX
        spec = getattr(self.controller, "actuator_specs", {}).get(name)
        unit = getattr(spec, "unit", "%") if spec is not None else "0/1"
        self._ensure_series(key, unit, True).append(timestamp, value)

    def load_project(self, project=None):
        self.refresh_series()

    def refresh_series(self):
        """Rebuild the series list from the controller's sensor / valve keys,
        keeping what was ticked and its axis."""
        ticked = {k for k, r in self._rows.items() if r.check.isChecked()}
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()                # deleteLater alone leaves a ghost until the event loop runs
                w.setParent(None)
                w.deleteLater()
        self._rows.clear()
        c = self.controller
        groups = [
            ("Pressure Transducers", [(k, k) for k in c.pt_keys]),
            ("Thermocouples", [(k, k) for k in c.tc_keys]),
            ("Load Cells", [(k, k) for k in c.lc_keys]),
            ("Commands sent", [(k + CMD_SUFFIX, f"{k.strip() or '(unnamed valve)'} (sent)")
                               for k in sorted(c.valve_states)]),
        ]
        for title, items in groups:
            if not items:
                continue
            head = QLabel(title)
            head.setObjectName("panel_section_title")
            self._list_lay.addWidget(head)
            for key, label in items:
                row = _SeriesRow(key, label, self._on_selection_changed, self._toggle_axis)
                row.check.blockSignals(True)
                row.check.setChecked(key in ticked)
                row.check.blockSignals(False)
                self._rows[key] = row
                self._list_lay.addWidget(row)
        self._list_lay.addStretch()
        self._sync_axis_buttons()
        self._rebuild_lines()

    # SERIES / AXES ------------------------------------------------------------------------------------------------

    def _checked(self) -> List[str]:
        return [k for k, r in self._rows.items() if r.check.isChecked()]

    def _unit_of(self, key: str) -> str:
        s = self._series.get(key)
        if s is not None:
            return s.unit
        return "0/1" if key.endswith(CMD_SUFFIX) else sensor_unit(key)

    def _axis_of(self, key: str) -> str:
        """User's choice, else by unit: the first ticked series' unit is axis A,
        anything with a different unit goes to B."""
        if key in self._axis_choice:
            return self._axis_choice[key]
        for other in self._checked():
            if other == key:
                return "A"
            if other in self._axis_choice:
                continue
            return "A" if self._unit_of(key) == self._unit_of(other) else "B"
        return "A"

    def _toggle_axis(self, key: str):
        self._axis_choice[key] = "B" if self._axis_of(key) == "A" else "A"
        self._on_selection_changed()

    def _sync_axis_buttons(self):
        for key, row in self._rows.items():
            row.axis_btn.setText(self._axis_of(key))

    def _on_selection_changed(self):
        self._sync_axis_buttons()
        self._rebuild_lines()

    def _color(self, key: str) -> str:
        if key not in self._color_idx:
            self._color_idx[key] = len(self._color_idx)
        pal = SERIES_COLORS_DARK if self.dark_mode else SERIES_COLORS_LIGHT
        return pal[self._color_idx[key] % len(pal)]

    def _rebuild_lines(self):
        for line in self._lines.values():
            line.remove()
        self._lines.clear()
        fg, bg, grid, _ = self._theme()
        units = {"A": [], "B": []}
        for key in self._checked():
            ax_name = self._axis_of(key)
            ax = self.ax_a if ax_name == "A" else self.ax_b
            s = self._series.get(key)
            step = (s.step if s is not None else key.endswith(CMD_SUFFIX))
            line, = ax.plot([], [], color=self._color(key), linewidth=2,
                            linestyle="--" if step else "-",
                            drawstyle="steps-post" if step else "default",
                            label=f"{key} [{ax_name}]")
            self._lines[key] = line
            u = self._unit_of(key)
            if u and u not in units[ax_name]:
                units[ax_name].append(u)
        self.ax_a.set_ylabel("A: " + (", ".join(units["A"]) or "-"), color=fg,
                             fontsize=10, fontfamily="monospace")
        self.ax_b.set_ylabel("B: " + (", ".join(units["B"]) or "-"), color=fg,
                             fontsize=10, fontfamily="monospace")
        self.ax_b.yaxis.set_label_position("right")
        leg = self.ax_b.get_legend()
        if leg is not None:
            leg.remove()
        if self._lines:
            leg = self.ax_b.legend(list(self._lines.values()), [l.get_label() for l in self._lines.values()],
                                   loc="upper left", fontsize=9, framealpha=0.85,
                                   facecolor=bg, edgecolor=grid, labelcolor=fg)
            for t in leg.get_texts():
                t.set_fontfamily("monospace")
        self._annot.set_visible(False)
        self._mark_dirty()

    # VIEW STATE ---------------------------------------------------------------------------------------------------

    def _now_rel(self) -> float:
        return QDateTime.currentMSecsSinceEpoch() / 1000.0 - (self._t0 or 0.0)

    def _live_x(self):
        w = self.window_combo.currentData()
        now = max(self._now_rel(), 1e-3)
        if not w:
            return 0.0, max(now, 1.0)
        x1 = max(now, w)            # fill the window first, then scroll
        return x1 - w, x1

    def _mark_dirty(self, *_):
        self._dirty = True

    def _current_view(self) -> dict:
        return {"x": tuple(self.ax_a.get_xlim()), "yA": tuple(self.ax_a.get_ylim()),
                "yB": tuple(self.ax_b.get_ylim())}

    def _sync_buttons(self):
        paused = not self._following
        self.pause_btn.setText("Resume" if paused else "Pause")
        self.back_btn.setEnabled(bool(self._zoom_stack))
        self.home_btn.setEnabled(paused)
        self.status_lbl.setText("PAUSED / ZOOMED" if paused else "LIVE")

    def _toggle_pause(self):
        if self._following:
            self._manual_view = self._current_view()
            self._following = False
        else:
            self.zoom_home()
        self._mark_dirty()
        self._sync_buttons()

    def zoom_back(self):
        if not self._zoom_stack:
            return
        prev = self._zoom_stack.pop()
        if prev == "LIVE":
            self._following, self._manual_view = True, None
        else:
            self._manual_view = prev
        self._mark_dirty()
        self._sync_buttons()

    def zoom_home(self):
        self._zoom_stack.clear()
        self._following, self._manual_view = True, None
        self._mark_dirty()
        self._sync_buttons()

    def clear_data(self):
        for s in self._series.values():
            del s.ts[:]
            del s.val[:]
        self._t0 = None
        self.zoom_home()

    def _on_press(self, event):
        if event.button == 3 and event.inaxes in (self.ax_a, self.ax_b):
            self.zoom_back()

    def _on_zoom_select(self, press, release):
        inv_a = self.ax_a.transData.inverted()
        inv_b = self.ax_b.transData.inverted()
        (xa0, ya0), (xa1, ya1) = inv_a.transform((press.x, press.y)), inv_a.transform((release.x, release.y))
        (_, yb0), (_, yb1) = inv_b.transform((press.x, press.y)), inv_b.transform((release.x, release.y))
        x0, x1 = sorted((xa0, xa1))
        if x1 <= x0:
            return
        self._zoom_stack.append("LIVE" if self._following else self._manual_view)
        self._manual_view = {"x": (x0, x1), "yA": tuple(sorted((ya0, ya1))),
                             "yB": tuple(sorted((yb0, yb1)))}
        self._following = False
        self._annot.set_visible(False)
        self._mark_dirty()
        self._sync_buttons()

    # RENDER -------------------------------------------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start(RENDER_MS)
        self._mark_dirty()
        self._sync_buttons()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _tick(self):
        if self._following or self._dirty:
            self.render()

    def render(self):
        self._dirty = False
        t0 = self._t0
        if t0 is None:
            self.ax_a.set_xlim(0, 10)
            self.canvas.draw_idle()
            return
        if self._following:
            x0, x1 = self._live_x()
        else:
            x0, x1 = self._manual_view["x"]
        a0, a1 = t0 + x0, t0 + x1
        ext = {"A": [None, None], "B": [None, None]}
        for key, line in self._lines.items():
            s = self._series.get(key)
            if s is None:
                line.set_data([], [])
                continue
            t, v = s.window(a0, a1)
            if s.step and len(t) and t[-1] < a1:
                t, v = np.append(t, a1), np.append(v, v[-1])      # hold the last command to the edge
            t, v = _decimate(t, v)
            line.set_data(t - t0, v)
            vis = (t >= a0) & (t <= a1)
            if vis.any():
                lo, hi = float(v[vis].min()), float(v[vis].max())
                e = ext["A" if line.axes is self.ax_a else "B"]
                e[0] = lo if e[0] is None else min(e[0], lo)
                e[1] = hi if e[1] is None else max(e[1], hi)
        self.ax_a.set_xlim(x0, x1)
        self.ax_b.set_xlim(x0, x1)
        for name, ax in (("A", self.ax_a), ("B", self.ax_b)):
            if self._following:
                lo, hi = ext[name]
                if lo is None:
                    continue
                pad = max(0.08 * (hi - lo), 0.05 * max(abs(hi), abs(lo), 1.0) if hi == lo else 0.0)
                ax.set_ylim(lo - pad, hi + pad)
            else:
                ax.set_ylim(*self._manual_view["y" + name])
        self.canvas.draw_idle()

    # HOVER --------------------------------------------------------------------------------------------------------

    def _on_hover(self, event):
        if event.inaxes not in (self.ax_a, self.ax_b) or not self._lines:
            if self._annot.get_visible():
                self._annot.set_visible(False)
                self.canvas.draw_idle()
            return
        best = None   # (distance, key, t, v, display_xy)
        for key, line in self._lines.items():
            t, v = line.get_data()
            if len(t) == 0:
                continue
            pts = line.axes.transData.transform(np.column_stack([np.asarray(t, float), np.asarray(v, float)]))
            d = np.hypot(pts[:, 0] - event.x, pts[:, 1] - event.y)
            i = int(d.argmin())
            if d[i] <= HOVER_PX and (best is None or d[i] < best[0]):
                best = (d[i], key, float(t[i]), float(v[i]), pts[i])
        if best is None:
            if self._annot.get_visible():
                self._annot.set_visible(False)
                self.canvas.draw_idle()
            return
        _, key, t, v, disp = best
        xy = self.ax_b.transData.inverted().transform(disp)
        unit = self._unit_of(key)
        s = self._series.get(key)
        val_txt = f"{v:.4g}" if not (s and s.step and s.unit == "0/1") else ("1 (open)" if v >= 0.5 else "0 (closed)")
        self._annot.xy = (xy[0], xy[1])
        self._annot.set_text(f"{key}  [{self._axis_of(key)}]\nt = {t:.3f} s\n{val_txt} {unit if unit != '0/1' else ''}".rstrip())
        self._annot.get_bbox_patch().set_edgecolor(self._lines[key].get_color())
        fg, _, _, annot_bg = self._theme()
        self._annot.set_color(fg)
        self._annot.get_bbox_patch().set_facecolor(annot_bg)
        self._annot.set_visible(True)
        self.canvas.draw_idle()
