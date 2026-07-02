import math
from PyQt5.QtWidgets import QWidget, QSizePolicy, QVBoxLayout, QPushButton, QLabel
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QTransform, QPainterPath, QPolygonF,
)
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal

from PID_SCHEMA import (
    PIDProject, Component, PipeLine, LayoutPoint,
    FLUID_COLORS, FLUID_GENERIC,
    COMP_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_TANK, COMP_INJECTOR,
    COMP_REGULATOR, COMP_CHECK_VALVE, COMP_RELIEF_VALVE, COMP_LABEL, COMP_JUNCTION,
    COMP_BALL_VALVE, COMP_PSV, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_REDUCER, COMP_PRV
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
    if ctype in (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL):
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
             zoom: float = 1.0):

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
            Renderer._sensor(p, pos, "PT",  value, zoom, scale_x, scale_y)
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
        
        p.restore()
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
    def _sensor(p, pos, symbol, value, zoom, scale_x=1.0, scale_y=1.0):
        x, y = pos.x, pos.y
        r = SNS_R * max(scale_x, scale_y)

        p.setBrush(QBrush(C_SENSOR_FILL))
        p.setPen(QPen(C_SYMBOL, 1.5 / zoom))
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
        r = VLV_HW * max(scale_x, scale_y)
        
        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)
        
        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        left_tri = QPolygonF([
            QPointF(x - r, y - r),
            QPointF(x - r, y + r),
            QPointF(x, y)
        ])

        right_tri = QPolygonF([
            QPointF(x + r, y - r), 
            QPointF(x + r, y + r),
            QPointF(x, y)
        ])
        
        p.drawPolygon(left_tri)
        p.drawPolygon(right_tri)

        ball_r = r * 0.6 
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
        r = VLV_HW * max(scale_x, scale_y)
        
        fill = (C_FILL_OPEN if state == "OPEN"
                else C_FILL_PEND if state == "PENDING"
                else C_FILL_CLOSED)
        
        p.setBrush(QBrush(fill))
        p.setPen(QPen(C_SYMBOL, 1.8 / zoom))

        pts_l = [QPointF(x - r, y - r), QPointF(x - r, y + r), QPointF(x, y)]
        pts_r = [QPointF(x + r, y - r), QPointF(x + r, y + r), QPointF(x, y)]
        
        p.drawPolygon(QPolygonF(pts_l))
        p.drawPolygon(QPolygonF(pts_r))

        globe_r = r * 0.5
        p.setBrush(QBrush(C_SYMBOL))
        p.drawEllipse(QPointF(x, y), globe_r, globe_r)
        
        if value is not None:
            pct = f"{int(value)}%"
            f = QFont("Courier New", max(int(6 / zoom), 4))
            p.setFont(f)
            p.setPen(QPen(C_LABEL))
            tw = QFontMetrics(f).horizontalAdvance(pct)
            p.drawText(QPointF(x - tw / 2, y + r + 8), pct)

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._state_lbl = QLabel("—")
        self._state_lbl.setAlignment(Qt.AlignCenter)
        self._state_lbl.setStyleSheet(
            "font-weight: bold; font-size: 9pt; color: #cccccc;")
        layout.addWidget(self._state_lbl)

        self._open_btn = QPushButton("▶  OPEN")
        self._open_btn.setFixedHeight(self._BTN_H)
        self._open_btn.setStyleSheet(
            "background:#1a4a1a; color:#00dd55; border:1px solid #00aa44;"
            "border-radius:4px; font-weight:bold;")
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

    def show_for(self, cid: str, state: str, screen_pos: QPointF):
        """Position and show the popup near screen_pos."""
        self._cid = cid
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
        colours = {"OPEN": "#00dd55", "CLOSED": "#ff5544", "PENDING": "#ff9900"}
        self._state_lbl.setText(state)
        self._state_lbl.setStyleSheet(
            f"font-weight:bold; font-size:9pt; color:{colours.get(state,'#aaa')};")
        self._open_btn.setEnabled(state != "OPEN")
        self._close_btn.setEnabled(state != "CLOSED")

    def _on_open(self):
        if self._cid:
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
        self.fit_view()
        self.update()

    def update_valve_state(self, cid: str, state: str):
        self.live_valve_states[cid] = state
        self._valve_popup.update_state(cid, state)
        self.update()

    def reset_callout_offset(self, cid: str):
        self._callout_offsets.pop(cid, None)
        self.update()

    def update_sensor_value(self, cid: str, value: float):
        self.live_sensor_values[cid] = value
        self.update()

    def _line_pressure_values(self) -> dict:
        if not self.project:
            return {}

        line_values: dict[str, float] = {}
        for cid, comp in self.project.components.items():
            if comp.type != COMP_PRESSURE:
                continue

            line_id = str(comp.extras.get("line_id", "")).strip()
            if not line_id:
                continue

            value = self.live_sensor_values.get(cid)
            if value is None:
                continue

            previous = line_values.get(line_id)
            if previous is None or value > previous:
                line_values[line_id] = value

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

    def update_throttle(self, cid: str, pct: float):
        self.live_throttle_pcts[cid] = pct
        self.update()

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

        p.setTransform(
            QTransform()
            .translate(self._pan.x() * self._zoom, self._pan.y() * self._zoom)
            .scale(self._zoom, self._zoom)
        )

        self._paint_grid(p)
        self._paint_lines(p)
        self._paint_components(p)
        if self._drawing_line:
            self._paint_line_preview(p)

        # Sensor callouts are drawn in screen-space (reset transform first)
        p.resetTransform()
        self._paint_sensor_callouts(p)

    def _callout_screen_pos(self, cid: str, comp_pos) -> QPointF:
        """Return the screen position for a sensor callout anchor."""
        dx, dy = self._callout_offsets.get(cid, (SNS_R + 10, -SNS_R - 10))
        wx = comp_pos.x + dx
        wy = comp_pos.y + dy
        return QPointF((wx + self._pan.x()) * self._zoom,
                       (wy + self._pan.y()) * self._zoom)

    def _callout_rect_at(self, sx: float, sy: float) -> QRectF:
        """Return the bounding rect (screen-space) for a callout box at (sx,sy)."""
        return QRectF(sx, sy - 24, 90, 30)

    def _paint_sensor_callouts(self, p: QPainter):
        if not self.project:
            return

        if self.interactive:
            return

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

            sp = self._callout_screen_pos(cid, pos)
            sx, sy = sp.x(), sp.y()

            pad_x, pad_y = 8, 5
            f_lbl = QFont("Courier New", 8)
            f_lbl.setBold(True)
            f_val = QFont("Courier New", 11)
            f_val.setBold(True)
            fm_lbl = QFontMetrics(f_lbl)
            fm_val = QFontMetrics(f_val)

            lbl_w = fm_lbl.horizontalAdvance(lbl)
            val_w = fm_val.horizontalAdvance(f"{val_str} {unit}")
            box_w = max(lbl_w, val_w) + pad_x * 2
            box_h = fm_lbl.height() + fm_val.height() + pad_y * 2 + 2

            box = QRectF(sx, sy, box_w, box_h)

            if box.right()  > self.width():
                box.moveRight(self.width() - 2)
            if box.bottom() > self.height():
                box.moveBottom(self.height() - 2)
            if box.left() < 0:
                box.moveLeft(2)
            if box.top() < 0:
                box.moveTop(2)

            bg     = SENSOR_CALLOUT_BG.get(comp.type,     QColor(20, 30, 50, 220))
            border = SENSOR_CALLOUT_BORDER.get(comp.type, QColor("#4488ff"))

            sensor_screen = QPointF(
                (pos.x + self._pan.x()) * self._zoom,
                (pos.y + self._pan.y()) * self._zoom,
            )
            p.setPen(QPen(border.darker(130), 1.0, Qt.DashLine))
            p.drawLine(sensor_screen, QPointF(box.left() + 4, box.center().y()))

            p.setBrush(QBrush(bg))
            p.setPen(QPen(border, 1.5))
            p.drawRoundedRect(box, 5, 5)

            p.setFont(f_lbl)
            p.setPen(QPen(border.lighter(160)))
            p.drawText(QRectF(box.left() + pad_x, box.top() + pad_y,
                              box.width() - pad_x*2, fm_lbl.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, lbl)

            value_color = QColor("#ffffff")
            if value is not None:
                value_color = self._sensor_value_color(comp.type, value, cid)
            p.setFont(f_val)
            p.setPen(QPen(value_color))
            p.drawText(QRectF(box.left() + pad_x,
                              box.top() + pad_y + fm_lbl.height() + 2,
                              box.width() - pad_x*2, fm_val.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, f"{val_str} {unit}")

    def _sensor_value_color(self, ctype: str, value: float, cid: str) -> QColor:
        """Return a colour for the sensor value (normal / warning / critical)."""
        # In future this can hook into warning_ranges; for now just white
        return QColor("#ffffff")

    def _callout_at(self, screen_pos: QPointF) -> "str | None":
        if not self.project:
            return None
        for cid, comp in self.project.components.items():
            if comp.type not in SENSOR_TYPES:
                continue
            pos = self.project.layout.get(cid)
            if not pos:
                continue
            sp = self._callout_screen_pos(cid, pos)

            hit = QRectF(sp.x(), sp.y() - 30, 100, 36)
            if hit.contains(screen_pos):
                return cid
        return None

    def _paint_grid(self, p):
        p.setPen(QPen(C_GRID, 1 / self._zoom))
        tl = self._to_world(0, 0)
        br = self._to_world(self.width(), self.height())
        x0 = int(tl.x() / GRID_SPACING) * GRID_SPACING
        y0 = int(tl.y() / GRID_SPACING) * GRID_SPACING
        x = x0
        while x <= br.x() + GRID_SPACING:
            y = y0
            while y <= br.y() + GRID_SPACING:
                p.drawPoint(QPointF(x, y))
                y += GRID_SPACING
            x += GRID_SPACING

    def _paint_lines(self, p):
        pressure_values = self._line_pressure_values()
        for line in self.project.lines:
            pts = line.points
            if len(pts) < 2:
                continue
            color = FLUID_QC.get(line.fluid, QColor("#c8c8c8"))

            pressure = pressure_values.get(line.id)
            if pressure is not None:
                max_pressure = 50.0
                for comp in self.project.components.values():
                    if comp.type != COMP_PRESSURE:
                        continue
                    if str(comp.extras.get("line_id", "")).strip() != line.id:
                        continue
                    try:
                        max_pressure = float(comp.extras.get("line_pressure_max", max_pressure))
                    except (TypeError, ValueError):
                        max_pressure = 50.0
                    break
                color = self._pressure_line_color(color, pressure, max_pressure)

            is_selected = line.id in self._selected_lines
            is_hovered  = line.id == self._hovered_line
            is_dotted   = getattr(line, 'dotted', False)
            pipe_style  = Qt.DashLine if is_dotted else Qt.SolidLine

            if is_selected:
                pen = QPen(C_SELECT, (PIPE_W + 2) / self._zoom)
                pen.setStyle(pipe_style)
            elif is_hovered:
                pen = QPen(C_HOVER, (PIPE_W + 1) / self._zoom)
                pen.setStyle(pipe_style)
            else:
                pen = QPen(color, PIPE_W / self._zoom)
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
            Renderer.draw(p, comp, pos,
                        state    = state,
                        value    = value,
                        selected = cid in self._selected_comps,
                        hovered  = cid == self._hovered_comp,
                        zoom     = self._zoom)

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
                dx, dy = self._callout_offsets.get(callout_cid, (SNS_R + 10, -SNS_R - 10))
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
                    self._valve_popup.show_for(cid, state, sp)

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