# PID_CANVAS.py
#
# The interactive canvas widget: pan/zoom, selection, hit-testing, dragging,
# corner-handle resize, pipe drawing, live-view valve popups/sensor callouts,
# and orchestrating repaints. What each component actually *looks like* is
# PID_RENDERER.py's job - this file calls into it (Renderer.draw, world_rect,
# the theme palette) rather than drawing shapes itself.

import math
from PyQt5.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QPushButton, QLabel, QMessageBox,
    QApplication,
)
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QTransform, QPolygonF, QPixmap,
)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer

from PID_SCHEMA import (
    PIDProject, PipeLine, LayoutPoint,
    FLUID_GENERIC,
    COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL,
    COMP_CHECK_VALVE, COMP_RELIEF_VALVE,
    COMP_BALL_VALVE, COMP_PSV, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_PRV,
    COMP_VALVE, COMP_IGNITER,
    COMP_ACTUATED_VALVE, COMP_ACTUATED_VALVE_LS, COMP_NEEDLE_VALVE,
    COMP_THREE_WAY_VALVE, COMP_EP_THROTTLE_VALVE,
    COMP_DIFF_PRESSURE, COMP_FLOW_METER,
)

import PID_RENDERER as PR
from PID_RENDERER import (
    GRID_SPACING, PIPE_W, SNS_R,
    FLUID_QC, apply_canvas_theme, snap, world_rect, Renderer,
    _blend_color,
)



# Inline components with real open/closed state that participate in pipe
# topology (pressurization linking) and get a click-to-open ValvePopup in
# live view. Passive/structural fittings (burst disk, bulkhead, quick
# disconnect, orifice, filter, ...) are intentionally left out, same as
# COMP_TANK/COMP_INJECTOR/COMP_JUNCTION always have been.
VALVE_TYPES = {
    COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE,
    COMP_PSV, COMP_PRV, COMP_RELIEF_VALVE, COMP_CHECK_VALVE,
    COMP_IGNITER,
    COMP_ACTUATED_VALVE, COMP_ACTUATED_VALVE_LS, COMP_NEEDLE_VALVE,
    COMP_THREE_WAY_VALVE, COMP_EP_THROTTLE_VALVE,
}

# Types with a live telemetry readout (gets a canvas callout box). Kept in
# sync with PID_EDITOR.HW_CHANNEL_TYPES. COMP_PRESSURE_GAUGE is deliberately
# excluded - it's a local mechanical gauge (RED-001 3.3 "PG"), not a
# digitized transmitter, so there's no live value to show.
SENSOR_TYPES = {COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL,
                COMP_DIFF_PRESSURE, COMP_FLOW_METER}

# Sensor callout colours by type
SENSOR_CALLOUT_BG = {
    COMP_PRESSURE:      QColor(20, 40, 70, 230),    # dark blue
    COMP_TEMPERATURE:   QColor(60, 20, 20, 230),    # dark red
    COMP_LOAD_CELL:     QColor(40, 20, 60, 230),    # dark purple
    COMP_DIFF_PRESSURE: QColor(20, 55, 55, 230),    # dark teal
    COMP_FLOW_METER:    QColor(20, 50, 25, 230),    # dark green
}
SENSOR_CALLOUT_BORDER = {
    COMP_PRESSURE:      QColor("#4488ff"),
    COMP_TEMPERATURE:   QColor("#ff6655"),
    COMP_LOAD_CELL:     QColor("#cc88ff"),
    COMP_DIFF_PRESSURE: QColor("#44ddcc"),
    COMP_FLOW_METER:    QColor("#66dd66"),
}
SENSOR_UNIT = {
    COMP_PRESSURE:      "psi",
    COMP_TEMPERATURE:   "°C",
    COMP_LOAD_CELL:     "lbf",
    COMP_DIFF_PRESSURE: "psid",
    COMP_FLOW_METER:    "gpm",
}

PRESSURIZED_MIN_PSI = 25.0   # PT at/above this marks its pipe pressurized
SENSOR_ATTACH_DIST  = 30.0   # world units: PT → nearest pipe attachment
VALVE_LINK_DIST     = 30.0   # world units: valve → pipe linking radius
ENDPOINT_JOIN_DIST  = 12.0   # world units: pipe endpoint → pipe join radius

OVERPRESSURE_MEOP = QColor("#ff9500")   # orange - at/above MEOP
OVERPRESSURE_MAWP = QColor("#5c0f0f")   # dark maroon red - at/near MAWP


