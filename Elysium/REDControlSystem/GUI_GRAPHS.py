# GUI_GRAPHS.py
# This file hosts the UI elements for plotting live data from various sensors aboard the flight hardware
import math
from collections import deque
from typing import Dict, List, Tuple

from PyQt5.QtWidgets import (
    QWidget, QLabel, QGridLayout, QDialog, QVBoxLayout, QHBoxLayout,
    QFrame, QToolButton, QCheckBox,
)
from PyQt5.QtCore import Qt, QDateTime, QPoint, QTimer, pyqtSignal
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from GUI_CONTROLLER import GUIController

SERIES_COLORS_DARK = [
    "#3987e5", "#199e70", "#c98500", "#008300",
    "#9085e9", "#e66767", "#d55181", "#d95926",
]
SERIES_COLORS_LIGHT = [
    "#2a78d6", "#1baf7a", "#eda100", "#008300",
    "#4a3aa7", "#e34948", "#e87ba4", "#eb6834",
]


def sensor_category(sensor_name: str) -> str:
    if sensor_name.startswith("TC"):
        return "Thermocouples"
    if sensor_name.startswith("LC") or sensor_name.startswith("B"):
        return "Load Cells"
    if sensor_name.startswith("P"):
        return "Pressure Transducers"
    return "Other"


def sensor_unit(sensor_name: str) -> str:
    return {
        "Pressure Transducers": "psi",
        "Thermocouples":        "°C",
        "Load Cells":           "lbf",
    }.get(sensor_category(sensor_name), "")


