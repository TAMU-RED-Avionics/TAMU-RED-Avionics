import math
from PyQt5.QtWidgets import QWidget, QSizePolicy, QVBoxLayout, QPushButton, QLabel, QMessageBox
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QTransform, QPainterPath, QPolygonF, QPixmap,
)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer

from PID_SCHEMA import (
    PIDProject, Component, PipeLine, LayoutPoint,
    FLUID_COLORS, FLUID_GENERIC,
    COMP_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_TANK, COMP_INJECTOR,
    COMP_REGULATOR, COMP_CHECK_VALVE, COMP_RELIEF_VALVE, COMP_LABEL, COMP_JUNCTION,
    COMP_BALL_VALVE, COMP_PSV, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_REDUCER, COMP_PRV,
    COMP_IGNITER,
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

C_BG          = QColor("#0d0d0f")
C_GRID        = QColor("#1c1c22")
C_SYMBOL      = QColor("#e8e8e8")      # Light gray for outlines
C_FILL_CLOSED = QColor("#2a2a2a")      # Dark gray for closed valves
C_FILL_OPEN   = QColor("#00c853")      # Green for open
C_FILL_PEND   = QColor("#ff9800")      # Orange for pending
C_SENSOR_FILL = QColor("#1a2a3a")      # Dark blue-gray
C_TANK_FILL   = QColor("#1a1a2e")      # Dark blue-black
C_LABEL       = QColor("#d0d0d0")
C_SELECT      = QColor("#ffd600")
C_HOVER       = QColor("#64b5f6")
C_PSV_FILL    = QColor("#2a2a2a")
C_PRV_FILL    = QColor("#2a2a2a")
C_SOLENOID_FILL = QColor("#2a2a2a")
C_REDUCER_FILL  = QColor("#2a2a2a")

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
                 COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_PSV, COMP_PRV):
        return QRectF(x - VLV_HW * scale_x, y - VLV_HH * scale_y, VLV_HW * 2 * scale_x, VLV_HH * 2 * scale_y)
    if ctype in (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL, COMP_IGNITER):
        r = SNS_R * max(scale_x, scale_y)
        return QRectF(x - r, y - r, r * 2, r * 2)
    if ctype == COMP_TANK:
        return QRectF(x - TNK_HW * scale_x, y - TNK_HH * scale_y, TNK_HW * 2 * scale_x, TNK_HH * 2 * scale_y)
    if ctype == COMP_REDUCER:
        return QRectF(x - VLV_HW * scale_x, y - VLV_HH * scale_y, VLV_HW * 2 * scale_x, VLV_HH * 2 * scale_y)
    if ctype == COMP_INJECTOR:
        return QRectF(x - 22 * scale_x, y - 28 * scale_y, 44 * scale_x, 56 * scale_y)
    if ctype == COMP_JUNCTION:
        r = JCT_R * max(scale_x, scale_y)
        return QRectF(x - r, y - r, r * 2, r * 2)
    return QRectF(x - half_w, y - half_h, half_w * 2, half_h * 2)

