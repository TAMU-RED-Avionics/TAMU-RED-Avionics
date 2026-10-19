import sys
import threading
from pathlib import Path

from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont, QPen
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, pyqtSignal

CREDITS_HEADER = "DESIGNED & BUILT BY"
CREDITS = [
    ("Connor Smeby", "Mihir Mankikar"),
    ("Simeon Shaffar", "Josh Mark"),
]


class SplashScreen(QWidget):

    finished_loading = pyqtSignal()
    _worker_done = pyqtSignal()     # a background step finished (emitted from its worker thread)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setStyleSheet("background:#000;")

        self._logo_src = QPixmap(str(Path(__file__).resolve().parent / "RED Logo White.png"))
        self._logo = self._logo_src
        self._logo_key = None

        self._steps = []
        self._build = None
        self._total = 1
        self._done = 0
        self._index = 0
        self._label = "Initializing"
        self._shown = 0.0
        self._emitted = False
        self._failed = False
        self._worker_exc = None

        self._worker_done.connect(self._on_worker_done)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def start(self, steps, build=None):
        """steps: (label, fn) or (label, fn, background) tuples, run in order.

        Steps run on the GUI thread one at a time, with the event loop turning between
        them so the splash keeps painting. Importing PyQt modules (or anything that does)
        off the GUI thread races the splash's painting inside sip and can segfault, so only
        a step marked background=True runs on a worker thread - and that step must not
        import or touch Qt (e.g. the pip dependency check)."""
        self._steps = steps
        self._build = build
        self._total = len(steps) + (1 if build else 0)
        self._label = steps[0][0] if steps else "Initializing"
        self._timer.start()
        QTimer.singleShot(0, self._next_step)

    def _next_step(self):
        if self._failed:
            return
        if self._index >= len(self._steps):
            self._run_build()
            return
        label, fn, *opt = self._steps[self._index]
        self._label = label
        if opt and opt[0]:
            self.update()
            threading.Thread(target=self._work, args=(fn,), name="splash-step", daemon=True).start()
            return
        self.repaint()                  # show the label before the (blocking) step
        try:
            fn()
        except Exception:
            self._fail(label)
            return
        self._step_done()

    def _work(self, fn):
        try:
            fn()
        except Exception as exc:
            self._worker_exc = exc
        self._worker_done.emit()

    def _on_worker_done(self):
        exc, self._worker_exc = self._worker_exc, None
        if exc is not None:
            self._fail(self._label, exc)
        else:
            self._step_done()

    def _step_done(self):
        self._done += 1
        self._index += 1
        QTimer.singleShot(0, self._next_step)   # let the event loop paint before the next step

    def _run_build(self):
        if not self._build:
            return
        self._label = "Building interface"
        self.repaint()
        try:
            self._build()
        except Exception:
            self._fail("Building interface")
            return
        self._done += 1

    def _fail(self, label, exc=None):
        """A load step failed: log it, tell the operator, and quit. Never re-raise here -
        an exception escaping a slot is logged and swallowed, which would leave the app
        stuck on the splash forever."""
        if exc is None:
            exc_type, exc, tb = sys.exc_info()
        else:
            exc_type, tb = type(exc), exc.__traceback__
        self._failed = True
        self._timer.stop()
        sys.excepthook(exc_type, exc, tb)       # stderr + gui_errors.log
        QMessageBox.critical(
            self, "RED Control System failed to start",
            f"Loading failed at \"{label}\":\n\n{exc_type.__name__}: {exc}\n\n"
            "Details were written to gui_errors.log.")
        QApplication.instance().exit(1)

    def _tick(self):
        real = self._done / self._total
        self._shown += (real - self._shown) * 0.25
        if abs(real - self._shown) < 0.002:
            self._shown = real
        if self._done >= self._total and not self._emitted:
            self._emitted = True
            self._timer.stop()
            self.finished_loading.emit()
            return
        self.update()


    def _logo_for(self, width):
        if self._logo_key != width:
            self._logo = self._logo_src.scaledToWidth(width, Qt.SmoothTransformation)
            self._logo_key = width
        return self._logo

    @staticmethod
    def _font(family, px, spacing):
        f = QFont(family)
        f.setPixelSize(max(8, int(px)))
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
        return f

    def paintEvent(self, _):
        w, h = self.width(), self.height()
        u = h / 1080.0   # layout unit: everything scales with the window height
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0))

        # Logo
        logo = self._logo_for(int(w * 0.46))
        p.drawPixmap(int((w - logo.width()) / 2), int(h * 0.40 - logo.height() / 2), logo)

        # Progress bar
        bar_w = w * 0.42
        x0 = (w - bar_w) / 2
        y = h * 0.72
        p.setPen(QPen(QColor(255, 255, 255, 45), max(1, 3 * u)))
        p.drawLine(QPointF(x0, y), QPointF(x0 + bar_w, y))
        if self._shown > 0:
            p.setPen(QPen(QColor(255, 255, 255), max(1, 3 * u)))
            p.drawLine(QPointF(x0, y), QPointF(x0 + bar_w * self._shown, y))

        p.setFont(self._font("Consolas", 16 * u, 3 * u))
        p.setPen(QColor(255, 255, 255, 140))
        row = QRectF(x0, y + 14 * u, bar_w, 28 * u)
        p.drawText(row, Qt.AlignLeft | Qt.AlignVCenter, self._label.upper())
        p.drawText(row, Qt.AlignRight | Qt.AlignVCenter, f"{int(self._shown * 100)}%")

        # Credits
        top = h * 0.84
        p.setFont(self._font("Segoe UI", 15 * u, 8 * u))
        p.setPen(QColor(255, 255, 255, 120))
        p.drawText(QRectF(0, top, w, 26 * u), Qt.AlignHCenter | Qt.AlignVCenter, CREDITS_HEADER)

        p.setFont(self._font("Segoe UI Semibold", 22 * u, 3 * u))
        p.setPen(QColor(255, 255, 255, 235))
        col_w = w * 0.2
        for i, row_names in enumerate(CREDITS):
            ry = top + 36 * u + i * 38 * u
            for j, name in enumerate(row_names):
                p.drawText(QRectF(w / 2 - col_w + j * col_w, ry, col_w, 34 * u),
                           Qt.AlignHCenter | Qt.AlignVCenter, name)
        p.end()
