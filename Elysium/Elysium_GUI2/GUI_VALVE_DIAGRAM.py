# GUI_VALVE_DIAGRAM.py
# This file will display a diagram of the various valves in the Elysium 2 system.
# They will update automatically according to various settings
from stat import SF_APPEND
from PyQt5.QtWidgets import QWidget, QLabel, QPushButton, QVBoxLayout, QSizePolicy
from PyQt5.QtGui import QPixmap, QColor, QImage
from PyQt5.QtCore import Qt, QSize

class ValveDiagramWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignRight | Qt.AlignTop)

       
        # Load and display the P&ID image
        self.label = QLabel(self)
        self.set_light_image()

         # Adjusts the size of this picture
        self.scalingFactor = 0.5
        
        layout.addWidget(self.label)
        self.setLayout(layout)

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
        self.positions = {
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
        sf = self.scalingFactor

        for name, (x, y) in self.positions.items():
            btn = QPushButton("", self.label)
            btn.setGeometry(int(x * sf), int(y * sf), int(40 * sf), int(40 * sf))
            btn.setStyleSheet(f"background-color: red; border-radius: {int(20 * sf)}px;")
            btn.setEnabled(False)  # Make non-clickable
            self.valve_buttons[name] = btn

    def update_button_positions(self):
        sf = self.scalingFactor
        for name, (x, y) in self.positions.items():
            self.valve_buttons[name].setGeometry(int(x * sf), int(y * sf), int(40 * sf), int(40 * sf))
            self.valve_buttons[name].setStyleSheet(f"background-color: red; border-radius: {int(20 * sf)}px;")

    def set_valve_state(self, name, state):
        sf = self.scalingFactor
        self.valve_states[name] = state
        color = "green" if state else "red"
        self.valve_buttons[name].setStyleSheet(f"background-color: {color}; border-radius: {int(25 * sf)}px;")

    def set_dark_image(self):
        self.pixmap = QPixmap("P&ID Dark.png")
        self.label.setScaledContents(True)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        min_size = QSize(200, 200 / self.pixmap.width() * self.pixmap.height())
        self.label.setPixmap(self.pixmap.scaled(min_size, aspectRatioMode=Qt.KeepAspectRatio, 
                                                transformMode=Qt.SmoothTransformation))
        # self.label.setFixedSize(self.pixmap.size() * self.scalingFactor)

    def set_light_image(self):
        self.pixmap = QPixmap("P&ID Light.png")
        self.label.setScaledContents(True)
        self.label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        min_size = QSize(500, 500 / self.pixmap.width() * self.pixmap.height())
        self.label.setPixmap(self.pixmap.scaled(min_size, aspectRatioMode=Qt.KeepAspectRatio, 
                                                transformMode=Qt.SmoothTransformation))
        # self.label.setFixedSize(self.pixmap.size() * self.scalingFactor)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        
        if not self.pixmap or self.pixmap.width() == 0:
            return

        ar = self.pixmap.width() / self.pixmap.height()
        height = self.width() / ar

        self.scalingFactor = height / self.pixmap.height()

        self.update_button_positions()
        self.label.setFixedHeight(min(height, self.height()))
