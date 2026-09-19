from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QPainterPath, QPolygonF,
)
from PyQt5.QtCore import Qt, QPointF, QRectF
import math

from PID_SCHEMA import (
    Component, LayoutPoint,
    FLUID_COLORS,
    COMP_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_TANK, COMP_INJECTOR,
    COMP_REGULATOR, COMP_CHECK_VALVE, COMP_RELIEF_VALVE, COMP_LABEL, COMP_JUNCTION,
    COMP_BALL_VALVE, COMP_PSV, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_REDUCER, COMP_PRV,
    COMP_IGNITER,
    COMP_ORIFICE, COMP_FILTER,
    COMP_ACTUATED_VALVE, COMP_ACTUATED_VALVE_LS, COMP_NEEDLE_VALVE, COMP_THREE_WAY_VALVE,
    COMP_EP_THROTTLE_VALVE, COMP_BURST_DISK, COMP_BULKHEAD, COMP_QUICK_DISCONNECT,
    COMP_CAP_PLUG, COMP_HAND_REGULATOR, COMP_DOME_REGULATOR, COMP_EP_CONVERTER,
    COMP_PUMP, COMP_PRESSURE_GAUGE, COMP_DIFF_PRESSURE, COMP_FLOW_METER,
    COMP_TO_ATMOSPHERE, COMP_FLEX_HOSE, COMP_BELLOWS, COMP_HEAT_EXCHANGER, COMP_PANEL,
)

GRID_SPACING = 10

# Standard sizes
VLV_HW = 18
VLV_HH = 14
SNS_R = 16
TNK_HW = 28
TNK_HH = 50
JCT_R = 5
PIPE_W = 2.5

_CANVAS_THEMES = {
    True: dict(   # dark
        bg="#0d0d0f", grid="#1c1c22", symbol="#e8e8e8", fill_closed="#2a2a2a",
        fill_open="#00c853", fill_pend="#ff9800", sensor_fill="#1a2a3a",
        tank_fill="#1a1a2e", label="#d0d0d0", select="#ffd600",
        hover="#64b5f6", aux_fill="#2a2a2a",
    ),
    False: dict(  # light
        bg="#f4f4f0", grid="#dcdcd4", symbol="#1a1a1a", fill_closed="#d6d6d0",
        fill_open="#00a344", fill_pend="#e07f00", sensor_fill="#d9e6f2",
        tank_fill="#e2e2ee", label="#202020", select="#c27b00",
        hover="#1976d2", aux_fill="#d6d6d0",
    ),
}

CANVAS_DARK_MODE = True

def apply_canvas_theme(dark: bool):
    global CANVAS_DARK_MODE, C_BG, C_GRID, C_SYMBOL, C_FILL_CLOSED
    global C_FILL_OPEN, C_FILL_PEND, C_SENSOR_FILL, C_TANK_FILL, C_LABEL
    global C_SELECT, C_HOVER, C_PSV_FILL, C_PRV_FILL, C_SOLENOID_FILL, C_REDUCER_FILL
    global C_AUX_FILL
    CANVAS_DARK_MODE = bool(dark)
    t = _CANVAS_THEMES[CANVAS_DARK_MODE]
    C_BG          = QColor(t["bg"])
    C_GRID        = QColor(t["grid"])
    C_SYMBOL      = QColor(t["symbol"])
    C_FILL_CLOSED = QColor(t["fill_closed"])
    C_FILL_OPEN   = QColor(t["fill_open"])
    C_FILL_PEND   = QColor(t["fill_pend"])
    C_SENSOR_FILL = QColor(t["sensor_fill"])
    C_TANK_FILL   = QColor(t["tank_fill"])
    C_LABEL       = QColor(t["label"])
    C_SELECT      = QColor(t["select"])
    C_HOVER       = QColor(t["hover"])
    C_PSV_FILL      = QColor(t["aux_fill"])
    C_PRV_FILL      = QColor(t["aux_fill"])
    C_SOLENOID_FILL = QColor(t["aux_fill"])
    C_REDUCER_FILL  = QColor(t["aux_fill"])
    # Shared fill for the new RED-001 3.3 passive/inline fittings (orifice,
    # filter, bulkhead, burst disk, quick disconnect, cap/plug, EP converter,
    # flex hose, bellows, heat exchanger).
    C_AUX_FILL      = QColor(t["aux_fill"])

apply_canvas_theme(True)

# RED-001 3.3 Panel fill color is a fixed document standard color (not
# theme-dependent), per Table 3.3.
C_PANEL_FILL = QColor("#D4E1F5")

FLUID_QC = {k: QColor(v) for k, v in FLUID_COLORS.items()}


def _blend_color(start: QColor, end: QColor, amount: float) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        int(start.red()   + (end.red()   - start.red())   * amount),
        int(start.green() + (end.green() - start.green()) * amount),
        int(start.blue()  + (end.blue()  - start.blue())  * amount),
        int(start.alpha() + (end.alpha() - start.alpha()) * amount),
    )

def snap(x: float, y: float, grid: float = GRID_SPACING):
    return (round(x / grid) * grid, round(y / grid) * grid)


def _component_scale(comp: Component) -> tuple[float, float]:
    def _read(name: str) -> float:
        try:
            return max(0.2, float(comp.extras.get(name, 1.0)))
        except (TypeError, ValueError):
            return 1.0

    return _read("scale_x"), _read("scale_y")


