# GUI_LIVEDATA.py
# Live Data tab: a grid of live plots, one per sensor type (pressure transducers,
# thermocouples, load cells) plus a log of the commands sent to the system.
#
#   * Sensors come from controller.signals.sensor_updated; the sidebar ticks which
#     ones are plotted, with All / None buttons per sensor type.
#   * Commands (what the GUI sent to a valve / actuator) come from
#     controller.signals.command_sent and are listed in the command log.
#   * The grid starts as 2x2 (PT, TC, LC, Commands). The Panels buttons - or the x on
#     a panel - add and remove panels; the rest re-flow to fill the space, down to a
#     single full-screen panel.
#   * Time is shared: the window / pause / zoom controls move every plot together.
#     Drag-zoom also fixes the y range of the plot you dragged in; the others
#     autoscale to the zoomed time span. Back / Ctrl+Z / right-click undoes a zoom,
#     Home / Esc returns to the live view.
#
# The page only needs the controller's signals and its sensor key lists, so it can
# be fed by any controller-shaped object (e.g. a read-only viewer controller).
from array import array
from bisect import bisect_left, bisect_right
from typing import Dict, List, Optional

import numpy as np
from PyQt5.QtCore import Qt, QDateTime, QTimer
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QPushButton, QScrollArea, QShortcut, QSizePolicy, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout, QWidget,
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
MAX_COMMANDS = 5000           # command log entries kept; oldest trimmed beyond this

# (panel id, title, short button label, controller attribute holding its sensor keys)
SENSOR_PANELS = [
    ("pt", "Pressure Transducers", "PTs", "pt_keys"),
    ("tc", "Thermocouples", "TCs", "tc_keys"),
    ("lc", "Load Cells", "LCs", "lc_keys"),
]
CMD_PANEL = ("cmd", "Commands Sent", "Commands")
PANEL_IDS = [p[0] for p in SENSOR_PANELS] + [CMD_PANEL[0]]


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


class _PanelFrame(QFrame):
    """Bordered panel with a title bar and a close (x) button."""

    def __init__(self, page, pid: str, title: str):
        super().__init__()
        self.page = page
        self.pid = pid
        self.setFrameShape(QFrame.StyledPanel)
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(4, 2, 4, 4)
        self.outer.setSpacing(2)
        bar = QHBoxLayout()
        bar.setContentsMargins(2, 0, 0, 0)
        lbl = QLabel(title.upper())
        lbl.setObjectName("panel_section_title")
        bar.addWidget(lbl)
        bar.addStretch()
        close = QToolButton()
        close.setText("✕")
        close.setAutoRaise(True)
        close.setToolTip("Remove this panel (bring it back with the Panels buttons)")
        close.clicked.connect(lambda: page.set_panel_visible(pid, False))
        bar.addWidget(close)
        self.outer.addLayout(bar)


