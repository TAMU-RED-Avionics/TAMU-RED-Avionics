# --- GUI_VALVE_DIAGRAM.py ---
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class ValveDiagram(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Load and display the P&ID image
        self.label = QLabel(self)
        pixmap = QPixmap("P&ID.png")
        self.label.setPixmap(pixmap)
        self.label.setFixedSize(pixmap.size())
        layout.addWidget(self.label)

        # Initial valve states: False = closed (red), True = open (green)
        self.valve_states = {
            "NCS1": False,
            "NCS2": False,
            "NCS3": False,
            # "NCS4": False,
            "NCS5": False,
            "NCS6": False,
            "LA-BV1": False,
            "GV-1": False,
            "GV-2": False
        }

        # Create and position valve indicators (not clickable)
        self.valve_buttons = {}
        positions = {
            "NCS1": (670, 671),
            "NCS2": (239, 541),
            "NCS3": (582, 531),
            # "NCS4": (582, 585),   # Removed by Simeon according to Austin's instruction on Aug 31
            "NCS5": (464, 72),
            "NCS6": (464, 5),
            "LA-BV1": (513, 226),
            "GV-1": (455, 626),
            "GV-2": (505, 626)
        }

        for name, (x, y) in positions.items():
            btn = QPushButton("", self.label)
            btn.setGeometry(x, y, 40, 40)
            btn.setStyleSheet("background-color: red; border-radius: 20px;")
            btn.setEnabled(False)  # Make non-clickable
            self.valve_buttons[name] = btn

    def set_valve_state(self, name, state):
        self.valve_states[name] = state
        color = "green" if state else "red"
        self.valve_buttons[name].setStyleSheet(f"background-color: {color}; border-radius: 20px;")