def world_rect(pos: LayoutPoint, ctype: str, comp: Component | None = None) -> QRectF:
    x, y = pos.x, pos.y
    scale_x, scale_y = (1.0, 1.0)
    if comp is not None:
        scale_x, scale_y = _component_scale(comp)

    half_w = 20 * scale_x
    half_h = 14 * scale_y
    if ctype in (COMP_VALVE, COMP_CHECK_VALVE,
                 COMP_RELIEF_VALVE, COMP_REGULATOR, COMP_BALL_VALVE,
                 COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_PSV, COMP_PRV,
                 COMP_NEEDLE_VALVE, COMP_THREE_WAY_VALVE):
        return QRectF(x - VLV_HW * scale_x, y - VLV_HH * scale_y, VLV_HW * 2 * scale_x, VLV_HH * 2 * scale_y)
    if ctype in (COMP_ACTUATED_VALVE, COMP_ACTUATED_VALVE_LS, COMP_EP_THROTTLE_VALVE,
                 COMP_HAND_REGULATOR, COMP_DOME_REGULATOR):
        # Taller bounding box: these stack an actuator/dome/E-P box above the
        # valve body itself.
        return QRectF(x - VLV_HW * scale_x, y - (VLV_HH + 28) * scale_y,
                       VLV_HW * 2 * scale_x, (VLV_HH * 2 + 28) * scale_y)
    if ctype in (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL, COMP_IGNITER,
                 COMP_PRESSURE_GAUGE, COMP_DIFF_PRESSURE, COMP_PUMP):
        r = SNS_R * max(scale_x, scale_y)
        return QRectF(x - r, y - r, r * 2, r * 2)
    if ctype == COMP_FLOW_METER:
        r = SNS_R * max(scale_x, scale_y)
        return QRectF(x - r * 1.6, y - r, r * 3.2, r * 2)
    if ctype == COMP_TANK:
        return QRectF(x - TNK_HW * scale_x, y - TNK_HH * scale_y, TNK_HW * 2 * scale_x, TNK_HH * 2 * scale_y)
    if ctype == COMP_REDUCER:
        return QRectF(x - VLV_HW * scale_x, y - VLV_HH * scale_y, VLV_HW * 2 * scale_x, VLV_HH * 2 * scale_y)
    if ctype == COMP_INJECTOR:
        return QRectF(x - 22 * scale_x, y - 28 * scale_y, 44 * scale_x, 56 * scale_y)
    if ctype == COMP_JUNCTION:
        r = JCT_R * max(scale_x, scale_y)
        return QRectF(x - r, y - r, r * 2, r * 2)
    if ctype in (COMP_ORIFICE, COMP_FILTER, COMP_BULKHEAD, COMP_QUICK_DISCONNECT,
                 COMP_CAP_PLUG, COMP_BURST_DISK, COMP_EP_CONVERTER, COMP_FLEX_HOSE,
                 COMP_BELLOWS, COMP_HEAT_EXCHANGER, COMP_TO_ATMOSPHERE):
        return QRectF(x - half_w, y - half_h, half_w * 2, half_h * 2)
    if ctype == COMP_PANEL:
        pw = 100 * scale_x
        ph = 60 * scale_y
        return QRectF(x - pw, y - ph, pw * 2, ph * 2)
    return QRectF(x - half_w, y - half_h, half_w * 2, half_h * 2)