class _PlotPanel(_PanelFrame):
    """Live plot of the ticked sensors of one type."""

    def __init__(self, page, pid: str, title: str, noun: str):
        super().__init__(page, pid, title)
        self.noun = noun
        self.keys: List[str] = []           # every sensor of this type in the project
        self.checked: List[str] = []        # the ones plotted
        self.lines: dict = {}

        self.fig = Figure()
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.setMinimumSize(160, 110)
        self.outer.addWidget(self.canvas, stretch=1)

        self.ax = self.fig.add_subplot(111)
        self.fig.subplots_adjust(left=0.11, right=0.98, top=0.96, bottom=0.15)
        self.annot = self.ax.annotate(
            "", xy=(0, 0), xytext=(14, 14), textcoords="offset points", fontsize=9,
            fontfamily="monospace", zorder=30,
            bbox=dict(boxstyle="round,pad=0.6", fc="#2a2a38", ec="#8b1a1a", lw=1.6, alpha=0.97))
        self.annot.set_visible(False)
        self.note = self.ax.text(0.5, 0.5, "", transform=self.ax.transAxes, ha="center",
                                 va="center", fontsize=10, zorder=5)
        self.selector = RectangleSelector(
            self.ax, lambda p, r: page._on_zoom_select(self, p, r), useblit=False, button=[1],
            minspanx=6, minspany=6, spancoords="pixels", interactive=False,
            props=dict(facecolor="#3b82f6", edgecolor="#3b82f6", alpha=0.25))
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.apply_theme()
        self.rebuild_lines()

    def apply_theme(self):
        fg, bg, grid, annot_bg = self.page._theme()
        self.fig.set_facecolor(bg)
        self.ax.set_facecolor(bg)
        self.ax.tick_params(colors=fg, labelsize=8)
        for sp in self.ax.spines.values():
            sp.set_color(grid)
        self.ax.grid(True, color=grid, linestyle="--", linewidth=0.5, alpha=0.7)
        self.ax.set_xlabel("Time (s)", color=fg, fontsize=9, fontfamily="monospace")
        self.annot.get_bbox_patch().set_facecolor(annot_bg)
        self.annot.set_color(fg)
        self.note.set_color(fg)

    def set_keys(self, keys: List[str], checked: List[str]):
        self.keys = list(keys)
        self.checked = [k for k in self.keys if k in checked]
        self.rebuild_lines()

    def set_checked(self, checked: List[str]):
        self.checked = [k for k in self.keys if k in checked]
        self.rebuild_lines()

    def color(self, key: str) -> str:
        pal = SERIES_COLORS_DARK if self.page.dark_mode else SERIES_COLORS_LIGHT
        return pal[self.keys.index(key) % len(pal)]

    def unit(self) -> str:
        units = []
        for k in self.checked or self.keys:
            u = sensor_unit(k)
            if u and u not in units:
                units.append(u)
        return ", ".join(units)

    def rebuild_lines(self):
        for line in self.lines.values():
            line.remove()
        self.lines.clear()
        fg, bg, grid, _ = self.page._theme()
        for key in self.checked:
            line, = self.ax.plot([], [], color=self.color(key), linewidth=1.8, label=key)
            self.lines[key] = line
        self.ax.set_ylabel(self.unit(), color=fg, fontsize=9, fontfamily="monospace")
        leg = self.ax.get_legend()
        if leg is not None:
            leg.remove()
        if self.lines:
            leg = self.ax.legend(list(self.lines.values()), list(self.lines), loc="upper left",
                                 fontsize=8, framealpha=0.85, facecolor=bg, edgecolor=grid,
                                 labelcolor=fg, ncol=2 if len(self.lines) > 6 else 1)
            for t in leg.get_texts():
                t.set_fontfamily("monospace")
        if not self.keys:
            self.note.set_text(f"No {self.noun.lower()} in this project")
        elif not self.checked:
            self.note.set_text("Tick sensors on the left to plot them")
        else:
            self.note.set_text("")
        self.annot.set_visible(False)
        self.page._mark_dirty()

    def render(self, t0: float, x0: float, x1: float, y_manual):
        a0, a1 = t0 + x0, t0 + x1
        lo = hi = None
        for key, line in self.lines.items():
            s = self.page._series.get(key)
            if s is None:
                line.set_data([], [])
                continue
            t, v = _decimate(*s.window(a0, a1))
            line.set_data(t - t0, v)
            vis = (t >= a0) & (t <= a1)
            if vis.any():
                vlo, vhi = float(v[vis].min()), float(v[vis].max())
                lo = vlo if lo is None else min(lo, vlo)
                hi = vhi if hi is None else max(hi, vhi)
        self.ax.set_xlim(x0, x1)
        if y_manual is not None:
            self.ax.set_ylim(*y_manual)
        elif lo is not None:
            pad = max(0.08 * (hi - lo), 0.05 * max(abs(hi), abs(lo), 1.0) if hi == lo else 0.0)
            self.ax.set_ylim(lo - pad, hi + pad)
        self.canvas.draw_idle()

    def idle(self):
        """No data yet: just show a default time span."""
        self.ax.set_xlim(0, 10)
        self.canvas.draw_idle()

    def current_xlim(self):
        return tuple(self.ax.get_xlim())

    def _on_press(self, event):
        if event.button == 3 and event.inaxes is self.ax:
            self.page.zoom_back()

    def _hide_annot(self):
        if self.annot.get_visible():
            self.annot.set_visible(False)
            self.canvas.draw_idle()

    def _on_hover(self, event):
        if event.inaxes is not self.ax or not self.lines:
            self._hide_annot()
            return
        best = None   # (distance, key, t, v, display_xy)
        for key, line in self.lines.items():
            t, v = line.get_data()
            if len(t) == 0:
                continue
            pts = self.ax.transData.transform(np.column_stack([np.asarray(t, float), np.asarray(v, float)]))
            d = np.hypot(pts[:, 0] - event.x, pts[:, 1] - event.y)
            i = int(d.argmin())
            if d[i] <= HOVER_PX and (best is None or d[i] < best[0]):
                best = (d[i], key, float(t[i]), float(v[i]), pts[i])
        if best is None:
            self._hide_annot()
            return
        _, key, t, v, disp = best
        xy = self.ax.transData.inverted().transform(disp)
        fg, _, _, annot_bg = self.page._theme()
        self.annot.xy = (xy[0], xy[1])
        self.annot.set_text(f"{key}\nt = {t:.3f} s\n{v:.4g} {sensor_unit(key)}".rstrip())
        self.annot.get_bbox_patch().set_edgecolor(self.lines[key].get_color())
        self.annot.set_color(fg)
        self.annot.get_bbox_patch().set_facecolor(annot_bg)
        self.annot.set_visible(True)
        self.canvas.draw_idle()