class Renderer:

    @staticmethod
    def draw(p: QPainter, comp: Component, pos: LayoutPoint,
             state: str = "CLOSED", value: float = None,
             selected: bool = False, hovered: bool = False,
             zoom: float = 1.0, show_label: bool = True, **kwargs):

        t   = comp.type
        lbl = comp.label or comp.id
        scale_x, scale_y = _component_scale(comp)

        p.save()
        p.translate(pos.x, pos.y)
        p.rotate(comp.rotation)
        p.translate(-pos.x, -pos.y)

        if t == COMP_VALVE:
            Renderer._valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_CHECK_VALVE:
            Renderer._check_valve(p, pos, zoom, scale_x, scale_y)
        elif t == COMP_RELIEF_VALVE:
            Renderer._relief_valve(p, pos, state, zoom, scale_x, scale_y)
        elif t == COMP_PRESSURE:
            Renderer._sensor(p, pos, "PT",  value, zoom, scale_x, scale_y,
                             alert_color=kwargs.get("alert_color"))
        elif t == COMP_TEMPERATURE:
            Renderer._sensor(p, pos, "TC",  value, zoom, scale_x, scale_y)
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
        elif t == COMP_LABEL:
            Renderer._free_label(p, pos, "", zoom)
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

        p.restore()
        if show_label:
            lbl = comp.label or comp.id
            offset = (VLV_HH + 20) * max(scale_y, 0.8)
            Renderer._lbl(p, pos, lbl, zoom, offset, comp)

        if selected or hovered:
            r = world_rect(pos, t, comp).adjusted(-6, -6, 6, 6)
            c = C_SELECT if selected else C_HOVER
            p.setPen(QPen(c, 1.5 / zoom, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
            p.drawRect(r)

    @staticmethod
    def _lbl(p, pos, label, zoom, offset, comp):
        if not label: return
        if getattr(comp, 'hide_lbl', False): return
        
        f = QFont("Segoe UI", max(int(8 / zoom), 6))
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
        Renderer._valve(p, pos, state, zoom, scale_x, scale_y)
        x, y = pos.x, pos.y
        p.setPen(QPen(C_SYMBOL, 1.2 / zoom))
        p.drawArc(QRectF(x + VLV_HW * scale_x - 2, y - 8 * scale_y, 10 * scale_x, 8 * scale_y),  0,  180 * 16)
        p.drawArc(QRectF(x + VLV_HW * scale_x - 2, y,     10 * scale_x, 8 * scale_y),  0, -180 * 16)


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
    def _free_label(p, pos, text, zoom):
        f = QFont("Courier New", max(int(11 / zoom), 7))
        p.setFont(f)
        p.setPen(QPen(C_LABEL))
        p.drawText(QPointF(pos.x, pos.y), text)

    
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
        


VALVE_TYPES = {
    COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE,
    COMP_PSV, COMP_PRV, COMP_RELIEF_VALVE, COMP_CHECK_VALVE,
    COMP_IGNITER,
}

SENSOR_TYPES = {COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL}

# Sensor callout colours by type
SENSOR_CALLOUT_BG = {
    COMP_PRESSURE:    QColor(20, 40, 70, 230),    # dark blue
    COMP_TEMPERATURE: QColor(60, 20, 20, 230),    # dark red
    COMP_LOAD_CELL:   QColor(40, 20, 60, 230),    # dark purple
}
SENSOR_CALLOUT_BORDER = {
    COMP_PRESSURE:    QColor("#4488ff"),
    COMP_TEMPERATURE: QColor("#ff6655"),
    COMP_LOAD_CELL:   QColor("#cc88ff"),
}
SENSOR_UNIT = {
    COMP_PRESSURE:    "psi",
    COMP_TEMPERATURE: "°C",
    COMP_LOAD_CELL:   "lbf",
}

# ── Line pressurization inference ────────────────────────────────────────
# Topology is derived geometrically from the drawing, so existing .red files
# work unchanged: a PT "watches" the pipe it is drawn next to; pipes that
# touch end-to-end flow freely. Valve OPEN/CLOSED state is intentionally
# NOT used to gate pressurization propagation: closing a valve does not
# depressurize a line the PT still reads high, and opening a valve does not
# pressurize the far side until a real PT there confirms it.
PRESSURIZED_MIN_PSI = 25.0   # PT at/above this marks its pipe pressurized
SENSOR_ATTACH_DIST  = 30.0   # world units: PT → nearest pipe attachment
VALVE_LINK_DIST     = 30.0   # world units: valve → pipe linking radius
ENDPOINT_JOIN_DIST  = 12.0   # world units: pipe endpoint → pipe join radius


# Over-pressure indication (MEOP/MAWP). Kept visually distinct from both the
# ordinary fluid colours (e.g. oxidizer/fuel red) and the normal pressurized
# glow, so a real over-pressure condition never blends in.
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
    Zoomable/pannable P&ID canvas.

    In live (interactive=False) mode:
      - Clicking a valve shows ValvePopup with Open / Close.
      - Sensor callout boxes are drawn in screen-space near each sensor,
        showing the live value with colour-coded background.

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

        # Callout anchor offsets (per comp_id, in world units relative to comp centre).
        # Users can drag the callout label to reposition it.
        self._callout_offsets: dict = {}   # cid -> (dx, dy)  world units
        self._callout_rects:   dict = {}   # cid -> QRectF, screen space, cached at paint time

        self._zoom = 1.0
        self._pan  = QPointF(0, 0)

        self._pan_start:        QPointF = None
        self._pan_origin:       QPointF = None
        self._dragging_comp:    str     = None
        self._drag_start_world: QPointF = None
        self._drag_start_pos:   LayoutPoint = None
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

        # Line-pressurization topology (built once per project load)
        self._line_sensor_map:  dict = {}   # line_id -> [PT comp_ids]
        self._line_static_adj:  dict = {}   # line_id -> set(line_id)
        self._valve_line_links: list = []   # (valve_cid, set(line_ids))

        # Repaint coalescing for high-rate telemetry (sensor/valve updates
        # request a repaint; at most ~30 repaints/s actually happen)
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
        # The widget usually hasn't been laid out yet when a project loads -
        # re-fit once it gets its real size.
        self._needs_fit = True
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, "_needs_fit", False) and self.width() > 400:
            self._needs_fit = False
            self.fit_view()

    def _request_repaint(self):
        """Coalesce repaints caused by telemetry so a burst of sensor packets
        results in one paint, not one paint per packet."""
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
        """Derive pipe connectivity from the drawing geometry."""
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
            # Free-flow joins only within one fluid system (generic bridges
            # anything). Different fluids meeting without a valve is almost
            # always drawing coincidence (e.g. pressurant entering a tank the
            # oxidizer line leaves), not a real connection.
            return (la.fluid == lb.fluid
                    or la.fluid == FLUID_GENERIC or lb.fluid == FLUID_GENERIC)

        # Pipes joined end-to-end flow freely - unless the joint sits at a
        # valve, in which case the valve governs it (handled below).
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
        """Pipes currently holding pressure: seeded by live PT readings and
        propagated through physically-touching pipes (static adjacency only).

        Valve state is intentionally excluded from this calculation:
          - Closing a valve does not depressurize a line whose PT still reads
            high (gas is still trapped on that side).
          - Opening a valve does not pressurize the far side until a real PT
            there actually reads above the threshold.
        Propagation therefore travels only through direct pipe-endpoint joins,
        never through valve-adjacency links.
        """
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
        """Highest live PT reading attached to each line - used for both the
        pressure-ramp fill and the MEOP/MAWP overpressure glow.

        A PT counts as "attached" to a line the same way the ordinary
        pressurized-glow feature decides it (drawing-proximity, via
        _line_sensor_map from _build_line_topology()) so the overpressure
        glow lights up the same pipes the normal glow already does - no
        separate manual setup needed. An explicit "Linked Line ID" on the PT
        (extras["line_id"]) is honoured too, for the rare case a PT is drawn
        away from its line and proximity detection misses it.
        """
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
        """Colour for a line whose sensor is at/above MEOP.

        Glows orange at MEOP, gradients toward a dark maroon red as the
        reading approaches MAWP. Deliberately a different hue/value from
        both the normal fluid-pressurization glow and the fluid colours
        themselves (e.g. oxidizer/fuel red) so an over-pressure condition
        is never confused with an ordinary pressurized line.

        Returns None if the reading is below MEOP (or MEOP isn't set) -
        meaning the caller should fall back to normal line colouring.
        """
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

        from PID_SCHEMA import PipeLine
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
            if comp and world_rect(pos, comp.type).contains(world):
                return cid
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
        p.fillRect(self.rect(), C_BG)

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
        if self._drawing_line:
            self._paint_line_preview(p)

        # Sensor callouts are drawn in screen-space (reset transform first)
        p.resetTransform()
        self._paint_sensor_callouts(p)

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
            gp.setPen(QPen(C_GRID, 1.5))
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
                pen = QPen(C_SELECT, (PIPE_W + 2) / self._zoom)
                pen.setStyle(pipe_style)
            elif is_hovered:
                pen = QPen(C_HOVER, (PIPE_W + 1) / self._zoom)
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
                p.setPen(QPen(C_SELECT, 1.5 / self._zoom))
                p.setBrush(QBrush(C_SELECT))
                for pt in pts:
                    p.drawEllipse(QPointF(pt.x, pt.y), 5 / self._zoom, 5 / self._zoom)

    def _paint_components(self, p):
        for cid, comp in self.project.components.items():
            pos = self.project.layout.get(cid)
            if not pos:
                continue
            state = self.live_valve_states.get(cid, "CLOSED")
            value = self.live_sensor_values.get(cid)
            if comp.type == COMP_GLOBE_VALVE:
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
        if self._dragging_callout:
            self._dragging_callout = None
            self.setCursor(Qt.ArrowCursor)
            return
        if self._dragging_comp:
            pos = self.project.layout[self._dragging_comp]
            self.component_moved.emit(self._dragging_comp, pos.x, pos.y)
            self._dragging_comp = None
            self.setCursor(Qt.ArrowCursor)

    def wheelEvent(self, event):
        delta = event.pixelDelta().y()
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
        else:
            super().keyPressEvent(event)


def _seg_dist(p: QPointF, a: QPointF, b: QPointF) -> float:
    dx, dy = b.x() - a.x(), b.y() - a.y()
    if dx == 0 and dy == 0:
        return math.hypot(p.x() - a.x(), p.y() - a.y())
    t = max(0.0, min(1.0, ((p.x()-a.x())*dx + (p.y()-a.y())*dy) / (dx*dx+dy*dy)))
    return math.hypot(p.x()-(a.x()+t*dx), p.y()-(a.y()+t*dy))