class Renderer:

    @staticmethod
    def draw(p: QPainter, comp: Component, pos: LayoutPoint,
             state: str = "CLOSED", value: float = None,
             selected: bool = False, hovered: bool = False,
             zoom: float = 1.0, show_label: bool = True, **kwargs):

        t = comp.type
        scale_x, scale_y = _component_scale(comp)

        p.save()
        p.translate(pos.x, pos.y)
        p.rotate(comp.rotation)
        p.translate(-pos.x, -pos.y)

        if t == COMP_VALVE:
            # RED-001 3.3: Manual Valve
            Renderer._valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_CHECK_VALVE:
            Renderer._check_valve(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_RELIEF_VALVE:
            Renderer._relief_valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_PRESSURE:
            Renderer._sensor(p, pos, "P",  value, zoom, scale_x, scale_y,
                             alert_color=kwargs.get("alert_color"))
        elif t == COMP_TEMPERATURE:
            Renderer._sensor(p, pos, "T",  value, zoom, scale_x, scale_y)
        elif t == COMP_LOAD_CELL:
            Renderer._sensor(p, pos, "LC", value, zoom, scale_x, scale_y)
        elif t == COMP_TANK:
            Renderer._tank(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_INJECTOR:
            Renderer._injector(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_REGULATOR:
            Renderer._regulator(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_JUNCTION:
            Renderer._junction(p, pos, scale_x, scale_y)
        elif t == COMP_BALL_VALVE:
            Renderer._ball_valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_SOLENOID:
            Renderer._solenoid_valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_GLOBE_VALVE:
            Renderer._globe_valve(p, pos, state, value, zoom, scale_x, scale_y)
        elif t == COMP_PSV:
            Renderer._psv(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_PRV:
            Renderer._prv(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_REDUCER:
            Renderer._reducer(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_IGNITER:
            Renderer._igniter(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_ORIFICE:
            Renderer._orifice(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_FILTER:
            Renderer._filter(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_ACTUATED_VALVE:
            Renderer._actuated_valve(p, pos, state, zoom, scale_x, scale_y, limit=False)
        elif t == COMP_ACTUATED_VALVE_LS:
            Renderer._actuated_valve(p, pos, state, zoom, scale_x, scale_y, limit=True)
        elif t == COMP_NEEDLE_VALVE:
            Renderer._needle_valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_THREE_WAY_VALVE:
            Renderer._three_way_valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_EP_THROTTLE_VALVE:
            Renderer._ep_throttle_valve(p, pos, state, value, zoom, scale_x, scale_y)
        elif t == COMP_BURST_DISK:
            Renderer._burst_disk(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_BULKHEAD:
            Renderer._bulkhead(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_QUICK_DISCONNECT:
            Renderer._quick_disconnect(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_CAP_PLUG:
            Renderer._cap_plug(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_HAND_REGULATOR:
            Renderer._hand_regulator(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_DOME_REGULATOR:
            Renderer._dome_regulator(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_EP_CONVERTER:
            Renderer._ep_converter(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_PUMP:
            Renderer._pump(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_PRESSURE_GAUGE:
            Renderer._pressure_gauge(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_DIFF_PRESSURE:
            Renderer._diff_pressure(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_FLOW_METER:
            Renderer._flow_meter(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_TO_ATMOSPHERE:
            Renderer._to_atmosphere(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_FLEX_HOSE:
            Renderer._flex_hose(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_BELLOWS:
            Renderer._bellows(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_HEAT_EXCHANGER:
            Renderer._heat_exchanger(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_PANEL:
            Renderer._panel(p, pos, zoom, scale_x, scale_y)

        p.restore()
        if show_label and t == COMP_PANEL:
            # RED-001 3.3: Panel — bold "Description" label sits inside the
            # panel at the top-left, not centered below like other parts.
            Renderer._panel_lbl(p, pos, comp.label or "Description", zoom, scale_x, scale_y)
        elif show_label:
            lbl = comp.label or comp.id
            offset = (VLV_HH + 20) * max(scale_y, 0.8)
            font_scale = max(scale_x, scale_y) if t == COMP_LABEL else 1.0
            Renderer._lbl(p, pos, lbl, zoom, offset, comp, font_scale=font_scale)

        if selected or hovered:
            r = world_rect(pos, t, comp).adjusted(-6, -6, 6, 6)
            c = C_SELECT if selected else C_HOVER
            p.setPen(QPen(c, 1.5 / zoom, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)

    @staticmethod
    def _lbl(p, pos, label, zoom, offset, comp, font_scale=1.0):
        if not label: return
        if getattr(comp, 'hide_lbl', False): return

        f = QFont("Segoe UI", max(int(8 * font_scale / zoom), 6))
        p.setFont(f)
        p.setPen(QPen(C_LABEL))

        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(label)

        p.drawText(QPointF(pos.x - tw / 2, pos.y + offset), label)

    # Drawing Methods (this is how we draw icons, could be replaced with image assets)

    @staticmethod
    def _valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y

        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)

        path = QPainterPath()
        path.moveTo(x - hw, y - hh)
        path.lineTo(x + hw, y + hh)
        path.lineTo(x + hw, y - hh)
        path.lineTo(x - hw, y + hh)
        path.closeSubpath()

        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))
        p.drawPath(path)

        p.drawLine(QPointF(x, y - hh), QPointF(x, y - hh - 10))
        p.drawLine(QPointF(x - 8, y - hh - 10), QPointF(x + 8, y - hh - 10))

    @staticmethod
    def _check_valve(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        p.drawLine(QPointF(x - hw, y - hh), QPointF(x - hw, y + hh))
        p.drawLine(QPointF(x + hw, y - hh), QPointF(x + hw, y + hh))

        p.drawLine(QPointF(x - hw, y - hh), QPointF(x + hw - 4, y + hh - 4))

        p.setBrush(QBrush(C_SYMBOL))
        head = QPolygonF([
            QPointF(x + hw, y + hh),
            QPointF(x + hw - 8, y + hh),
            QPointF(x + hw, y + hh - 8)
        ])
        p.drawPolygon(head)


    @staticmethod
    def _relief_valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Relief Valve (RV): bowtie with a straight stem above
        crossed by four short diagonal spring-hatch ticks, per Table 3.3."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y
        fill = Renderer._valve_fill(state)

        Renderer._bowtie(p, x, y, hw, hh, fill, zoom)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.4 / zoom))
        sy = y - hh
        top_y = sy - 20 * scale_y
        p.drawLine(QPointF(x, sy), QPointF(x, top_y))

        for i in range(4):
            ty = sy - (4 + i * 4) * scale_y
            p.drawLine(QPointF(x - 4 * scale_x, ty + 3 * scale_y), QPointF(x + 4 * scale_x, ty - 3 * scale_y))


    @staticmethod
    def _sensor(p, pos, symbol, value, zoom, scale_x=1.0, scale_y=1.0,
                alert_color: QColor = None):
        x, y = pos.x, pos.y
        r = SNS_R * max(scale_x, scale_y)

        # Alert glow ring (MEOP/MAWP over-pressure on a PT)
        if alert_color is not None:
            glow = QColor(alert_color)
            glow.setAlpha(160)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(glow, (r * 0.55) / zoom, Qt.SolidLine, Qt.RoundCap))
            p.drawEllipse(QPointF(x, y), r + r * 0.35, r + r * 0.35)

        p.setBrush(QBrush(C_SENSOR_FILL))
        # Sensor circle border takes the alert color when pressurized above MEOP
        border_color = alert_color if alert_color is not None else C_SYMBOL
        p.setPen(QPen(border_color, 1.5 / zoom))
        p.drawEllipse(QPointF(x, y), r, r)

        fsz = max(int(9 / zoom), 6)
        f   = QFont("Courier New", fsz)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(C_LABEL))
        fm  = QFontMetrics(f)
        tw  = fm.horizontalAdvance(symbol)
        p.drawText(QPointF(x - tw / 2, y + fm.ascent() / 2 - 1 / zoom), symbol)


    @staticmethod
    def _igniter(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        """Circle like a sensor, but it's an actuated output: dark/grey when
        idle, green when firing - never a live reading."""
        x, y = pos.x, pos.y
        r = SNS_R * max(scale_x, scale_y)

        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)

        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.5 / zoom))
        p.drawEllipse(QPointF(x, y), r, r)

        fsz = max(int(8 / zoom), 6)
        f = QFont("Courier New", fsz)
        f.setBold(True)
        p.setFont(f)
        # Dark text reads better over the bright green "firing" fill
        p.setPen(QPen(QColor("#0a2a12") if state == "OPEN" else C_LABEL))
        fm = QFontMetrics(f)
        text = "IGN"
        tw = fm.horizontalAdvance(text)
        p.drawText(QPointF(x - tw / 2, y + fm.ascent() / 2 - 1 / zoom), text)

    @staticmethod
    def _tank(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hw, hh = TNK_HW * scale_x, TNK_HH * scale_y
        dome = 12 * scale_y

        p.setBrush(QBrush(C_TANK_FILL))
        p.setPen(QPen(C_SYMBOL, 1.5 / zoom))
        p.drawRect(QRectF(x - hw, y - hh + dome, hw * 2, (hh - dome) * 2))
        p.drawArc(QRectF(x - hw, y - hh - dome / 2, hw * 2, dome * 2),  0,  180 * 16)
        p.drawArc(QRectF(x - hw, y + hh - dome * 3 / 2, hw * 2, dome * 2), 0, -180 * 16)


    @staticmethod
    def _injector(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        tw, th, bw = 32 * scale_x, 44 * scale_y, 18 * scale_x

        path = QPainterPath()
        path.moveTo(x - tw / 2, y - th / 2)
        path.lineTo(x + tw / 2, y - th / 2)
        path.lineTo(x + bw / 2, y + th / 2)
        path.lineTo(x - bw / 2, y + th / 2)
        path.closeSubpath()

        p.setBrush(QBrush(C_TANK_FILL))
        p.setPen(QPen(C_SYMBOL, 1.5 / zoom))
        p.drawPath(path)

        f   = QFont("Courier New", max(int(7 / zoom), 5))
        p.setFont(f)
        p.setPen(QPen(C_LABEL))
        fm  = QFontMetrics(f)
        t   = "INJ"
        tw2 = fm.horizontalAdvance(t)
        p.drawText(QPointF(x - tw2 / 2, y + fm.ascent() / 2 - 4 / zoom), t)

    @staticmethod
    def _regulator(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        size = VLV_HW * 1.2 * max(scale_x, scale_y)

        p.setBrush(Qt.NoBrush)
        pen = QPen(C_SYMBOL, 1.8 / zoom)

        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(x - size, y, size, size))

        pen.setStyle(Qt.SolidLine)
        p.setPen(pen)
        p.setBrush(QBrush(C_TANK_FILL))
        p.drawRect(QRectF(x - size * 0.5, y - size * 0.7, size, size))

        p.setBrush(Qt.NoBrush)
        spring = QPainterPath()
        sx, sy = x + size * 0.5, y - size * 0.2
        spring.moveTo(sx, sy)
        spring.lineTo(sx + 4, sy)

        spring.lineTo(sx + 8, sy - 8)
        spring.lineTo(sx + 12, sy + 8)
        spring.lineTo(sx + 16, sy - 12)
        end_x, end_y = sx + 25, sy + 15
        spring.lineTo(end_x, end_y)
        p.drawPath(spring)

        p.setBrush(QBrush(C_SYMBOL))
        head = QPolygonF([
            QPointF(end_x, end_y),
            QPointF(end_x - 8, end_y - 2),
            QPointF(end_x - 2, end_y - 8)
        ])
        p.drawPolygon(head)


    @staticmethod
    def _junction(p, pos, scale_x=1.0, scale_y=1.0):
        p.setBrush(QBrush(C_SYMBOL))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(pos.x, pos.y), JCT_R * max(scale_x, scale_y), JCT_R * max(scale_x, scale_y))

    @staticmethod
    def _ball_valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y

        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)

        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        left_tri = QPolygonF([
            QPointF(x - hw, y - hh),
            QPointF(x - hw, y + hh),
            QPointF(x, y)
        ])

        right_tri = QPolygonF([
            QPointF(x + hw, y - hh),
            QPointF(x + hw, y + hh),
            QPointF(x, y)
        ])

        p.drawPolygon(left_tri)
        p.drawPolygon(right_tri)

        ball_r = min(hw, hh) * 0.75
        p.drawEllipse(QPointF(x, y), ball_r, ball_r)

        # internal indicator, if open, draw horizontal; if closed, draw vertical
        if state == "OPEN":
            p.drawLine(QPointF(x - ball_r + 2, y), QPointF(x + ball_r - 2, y))
        else:
            p.drawLine(QPointF(x, y - ball_r + 2), QPointF(x, y + ball_r - 2))


    @staticmethod
    def _solenoid_valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Solenoid Valve: bowtie with a coiled solenoid
        actuator on a stem above."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y

        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_SOLENOID_FILL)

        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        left_tri = QPolygonF([
            QPointF(x - hw, y - hh),
            QPointF(x - hw, y + hh),
            QPointF(x, y)
        ])

        right_tri = QPolygonF([
            QPointF(x + hw, y - hh),
            QPointF(x + hw, y + hh),
            QPointF(x, y)
        ])

        p.drawPolygon(left_tri)
        p.drawPolygon(right_tri)

        # Solenoid coil: a smooth curled spring directly off the valve top,
        # matching the spec's "S" squiggle rather than a sharp zigzag.
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.3 / zoom))
        sy = y - hh
        coil = QPainterPath()
        coil.moveTo(x, sy)
        loop_h = 4.2 * scale_y
        for i in range(3):
            top = sy - loop_h * (i + 1)
            mid = sy - loop_h * (i + 0.5)
            sign = 1 if i % 2 == 0 else -1
            coil.cubicTo(
                QPointF(x + sign * 5 * scale_x, mid + loop_h * 0.15),
                QPointF(x + sign * 5 * scale_x, mid - loop_h * 0.15),
                QPointF(x, top),
            )
        p.drawPath(coil)

    @staticmethod
    def _globe_valve(p, pos, state, value, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y

        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)

        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        pts_l = [QPointF(x - hw, y - hh), QPointF(x - hw, y + hh), QPointF(x, y)]
        pts_r = [QPointF(x + hw, y - hh), QPointF(x + hw, y + hh), QPointF(x, y)]

        p.drawPolygon(QPolygonF(pts_l))
        p.drawPolygon(QPolygonF(pts_r))

        # Globe body: outlined disc filled like the valve (ISA style), not a
        # solid white blob
        globe_r = min(hw, hh) * 0.65
        p.setBrush(QBrush(fill))
        p.drawEllipse(QPointF(x, y), globe_r, globe_r)
        p.drawLine(QPointF(x - globe_r, y), QPointF(x + globe_r, y))

        if value is not None:
            pct = f"{int(value)}%"
            f = QFont("Courier New", max(int(6 / zoom), 4))
            p.setFont(f)
            p.setPen(QPen(C_LABEL))
            tw = QFontMetrics(f).horizontalAdvance(pct)
            p.drawText(QPointF(x - tw / 2, y + hh + 8), pct)

    @staticmethod
    def _psv(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y

        p.setBrush(QBrush(C_PSV_FILL))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        top_tri = QPolygonF([QPointF(x - hw, y - hh), QPointF(x + hw, y - hh), QPointF(x, y)])
        bot_tri = QPolygonF([QPointF(x - hw, y + hh), QPointF(x + hw, y + hh), QPointF(x, y)])

        p.drawPolygon(top_tri)
        p.drawPolygon(bot_tri)

        p.setBrush(Qt.NoBrush)
        spring_path = QPainterPath()
        spring_path.moveTo(x, y)
        spring_path.lineTo(x + 6, y)

        spring_path.lineTo(x + 9, y - 5)
        spring_path.lineTo(x + 12, y + 5)
        spring_path.lineTo(x + 15, y - 5)
        spring_path.lineTo(x + 18, y)
        spring_path.lineTo(x + 24, y)
        p.drawPath(spring_path)

        arrow_head = QPolygonF([
            QPointF(x + 24, y - 4),
            QPointF(x + 30, y),
            QPointF(x + 24, y + 4)
        ])
        p.setBrush(QBrush(C_SYMBOL))
        p.drawPolygon(arrow_head)


    @staticmethod
    def _prv(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        hh = VLV_HH * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        p.drawLine(QPointF(x, y - hh - 5), QPointF(x, y + hh + 5))

        spring = QPainterPath()
        sy = y - 10
        spring.moveTo(x, sy)
        for i in range(4):
            spring.lineTo(x - 5, sy + (i * 4) + 1)
            spring.lineTo(x + 5, sy + (i * 4) + 3)
        spring.lineTo(x, sy + 16)
        p.drawPath(spring)

        ay = y + 6
        head = QPolygonF([
            QPointF(x - 4, ay),
            QPointF(x + 4, ay),
            QPointF(x, ay + 7)
        ])
        p.setBrush(QBrush(C_SYMBOL))
        p.drawPolygon(head)


    @staticmethod
    def _reducer(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        w = VLV_HW * 1.5 * scale_x
        h = VLV_HH * 2 * scale_y

        p.setBrush(QBrush(C_REDUCER_FILL))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        path = QPolygonF([
            QPointF(x - w/3, y - h/2),
            QPointF(x + w/3, y - h/2),
            QPointF(x + w/2, y + h/2),
            QPointF(x - w/2, y + h/2)
        ])

        p.drawPolygon(path)

    # ------------------------------------------------------------------
    # RED-001 3.3 standardized parts
    # ------------------------------------------------------------------

    @staticmethod
    def _bowtie(p, x, y, hw, hh, fill, zoom):
        """Shared two-triangle valve body used by several RED-001 valve
        symbols. Caller sets up anything drawn on top (stems/actuators)."""
        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))
        left_tri = QPolygonF([QPointF(x - hw, y - hh), QPointF(x - hw, y + hh), QPointF(x, y)])
        right_tri = QPolygonF([QPointF(x + hw, y - hh), QPointF(x + hw, y + hh), QPointF(x, y)])
        p.drawPolygon(left_tri)
        p.drawPolygon(right_tri)

    @staticmethod
    def _valve_fill(state):
        return (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)

    @staticmethod
    def _orifice(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Orifice: two thin stacked arcs pinching toward each
        other, like a restriction plate seen edge-on."""
        x, y = pos.x, pos.y
        hw = VLV_HW * 0.9 * scale_x
        gap = 3 * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.4 / zoom))

        top = QPainterPath()
        top.moveTo(x - hw, y - gap * 1.6)
        top.quadTo(x, y + gap * 0.4, x + hw, y - gap * 1.6)
        p.drawPath(top)

        bottom = QPainterPath()
        bottom.moveTo(x - hw, y + gap * 1.6)
        bottom.quadTo(x, y - gap * 0.4, x + hw, y + gap * 1.6)
        p.drawPath(bottom)

    @staticmethod
    def _filter(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Filter: unfilled diamond with a dashed VERTICAL line
        top-to-bottom (drawn rotated 45deg per spec note)."""
        x, y = pos.x, pos.y
        r = VLV_HH * scale_x
        rv = VLV_HH * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        diamond = QPolygonF([
            QPointF(x, y - rv), QPointF(x + r, y),
            QPointF(x, y + rv), QPointF(x - r, y),
        ])
        p.drawPolygon(diamond)

        pen = QPen(C_SYMBOL, 1.2 / zoom, Qt.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(x, y - rv), QPointF(x, y + rv))

    @staticmethod
    def _actuated_valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0, limit=False):
        """Actuated Valve, with or without limit switch: bowtie + stem up to
        a square pneumatic/electric actuator. Per RED-001 3.3 Table 3.3, the
        "with limit" variant is a plain (empty) actuator box; the "no limit"
        variant has an X drawn inside the actuator box."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y
        fill = Renderer._valve_fill(state)

        Renderer._bowtie(p, x, y, hw, hh, fill, zoom)

        stem_top = y - hh - 12 * scale_y
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))
        p.drawLine(QPointF(x, y - hh), QPointF(x, stem_top))

        act_hw, act_hh = 7 * scale_x, 7 * scale_y
        act_rect = QRectF(x - act_hw, stem_top - act_hh * 2, act_hw * 2, act_hh * 2)
        p.setBrush(QBrush(C_AUX_FILL))
        p.drawRect(act_rect)

        if not limit:
            p.drawLine(act_rect.topLeft(), act_rect.bottomRight())
            p.drawLine(act_rect.topRight(), act_rect.bottomLeft())

    @staticmethod
    def _needle_valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Needle Valve: bowtie with a bold filled needle bar
        through the center."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y
        fill = Renderer._valve_fill(state)

        Renderer._bowtie(p, x, y, hw, hh, fill, zoom)

        bar_w = 2.6 * scale_x
        p.setBrush(QBrush(C_SYMBOL))
        p.setPen(QPen(C_SYMBOL, 1.0 / zoom))
        p.drawRect(QRectF(x - bar_w / 2, y - hh, bar_w, hh * 2))

    @staticmethod
    def _three_way_valve(p, pos, state, zoom, scale_x=1.0, scale_y=1.0):
        """3-Way Valve per RED-001 3.3: a manual-valve bowtie (left/right
        ports) plus a third triangular port opening downward from center."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y
        fill = Renderer._valve_fill(state)

        Renderer._bowtie(p, x, y, hw, hh, fill, zoom)

        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))
        bot_tri = QPolygonF([
            QPointF(x - hw * 0.75, y + hh * 1.3),
            QPointF(x + hw * 0.75, y + hh * 1.3),
            QPointF(x, y),
        ])
        p.drawPolygon(bot_tri)

    @staticmethod
    def _ep_throttle_valve(p, pos, state, value, zoom, scale_x=1.0, scale_y=1.0):
        """Electro-Pneumatic Throttle Valve per RED-001 3.3: valve bowtie,
        stem up to a domed pneumatic-actuator hood, then an elbowed line up
        to an E/P box offset to the upper-left."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y
        fill = Renderer._valve_fill(state)

        Renderer._bowtie(p, x, y, hw, hh, fill, zoom)

        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        p.setBrush(Qt.NoBrush)
        dome_y = y - hh - 8 * scale_y
        p.drawLine(QPointF(x, y - hh), QPointF(x, dome_y))
        dome = QPainterPath()
        dome.moveTo(x - 9 * scale_x, dome_y)
        dome.quadTo(x, dome_y - 8 * scale_y, x + 9 * scale_x, dome_y)
        p.drawPath(dome)

        elbow_y = dome_y - 10 * scale_y
        box_x = x - 14 * scale_x
        p.drawLine(QPointF(x, dome_y), QPointF(x, elbow_y))
        p.drawLine(QPointF(x, elbow_y), QPointF(box_x, elbow_y))
        Renderer._ep_box(p, box_x, elbow_y - 5 * scale_y, zoom, scale_x, scale_y)

        if value is not None:
            pct = f"{int(value)}%"
            f = QFont("Courier New", max(int(6 / zoom), 4))
            p.setFont(f)
            p.setPen(QPen(C_LABEL))
            tw = QFontMetrics(f).horizontalAdvance(pct)
            p.drawText(QPointF(x - tw / 2, y + hh + 8), pct)

    @staticmethod
    def _ep_box(p, x, y, zoom, scale_x=1.0, scale_y=1.0):
        """Small labeled 'E/P' rectangle, the electro-pneumatic actuation
        indicator shared by several RED-001 symbols."""
        w, h = 16 * scale_x, 10 * scale_y
        rect = QRectF(x - w / 2, y - h / 2, w, h)
        p.setBrush(QBrush(C_AUX_FILL))
        p.setPen(QPen(C_SYMBOL, 1.4 / zoom))
        p.drawRect(rect)

        f = QFont("Courier New", max(int(6 / zoom), 4))
        p.setFont(f)
        p.setPen(QPen(C_LABEL))
        fm = QFontMetrics(f)
        text = "E/P"
        tw = fm.horizontalAdvance(text)
        p.drawText(QPointF(x - tw / 2, y + fm.ascent() / 2 - 1 / zoom), text)

    @staticmethod
    def _burst_disk(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Burst Disk: a vertical post, a small S-curve rupture
        bulge, and a discharge arrow to the right."""
        x, y = pos.x, pos.y
        hh = VLV_HH * 0.7 * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))

        post_x = x - 8 * scale_x
        p.drawLine(QPointF(post_x, y - hh), QPointF(post_x, y + hh))

        bulge = QPainterPath()
        bulge.moveTo(post_x + 2 * scale_x, y - hh * 0.9)
        bulge.quadTo(post_x + 7 * scale_x, y - hh * 0.35, post_x + 2 * scale_x, y)
        bulge.quadTo(post_x + 7 * scale_x, y + hh * 0.35, post_x + 2 * scale_x, y + hh * 0.9)
        p.drawPath(bulge)

        p.drawLine(QPointF(post_x + 7 * scale_x, y), QPointF(x + 12 * scale_x, y))
        arrow = QPolygonF([
            QPointF(x + 12 * scale_x, y - 4 * scale_y),
            QPointF(x + 18 * scale_x, y),
            QPointF(x + 12 * scale_x, y + 4 * scale_y),
        ])
        p.setBrush(QBrush(C_SYMBOL))
        p.drawPolygon(arrow)

    @staticmethod
    def _bulkhead(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Bulkhead: a central box straddled by a thick vertical
        bar, with small pipe-stub tabs on the left and right."""
        x, y = pos.x, pos.y
        box_hw, box_hh = 8 * scale_x, 8 * scale_y
        bar_h = 14 * scale_y
        tab_w, tab_h = 6 * scale_x, 4 * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        box = QRectF(x - box_hw, y - box_hh, box_hw * 2, box_hh * 2)
        p.drawRect(box)
        p.drawRect(QRectF(x - box_hw - tab_w, y - tab_h, tab_w, tab_h * 2))
        p.drawRect(QRectF(x + box_hw, y - tab_h, tab_w, tab_h * 2))

        p.setPen(QPen(C_SYMBOL, 2.6 / zoom))
        p.drawLine(QPointF(x, y - bar_h), QPointF(x, y + bar_h))

    @staticmethod
    def _quick_disconnect(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Quick Disconnect: '\u2192| |\u2190' — two arrowheads
        facing each other, each stopped at a small tick mark."""
        x, y = pos.x, pos.y
        hh = VLV_HH * 0.5 * scale_y
        w = 9 * scale_x

        p.setBrush(QBrush(C_SYMBOL))
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))

        p.drawLine(QPointF(x - w * 2.2, y), QPointF(x - w * 0.4, y))
        left_arrow = QPolygonF([
            QPointF(x - w * 0.9, y - hh), QPointF(x - w * 0.9, y + hh), QPointF(x - w * 0.4, y),
        ])
        p.drawPolygon(left_arrow)
        p.drawLine(QPointF(x - w * 0.2, y - hh), QPointF(x - w * 0.2, y + hh))

        p.drawLine(QPointF(x + w * 0.4, y), QPointF(x + w * 2.2, y))
        right_arrow = QPolygonF([
            QPointF(x + w * 0.9, y - hh), QPointF(x + w * 0.9, y + hh), QPointF(x + w * 0.4, y),
        ])
        p.drawPolygon(right_arrow)
        p.drawLine(QPointF(x + w * 0.2, y - hh), QPointF(x + w * 0.2, y + hh))

    @staticmethod
    def _cap_plug(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """Cap/Plug: a filled half-disc (line end terminator)."""
        x, y = pos.x, pos.y
        r = VLV_HH * 0.7 * max(scale_x, scale_y)

        p.setBrush(QBrush(C_SYMBOL))
        p.setPen(QPen(C_SYMBOL, 1.4 / zoom))
        rect = QRectF(x - r, y - r, r * 2, r * 2)
        p.drawChord(rect, -90 * 16, 180 * 16)

    @staticmethod
    def _reg_valve(p, x, y, zoom, scale_x=1.0, scale_y=1.0):
        """Shared bowtie+ball valve body for Hand/Dome Regulator. The ball
        is drawn with an opaque canvas-color fill so it visually masks the
        bowtie's crossing lines underneath it, matching the spec's clean
        unbroken oval. Returns the valve's half-height so callers can find
        the stem's start point."""
        hw, hh = VLV_HW * scale_x, VLV_HH * scale_y
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        left_tri = QPolygonF([QPointF(x - hw, y - hh), QPointF(x - hw, y + hh), QPointF(x, y)])
        right_tri = QPolygonF([QPointF(x + hw, y - hh), QPointF(x + hw, y + hh), QPointF(x, y)])
        p.drawPolygon(left_tri)
        p.drawPolygon(right_tri)

        ball_r = min(hw, hh) * 0.85
        p.setBrush(QBrush(C_BG))
        p.drawEllipse(QPointF(x, y), ball_r, ball_r)
        p.setBrush(Qt.NoBrush)
        return hh

    @staticmethod
    def _hand_icon(p, x, y, zoom, scale_x=1.0, scale_y=1.0):
        """Simplified pointing-hand glyph: a fist blob at (x, y) with a
        tapered finger extending down-right, toward the pilot circle it
        sits beside — matching the spec's Hand Regulator icon."""
        s = max(scale_x, scale_y)
        p.setBrush(QBrush(C_SYMBOL))
        p.setPen(QPen(C_SYMBOL, 1.0 / zoom))
        p.drawEllipse(QPointF(x, y), 5 * s, 4 * s)
        finger = QPolygonF([
            QPointF(x + 2 * s, y + 2 * s),
            QPointF(x + 11 * s, y + 7 * s),
            QPointF(x + 9.5 * s, y + 9.5 * s),
            QPointF(x + 0.5 * s, y + 4.5 * s),
        ])
        p.drawPolygon(finger)
        # Knuckle ticks for a bit of texture on the fist.
        p.setPen(QPen(C_BG, 0.8 / zoom))
        for i in range(3):
            ox = x - 3 * s + i * 2.2 * s
            p.drawLine(QPointF(ox, y - 2.5 * s), QPointF(ox + 1.5 * s, y - 0.5 * s))
        p.setPen(QPen(C_SYMBOL, 1.0 / zoom))

    @staticmethod
    def _hand_regulator(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Hand Regulator: valve stem rises to the LEFT corner
        of a horizontal bar; the bar's right corner drops as a dangling
        sense-line stub; the pilot circle branches upward from partway
        along the bar; the hand icon floats above-left of the circle."""
        x, y = pos.x, pos.y
        hh = Renderer._reg_valve(p, x, y, zoom, scale_x, scale_y)

        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        stem_top = y - hh
        bar_y = stem_top - 9 * scale_y
        right_x = x + 24 * scale_x
        branch_x = x + 13 * scale_x
        pilot_y = bar_y - 9 * scale_y
        pilot_r = 4.5 * max(scale_x, scale_y)

        p.drawLine(QPointF(x, stem_top), QPointF(x, bar_y))
        p.drawLine(QPointF(x, bar_y), QPointF(right_x, bar_y))
        p.drawLine(QPointF(right_x, bar_y), QPointF(right_x, bar_y + 14 * scale_y))
        p.drawLine(QPointF(branch_x, bar_y), QPointF(branch_x, pilot_y))

        p.setBrush(QBrush(C_AUX_FILL))
        p.drawEllipse(QPointF(branch_x, pilot_y), pilot_r, pilot_r)
        p.setBrush(Qt.NoBrush)

        Renderer._hand_icon(p, branch_x - 10 * scale_x, pilot_y - 9 * scale_y, zoom, scale_x, scale_y)

    @staticmethod
    def _dome_regulator(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Dome Regulator: valve stem rises straight to the
        pilot circle (centered on the stem); a dangling sense-line stub
        branches right off the circle; the stem continues straight up to
        the E/P box."""
        x, y = pos.x, pos.y
        hh = Renderer._reg_valve(p, x, y, zoom, scale_x, scale_y)

        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        stem_top = y - hh
        pilot_y = stem_top - 10 * scale_y
        pilot_r = 4.5 * max(scale_x, scale_y)
        branch_len = 12 * scale_x

        p.drawLine(QPointF(x, stem_top), QPointF(x, pilot_y))
        p.drawLine(QPointF(x, pilot_y), QPointF(x + branch_len, pilot_y))
        p.drawLine(QPointF(x + branch_len, pilot_y), QPointF(x + branch_len, pilot_y + 10 * scale_y))

        p.setBrush(QBrush(C_AUX_FILL))
        p.drawEllipse(QPointF(x, pilot_y), pilot_r, pilot_r)
        p.setBrush(Qt.NoBrush)

        ep_y = pilot_y - 10 * scale_y
        p.drawLine(QPointF(x, pilot_y), QPointF(x, ep_y))
        Renderer._ep_box(p, x, ep_y - 5 * scale_y, zoom, scale_x, scale_y)

    @staticmethod
    def _ep_converter(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """Standalone Electro-Pneumatic Converter: just the E/P box."""
        Renderer._ep_box(p, pos.x, pos.y, zoom, scale_x * 1.4, scale_y * 1.4)

    @staticmethod
    def _pump(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Pump: a volute (snail-shell) outline with a small
        discharge tab, an inner hub circle, and a trapezoid base."""
        x, y = pos.x, pos.y
        r = SNS_R * 0.85 * max(scale_x, scale_y)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))

        # Volute body: most of a circle, left open at the upper-right where
        # the discharge tab attaches.
        rect = QRectF(x - r, y - r, r * 2, r * 2)
        p.drawArc(rect, 20 * 16, 300 * 16)

        # Discharge tab: a small rectangle continuing tangent off the gap.
        gx = x + r * math.cos(math.radians(20))
        gy = y - r * math.sin(math.radians(20))
        tab = QPolygonF([
            QPointF(gx, gy),
            QPointF(gx + r * 0.55, gy),
            QPointF(gx + r * 0.55, gy + r * 0.55),
            QPointF(x + r * math.cos(math.radians(-20)), y - r * math.sin(math.radians(-20))),
        ])
        p.drawPolyline(tab)

        # Impeller hub.
        p.drawEllipse(QPointF(x, y), r * 0.32, r * 0.32)

        # Trapezoid base.
        base_y = y + r + 2 * scale_y
        base = QPolygonF([
            QPointF(x - r * 0.55, base_y),
            QPointF(x + r * 0.55, base_y),
            QPointF(x + r * 0.9, base_y + r * 0.5),
            QPointF(x - r * 0.9, base_y + r * 0.5),
        ])
        p.drawPolygon(base)

    @staticmethod
    def _pressure_gauge(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """Pressure Gauge: circle with an X through it."""
        x, y = pos.x, pos.y
        r = SNS_R * max(scale_x, scale_y)

        p.setBrush(QBrush(C_SENSOR_FILL))
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        p.drawEllipse(QPointF(x, y), r, r)

        d = r * 0.65
        p.drawLine(QPointF(x - d, y - d), QPointF(x + d, y + d))
        p.drawLine(QPointF(x - d, y + d), QPointF(x + d, y - d))

    @staticmethod
    def _diff_pressure(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Differential Pressure Transducer: unfilled circle
        split by a plain vertical line."""
        x, y = pos.x, pos.y
        r = SNS_R * max(scale_x, scale_y)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        p.drawEllipse(QPointF(x, y), r, r)
        p.drawLine(QPointF(x, y - r), QPointF(x, y + r))

    @staticmethod
    def _flow_meter(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Flow Meter: two side-by-side circles inside a
        bounding rectangle."""
        x, y = pos.x, pos.y
        r = SNS_R * 0.65 * max(scale_x, scale_y)
        offset = r * 0.95

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        p.drawRect(QRectF(x - offset - r * 1.15, y - r * 1.15, (offset + r * 1.15) * 2, r * 2.3))
        p.drawEllipse(QPointF(x - offset, y), r, r)
        p.drawEllipse(QPointF(x + offset, y), r, r)

    @staticmethod
    def _to_atmosphere(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 To Atmosphere: a single arrowhead at a point with
        three dashed lines fanning outward from that same point."""
        x, y = pos.x, pos.y

        p.setPen(QPen(C_SYMBOL, 1.6 / zoom, Qt.DashLine))
        angles = (35, 55, 75)  # degrees from horizontal, fanning up-right
        for deg in angles:
            rad = math.radians(deg)
            dx, dy = math.cos(rad), -math.sin(rad)
            p.drawLine(QPointF(x + 6 * scale_x * dx, y + 6 * scale_y * dy),
                       QPointF(x + 16 * scale_x * dx, y + 16 * scale_y * dy))

        p.setPen(QPen(C_SYMBOL, 1.6 / zoom, Qt.SolidLine))
        p.setBrush(QBrush(C_SYMBOL))
        arrow = QPolygonF([
            QPointF(x - 5 * scale_x, y - 3 * scale_y),
            QPointF(x + 5 * scale_x, y - 3 * scale_y),
            QPointF(x, y + 5 * scale_y),
        ])
        p.save()
        p.translate(x, y)
        p.rotate(-55)
        p.translate(-x, -y)
        p.drawPolygon(arrow)
        p.restore()

    @staticmethod
    def _flex_hose(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Flex Hose: a smooth squiggle with vertical end-caps."""
        x, y = pos.x, pos.y
        w, amp = 18 * scale_x, 6 * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        p.drawLine(QPointF(x - w, y - 6 * scale_y), QPointF(x - w, y + 6 * scale_y))
        p.drawLine(QPointF(x + w, y - 6 * scale_y), QPointF(x + w, y + 6 * scale_y))

        path = QPainterPath()
        path.moveTo(x - w, y)
        path.cubicTo(x - w / 2, y - amp, x - w / 6, y - amp, x, y)
        path.cubicTo(x + w / 6, y + amp, x + w / 2, y + amp, x + w, y)
        p.drawPath(path)

    @staticmethod
    def _bellows(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Bellow: sharp triangular accordion zigzag inside a
        bounding rectangle."""
        x, y = pos.x, pos.y
        w, amp = 16 * scale_x, 7 * scale_y

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))
        p.drawRect(QRectF(x - w - 4 * scale_x, y - amp - 2 * scale_y, (w + 4 * scale_x) * 2, (amp + 2 * scale_y) * 2))

        path = QPainterPath()
        n = 4
        step = (w * 2) / n
        path.moveTo(x - w, y)
        for i in range(n):
            sign = -1 if i % 2 == 0 else 1
            path.lineTo(x - w + step * (i + 0.5), y + sign * amp)
        path.lineTo(x + w, y)
        p.drawPath(path)

    @staticmethod
    def _heat_exchanger(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """RED-001 3.3 Heat Exchanger: rectangle with four cross-hatch tick
        marks through a centerline."""
        x, y = pos.x, pos.y
        hw, hh = VLV_HW * scale_x, VLV_HH * 0.6 * scale_y

        p.setBrush(QBrush(C_AUX_FILL))
        p.setPen(QPen(C_SYMBOL, 1.6 / zoom))
        rect = QRectF(x - hw, y - hh, hw * 2, hh * 2)
        p.drawRect(rect)

        p.drawLine(QPointF(x - hw, y), QPointF(x + hw, y))
        for i in range(4):
            tx = x - hw * 0.7 + i * hw * 0.47
            p.drawLine(QPointF(tx, y - hh * 0.7), QPointF(tx, y + hh * 0.7))

    @staticmethod
    def _panel(p, pos, zoom, scale_x=1.0, scale_y=1.0):
        """Panel: dash-dot rounded rectangle container with the RED-001
        standard fill color, drawn behind whatever's grouped inside it."""
        x, y = pos.x, pos.y
        w, h = 100 * scale_x, 60 * scale_y

        fill = QColor(C_PANEL_FILL)
        fill.setAlpha(90)
        p.setBrush(QBrush(fill))
        pen = QPen(C_SYMBOL, 1.4 / zoom, Qt.DashDotLine)
        p.setPen(pen)
        p.drawRoundedRect(QRectF(x - w, y - h, w * 2, h * 2), 8, 8)

    @staticmethod
    def _panel_lbl(p, pos, label, zoom, scale_x=1.0, scale_y=1.0):
        if not label:
            return
        x, y = pos.x, pos.y
        w, h = 100 * scale_x, 60 * scale_y

        f = QFont("Segoe UI", max(int(9 / zoom), 6))
        f.setBold(True)
        p.setFont(f)
        p.setPen(QPen(C_LABEL))
        p.drawText(QPointF(x - w + 8, y - h + 16), label)