class SensorPickerPopup(QWidget):
    selection_changed = pyqtSignal(list)

    def __init__(self, sensors: List[str], selected: List[str], parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint)
        self.setObjectName("sensor_picker")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._boxes: Dict[str, QCheckBox] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(4)

        title = QLabel("GRAPH SENSORS")
        title.setObjectName("panel_section_title")
        outer.addWidget(title)

        hint = QLabel("One sensor type at a time")
        hint.setObjectName("sensor_unit_label")
        outer.addWidget(hint)

        groups: Dict[str, List[str]] = {}
        for name in sensors:
            groups.setdefault(sensor_category(name), []).append(name)

        for cat, names in groups.items():
            cat_lbl = QLabel(cat)
            cat_lbl.setObjectName("collapsible_title")
            outer.addSpacing(6)
            outer.addWidget(cat_lbl)

            grid = QGridLayout()
            grid.setContentsMargins(4, 0, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(2)
            for i, name in enumerate(names):
                cb = QCheckBox(name)
                cb.setChecked(name in selected)
                cb.toggled.connect(self._on_toggled)
                self._boxes[name] = cb
                grid.addWidget(cb, i // 4, i % 4)
            outer.addLayout(grid)

        self._sync_enabled()

    def _selected(self) -> List[str]:
        return [n for n, cb in self._boxes.items() if cb.isChecked()]

    def _sync_enabled(self):
        selected = self._selected()
        active_cat = sensor_category(selected[0]) if selected else None
        for name, cb in self._boxes.items():
            cb.setEnabled(active_cat is None or sensor_category(name) == active_cat)

    def _on_toggled(self, _checked: bool):
        self._sync_enabled()
        self.selection_changed.emit(self._selected())

    def open_at(self, global_pos: QPoint):
        self.adjustSize()
        self.move(global_pos - QPoint(self.width(), 0))
        self.show()


"""
Sensor Graph

This widget uses matplotlib to plot one or more live sensor series over a
rolling time window. It is intended to be heavily manually controlled by its
parent: the parent pushes samples in via update_single() and swaps the plotted
series via set_sensors().

Rendering is decoupled from data rate: update_single() only appends to the
data buffers (cheap), and an internal timer redraws at a fixed 10 Hz - and
only while the widget is actually visible. Frames are drawn with matplotlib
blitting (restore cached background, redraw just the line artists) so a
frame costs ~1 ms instead of a full figure redraw; the full redraw only
happens when the y-axis limits actually need to change. This keeps even a
popped-out window full of graphs from starving the GUI thread (and the
comms signal queue with it).
"""
class SensorGraph(QWidget):
    settings_requested = pyqtSignal(QPoint)   # global pos to anchor the picker
    popout_requested   = pyqtSignal()
    close_requested    = pyqtSignal(object)   # emits self

    def __init__(self, sensor_name: str, parent=None, show_gear: bool = False,
                 show_popout: bool = False, show_close: bool = False):
        super().__init__(parent)

        self.render_seconds: int = 10                # render the last 10 seconds
        self.backend_maxlen: int = 1000              # enough to store 10s of 100Hz data
        self.render_maxlen:  int = 300               # cheaper to render
        self.step = self.render_seconds / self.render_maxlen

        self.sensors: List[str] = [sensor_name]
        self.data: Dict[str, deque] = {sensor_name: deque(maxlen=self.backend_maxlen)}

        self.dark_mode = False
        self._lines: dict = {}

        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.figure.set_constrained_layout(True)

        # Blitting state: cached rendering of everything except the line
        # artists (axes, grid, labels, legend). Recaptured on any full draw.
        self._bg = None
        self.canvas.mpl_connect("draw_event", self._on_mpl_draw)

        # Fixed-rate render clock, running only while visible (see
        # showEvent/hideEvent). Data ingestion never triggers a draw.
        self.render_interval_ms: int = 100
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self.update_graph)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 4, 2)
        header_layout.setSpacing(4)

        self.title_lbl = QLabel("")
        self.title_lbl.setObjectName("graph_title_label")
        header_layout.addWidget(self.title_lbl, stretch=1)

        self.popout_btn = None
        if show_popout:
            self.popout_btn = QToolButton()
            self.popout_btn.setText("⤢")
            self.popout_btn.setObjectName("graph_popout_btn")
            self.popout_btn.setToolTip("Pop out into a separate multi-graph window")
            self.popout_btn.setCursor(Qt.PointingHandCursor)
            self.popout_btn.clicked.connect(self.popout_requested.emit)
            header_layout.addWidget(self.popout_btn)

        self.gear_btn = None
        if show_gear:
            self.gear_btn = QToolButton()
            self.gear_btn.setText("⚙")
            self.gear_btn.setObjectName("graph_gear_btn")
            self.gear_btn.setToolTip("Choose which sensors to plot")
            self.gear_btn.setCursor(Qt.PointingHandCursor)
            self.gear_btn.clicked.connect(self._on_gear_clicked)
            header_layout.addWidget(self.gear_btn)

        self.close_btn = None
        if show_close:
            self.close_btn = QToolButton()
            self.close_btn.setText("✕")
            self.close_btn.setObjectName("graph_close_btn")
            self.close_btn.setToolTip("Remove this graph")
            self.close_btn.setCursor(Qt.PointingHandCursor)
            self.close_btn.clicked.connect(lambda: self.close_requested.emit(self))
            header_layout.addWidget(self.close_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addWidget(self.canvas, stretch=1)

        self._rebuild_axes()

    def _on_gear_clicked(self):
        self.settings_requested.emit(
            self.gear_btn.mapToGlobal(
                QPoint(self.gear_btn.width(), self.gear_btn.height() + 2)))


    def set_sensors(self, sensors: List[str], history: Dict[str, deque] = None):
        self.sensors = list(sensors)
        self.data = {name: deque(maxlen=self.backend_maxlen) for name in self.sensors}
        if history:
            for name in self.sensors:
                for ts, val in history.get(name, ()):
                    self.data[name].append((ts, val))
        self._rebuild_axes()
        self.update_graph(force=True)

    def _palette(self) -> List[str]:
        return SERIES_COLORS_DARK if self.dark_mode else SERIES_COLORS_LIGHT

    def _title_text(self) -> str:
        if not self.sensors:
            return "No sensors selected"
        unit = sensor_unit(self.sensors[0])
        names = ", ".join(self.sensors) if len(self.sensors) <= 4 \
            else f"{', '.join(self.sensors[:3])} +{len(self.sensors) - 3} more"
        return f"{names}  ({unit})" if unit else names

    def _rebuild_axes(self):
        fg, bg, grid = self._theme_colors()
        self.ax.clear()
        self._lines.clear()

        palette = self._palette()
        for i, name in enumerate(self.sensors):
            color = palette[i % len(palette)]
            line, = self.ax.plot([], [], color=color, linewidth=2, label=name)
            # animated=True keeps the lines out of full draws so the cached
            # blit background contains only the static chrome.
            line.set_animated(True)
            self._lines[name] = line

        self.title_lbl.setText(self._title_text())
        unit = sensor_unit(self.sensors[0]) if self.sensors else ""
        self.ax.set_xlabel("Time (seconds ago)", fontsize=9, fontfamily="monospace", color=fg)
        self.ax.set_ylabel(f"Value ({unit})" if unit else "Value",
                           fontsize=9, fontfamily="monospace", color=fg)
        self.ax.tick_params(colors=fg, labelsize=8)
        self.ax.grid(True, color=grid, linestyle="--", linewidth=0.5, alpha=0.6)
        self.ax.set_facecolor(bg)
        self.figure.set_facecolor(bg)
        for spine in self.ax.spines.values():
            spine.set_color(grid)

        if len(self.sensors) >= 2:
            legend = self.ax.legend(loc="upper left", fontsize=8, framealpha=0.85,
                                    facecolor=bg, edgecolor=grid, labelcolor=fg)
            for text in legend.get_texts():
                text.set_fontfamily("monospace")

        self.ax.set_xlim(-self.render_seconds, 0)
        self._bg = None
        self.canvas.draw()

    def _on_mpl_draw(self, _event):
        """Any full matplotlib draw (initial, resize, theme change) leaves a
        fresh line-free rendering on the canvas - cache it for blitting."""
        self._bg = self.canvas.copy_from_bbox(self.figure.bbox)

    def showEvent(self, event):
        super().showEvent(event)
        self._render_timer.start(self.render_interval_ms)
        self.update_graph(force=True)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._render_timer.stop()

    def update_single(self, sensor_name: str, value: float, timestamp: float):
        series = self.data.get(sensor_name)
        if series is not None:
            series.append((timestamp, value))

    def _downsample(self, series: deque, now: float) -> Tuple[list, list]:
        xs, ys = [], []
        last_ts = None
        for ts, val in reversed(series):
            rel = ts - now
            if rel < -self.render_seconds:
                break
            if rel > 0:
                continue
            if last_ts is not None and (last_ts - rel) < self.step:
                continue
            xs.append(rel)
            ys.append(val)
            last_ts = rel
        xs.reverse()
        ys.reverse()
        return xs, ys

    def _ensure_ylim(self, y_min: float, y_max: float) -> bool:
        pad = max(0.1 * (y_max - y_min), 0.1)
        needed_lo, needed_hi = y_min - pad, y_max + pad
        cur_lo, cur_hi = self.ax.get_ylim()
        needed_span = needed_hi - needed_lo
        # Redraw when data escapes the current limits, or when the current
        # range is so oversized the trace flattens into a sliver.
        if needed_lo < cur_lo or needed_hi > cur_hi or (cur_hi - cur_lo) > 3.0 * needed_span:
            margin = 0.25 * needed_span
            self.ax.set_ylim(needed_lo - margin, needed_hi + margin)
            return True
        return False

    def update_graph(self, force: bool = False):
        now = QDateTime.currentMSecsSinceEpoch() / 1000.0

        y_min, y_max = None, None
        any_data = False
        for name in self.sensors:
            line = self._lines.get(name)
            if line is None:
                continue
            xs, ys = self._downsample(self.data[name], now)
            line.set_data(xs, ys)
            if ys:
                any_data = True
                lo, hi = min(ys), max(ys)
                y_min = lo if y_min is None else min(y_min, lo)
                y_max = hi if y_max is None else max(y_max, hi)

        if not any_data:
            if force:
                self.ax.set_ylim(0, 1)
                self._bg = None
                self.canvas.draw()
            return

        if self._ensure_ylim(y_min, y_max) or self._bg is None or force:
            # Full draw re-renders the static chrome and recaptures the
            # blit background (via the draw_event hook).
            self.canvas.draw()

        self.canvas.restore_region(self._bg)
        for name in self.sensors:
            line = self._lines.get(name)
            if line is not None:
                self.ax.draw_artist(line)
        self.canvas.blit(self.figure.bbox)

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        self._rebuild_axes()
        self.update_graph(force=True)

    def _theme_colors(self) -> Tuple[str, str, str]:
        if self.dark_mode:
            return "#e8e6e0", "#1e1e24", "#44444f"
        return "#1a1a1a", "#ffffff", "#cccccc"


class SensorPopupGraph(QDialog):
    def __init__(self, sensor_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{sensor_name} - Live Graph")
        self.resize(800, 500)
        self.sensor_name = sensor_name
        self.setModal(False)

        self.sensor_graph = SensorGraph(sensor_name=self.sensor_name, parent=parent)

        layout = QVBoxLayout()
        layout.addWidget(self.sensor_graph)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

class SensorFrame(QFrame):
    def __init__(self):
        super().__init__()


"""
SensorGridWindow

This window displays a big grid of the current sensor readings.
A single click to each sensor reading will update the main graph in the layout to that sensor
A double click to each sensor reading opens up a separate window containing its data

The main graph also has a gear button which opens a picker so several sensors of
the same category can be overlaid at once (colour-coded, with a legend).

INPUT DEPENDENCIES:
    GUIController.signals.sensor_updated(str, float, float)
        When data comes in directly from the comms system and is post processed by the GUIController,
        it updates this view in order to see new sensor readings and updated graphs

OUTPUT DEPENDENCIES:
    self.open_graph(str)
        Opens a new window with a corresponding graph (albeit that window is still owned and managed by this window)
"""
class SensorGridWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.sensor_updated.connect(self.update_sensor_value)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.setLayout(self.grid)

        self.sensors: List[str] = []

        self.sensor_frames: Dict[str, SensorFrame] = {}
        self.value_labels:  Dict[str, QLabel] = {}
        self.graphs: Dict[str, SensorPopupGraph] = {}
        self.sensor_history: Dict[str, deque] = {}
        self.dark_mode = False
        self._picker: SensorPickerPopup = None

        self.main_graph = SensorGraph("", show_gear=True, show_popout=True)
        self.main_graph.settings_requested.connect(self._open_sensor_picker)
        self.main_graph.popout_requested.connect(self.open_multi_graph_window)

        self.multi_graph_window: "MultiGraphWindow" = None

        self._pending_values: Dict[str, float] = {}
        self._label_status: Dict[str, str] = {}
        self._label_timer = QTimer(self)
        self._label_timer.timeout.connect(self._flush_labels)
        self._label_timer.start(100)

        self.refresh_sensors()

    def load_project(self, project=None):
        self.refresh_sensors()

    def refresh_sensors(self):
        new_sensors = list(self.controller.pt_keys) + list(self.controller.tc_keys) + list(self.controller.lc_keys)
        if new_sensors == self.sensors:
            return
        self.sensors = new_sensors

        for frame in self.sensor_frames.values():
            self.grid.removeWidget(frame)
            frame.setParent(None)
            frame.deleteLater()
        self.sensor_frames.clear()
        self.value_labels.clear()

        stale = [name for name in self.graphs if name not in self.sensors]
        for name in stale:
            self.graphs.pop(name).close()

        self.sensor_history = {
            name: self.sensor_history.get(name, deque(maxlen=10000))  # much larger than the render buffer
            for name in self.sensors
        }

        for idx, name in enumerate(self.sensors):
            self.create_sensor_box(name, idx)

        if self.sensors:
            self.main_graph.set_sensors([self.sensors[0]], self.sensor_history)
        else:
            self.main_graph.set_sensors([], self.sensor_history)

    def create_sensor_box(self, name: str, idx: int):
        frame = SensorFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(2)

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)
        frame_layout.setSpacing(5)

        name_label = QLabel(f"{name}:")
        name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        frame_layout.addWidget(name_label)

        value_label = QLabel("---")
        value_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        frame_layout.addWidget(value_label)

        unit_label = QLabel(sensor_unit(name))
        unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        frame_layout.addWidget(unit_label)

        row, col = divmod(idx, 4)
        self.grid.addWidget(frame, row, col)

        self.sensor_frames[name] = frame
        self.value_labels[name] = value_label

        # Make entire frame clickable to open graph
        frame.mousePressEvent = lambda event, sn=name: self.update_main_graph(sn)
        frame.mouseDoubleClickEvent = lambda event, sn=name: self.open_graph(sn)

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        self.main_graph.set_dark_mode(dark)
        for graph in self.graphs.values():
            graph.sensor_graph.set_dark_mode(dark)
        if self.multi_graph_window is not None:
            self.multi_graph_window.set_dark_mode(dark)

    def open_multi_graph_window(self):
        if self.multi_graph_window is None:
            self.multi_graph_window = MultiGraphWindow(self)
        if not self.multi_graph_window.graphs:
            initial = self.main_graph.sensors[0] if self.main_graph.sensors else None
            self.multi_graph_window.add_graph(initial)
        self.multi_graph_window.show()
        self.multi_graph_window.raise_()
        self.multi_graph_window.activateWindow()

    def update_sensor_value(self, sensor: str, value: float, timestamp: float):
        """Per-sample ingestion: append-only buffer work. All drawing (labels
        and graphs) happens on fixed-rate timers, never per packet."""
        if sensor not in self.value_labels:
            return

        self._pending_values[sensor] = value
        self.sensor_history[sensor].append((timestamp, value))

        if sensor in self.graphs:
            self.graphs[sensor].sensor_graph.update_single(sensor, value, timestamp)

        self.main_graph.update_single(sensor, value, timestamp)

        if self.multi_graph_window is not None:
            self.multi_graph_window.update_single(sensor, value, timestamp)

    def _flush_labels(self):
        if not self._pending_values or not self.isVisible():
            return
        pending, self._pending_values = self._pending_values, {}
        for sensor, value in pending.items():
            label = self.value_labels.get(sensor)
            if label is None:
                continue
            status = self.controller.get_sensor_status(sensor, value)
            if status != self._label_status.get(sensor):
                self._label_status[sensor] = status
                label.setStyleSheet({
                    "RED":    "color: #b00020; font-weight: bold;",
                    "ORANGE": "color: #ff8c00; font-weight: bold;",
                    "BLUE":   "color: #0000ff; font-weight: bold;",
                }.get(status, ""))
            label.setText(f"{value:.2f}")

    def update_main_graph(self, sensor: str):
        self.main_graph.set_sensors([sensor], self.sensor_history)

    def _open_sensor_picker(self, global_pos: QPoint):
        self.open_picker_for(self.main_graph, global_pos)

    def open_picker_for(self, graph: "SensorGraph", global_pos: QPoint):
        """Shared picker-popup wiring, reused by the main graph and every
        graph cell inside a popped-out MultiGraphWindow."""
        self._picker = SensorPickerPopup(self.sensors, graph.sensors, parent=graph)
        self._picker.selection_changed.connect(
            lambda selected: graph.set_sensors(selected, self.sensor_history))
        self._picker.open_at(global_pos)

    def open_graph(self, sensor: str):
        if sensor not in self.graphs:
            popup = SensorPopupGraph(sensor)
            popup.sensor_graph.set_sensors([sensor], self.sensor_history)
            popup.sensor_graph.set_dark_mode(self.dark_mode)
            self.graphs[sensor] = popup

        self.graphs[sensor].show()
        self.graphs[sensor].raise_()
        self.graphs[sensor].activateWindow()


"""
MultiGraphWindow

A separate top-level window holding a grid of independent SensorGraph
widgets - meant to be dragged onto a second monitor and full-screened during
a test. Each cell has its own gear (pick sensors) and close button; a
toolbar button adds more cells up to MAX_GRAPHS. The grid auto-arranges into
roughly-square rows/cols (so 9 graphs -> 3x3, 10 -> 4x3, etc.) rather than
forcing a fixed NxN shape - the user only needs a hard cap, not a fixed size.
"""
class MultiGraphWindow(QWidget):
    MAX_GRAPHS = 16

    def __init__(self, sensor_grid: "SensorGridWindow"):
        super().__init__(None, Qt.Window)
        self.sensor_grid = sensor_grid
        self.setWindowTitle("Graphs")
        self.resize(1200, 800)

        self.graphs: List[SensorGraph] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        toolbar = QHBoxLayout()
        self.add_btn = QToolButton()
        self.add_btn.setText("+ Add Graph")
        self.add_btn.setCursor(Qt.PointingHandCursor)
        self.add_btn.clicked.connect(lambda: self.add_graph())
        toolbar.addWidget(self.add_btn)
        toolbar.addStretch()
        outer.addLayout(toolbar)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(8)
        outer.addWidget(self._grid_container, stretch=1)

    def add_graph(self, sensor: str = None):
        if len(self.graphs) >= self.MAX_GRAPHS:
            return
        graph = SensorGraph("", show_gear=True, show_close=True)
        graph.settings_requested.connect(lambda pos, g=graph: self.sensor_grid.open_picker_for(g, pos))
        graph.close_requested.connect(self.remove_graph)
        graph.set_dark_mode(self.sensor_grid.dark_mode)
        if sensor is None and self.sensor_grid.sensors:
            sensor = self.sensor_grid.sensors[0]
        if sensor:
            graph.set_sensors([sensor], self.sensor_grid.sensor_history)
        self.graphs.append(graph)
        self._relayout()
        self._sync_add_btn()

    def remove_graph(self, graph: "SensorGraph"):
        if graph not in self.graphs:
            return
        self.graphs.remove(graph)
        self._grid_layout.removeWidget(graph)
        graph.setParent(None)
        graph.deleteLater()
        self._relayout()
        self._sync_add_btn()

    def _sync_add_btn(self):
        self.add_btn.setEnabled(len(self.graphs) < self.MAX_GRAPHS)

    def _relayout(self):
        n = len(self.graphs)
        cols = max(1, math.ceil(math.sqrt(n)))
        for idx, graph in enumerate(self.graphs):
            row, col = divmod(idx, cols)
            self._grid_layout.addWidget(graph, row, col)

    def update_single(self, sensor: str, value: float, timestamp: float):
        for graph in self.graphs:
            graph.update_single(sensor, value, timestamp)

    def set_dark_mode(self, dark: bool):
        for graph in self.graphs:
            graph.set_dark_mode(dark)

    def closeEvent(self, event):
        # Keep the graphs/window alive in the background rather than tearing
        # them down - closing the window is just "hide it", same spirit as
        # the other popup graphs in this file.
        event.ignore()
        self.hide()
