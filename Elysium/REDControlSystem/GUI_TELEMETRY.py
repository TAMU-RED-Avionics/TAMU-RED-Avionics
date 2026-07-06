import os
from datetime import datetime
from typing import Optional

import openpyxl
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QLabel,
    QHeaderView, QFrame, QPushButton, QAbstractItemView,
    QSizePolicy, QToolButton, QStackedWidget, QComboBox,
    QLineEdit, QMessageBox, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QScrollArea, QGroupBox, QCheckBox,
)
from PyQt5.QtCore import Qt, pyqtSignal, QSortFilterProxyModel, QThread, pyqtSlot
from PyQt5.QtGui import QColor, QFont, QPalette

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from GUI_GRAPHS import SERIES_COLORS_DARK, SERIES_COLORS_LIGHT, sensor_category

DATA_DIR = "Data"

def _discover_files(root: str) -> list[tuple[str, str]]:
    if not os.path.isdir(root):
        return []
    results: list[tuple[str, str]] = []
    for fname in sorted(os.listdir(root)):
        if fname.lower().endswith(".xlsx"):
            results.append((fname, os.path.abspath(os.path.join(root, fname))))
    return results


def _load_xlsx(path: str) -> tuple[list[str], list[list]]:

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active

    headers: list[str] = []
    rows: list[list] = []

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            headers = [str(c) if c is not None else "" for c in row]
        else:
            rows.append([str(c) if c is not None else "" for c in row])

    wb.close()
    return headers, rows


def _vsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def _hsep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


class FileBrowser(QWidget):
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("telemetry_file_browser")
        self.setMinimumWidth(200)
        self.setMaximumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_row = QWidget()
        header_row.setObjectName("browser_header")
        hr_layout = QHBoxLayout(header_row)
        hr_layout.setContentsMargins(8, 6, 8, 6)

        title = QLabel("DATA FILES")
        title.setObjectName("browser_title")
        hr_layout.addWidget(title)
        hr_layout.addStretch()

        self.refresh_btn = QToolButton()
        self.refresh_btn.setText("⟳")
        self.refresh_btn.setToolTip("Refresh file list")
        self.refresh_btn.clicked.connect(self.refresh)
        hr_layout.addWidget(self.refresh_btn)

        layout.addWidget(header_row)
        layout.addWidget(_hsep())

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter files…")
        self.search.setObjectName("browser_search")
        self.search.textChanged.connect(self._filter)
        self.search.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setObjectName("browser_tree")
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.tree)

        self.refresh()

    def refresh(self):
        self.tree.clear()
        files = _discover_files(DATA_DIR)

        if not files:
            placeholder = QTreeWidgetItem(["(no .xlsx files in Data/)"])
            placeholder.setFlags(Qt.NoItemFlags)
            self.tree.addTopLevelItem(placeholder)
            return

        groups: dict[str, list[tuple[str, str]]] = {}
        for display, path in files:
            parts = display.split("_")
            if len(parts) >= 3:
                group = "_".join(parts[:-2])
            elif len(parts) == 2:
                group = parts[0]
            else:
                group = "Other"

            groups.setdefault(group, []).append((display, path))

        for group, entries in sorted(groups.items()):
            if len(groups) > 1:
                group_item = QTreeWidgetItem([group])
                group_item.setFlags(Qt.ItemIsEnabled)
                group_item.setExpanded(True)
                self.tree.addTopLevelItem(group_item)
                parent = group_item
            else:
                parent = self.tree.invisibleRootItem()

            for display, path in entries:
                item = QTreeWidgetItem([display])
                item.setData(0, Qt.UserRole, path)
                item.setToolTip(0, path)
                parent.addChild(item)

        self.tree.expandAll()

    def _filter(self, text: str):
        text = text.strip().lower()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            group = root.child(i)
            any_visible = False
            for j in range(group.childCount()):
                child = group.child(j)
                match = not text or text in child.text(0).lower()
                child.setHidden(not match)
                if match:
                    any_visible = True
            group.setHidden(not any_visible)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _col: int):
        path = item.data(0, Qt.UserRole)
        if path:
            self.file_selected.emit(path)

    def selected_path(self) -> Optional[str]:
        items = self.tree.selectedItems()
        if items:
            return items[0].data(0, Qt.UserRole)
        return None



