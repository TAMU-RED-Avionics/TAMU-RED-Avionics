from PyQt5.QtWidgets import QComboBox, QApplication
from PyQt5.QtCore import QPoint


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
