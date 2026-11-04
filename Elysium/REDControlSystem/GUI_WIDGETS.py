from PyQt5.QtWidgets import QComboBox, QApplication, QLabel, QInputDialog
from PyQt5.QtCore import QPoint, Qt, QMimeData, pyqtSignal
from PyQt5.QtGui import QDrag


class UpwardComboBox(QComboBox):
    """Combo box whose popup opens above the box, for controls docked at the bottom
    of the window where a downward popup would run off the bottom of the screen.
    Falls back to the default placement if there is no room above."""

    def showPopup(self):
        super().showPopup()
        popup = self.view().window()
        top_left = self.mapToGlobal(QPoint(0, 0))
        screen = QApplication.screenAt(top_left) or QApplication.primaryScreen()
        y = top_left.y() - popup.height()
        if screen is not None and y < screen.availableGeometry().top():
            return
        popup.move(popup.x(), y)


class DragHandle(QLabel):
    """Grip at the left of a reorderable row. Dragging it starts a reorder carrying `key`
    in a mime payload of type `mime`; the list that owns the rows handles the drop."""

    def __init__(self, key: str, mime: str, parent=None):
        super().__init__("\u22ee\u22ee", parent)
        self._key = key
        self._mime = mime
        self._press = None
        self.setFixedWidth(16)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Drag to reorder")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.pos()

    def mouseMoveEvent(self, event):
        if self._press is None or not (event.buttons() & Qt.LeftButton):
            return
        if (event.pos() - self._press).manhattanLength() < QApplication.startDragDistance():
            return
        self._press = None
        row = self.parentWidget()
        mime = QMimeData()
        mime.setData(self._mime, self._key.encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(row.grab())
        drag.setHotSpot(self.mapTo(row, event.pos()))
        drag.exec_(Qt.MoveAction)

    def mouseReleaseEvent(self, event):
        self._press = None


class RenameLabel(QLabel):
    """Name label that emits rename_requested on a double-click."""
    rename_requested = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setToolTip("Double-click to rename (this session only)")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.rename_requested.emit()
        else:
            super().mouseDoubleClickEvent(event)


def ask_new_name(parent, current: str, original: str):
    """Rename dialog. Returns the new name, "" to restore the original, or None if cancelled."""
    text, ok = QInputDialog.getText(
        parent, "Rename",
        f"Display name for {original}\n(this session only; leave empty to restore the original):",
        text=current)
    if not ok:
        return None
    return text.strip()