class SpreadsheetTable(QTableWidget):

    HEADER_BG = "#8b1a1a"
    HEADER_FG = "#ffffff"
    ALT_ROW   = "#2a2a32"

    # Rows whose "Event Type" column starts with "SEQUENCE" (SEQUENCE:START,
    # SEQUENCE:STEP, SEQUENCE:CANCELED - the same prefix GUIController already
    # logs sequence events under) get bolded + tinted so they stand out from
    # the surrounding numeric telemetry.
    SEQUENCE_ROW_BG_DARK  = QColor("#4a3a12")
    SEQUENCE_ROW_BG_LIGHT = QColor("#fff3cd")

    def __init__(self, controller=None, parent=None):
        super().__init__(parent)

        self.controller = controller

        self.setObjectName("telemetry_table")
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)

        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(False)

        self.verticalHeader().setDefaultSectionSize(22)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        self._apply_theme()

    def _apply_theme(self):

        dark_mode = False

        if self.controller:
            dark_mode = getattr(self.controller, "dark_mode", False)

        style = ""

        if dark_mode:

            style += f"""
                QTableWidget {{
                    background-color: #1e1e24;
                    alternate-background-color: {self.ALT_ROW};
                    color: #e6e6e6;
                    gridline-color: #3a3a44;
                    selection-background-color: #8b1a1a;
                    selection-color: white;
                }}

                QHeaderView::section {{
                    background-color: {self.HEADER_BG};
                    color: {self.HEADER_FG};
                    padding: 4px;
                    border: 1px solid #444;
                    font-weight: bold;
                }}

                QTableCornerButton::section {{
                    background-color: {self.HEADER_BG};
                    border: 1px solid #444;
                }}

                QScrollBar:vertical {{
                    background: #1e1e24;
                    width: 16px;
                    margin: 0px;
                }}

                QScrollBar::handle:vertical {{
                    background: #555;
                    min-height: 30px;
                    border-radius: 7px;
                }}

                QScrollBar::handle:vertical:hover {{
                    background: #777;
                }}

                QScrollBar:horizontal {{
                    background: #1e1e24;
                    height: 16px;
                    margin: 0px;
                }}

                QScrollBar::handle:horizontal {{
                    background: #555;
                    min-width: 30px;
                    border-radius: 7px;
                }}

                QScrollBar::handle:horizontal:hover {{
                    background: #777;
                }}
            """

        else:

            style += """
                QScrollBar:vertical {
                    width: 16px;
                }

                QScrollBar::handle:vertical {
                    min-height: 30px;
                }

                QScrollBar:horizontal {
                    height: 16px;
                }

                QScrollBar::handle:horizontal {
                    min-width: 30px;
                }
            """

        style += """
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical,
            QScrollBar::add-page:horizontal,
            QScrollBar::sub-page:horizontal {
                background: none;
            }
        """

        self.setStyleSheet(style)

    def load(self, headers: list[str], rows: list[list]):

        self.setSortingEnabled(False)

        self.clear()

        self.setRowCount(len(rows))
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        event_col = next((i for i, h in enumerate(headers)
                          if h.strip().lower() == "event type"), None)
        dark_mode = bool(self.controller and getattr(self.controller, "dark_mode", True))
        highlight_bg = self.SEQUENCE_ROW_BG_DARK if dark_mode else self.SEQUENCE_ROW_BG_LIGHT

        for r, row in enumerate(rows):
            is_sequence_row = (event_col is not None and event_col < len(row)
                              and row[event_col].strip().upper().startswith("SEQUENCE"))

            for c, val in enumerate(row):

                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                if is_sequence_row:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                    item.setBackground(highlight_bg)

                self.setItem(r, c, item)

        self.resizeColumnsToContents()

        for c in range(self.columnCount()):

            if self.columnWidth(c) > 200:
                self.setColumnWidth(c, 200)

        self.setSortingEnabled(True)