class ValvePopup(QWidget):
    """
    Small floating widget that appears near a valve on the live canvas.
    Shows the current state and Open / Close buttons.
    """
    open_requested  = pyqtSignal(str)   # comp_id
    close_requested = pyqtSignal(str)   # comp_id

    _BTN_H = 28
    _W     = 110

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setFixedWidth(self._W)
        self._cid: str = None
        self._is_igniter: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._state_lbl = QLabel("-")
        self._state_lbl.setAlignment(Qt.AlignCenter)
        self._state_lbl.setStyleSheet(
            "font-weight: bold; font-size: 9pt; color: #cccccc;")
        layout.addWidget(self._state_lbl)

        self._open_btn = QPushButton("▶  OPEN")
        self._open_btn.setFixedHeight(self._BTN_H)
        self._open_btn.clicked.connect(self._on_open)
        layout.addWidget(self._open_btn)

        self._close_btn = QPushButton("■  CLOSE")
        self._close_btn.setFixedHeight(self._BTN_H)
        self._close_btn.setStyleSheet(
            "background:#4a1a1a; color:#ff5544; border:1px solid #aa2222;"
            "border-radius:4px; font-weight:bold;")
        self._close_btn.clicked.connect(self._on_close)
        layout.addWidget(self._close_btn)

        self.adjustSize()
        self.hide()

        # Rounded dark panel look
        self.setStyleSheet(
            "ValvePopup { background:#1e1e2a; border:1px solid #555566;"
            "border-radius:8px; }")
        self.setAttribute(Qt.WA_StyledBackground, True)

    def show_for(self, cid: str, state: str, screen_pos: QPointF, is_igniter: bool = False):
        """Position and show the popup near screen_pos."""
        self._cid = cid
        self._is_igniter = is_igniter

        if is_igniter:
            self._open_btn.setText("FIRE")
            self._open_btn.setStyleSheet(
                "background:#4a2a00; color:#ff8800; border:1px solid #cc5500;"
                "border-radius:4px; font-weight:bold;")
            self._close_btn.setText("SAFE")
        else:
            self._open_btn.setText("▶  OPEN")
            self._open_btn.setStyleSheet(
                "background:#1a4a1a; color:#00dd55; border:1px solid #00aa44;"
                "border-radius:4px; font-weight:bold;")
            self._close_btn.setText("■  CLOSE")

        self._update_state(state)

        # Keep within parent bounds
        px = int(screen_pos.x()) + 14
        py = int(screen_pos.y()) - self.sizeHint().height() // 2
        pw = self.parent().width()
        ph = self.parent().height()
        if px + self._W > pw:
            px = int(screen_pos.x()) - self._W - 14
        py = max(4, min(py, ph - self.sizeHint().height() - 4))

        self.move(px, py)
        self.raise_()
        self.show()

    def update_state(self, cid: str, state: str):
        if cid == self._cid and self.isVisible():
            self._update_state(state)

    def _update_state(self, state: str):
        labels = ({"OPEN": "ACTIVE", "CLOSED": "SAFE", "PENDING": "PENDING"}
                  if self._is_igniter else
                  {"OPEN": "OPEN", "CLOSED": "CLOSED", "PENDING": "PENDING"})
        colours = {"OPEN": "#ff8800" if self._is_igniter else "#00dd55",
                  "CLOSED": "#5599ff" if self._is_igniter else "#ff5544",
                  "PENDING": "#ff9900"}
        self._state_lbl.setText(labels.get(state, state))
        self._state_lbl.setStyleSheet(
            f"font-weight:bold; font-size:9pt; color:{colours.get(state,'#aaa')};")
        self._open_btn.setEnabled(state != "OPEN")
        self._close_btn.setEnabled(state != "CLOSED")

    def _on_open(self):
        if not self._cid:
            return
        if self._is_igniter:
            reply = QMessageBox.warning(
                self, "Confirm Ignition",
                "Fire this igniter now?\n\nThis sends a live command to the hardware.",
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if reply != QMessageBox.Yes:
                return
        self.open_requested.emit(self._cid)
        self.hide()

    def _on_close(self):
        if self._cid:
            self.close_requested.emit(self._cid)
            self.hide()


class PIDCanvas(QWidget):
    """
    Signals
    -------
    component_clicked(cid)
    component_moved(cid, x, y)
    canvas_clicked(wx, wy)
    line_clicked(line_id)
    line_finished(PipeLine)
    valve_open_requested(cid)
    valve_close_requested(cid)
    """

    component_clicked    = pyqtSignal(str)
    component_moved      = pyqtSignal(str, float, float)
    component_resized    = pyqtSignal(str)
    canvas_clicked       = pyqtSignal(float, float)
    line_clicked         = pyqtSignal(str)
    line_finished        = pyqtSignal(object)
    valve_open_requested  = pyqtSignal(str)
    valve_close_requested = pyqtSignal(str)

    def __init__(self, parent=None, interactive: bool = True):
        super().__init__(parent)
        self.interactive = interactive
        self.project: PIDProject = None

        self.live_valve_states:  dict = {}
        self.live_sensor_values: dict = {}
        self.live_throttle_pcts: dict = {}

        self._callout_offsets: dict = {}   # cid -> (dx, dy)  world units
        self._callout_rects:   dict = {}   # cid -> QRectF, screen space, cached at paint time

        self._zoom = 1.0
        self._pan  = QPointF(0, 0)

        self._pan_start:        QPointF = None
        self._pan_origin:       QPointF = None
        self._dragging_comp:    str     = None
        self._drag_start_world: QPointF = None
        self._drag_start_pos:   LayoutPoint = None
        # corner-handle resize: hold Ctrl and drag a selected component's
        self._resizing_comp:    str     = None
        self._resize_base_half: tuple   = None   # (half_w, half_h) at scale 1.0
        self._resize_center:    QPointF = None
        self._dragging_callout: str     = None   # cid of callout being dragged
        self._callout_drag_start_world: QPointF = None
        self._callout_drag_start_off:   tuple   = None
        self._hovered_comp:     str     = None
        self._selected_comps:   set     = set()
        self._selected_lines:   set     = set()
        self._hovered_line:     str     = None

        self._drawing_line     = False
        self._line_fluid       = FLUID_GENERIC
        self._line_points: list = []
        self._line_cursor: QPointF = None

        self._line_sensor_map:  dict = {}   # line_id -> [PT comp_ids]
        self._line_static_adj:  dict = {}   # line_id -> set(line_id)
        self._valve_line_links: list = []   # (valve_cid, set(line_ids))

        self._repaint_pending = False

        # Cached background grid (regenerated on zoom/resize, blitted on pan)
        self._grid_pixmap = None
        self._grid_cache_key = None

        # Valve popup (child widget, always present, hidden until needed)
        self._valve_popup = ValvePopup(self)
        self._valve_popup.open_requested.connect(self.valve_open_requested)
        self._valve_popup.close_requested.connect(self.valve_close_requested)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(300, 200)

    def set_project(self, project: PIDProject):
        self.project = project
        self.live_valve_states.clear()
        self.live_sensor_values.clear()
        self.live_throttle_pcts.clear()
        self._callout_offsets.clear()
        self._valve_popup.hide()
        self._build_line_topology()
        self.fit_view()
        self._needs_fit = True
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_needs_fit", False) and self.width() > 400:
            self._needs_fit = False
            self.fit_view()

    def _request_repaint(self):
        if self._repaint_pending:
            return
        self._repaint_pending = True
        QTimer.singleShot(33, self._flush_repaint)

    def _flush_repaint(self):
        self._repaint_pending = False
        self.update()

    def update_valve_state(self, cid: str, state: str):
        self.live_valve_states[cid] = state
        self._valve_popup.update_state(cid, state)
        self._request_repaint()

    def reset_callout_offset(self, cid: str):
        self._callout_offsets.pop(cid, None)
        self.update()

    def update_sensor_value(self, cid: str, value: float):
        self.live_sensor_values[cid] = value
        self._request_repaint()

    # ── Line pressurization ──────────────────────────────────────────────

    def _build_line_topology(self):
        self._line_sensor_map = {}
        self._line_static_adj = {}
        self._valve_line_links = []
        if not self.project:
            return

        lines = [l for l in self.project.lines if len(l.points) >= 2]

        def dist_to_line(pt: QPointF, line) -> float:
            best = float("inf")
            for i in range(len(line.points) - 1):
                a = QPointF(line.points[i].x,     line.points[i].y)
                b = QPointF(line.points[i + 1].x, line.points[i + 1].y)
                best = min(best, _seg_dist(pt, a, b))
            return best

        valve_positions = []
        for cid, comp in self.project.components.items():
            if comp.type in VALVE_TYPES:
                pos = self.project.layout.get(cid)
                if pos:
                    valve_positions.append((cid, QPointF(pos.x, pos.y)))

        # PTs attach to their closest pipe within radius
        for cid, comp in self.project.components.items():
            if comp.type != COMP_PRESSURE:
                continue
            pos = self.project.layout.get(cid)
            if not pos:
                continue
            pt = QPointF(pos.x, pos.y)
            best_line, best_d = None, SENSOR_ATTACH_DIST
            for line in lines:
                d = dist_to_line(pt, line)
                if d < best_d:
                    best_line, best_d = line.id, d
            if best_line:
                self._line_sensor_map.setdefault(best_line, []).append(cid)

        def near_valve(pt: QPointF) -> bool:
            return any(math.hypot(pt.x() - vp.x(), pt.y() - vp.y()) <= VALVE_LINK_DIST
                       for _, vp in valve_positions)

        def fluids_compatible(la, lb) -> bool:
            return (la.fluid == lb.fluid
                    or la.fluid == FLUID_GENERIC or lb.fluid == FLUID_GENERIC)

        for i, la in enumerate(lines):
            self._line_static_adj.setdefault(la.id, set())
            for lb in lines[i + 1:]:
                if not fluids_compatible(la, lb):
                    continue
                joined = False
                for line_a, line_b in ((la, lb), (lb, la)):
                    for lp in (line_a.points[0], line_a.points[-1]):
                        end = QPointF(lp.x, lp.y)
                        if dist_to_line(end, line_b) <= ENDPOINT_JOIN_DIST and not near_valve(end):
                            joined = True
                            break
                    if joined:
                        break
                if joined:
                    self._line_static_adj.setdefault(la.id, set()).add(lb.id)
                    self._line_static_adj.setdefault(lb.id, set()).add(la.id)

        # A valve links the pipes drawn up to it; flow crosses only when OPEN
        for cid, vp in valve_positions:
            linked = {line.id for line in lines
                      if dist_to_line(vp, line) <= VALVE_LINK_DIST}
            if len(linked) >= 2:
                self._valve_line_links.append((cid, linked))

    def _pressurized_line_ids(self) -> set:
        pressurized = set()
        frontier = []
        for line_id, cids in self._line_sensor_map.items():
            for cid in cids:
                value = self.live_sensor_values.get(cid)
                if value is not None and value >= PRESSURIZED_MIN_PSI:
                    pressurized.add(line_id)
                    frontier.append(line_id)
                    break

        while frontier:
            cur = frontier.pop()
            for nxt in self._line_static_adj.get(cur, ()):
                if nxt not in pressurized:
                    pressurized.add(nxt)
                    frontier.append(nxt)
        return pressurized


    def _line_pressure_values(self) -> dict:
        if not self.project:
            return {}

        line_values: dict[str, float] = {}

        def _consider(cid: str, line_id: str):
            value = self.live_sensor_values.get(cid)
            if value is None:
                return
            previous = line_values.get(line_id)
            if previous is None or value > previous:
                line_values[line_id] = value

        for line_id, cids in self._line_sensor_map.items():
            for cid in cids:
                _consider(cid, line_id)

        for cid, comp in self.project.components.items():
            if comp.type != COMP_PRESSURE:
                continue
            line_id = str(comp.extras.get("line_id", "")).strip()
            if line_id:
                _consider(cid, line_id)

        # Propagate to pipes with no PT of their own but physically joined
        # (same static-join-only rule as _pressurized_line_ids) to a pipe
        # that does - they're at the same real pressure. Never overwrite a
        # line that has its own direct reading; that PT's word is final for
        # its own pipe even if a neighbour's differs.
        directly_sensed = set(line_values.keys())
        frontier = list(directly_sensed)
        while frontier:
            cur = frontier.pop()
            cur_val = line_values[cur]
            for nxt in self._line_static_adj.get(cur, ()):
                if nxt in directly_sensed:
                    continue
                if line_values.get(nxt, -1.0) < cur_val:
                    line_values[nxt] = cur_val
                    frontier.append(nxt)

        return line_values

    def _pressure_line_color(self, base_color: QColor, pressure: float, max_pressure: float) -> QColor:
        if pressure is None:
            return base_color

        if max_pressure <= 0:
            max_pressure = 50.0

        pressure = max(0.0, float(pressure))
        if pressure <= 0.0:
            return base_color

        ramp = min(pressure / max_pressure, 1.0)
        return _blend_color(base_color, QColor("#ff3b30"), ramp)

    def _overpressure_line_color(self, pressure: float, meop, mawp):
        if meop is None or pressure is None:
            return None
        try:
            meop = float(meop)
        except (TypeError, ValueError):
            return None
        if pressure < meop:
            return None

        try:
            mawp = float(mawp) if mawp is not None else None
        except (TypeError, ValueError):
            mawp = None

        if mawp is not None and mawp > meop:
            ramp = min(max((pressure - meop) / (mawp - meop), 0.0), 1.0)
        else:
            # No usable MAWP to ramp against - just flag the MEOP exceedance.
            ramp = 0.0

        return _blend_color(OVERPRESSURE_MEOP, OVERPRESSURE_MAWP, ramp)

    def update_throttle(self, cid: str, pct: float):
        self.live_throttle_pcts[cid] = pct
        self._request_repaint()

    def set_selected(self, comp_ids):
        self._selected_comps = set(comp_ids)
        self.update()

    def start_line_draw(self, fluid: str = FLUID_GENERIC):
        self._drawing_line = True
        self._line_fluid   = fluid
        self._line_points  = []
        self._line_cursor  = None
        self.setCursor(Qt.CrossCursor)
        self.update()

    def finish_line_draw(self) -> "PipeLine | None":
        self._drawing_line = False
        self.setCursor(Qt.ArrowCursor)
        pts   = list(self._line_points)
        fluid = self._line_fluid
        self._line_points = []
        self._line_cursor = None
        self.update()

        if not self.project or len(pts) < 2:
            return None

        line_id = f"line_{len(self.project.lines)}"
        line = PipeLine(id=line_id, points=pts, fluid=fluid)
        self.line_finished.emit(line)
        return line

    def cancel_line_draw(self):
        self._drawing_line = False
        self._line_points  = []
        self._line_cursor  = None
        self.setCursor(Qt.ArrowCursor)
        self.update()

    def fit_view(self):
        if not self.project or not self.project.layout:
            self._zoom = 1.0
            self._pan  = QPointF(0, 0)
            return
        pts = list(self.project.layout.values())
        xs  = [p.x for p in pts]; ys = [p.y for p in pts]
        margin = 80
        ww = max(xs) - min(xs) + margin * 2
        wh = max(ys) - min(ys) + margin * 2
        if ww <= 0 or wh <= 0:
            return
        self._zoom = max(min(self.width() / ww, self.height() / wh, 2.0), 0.05)
        cx = (min(xs) + max(xs)) / 2
        cy = (min(ys) + max(ys)) / 2
        self._pan = QPointF(
            self.width()  / 2 / self._zoom - cx,
            self.height() / 2 / self._zoom - cy,
        )
        self.update()

    def _to_world(self, sx: float, sy: float) -> QPointF:
        return QPointF(sx / self._zoom - self._pan.x(),
                       sy / self._zoom - self._pan.y())

    def _comp_at(self, world: QPointF) -> "str | None":
        if not self.project:
            return None
        for cid, pos in self.project.layout.items():
            comp = self.project.components.get(cid)
            if comp and world_rect(pos, comp.type, comp).contains(world):
                return cid
        return None

    _RESIZE_HANDLE_PX = 8   # screen-pixel hit radius for corner resize handles

    def _resize_handle_at(self, world: QPointF):
        if not self.project or not self.interactive or len(self._selected_comps) != 1:
            return None
        cid = next(iter(self._selected_comps))
        comp = self.project.components.get(cid)
        pos = self.project.layout.get(cid)
        if not comp or not pos:
            return None
        rect = world_rect(pos, comp.type, comp)
        thr = self._RESIZE_HANDLE_PX / self._zoom
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            hx = pos.x + sx * rect.width() / 2
            hy = pos.y + sy * rect.height() / 2
            if abs(world.x() - hx) <= thr and abs(world.y() - hy) <= thr:
                return (cid, sx, sy)
        return None

    def _line_at(self, world: QPointF, thr: float = 8.0) -> "str | None":
        if not self.project:
            return None

        best_id = None
        best_d = float("inf")

        for line in self.project.lines:
            pts = line.points
            if len(pts) < 2:
                continue

            line_best = float("inf")
            for i in range(len(pts) - 1):
                d = _seg_dist(
                    world,
                    QPointF(pts[i].x, pts[i].y),
                    QPointF(pts[i + 1].x, pts[i + 1].y),
                )
                if d < line_best:
                    line_best = d

            if line_best < best_d:
                best_d = line_best
                best_id = line.id

        return best_id if best_d <= thr else None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), PR.C_BG)

        if not self.project:
            p.setPen(QPen(QColor("#555")))
            p.setFont(QFont("Courier New", 13))
            p.drawText(self.rect(), Qt.AlignCenter,
                       "No project loaded.")
            return

        # Grid is blitted in screen space from a cached pixmap (regenerated
        # only on zoom/resize) - much cheaper than per-point drawing.
        self._paint_grid_screen(p)

        p.setTransform(
            QTransform()
            .translate(self._pan.x() * self._zoom, self._pan.y() * self._zoom)
            .scale(self._zoom, self._zoom)
        )

        self._paint_lines(p)
        self._paint_components(p)
        self._paint_resize_handles(p)
        if self._drawing_line:
            self._paint_line_preview(p)

        # Sensor callouts are drawn in screen-space (reset transform first)
        p.resetTransform()
        self._paint_sensor_callouts(p)

    def _paint_resize_handles(self, p: QPainter):
        if not self.interactive:
            return
        actively_resizing = self._resizing_comp is not None
        ctrl_held = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        if not actively_resizing and (len(self._selected_comps) != 1 or not ctrl_held):
            return
        cid = self._resizing_comp or next(iter(self._selected_comps))
        comp = self.project.components.get(cid)
        pos = self.project.layout.get(cid)
        if not comp or not pos:
            return
        rect = world_rect(pos, comp.type, comp)
        hw, hh = rect.width() / 2, rect.height() / 2
        size = 6 / self._zoom
        p.setPen(QPen(PR.C_SELECT, 1.2 / self._zoom))
        p.setBrush(QBrush(PR.C_SELECT))
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            hx = pos.x + sx * hw
            hy = pos.y + sy * hh
            p.drawRect(QRectF(hx - size / 2, hy - size / 2, size, size))

    # Default anchor: directly below the sensor circle so the readout feels
    # like part of the symbol. Users can still drag it anywhere.
    _CALLOUT_DEFAULT_OFFSET = (0.0, SNS_R + 8.0)

    def _callout_screen_pos(self, cid: str, comp_pos) -> QPointF:
        """Return the screen position for a sensor callout anchor."""
        dx, dy = self._callout_offsets.get(cid, self._CALLOUT_DEFAULT_OFFSET)
        wx = comp_pos.x + dx
        wy = comp_pos.y + dy
        return QPointF((wx + self._pan.x()) * self._zoom,
                       (wy + self._pan.y()) * self._zoom)

    def _paint_sensor_callouts(self, p: QPainter):
        self._callout_rects.clear()
        if not self.project or self.interactive:
            return

        pad_x, pad_y, gap = 6, 3, 6
        f_lbl = QFont("Courier New", 7)
        f_lbl.setBold(True)
        f_val = QFont("Courier New", 9)
        f_val.setBold(True)
        fm_lbl = QFontMetrics(f_lbl)
        fm_val = QFontMetrics(f_val)

        for cid, comp in self.project.components.items():
            if comp.type not in SENSOR_TYPES:
                continue
            pos = self.project.layout.get(cid)
            if not pos:
                continue
            value = self.live_sensor_values.get(cid)

            if value is None:
                val_str = "---"
            elif comp.type == COMP_LOAD_CELL:
                val_str = f"{value:.1f}"
            else:
                val_str = f"{value:.2f}"
            unit = SENSOR_UNIT.get(comp.type, "")
            lbl  = comp.label or cid

            # Compact single-line pill:  P1  512.30 psi
            lbl_w  = fm_lbl.horizontalAdvance(lbl)
            val_w  = fm_val.horizontalAdvance(val_str)
            unit_w = fm_lbl.horizontalAdvance(unit)
            box_w  = pad_x * 2 + lbl_w + gap + val_w + (gap - 2 + unit_w if unit else 0)
            box_h  = fm_val.height() + pad_y * 2

            # Anchor sits below the sensor; box is centred on it
            sp  = self._callout_screen_pos(cid, pos)
            box = QRectF(sp.x() - box_w / 2, sp.y(), box_w, box_h)

            if box.right()  > self.width():  box.moveRight(self.width() - 2)
            if box.bottom() > self.height(): box.moveBottom(self.height() - 2)
            if box.left()   < 0:             box.moveLeft(2)
            if box.top()    < 0:             box.moveTop(2)

            self._callout_rects[cid] = QRectF(box)

            bg     = SENSOR_CALLOUT_BG.get(comp.type,     QColor(20, 30, 50, 220))
            border = SENSOR_CALLOUT_BORDER.get(comp.type, QColor("#4488ff"))

            # Override border with MEOP/MAWP alert color for pressure sensors
            if comp.type == COMP_PRESSURE and value is not None:
                alert = self._sensor_alert_color(cid, value)
                if alert is not None:
                    border = alert
                    # Also tint the background slightly toward the alert hue
                    tinted = QColor(alert)
                    tinted.setAlpha(60)
                    bg = tinted
            # Leader line only when the callout was dragged away from its sensor
            if cid in self._callout_offsets:
                sensor_screen = QPointF(
                    (pos.x + self._pan.x()) * self._zoom,
                    (pos.y + self._pan.y()) * self._zoom,
                )
                if not box.adjusted(-8, -8, 8, 8).contains(sensor_screen):
                    p.setPen(QPen(border.darker(130), 1.0, Qt.DashLine))
                    p.drawLine(sensor_screen, box.center())

            p.setBrush(QBrush(bg))
            p.setPen(QPen(border, 1.2))
            p.drawRoundedRect(box, box_h / 2, box_h / 2)

            baseline = box.top() + pad_y + fm_val.ascent()
            x = box.left() + pad_x

            p.setFont(f_lbl)
            p.setPen(QPen(border.lighter(160)))
            p.drawText(QPointF(x, baseline - 1), lbl)
            x += lbl_w + gap

            p.setFont(f_val)
            p.setPen(QPen(self._sensor_value_color(comp.type, value, cid)))
            p.drawText(QPointF(x, baseline), val_str)
            x += val_w + gap - 2

            if unit:
                p.setFont(f_lbl)
                p.setPen(QPen(QColor("#9b9990")))
                p.drawText(QPointF(x, baseline - 1), unit)

    def _sensor_alert_color(self, cid: str, value: float) -> "QColor | None":
        if value is None or not self.project:
            return None
        comp = self.project.components.get(cid)
        if not comp:
            return None

        thresholds = comp.extras.get("thresholds") or {}
        meop = thresholds.get("meop")
        mawp = thresholds.get("mawp")

        # Fall back to system-wide limits when per-sensor ones are absent
        params = getattr(self.project, "parameters", None)
        if meop is None and params is not None:
            meop = getattr(params, "system_meop", None)
        if mawp is None and params is not None:
            mawp = getattr(params, "system_mawp", None)

        return self._overpressure_line_color(value, meop, mawp)

    def _sensor_value_color(self, ctype: str, value: float, cid: str) -> QColor:
        """Return a colour for the sensor value text in the callout box.
        White normally; transitions to orange then dark maroon as the reading
        approaches/exceeds MEOP and MAWP."""
        alert = self._sensor_alert_color(cid, value)
        if alert is not None:
            return alert
        return QColor("#ffffff")

    def _callout_at(self, screen_pos: QPointF) -> "str | None":
        for cid, rect in self._callout_rects.items():
            if rect.adjusted(-2, -2, 2, 2).contains(screen_pos):
                return cid
        return None

    def _paint_grid_screen(self, p: QPainter):
        step = GRID_SPACING * self._zoom
        if step < 6:
            return  # zoomed far out - dots would be noise, skip for speed

        key = (round(step, 3), self.width(), self.height())
        if self._grid_cache_key != key:
            w = self.width() + int(step) + 2
            h = self.height() + int(step) + 2
            pm = QPixmap(w, h)
            pm.fill(Qt.transparent)
            gp = QPainter(pm)
            gp.setPen(QPen(PR.C_GRID, 1.5))
            pts = []
            y = 0.0
            while y <= h:
                x = 0.0
                while x <= w:
                    pts.append(QPointF(x, y))
                    x += step
                y += step
            gp.drawPoints(QPolygonF(pts))
            gp.end()
            self._grid_pixmap = pm
            self._grid_cache_key = key

        # Align the tile with world grid coordinates
        off_x = (self._pan.x() * self._zoom) % step - step
        off_y = (self._pan.y() * self._zoom) % step - step
        p.drawPixmap(int(off_x), int(off_y), self._grid_pixmap)

    def _paint_lines(self, p):
        pressure_values = self._line_pressure_values()
        pressurized = self._pressurized_line_ids() if not self.interactive else set()

        for line in self.project.lines:
            pts = line.points
            if len(pts) < 2:
                continue
            color = FLUID_QC.get(line.fluid, QColor("#c8c8c8"))

            pressure = pressure_values.get(line.id)
            is_overpressure = False
            if pressure is not None:
                max_pressure = None
                meop = mawp = None

                candidate_cids = list(self._line_sensor_map.get(line.id, ()))
                for cid, comp in self.project.components.items():
                    if (comp.type == COMP_PRESSURE
                            and str(comp.extras.get("line_id", "")).strip() == line.id
                            and cid not in candidate_cids):
                        candidate_cids.append(cid)

                for cid in candidate_cids:
                    comp = self.project.components.get(cid)
                    if not comp or self.live_sensor_values.get(cid) != pressure:
                        continue
                    try:
                        max_pressure = float(comp.extras["line_pressure_max"])
                    except (KeyError, TypeError, ValueError):
                        max_pressure = None
                    thresholds = comp.extras.get("thresholds") or {}
                    meop = thresholds.get("meop")
                    mawp = thresholds.get("mawp")
                    break

                params = getattr(self.project, "parameters", None)
                if meop is None and params is not None:
                    meop = getattr(params, "system_meop", None)
                if mawp is None and params is not None:
                    mawp = getattr(params, "system_mawp", None)

                overpressure_color = self._overpressure_line_color(pressure, meop, mawp)
                if overpressure_color is not None:
                    color = overpressure_color
                    is_overpressure = True
                elif max_pressure is not None:
                    color = self._pressure_line_color(color, pressure, max_pressure)

            is_selected    = line.id in self._selected_lines
            is_hovered     = line.id == self._hovered_line
            is_dotted      = getattr(line, 'dotted', False)
            is_generic     = line.fluid == FLUID_GENERIC
            is_pressurized = (line.id in pressurized and not is_generic) or is_overpressure
            pipe_style     = Qt.DashLine if is_dotted else Qt.SolidLine

            if is_pressurized and not (is_selected or is_hovered):
                glow = QColor(color)
                glow.setAlpha(150 if is_overpressure else 90)
                glow_width = (PIPE_W * 5.0 if is_overpressure else PIPE_W * 3.6) / self._zoom
                p.setPen(QPen(glow, glow_width, Qt.SolidLine, Qt.RoundCap))
                for i in range(len(pts) - 1):
                    p.drawLine(QPointF(pts[i].x,   pts[i].y),
                               QPointF(pts[i+1].x, pts[i+1].y))

            if is_selected:
                pen = QPen(PR.C_SELECT, (PIPE_W + 2) / self._zoom)
                pen.setStyle(pipe_style)
            elif is_hovered:
                pen = QPen(PR.C_HOVER, (PIPE_W + 1) / self._zoom)
                pen.setStyle(pipe_style)
            elif is_pressurized:
                pen = QPen(color.lighter(135), (PIPE_W * 1.5) / self._zoom)
                pen.setStyle(pipe_style)
            else:
                draw_color = color
                if not self.interactive and not is_generic:
                    # Live view: recede unpressurized fluid pipes so pressure pops
                    draw_color = QColor(color)
                    draw_color.setAlpha(110)
                pen = QPen(draw_color, PIPE_W / self._zoom)
                pen.setStyle(pipe_style)

            p.setPen(pen)
            for i in range(len(pts) - 1):
                p.drawLine(QPointF(pts[i].x,   pts[i].y),
                           QPointF(pts[i+1].x, pts[i+1].y))

            if is_selected:
                p.setPen(QPen(PR.C_SELECT, 1.5 / self._zoom))
                p.setBrush(QBrush(PR.C_SELECT))
                for pt in pts:
                    p.drawEllipse(QPointF(pt.x, pt.y), 5 / self._zoom, 5 / self._zoom)

    def _paint_components(self, p):
        for cid, comp in self.project.components.items():
            pos = self.project.layout.get(cid)
            if not pos:
                continue
            state = self.live_valve_states.get(cid, "CLOSED")
            value = self.live_sensor_values.get(cid)
            if comp.type in (COMP_GLOBE_VALVE, COMP_EP_THROTTLE_VALVE):
                thr = self.live_throttle_pcts.get(cid)
                if thr is not None:
                    value = thr
            # skip the world-space label so the two don't overlap.
            show_label = self.interactive or comp.type not in SENSOR_TYPES
            # Compute alert color for PT sensors (MEOP/MAWP glow)
            alert_color = None
            if comp.type == COMP_PRESSURE and not self.interactive:
                alert_color = self._sensor_alert_color(cid, value)
            Renderer.draw(p, comp, pos,
                        state       = state,
                        value       = value,
                        selected    = cid in self._selected_comps,
                        hovered     = cid == self._hovered_comp,
                        zoom        = self._zoom,
                        show_label  = show_label,
                        alert_color = alert_color)

    def _paint_line_preview(self, p):
        fluid_color = FLUID_QC.get(self._line_fluid, QColor("#c8c8c8"))

        if len(self._line_points) >= 2:
            p.setPen(QPen(fluid_color, PIPE_W / self._zoom))
            for i in range(len(self._line_points) - 1):
                p.drawLine(QPointF(self._line_points[i].x,   self._line_points[i].y),
                           QPointF(self._line_points[i+1].x, self._line_points[i+1].y))

        if self._line_points and self._line_cursor:
            dash_pen = QPen(fluid_color, PIPE_W / self._zoom, Qt.DashLine)
            p.setPen(dash_pen)
            lp = self._line_points[-1]
            p.drawLine(QPointF(lp.x, lp.y), self._line_cursor)

        p.setBrush(QBrush(fluid_color))
        p.setPen(Qt.NoPen)
        for pt in self._line_points:
            p.drawEllipse(QPointF(pt.x, pt.y), 4 / self._zoom, 4 / self._zoom)
        if self._line_cursor:
            p.drawEllipse(self._line_cursor, 3 / self._zoom, 3 / self._zoom)

    def mousePressEvent(self, event):
        world = self._to_world(event.x(), event.y())
        screen = QPointF(event.x(), event.y())

        # Hide popup on any press not inside it
        if self._valve_popup.isVisible():
            popup_rect = self._valve_popup.geometry()
            if not popup_rect.contains(event.pos()):
                self._valve_popup.hide()

        if (event.button() == Qt.RightButton or
                (event.button() == Qt.LeftButton and event.modifiers() & Qt.AltModifier)):
            self._pan_start  = event.pos()
            self._pan_origin = QPointF(self._pan)
            self.setCursor(Qt.ClosedHandCursor)
            return

        if self._drawing_line and event.button() == Qt.MiddleButton:
            if len(self._line_points) > 1:
                self._line_points.pop()
                self.update()
            else:
                self.cancel_line_draw()
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            if self.interactive and (event.modifiers() & Qt.ControlModifier):
                handle = self._resize_handle_at(world)
                if handle:
                    cid, sx, sy = handle
                    comp = self.project.components[cid]
                    pos  = self.project.layout[cid]
                    base_rect = world_rect(pos, comp.type, None)   # scale = 1.0
                    self._resizing_comp    = cid
                    self._resize_base_half = (base_rect.width() / 2, base_rect.height() / 2)
                    self._resize_center    = QPointF(pos.x, pos.y)
                    self.setCursor(Qt.SizeFDiagCursor if sx == sy else Qt.SizeBDiagCursor)
                    event.accept()
                    return

            if self._drawing_line:
                sx, sy = snap(world.x(), world.y())
                self._line_points.append(LayoutPoint(sx, sy))
                self.update()
                return

            # Check callout drag first (sensor labels)
            callout_cid = self._callout_at(screen)
            if callout_cid:
                self._dragging_callout      = callout_cid
                self._callout_drag_start_world = world
                dx, dy = self._callout_offsets.get(callout_cid, self._CALLOUT_DEFAULT_OFFSET)
                self._callout_drag_start_off = (dx, dy)
                self.setCursor(Qt.SizeAllCursor)
                return

            cid = self._comp_at(world)
            if cid:
                if event.modifiers() & Qt.ShiftModifier:
                    if cid in self._selected_comps:
                        self._selected_comps.remove(cid)
                    else:
                        self._selected_comps.add(cid)
                else:
                    self._selected_comps = {cid}
                    self._selected_lines.clear()

                self.component_clicked.emit(cid)

                # Show valve popup in live (non-interactive/non-editor) mode
                comp = self.project.components.get(cid) if self.project else None
                if comp and comp.type in VALVE_TYPES and not self.interactive:
                    state = self.live_valve_states.get(cid, "CLOSED")
                    comp_pos = self.project.layout[cid]
                    sp = QPointF(
                        (comp_pos.x + self._pan.x()) * self._zoom,
                        (comp_pos.y + self._pan.y()) * self._zoom,
                    )
                    self._valve_popup.show_for(cid, state, sp,
                                               is_igniter=(comp.type == COMP_IGNITER))

                if self.interactive:
                    self._dragging_comp    = cid
                    self._drag_start_world = world
                    self._drag_start_pos   = LayoutPoint(
                        self.project.layout[cid].x,
                        self.project.layout[cid].y,
                    )
                    self.setCursor(Qt.SizeAllCursor)
            else:
                lid = self._line_at(world, 8 / self._zoom)
                if lid:
                    if event.modifiers() & Qt.ShiftModifier:
                        if lid in self._selected_lines:
                            self._selected_lines.remove(lid)
                        else:
                            self._selected_lines.add(lid)
                    else:
                        self._selected_lines = {lid}
                        self._selected_comps.clear()
                    self.line_clicked.emit(lid)
                else:
                    self._selected_comps.clear()
                    self._selected_lines.clear()
                    self.canvas_clicked.emit(world.x(), world.y())
            self.update()

        if event.button() == Qt.RightButton and self._drawing_line:
            if self._line_points:
                self._line_points.pop()
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing_line:
            world = self._to_world(event.x(), event.y())
            sx, sy = snap(world.x(), world.y())
            pts = self._line_points
            if not pts or (sx, sy) != (pts[-1].x, pts[-1].y):
                pts.append(LayoutPoint(sx, sy))
            self.finish_line_draw()

    def mouseMoveEvent(self, event):
        world = self._to_world(event.x(), event.y())

        if self._pan_start is not None:
            delta = event.pos() - self._pan_start
            self._pan = QPointF(
                self._pan_origin.x() + delta.x() / self._zoom,
                self._pan_origin.y() + delta.y() / self._zoom,
            )
            self.update()
            return

        if self._resizing_comp and self.interactive:
            base_hw, base_hh = self._resize_base_half
            cx, cy = self._resize_center.x(), self._resize_center.y()
            comp = self.project.components.get(self._resizing_comp)
            if comp and base_hw > 0 and base_hh > 0:
                comp.extras["scale_x"] = round(max(0.2, abs(world.x() - cx) / base_hw), 3)
                comp.extras["scale_y"] = round(max(0.2, abs(world.y() - cy) / base_hh), 3)
                self.update()
            return

        if self._dragging_callout:
            dx0, dy0 = self._callout_drag_start_off
            delta_wx = world.x() - self._callout_drag_start_world.x()
            delta_wy = world.y() - self._callout_drag_start_world.y()
            self._callout_offsets[self._dragging_callout] = (dx0 + delta_wx, dy0 + delta_wy)
            self.update()
            return

        if self._dragging_comp and self.interactive:
            dx = world.x() - self._drag_start_world.x()
            dy = world.y() - self._drag_start_world.y()
            sx, sy = snap(self._drag_start_pos.x + dx, self._drag_start_pos.y + dy)
            self.project.layout[self._dragging_comp] = LayoutPoint(sx, sy)
            self.update()
            return

        if self._drawing_line:
            sx, sy = snap(world.x(), world.y())
            self._line_cursor = QPointF(sx, sy)
            self.update()
            return

        cid = self._comp_at(world)
        if cid != self._hovered_comp:
            self._hovered_comp = cid
            self.update()

        if not cid:
            lid = self._line_at(world, 8 / self._zoom)
            if lid != self._hovered_line:
                self._hovered_line = lid
                self.update()
        else:
            if self._hovered_line:
                self._hovered_line = None
                self.update()

        # Ctrl + hovering a selected component's corner handle -> resize cursor
        if self.interactive and len(self._selected_comps) == 1 and (event.modifiers() & Qt.ControlModifier):
            handle = self._resize_handle_at(world)
            if handle:
                _, hsx, hsy = handle
                self.setCursor(Qt.SizeFDiagCursor if hsx == hsy else Qt.SizeBDiagCursor)
                self.update()
                return

        # Change cursor if hovering a callout label
        callout_cid = self._callout_at(QPointF(event.x(), event.y()))
        if callout_cid:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.PointingHandCursor if (cid or self._hovered_line) else Qt.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self._pan_start is not None:
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            return
        if self._resizing_comp:
            cid = self._resizing_comp
            self._resizing_comp    = None
            self._resize_base_half = None
            self._resize_center    = None
            self.setCursor(Qt.ArrowCursor)
            self.component_resized.emit(cid)
            return
        if self._dragging_callout:
            self._dragging_callout = None
            self.setCursor(Qt.ArrowCursor)
            return
        if self._dragging_comp:
            pos = self.project.layout[self._dragging_comp]
            self.component_moved.emit(self._dragging_comp, pos.x, pos.y)
            self._dragging_comp = None
            self.setCursor(Qt.ArrowCursor)

    def set_dark_mode(self, dark: bool):
        """Swap the shared canvas palette (all canvases follow) and repaint."""
        apply_canvas_theme(dark)
        self.update()

    def wheelEvent(self, event):
        pixel = event.pixelDelta()

        # Trackpad two-finger scroll (Qt reports it via pixelDelta) pans the
        # view; hold Ctrl to zoom instead. A mouse wheel (angleDelta only)
        # keeps zooming like it always has.
        if not pixel.isNull() and not (event.modifiers() & Qt.ControlModifier):
            self._pan += QPointF(pixel.x() / self._zoom, pixel.y() / self._zoom)
            event.accept()
            self.update()
            return

        delta = pixel.y()
        if delta == 0:
            delta = event.angleDelta().y()
        if delta == 0:
            event.ignore()
            return

        # Trackpads often emit very small deltas; use a continuous curve so
        # the zoom feels smooth instead of jumping in coarse wheel steps.
        factor = math.exp((delta / 120.0) * math.log(1.15))
        self._zoom_at(event.pos().x(), event.pos().y(), factor)
        event.accept()
        self.update()

    def _zoom_at(self, screen_x: float, screen_y: float, factor: float):
        old_zoom = self._zoom
        new_zoom = max(0.05, min(old_zoom * factor, 10.0))
        if new_zoom == old_zoom:
            return

        world_x = screen_x / old_zoom - self._pan.x()
        world_y = screen_y / old_zoom - self._pan.y()

        self._zoom = new_zoom
        self._pan = QPointF(
            screen_x / self._zoom - world_x,
            screen_y / self._zoom - world_y,
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if self._drawing_line:
                self.cancel_line_draw()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if self._drawing_line:
                self.finish_line_draw()
        elif event.key() == Qt.Key_F:
            self.fit_view()
        elif event.key() == Qt.Key_Delete and self.interactive:
            for cid in list(self._selected_comps):
                if self.project:
                    self.project.remove_component(cid)
            self._selected_comps.clear()

            for lid in list(self._selected_lines):
                if self.project:
                    self.project.lines = [l for l in self.project.lines if l.id != lid]
            self._selected_lines.clear()
            
            self.update()
        elif event.key() == Qt.Key_Control and len(self._selected_comps) == 1:
            self.update()   # show resize handles immediately, don't wait for mouse move
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.update()   # hide resize handles as soon as Ctrl is released
        else:
            super().keyReleaseEvent(event)


def _seg_dist(p: QPointF, a: QPointF, b: QPointF) -> float:
    dx, dy = b.x() - a.x(), b.y() - a.y()
    if dx == 0 and dy == 0:
        return math.hypot(p.x() - a.x(), p.y() - a.y())
    t = max(0.0, min(1.0, ((p.x()-a.x())*dx + (p.y()-a.y())*dy) / (dx*dx+dy*dy)))
    return math.hypot(p.x()-(a.x()+t*dx), p.y()-(a.y()+t*dy))