class _CommandLog(_PanelFrame):
    """Time-stamped list of every command the GUI sent to a valve / actuator."""

    def __init__(self, page, pid: str, title: str):
        super().__init__(page, pid, title)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Time", "T+ (s)", "Command"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.outer.addWidget(self.table, stretch=1)

    def add(self, wall_ts: float, rel_t: float, name: str, text: str, opening: Optional[bool]):
        bar = self.table.verticalScrollBar()
        at_end = bar.value() >= bar.maximum() - 2
        row = self.table.rowCount()
        self.table.insertRow(row)
        stamp = QDateTime.fromMSecsSinceEpoch(int(wall_ts * 1000)).toString("HH:mm:ss.zzz")
        for col, txt in enumerate((stamp, f"{rel_t:.3f}", f"{name}  →  {text}")):
            item = QTableWidgetItem(txt)
            if col == 2 and opening is not None:
                item.setForeground(QColor("#3fb950" if opening else "#e5534b"))
            self.table.setItem(row, col, item)
        while self.table.rowCount() > MAX_COMMANDS:
            self.table.removeRow(0)
        if at_end:
            self.table.scrollToBottom()

    def clear(self):
        self.table.setRowCount(0)


class LiveDataPage(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.dark_mode = True

        self._series: Dict[str, _Series] = {}
        self._t0: Optional[float] = None
        self._rows: Dict[str, QCheckBox] = {}
        self._visible = {pid: True for pid in PANEL_IDS}

        # View state. Following = x window tracks "now"; otherwise the view is
        # frozen at _manual_view = {"x": (x0, x1), "y": {panel id: (lo, hi)}} (panels
        # without a y entry autoscale). _zoom_stack holds views zoomed away from
        # (the string "LIVE" stands for the following view).
        self._following = True
        self._manual_view: Optional[dict] = None
        self._zoom_stack: list = []
        self._dirty = True

        self.panels: Dict[str, _PlotPanel] = {}
        self.cmd_panel: Optional[_CommandLog] = None
        self._build_ui()
        self._connect_controller()
        self.refresh_series()
        self._relayout()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    # UI -----------------------------------------------------------------------------------------------------------

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = QWidget()
        side.setFixedWidth(290)
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(6, 6, 6, 6)
        title = QLabel("SENSORS")
        title.setObjectName("browser_title")
        side_lay.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._list_host = QWidget()
        self._list_lay = QVBoxLayout(self._list_host)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(0)
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
        bar_lay.addWidget(QLabel("Panels:"))
        self._panel_btns: Dict[str, QPushButton] = {}
        buttons = [(p[0], p[2], p[1]) for p in SENSOR_PANELS] + [(CMD_PANEL[0], CMD_PANEL[2], CMD_PANEL[1])]
        for pid, label, full in buttons:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setToolTip(f"Show / hide the {full} panel")
            btn.setStyleSheet("QPushButton:checked { background-color: #3b82f6; color: white; }")
            btn.toggled.connect(lambda on, p=pid: self.set_panel_visible(p, on))
            bar_lay.addWidget(btn)
            self._panel_btns[pid] = btn
        self.all_btn = QPushButton("Show All Sensors")
        self.all_btn.setToolTip("Tick every sensor and show the PT, TC and LC plots")
        self.all_btn.clicked.connect(self.show_all_sensors)
        bar_lay.addWidget(self.all_btn)
        bar_lay.addSpacing(12)
        bar_lay.addWidget(QLabel("Window:"))
        self.window_combo = QComboBox()
        for label, secs in WINDOWS:
            self.window_combo.addItem(label, secs)
        self.window_combo.setCurrentIndex(1)
        self.window_combo.currentIndexChanged.connect(self._mark_dirty)
        bar_lay.addWidget(self.window_combo)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setToolTip("Freeze the view (data keeps recording). Resume jumps back to live (Home / Esc).")
        self.pause_btn.clicked.connect(self._toggle_pause)
        bar_lay.addWidget(self.pause_btn)
        self.back_btn = QPushButton("Back")
        self.back_btn.setToolTip("Undo the last zoom (Backspace / Ctrl+Z / right-click)")
        self.back_btn.clicked.connect(self.zoom_back)
        bar_lay.addWidget(self.back_btn)
        bar_lay.addStretch()
        self.status_lbl = QLabel("")
        bar_lay.addWidget(self.status_lbl)
        right_lay.addWidget(bar)

        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(4, 4, 4, 4)
        self._grid.setSpacing(6)
        for pid, title_txt, _short, _attr in SENSOR_PANELS:
            self.panels[pid] = _PlotPanel(self, pid, title_txt, title_txt)
        self.cmd_panel = _CommandLog(self, CMD_PANEL[0], CMD_PANEL[1])
        self._empty_lbl = QLabel("No panels shown - turn some on with the Panels buttons above.")
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        right_lay.addWidget(self._grid_host, stretch=1)

        hint = QLabel("Drag on a plot to zoom (time zoom applies to every plot)  ·  Back / Ctrl+Z / right-click: undo zoom"
                      "  ·  Home / Esc: resume live")
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

    def _widget(self, pid: str) -> QWidget:
        return self.cmd_panel if pid == CMD_PANEL[0] else self.panels[pid]

    # PANEL LAYOUT -------------------------------------------------------------------------------------------------

    def panel_visible(self, pid: str) -> bool:
        return self._visible[pid]

    def set_panel_visible(self, pid: str, visible: bool):
        visible = bool(visible)
        if self._visible[pid] == visible:
            return
        self._visible[pid] = visible
        btn = self._panel_btns[pid]
        btn.blockSignals(True)
        btn.setChecked(visible)
        btn.blockSignals(False)
        self._relayout()

    def _relayout(self):
        """Re-flow the visible panels: 1 -> full, 2 -> side by side, 3 -> 2 + 1 wide, 4 -> 2x2."""
        for pid in PANEL_IDS:
            self._grid.removeWidget(self._widget(pid))
        self._grid.removeWidget(self._empty_lbl)
        shown = [pid for pid in PANEL_IDS if self._visible[pid]]
        n = len(shown)
        for pid in PANEL_IDS:
            if pid not in shown:
                self._widget(pid).hide()
        cols = 1 if n <= 1 else 2
        rows = (n + cols - 1) // cols
        for i, pid in enumerate(shown):
            r, c = divmod(i, cols)
            span = 2 if (n == 3 and i == 2) else 1
            self._grid.addWidget(self._widget(pid), r, c, 1, span)
            self._widget(pid).show()
        if n == 0:
            self._grid.addWidget(self._empty_lbl, 0, 0)
            self._empty_lbl.show()
        else:
            self._empty_lbl.hide()
        for r in range(2):
            self._grid.setRowStretch(r, 1 if r < max(rows, 1) else 0)
        for c in range(2):
            self._grid.setColumnStretch(c, 1 if c < max(cols, 1) else 0)
        self._mark_dirty()

    def _theme(self):
        if self.dark_mode:
            return "#e8e6e0", "#1e1e24", "#44444f", "#2a2a38"
        return "#1a1a1a", "#ffffff", "#cccccc", "#ffffff"

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        for panel in self.panels.values():
            panel.apply_theme()
            panel.rebuild_lines()

    # CONTROLLER ---------------------------------------------------------------------------------------------------

    def _connect_controller(self):
        sig = self.controller.signals
        sig.sensor_updated.connect(self._on_sensor)
        sig.project_changed.connect(self.refresh_series)      # whichever path loaded the project
        cmd = getattr(sig, "command_sent", None)
        if cmd is not None:
            cmd.connect(self._on_command)

    def _on_sensor(self, name: str, value: float, timestamp: float):
        if self._t0 is None:
            self._t0 = timestamp
        s = self._series.get(name)
        if s is None:
            s = self._series[name] = _Series(sensor_unit(name))
        s.append(timestamp, value)

    def _on_command(self, name: str, value: float, timestamp: float):
        if self._t0 is None:
            self._t0 = timestamp
        spec = getattr(self.controller, "actuator_specs", {}).get(name)
        if spec is not None:
            text, opening = f"{value:g} {getattr(spec, 'unit', '%')}".rstrip(), None
        else:
            opening = value >= 0.5
            text = "OPEN" if opening else "CLOSE"
        self.cmd_panel.add(timestamp, timestamp - self._t0, name.strip() or "(unnamed valve)", text, opening)

    def load_project(self, project=None):
        self.refresh_series()

    def refresh_series(self):
        """Rebuild the sensor list from the controller's sensor keys, keeping what was ticked."""
        ticked = {k for k, cb in self._rows.items() if cb.isChecked()}
        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()                # deleteLater alone leaves a ghost until the event loop runs
                w.setParent(None)
                w.deleteLater()
        self._rows.clear()
        if not any(getattr(self.controller, attr, []) for _p, _t, _n, attr in SENSOR_PANELS):
            hint = QLabel("No sensors yet - load a project to list its sensors here.")
            hint.setWordWrap(True)
            self._list_lay.addWidget(hint)
        first = True
        for pid, title, _noun, attr in SENSOR_PANELS:
            keys = list(getattr(self.controller, attr, []))
            self.panels[pid].set_keys(keys, [k for k in keys if k in ticked])
            if not keys:
                continue
            head = QWidget()
            head_lay = QHBoxLayout(head)
            head_lay.setContentsMargins(0, 0 if first else 12, 0, 4)
            first = False
            head_lay.setSpacing(2)
            lbl = QLabel(title)
            lbl.setObjectName("panel_section_title")
            head_lay.addWidget(lbl, stretch=1)
            for text, tip, on in (("All", f"Plot every {title.lower()} sensor", True),
                                  ("None", f"Plot no {title.lower()} sensors", False)):
                btn = QToolButton()
                btn.setText(text)
                btn.setToolTip(tip)
                btn.clicked.connect(lambda _c=False, k=keys, o=on: self._set_all(k, o))
                head_lay.addWidget(btn)
            self._list_lay.addWidget(head)
            for key in keys:
                cb = QCheckBox(key)
                cb.setFixedHeight(24)
                cb.setContentsMargins(8, 0, 0, 0)
                cb.blockSignals(True)
                cb.setChecked(key in ticked)
                cb.blockSignals(False)
                cb.toggled.connect(lambda _c: self._on_selection_changed())
                self._rows[key] = cb
                self._list_lay.addWidget(cb)
        self._list_lay.addStretch()

    # SELECTION ----------------------------------------------------------------------------------------------------

    def _checked(self) -> List[str]:
        return [k for k, cb in self._rows.items() if cb.isChecked()]

    def _set_all(self, keys: List[str], on: bool):
        for k in keys:
            cb = self._rows.get(k)
            if cb is not None:
                cb.blockSignals(True)
                cb.setChecked(on)
                cb.blockSignals(False)
        self._on_selection_changed()

    def show_all_sensors(self):
        """Tick every sensor of every type and make sure the plots for them are showing."""
        self._set_all(list(self._rows), True)
        for pid, *_ in SENSOR_PANELS:
            self.set_panel_visible(pid, True)

    def _on_selection_changed(self):
        checked = self._checked()
        for panel in self.panels.values():
            panel.set_checked(checked)

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

    def _current_x(self):
        for pid in PANEL_IDS[:-1]:
            if self._visible[pid]:
                return self.panels[pid].current_xlim()
        return self._live_x()

    def _sync_buttons(self):
        paused = not self._following
        self.pause_btn.setText("Resume" if paused else "Pause")
        self.back_btn.setEnabled(bool(self._zoom_stack))
        self.status_lbl.setText("PAUSED / ZOOMED" if paused else "LIVE")

    def _toggle_pause(self):
        if self._following:
            self._manual_view = {"x": self._current_x(), "y": {}}
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
        """Discard the plotted history and command log and restart the time axis at 0
        (no button for it: a stray click mid-test would lose the plots)."""
        for s in self._series.values():
            del s.ts[:]
            del s.val[:]
        self.cmd_panel.clear()
        self._t0 = None
        self.zoom_home()

    def _on_zoom_select(self, panel: _PlotPanel, press, release):
        inv = panel.ax.transData.inverted()
        (x0, y0), (x1, y1) = inv.transform((press.x, press.y)), inv.transform((release.x, release.y))
        x0, x1 = sorted((x0, x1))
        if x1 <= x0:
            return
        prev_y = {} if self._following else dict(self._manual_view["y"])
        self._zoom_stack.append("LIVE" if self._following else self._manual_view)
        prev_y[panel.pid] = tuple(sorted((y0, y1)))
        self._manual_view = {"x": (x0, x1), "y": prev_y}
        self._following = False
        for p in self.panels.values():
            p.annot.set_visible(False)
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
        shown = [self.panels[pid] for pid in PANEL_IDS[:-1] if self._visible[pid]]
        if t0 is None:
            for panel in shown:
                panel.idle()
            return
        if self._following:
            x0, x1 = self._live_x()
            ys = {}
        else:
            x0, x1 = self._manual_view["x"]
            ys = self._manual_view["y"]
        for panel in shown:
            panel.render(t0, x0, x1, ys.get(panel.pid))