class FilePanel(QWidget):

    def __init__(self, title="File A", controller=None, parent=None):
        super().__init__(parent)

        self.controller = controller
        self._title = title
        self._path: Optional[str] = None
        self._headers: list[str] = []
        self._rows: list[list] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top toolbar ───────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setObjectName("file_panel_toolbar")
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 4, 8, 4)
        tb.setSpacing(8)

        self.panel_label = QLabel(title)
        self.panel_label.setObjectName("panel_label")
        tb.addWidget(self.panel_label)
        tb.addWidget(_vsep())

        self.file_label = QLabel("No file loaded")
        self.file_label.setObjectName("file_path_label")
        self.file_label.setWordWrap(False)
        tb.addWidget(self.file_label, stretch=1)
        tb.addWidget(_vsep())

        self.stats_label = QLabel("")
        self.stats_label.setObjectName("stats_label")
        tb.addWidget(self.stats_label)

        tb.addWidget(_vsep())

        # View toggle buttons
        self._table_btn = QPushButton("Table")
        self._table_btn.setObjectName("action_bar_btn")
        self._table_btn.setCheckable(True)
        self._table_btn.setChecked(True)
        self._table_btn.clicked.connect(lambda: self._switch_view(0))
        tb.addWidget(self._table_btn)

        self._graph_btn = QPushButton("Graph")
        self._graph_btn.setObjectName("action_bar_btn")
        self._graph_btn.setCheckable(True)
        self._graph_btn.setChecked(False)
        self._graph_btn.clicked.connect(lambda: self._switch_view(1))
        tb.addWidget(self._graph_btn)

        layout.addWidget(toolbar)
        layout.addWidget(_hsep())

        # ── Stacked views ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()

        self.table = SpreadsheetTable(controller=self.controller)
        self._stack.addWidget(self.table)            # index 0

        dark = getattr(controller, "dark_mode", True) if controller else True
        self.graph = SensorGraphPanel(dark_mode=dark)
        self._stack.addWidget(self.graph)            # index 1

        layout.addWidget(self._stack, stretch=1)

    def _switch_view(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._table_btn.setChecked(idx == 0)
        self._graph_btn.setChecked(idx == 1)

    def load_file(self, path: str):
        self._path = path
        fname = os.path.basename(path)
        self.file_label.setText(fname)
        self.file_label.setToolTip(path)

        try:
            headers, rows = _load_xlsx(path)
            self._headers = headers
            self._rows = rows

            self.table.load(headers, rows)
            self.graph.load_data(headers, rows)

            self.stats_label.setText(f"{len(rows)} rows × {len(headers)} cols")

        except Exception as exc:
            QMessageBox.critical(self, "Load Error",
                                 f"Could not load file:\n{path}\n\n{exc}")
            self.file_label.setText("(load error)")
            self.stats_label.setText("")

    def clear(self):
        self._path = None
        self._headers = []
        self._rows = []
        self.file_label.setText("No file loaded")
        self.stats_label.setText("")
        self.table.clear()
        self.table.setRowCount(0)
        self.table.setColumnCount(0)
        self._switch_view(0)



def _parse_local_time(s: str) -> Optional[datetime]:
    """Parse the 'Local Time (YYYY-MM-DD HH:mm:ss)' column value."""
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _extract_sensor_data(headers: list[str], rows: list[list]) -> dict:
    """
    Parse loaded xlsx data into a dict:
        {
            "t": [float, ...],          # seconds from first row
            "sensors": {col_name: [float|None, ...], ...},
            "events":  [(t, event_type, event_details), ...]
        }
    Skips blank header columns and non-sensor columns (Control State, Event Type etc).
    """
    NON_SENSOR = {"", "Local Time (YYYY-MM-DD HH:mm:ss)",
                  "Teensy Timestamp (µs from boot)",
                  "Control State", "Event Type", "Event Details"}

    time_col = next((i for i, h in enumerate(headers)
                     if "local time" in h.lower()), None)
    ev_type_col = next((i for i, h in enumerate(headers)
                        if h.strip().lower() == "event type"), None)
    ev_det_col = next((i for i, h in enumerate(headers)
                       if h.strip().lower() == "event details"), None)

    sensor_cols = {i: h for i, h in enumerate(headers)
                   if h and h not in NON_SENSOR}

    t_raw: list[Optional[datetime]] = []
    sensor_rows: dict[int, list] = {i: [] for i in sensor_cols}

    for row in rows:
        # Parse timestamp
        if time_col is not None and time_col < len(row):
            t_raw.append(_parse_local_time(row[time_col]))
        else:
            t_raw.append(None)

        for col_idx in sensor_cols:
            val = row[col_idx] if col_idx < len(row) else ""
            try:
                sensor_rows[col_idx].append(float(val))
            except (ValueError, TypeError):
                sensor_rows[col_idx].append(None)

    # Build t in seconds from first valid timestamp
    first_t = next((t for t in t_raw if t is not None), None)
    t_seconds: list[Optional[float]] = []
    for t in t_raw:
        if t is not None and first_t is not None:
            t_seconds.append((t - first_t).total_seconds())
        else:
            t_seconds.append(None)

    # Collect logged events (rows with a non-empty Event Type)
    events: list[tuple[float, str, str]] = []
    if ev_type_col is not None:
        for row, t in zip(rows, t_seconds):
            if t is None or ev_type_col >= len(row):
                continue
            ev_type = str(row[ev_type_col]).strip()
            if not ev_type:
                continue
            ev_det = str(row[ev_det_col]).strip() \
                if ev_det_col is not None and ev_det_col < len(row) else ""
            events.append((t, ev_type, ev_det))

    return {
        "t": t_seconds,
        "sensors": {sensor_cols[i]: sensor_rows[i] for i in sensor_cols},
        "events": events,
    }


class SensorGraphPanel(QWidget):

    def __init__(self, dark_mode: bool = True, parent=None):
        super().__init__(parent)

        self._data = None
        self._dark = dark_mode
        self._hover_cid = None
        self._plotted_lines = []
        self._annot = None
        self._ax = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar_row = QWidget()
        tb = QHBoxLayout(toolbar_row)
        tb.setContentsMargins(8, 4, 8, 4)
        tb.setSpacing(10)

        tb.addWidget(QLabel("Sensors:"))

        self._sensor_list = QListWidget()
        self._sensor_list.setFixedWidth(180)
        self._sensor_list.setMaximumHeight(120)
        self._sensor_list.setSelectionMode(QAbstractItemView.NoSelection)
        tb.addWidget(self._sensor_list)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        tb.addWidget(sep1)

        tb.addWidget(QLabel("t start (s):"))

        self._t_start = QDoubleSpinBox()
        self._t_start.setDecimals(1)
        self._t_start.setRange(0.0, 999999.0)
        self._t_start.setFixedWidth(80)
        tb.addWidget(self._t_start)

        tb.addWidget(QLabel("t end (s):"))

        self._t_end = QDoubleSpinBox()
        self._t_end.setDecimals(1)
        self._t_end.setRange(0.0, 999999.0)
        self._t_end.setFixedWidth(80)
        tb.addWidget(self._t_end)

        self._plot_btn = QPushButton("Plot")
        self._plot_btn.clicked.connect(self._draw)
        self._plot_btn.setEnabled(False)
        tb.addWidget(self._plot_btn)

        self._reset_btn = QPushButton("Reset Range")
        self._reset_btn.clicked.connect(self._reset_range)
        self._reset_btn.setEnabled(False)
        tb.addWidget(self._reset_btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        tb.addWidget(sep2)

        tb.addWidget(QLabel("Markers:"))

        # Vertical event lines on the plot: sequence operations (default),
        # individual valve open/close commands, or none.
        self._marker_combo = QComboBox()
        self._marker_combo.addItem("Sequence ops", "sequence")
        self._marker_combo.addItem("Valve ops", "valve")
        self._marker_combo.addItem("Off", "off")
        self._marker_combo.currentIndexChanged.connect(
            lambda _: self._draw() if self._data else None)
        tb.addWidget(self._marker_combo)

        tb.addStretch()

        layout.addWidget(toolbar_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._fig = Figure(tight_layout=True)

        self._canvas = FigureCanvasQTAgg(self._fig)
        self._canvas.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        self._nav = NavigationToolbar2QT(self._canvas, self)

        layout.addWidget(self._nav)
        layout.addWidget(self._canvas, stretch=1)

    def load_data(self, headers: list[str], rows: list[list]):

        self._data = _extract_sensor_data(headers, rows)

        self._sensor_list.clear()

        # Group by category (pressure first); check only the first category by
        # default so the initial plot isn't a mixed-unit wall of lines.
        cat_rank = {"Pressure Transducers": 0, "Thermocouples": 1, "Load Cells": 2}
        names = sorted(self._data["sensors"].keys(),
                       key=lambda n: (cat_rank.get(sensor_category(n), 9), len(n), n))
        default_cat = sensor_category(names[0]) if names else None

        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked if sensor_category(name) == default_cat else Qt.Unchecked)
            self._sensor_list.addItem(item)

        self._plot_btn.setEnabled(True)
        self._reset_btn.setEnabled(True)

        self._reset_range()

    def set_dark_mode(self, dark: bool):
        self._dark = dark
        if self._data:
            self._draw()

    def _selected_sensors(self):

        sensors = []

        for i in range(self._sensor_list.count()):

            item = self._sensor_list.item(i)

            if item.checkState() == Qt.Checked:
                sensors.append(item.text())

        return sensors

    def _reset_range(self):

        if not self._data:
            return

        valid_t = [t for t in self._data["t"] if t is not None]

        if not valid_t:
            return

        max_t = max(valid_t)

        self._t_start.setValue(0.0)
        self._t_end.setMaximum(max_t + 1.0)
        self._t_end.setValue(round(max_t, 1))

        self._draw()

    def _draw(self):

        if not self._data:
            return

        selected = self._selected_sensors()

        if not selected:
            return

        t_start = self._t_start.value()
        t_end = self._t_end.value()

        if t_end <= t_start:
            return

        bg = "#1e1e24" if self._dark else "#f4f2ee"
        fg = "#e8e6e0" if self._dark else "#1a1a1a"
        grid = "#333340" if self._dark else "#cccccc"

        self._fig.clear()

        if self._hover_cid is not None:
            self._canvas.mpl_disconnect(self._hover_cid)
            self._hover_cid = None

        self._ax = self._fig.add_subplot(111)

        ax = self._ax

        ax.set_facecolor(bg)
        self._fig.set_facecolor(bg)

        self._plotted_lines.clear()

        t_all = self._data["t"]

        for idx, name in enumerate(selected):

            vals = self._data["sensors"].get(name, [])

            t_plot = []
            v_plot = []

            for t, v in zip(t_all, vals):

                if t is None or v is None:
                    continue

                if t_start <= t <= t_end:
                    t_plot.append(t)
                    v_plot.append(v)

            palette = SERIES_COLORS_DARK if self._dark else SERIES_COLORS_LIGHT
            color = palette[idx % len(palette)]

            line, = ax.plot(
                t_plot,
                v_plot,
                label=name,
                color=color,
                linewidth=2.2,
                alpha=0.95,
            )

            line.set_pickradius(10)

            self._plotted_lines.append(line)

        ax.set_xlabel(
            "Time (s)",
            color=fg,
            fontsize=10,
            fontfamily="monospace",
        )

        ax.set_ylabel(
            "Value",
            color=fg,
            fontsize=10,
            fontfamily="monospace",
        )

        ax.tick_params(colors=fg, labelsize=9)

        ax.grid(
            color=grid,
            linestyle="--",
            linewidth=0.5,
            alpha=0.7,
        )

        for spine in ax.spines.values():
            spine.set_edgecolor(grid)

        legend = ax.legend(
            fontsize=9,
            loc="upper right",
            ncol=2 if len(selected) > 8 else 1,
            facecolor=bg,
            edgecolor=grid,
            labelcolor=fg,
            framealpha=0.85,
            borderpad=0.6,
            labelspacing=0.4,
            handlelength=2.0,
        )

        for text in legend.get_texts():
            text.set_fontfamily("monospace")

        ax.set_xlim(t_start, t_end)

        self._draw_event_markers(ax, t_start, t_end)

        annot_bg = "#2a2a38" if self._dark else "#ffffff"
        annot_fg = "#e8e6e0" if self._dark else "#1a1a1a"

        self._annot = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(18, 18),
            textcoords="offset points",
            fontsize=11,
            fontfamily="monospace",
            color=annot_fg,
            bbox=dict(
                boxstyle="round,pad=0.8",
                fc=annot_bg,
                ec="#8b1a1a",
                lw=2.0,
                alpha=0.97,
            ),
            zorder=20,
        )

        self._annot.set_visible(False)

        self._hover_cid = self._canvas.mpl_connect(
            "motion_notify_event",
            self._on_hover,
        )

        self._canvas.draw_idle()

    # Event types that count as "sequence operations"
    _SEQ_EVENT_TYPES = ("SEQUENCE:START", "SEQUENCE:STEP", "OPERATION",
                        "ABORT", "SAFE_STATE")
    # Valve-level events
    _VALVE_EVENT_TYPES = ("VALVE_CHANGED", "AUTO_VALVE_OPEN")

    def _marker_for_event(self, ev_type: str, ev_det: str, mode: str):
        """Return (label, color) if this event should be marked in the given
        mode, else None. Aborts are shown in both modes - they matter."""
        good = "#199e70" if self._dark else "#1baf7a"
        bad  = "#e66767" if self._dark else "#e34948"
        neutral = "#9b9990" if self._dark else "#6b6963"

        if ev_type == "ABORT":
            reason = ev_det.split(":", 1)[0]
            return (f"ABORT {reason}".strip()[:30], bad)

        if mode == "sequence":
            if ev_type in self._SEQ_EVENT_TYPES or ev_type.startswith("SEQUENCE"):
                return (ev_det or ev_type, neutral)
        elif mode == "valve":
            if ev_type in self._VALVE_EVENT_TYPES:
                # VALVE_CHANGED details look like "NCS1:True"
                name, _, state = ev_det.partition(":")
                if state.strip() in ("True", "1", "OPEN"):
                    return (f"{name} open", good)
                if state.strip() in ("False", "0", "CLOSED"):
                    return (f"{name} close", bad)
                return (ev_det or ev_type, neutral)
        return None

    def _draw_event_markers(self, ax, t_start: float, t_end: float):
        mode = self._marker_combo.currentData()
        if mode == "off" or not self._data:
            return

        trans = ax.get_xaxis_transform()   # x = data coords, y = axes fraction
        for t, ev_type, ev_det in self._data.get("events", []):
            if not (t_start <= t <= t_end):
                continue
            marker = self._marker_for_event(ev_type, ev_det, mode)
            if marker is None:
                continue
            label, color = marker

            ax.axvline(t, color=color, linestyle="--", linewidth=1.0,
                       alpha=0.65, zorder=5)
            ax.text(t, 0.99, f" {label}", transform=trans,
                    rotation=90, ha="right", va="top",
                    fontsize=7, fontfamily="monospace",
                    color=color, alpha=0.95, zorder=6, clip_on=True)

    def _on_hover(self, event):

        if event.inaxes != self._ax:

            if self._annot.get_visible():
                self._annot.set_visible(False)
                self._canvas.draw_idle()

            return

        redraw = False
        visible = False

        for line in self._plotted_lines:

            contains, info = line.contains(event)

            if not contains:
                continue

            ind = info["ind"][0]

            xdata = line.get_xdata()
            ydata = line.get_ydata()

            x = xdata[ind]
            y = ydata[ind]

            self._annot.xy = (x, y)

            self._annot.set_text(
                f"{line.get_label()}\n"
                f"t = {x:.3f} s\n"
                f"{y:.4f}"
            )

            self._annot.get_bbox_patch().set_edgecolor(
                line.get_color()
            )

            if not self._annot.get_visible():
                redraw = True

            self._annot.set_visible(True)

            visible = True

            break

        if not visible and self._annot.get_visible():

            self._annot.set_visible(False)
            redraw = True

        if redraw or visible:
            self._canvas.draw_idle()

class TelemetryPage(QWidget):
    def __init__(self, controller=None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._compare_mode = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.browser = FileBrowser()
        self.browser.file_selected.connect(self._on_file_selected)
        layout.addWidget(self.browser)

        layout.addWidget(_vsep())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        top_bar = QWidget()
        top_bar.setObjectName("telemetry_toolbar")
        tb_layout = QHBoxLayout(top_bar)
        tb_layout.setContentsMargins(10, 6, 10, 6)
        tb_layout.setSpacing(10)

        tb_layout.addWidget(QLabel("Telemetry"))
        tb_layout.addWidget(_vsep())

        self.open_btn = QPushButton("Open File →")
        self.open_btn.setObjectName("action_bar_btn")
        self.open_btn.setToolTip("Double-click a file in the browser to open it")
        self.open_btn.clicked.connect(self._open_selected)
        tb_layout.addWidget(self.open_btn)

        self.compare_btn = QPushButton("Compare ⇌")
        self.compare_btn.setObjectName("action_bar_btn")
        self.compare_btn.setCheckable(True)
        self.compare_btn.setToolTip("Toggle side-by-side comparison mode")
        self.compare_btn.clicked.connect(self._toggle_compare)
        tb_layout.addWidget(self.compare_btn)

        tb_layout.addWidget(_vsep())

        self.hint_label = QLabel("Double-click a file in the browser to load it")
        self.hint_label.setObjectName("stats_label")
        tb_layout.addWidget(self.hint_label, stretch=1)

        right_layout.addWidget(top_bar)
        right_layout.addWidget(_hsep())

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(4)

        self.panel_a = FilePanel("File A", controller=self.controller)
        self.panel_b = FilePanel("File B", controller=self.controller)
        self.panel_b.setVisible(False)

        self.splitter.addWidget(self.panel_a)
        self.splitter.addWidget(self.panel_b)

        right_layout.addWidget(self.splitter, stretch=1)

        layout.addWidget(right, stretch=1)

        self._next_panel = "A"

    def _open_selected(self):
        path = self.browser.selected_path()
        if path:
            self._load_into_next(path)
        else:
            self.hint_label.setText("Select a file in the browser first")

    def _on_file_selected(self, path: str):
        self._load_into_next(path)

    def _load_into_next(self, path: str):
        if not self._compare_mode or self._next_panel == "A":
            self.panel_a.load_file(path)
            if self._compare_mode:
                self._next_panel = "B"
                self.hint_label.setText("File A loaded | Select File B")
            else:
                self.hint_label.setText(f"Loaded: {os.path.basename(path)}")
        else:
            self.panel_b.load_file(path)
            self._next_panel = "A"
            self.hint_label.setText("Compare Enabled | Select a file to Reload File A")

    def _toggle_compare(self, checked: bool):
        self._compare_mode = checked
        self.panel_b.setVisible(checked)

        if checked:
            self.splitter.setSizes([self.width() // 2, self.width() // 2])
            self._next_panel = "B"
            self.hint_label.setText("Compare Enabled")
            self.compare_btn.setText("Single View ✕")
        else:
            self.panel_b.clear()
            self._next_panel = "A"
            self.hint_label.setText("Compare Disabled")
            self.compare_btn.setText("Compare ⇌")