# GUI_LOGO.py
# This file displays the RED logo with some scaling
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class LogoWindow(QWidget):
    def __init__(self, scale_width=150):
        super().__init__()
        self.scale_width = scale_width

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self.logo_label = QLabel(self)
        self.set_light_image()

        self.logo_label.setAlignment(Qt.AlignLeading)
        layout.addWidget(self.logo_label)
    
    def set_dark_image(self):
        pixmap = QPixmap("RED Logo White.png")
        pixmap = pixmap.scaledToWidth(self.scale_width, Qt.SmoothTransformation)
        self.logo_label.setPixmap(pixmap)

    def set_light_image(self):
        pixmap = QPixmap("RED Logo Maroon.png")
        pixmap = pixmap.scaledToWidth(self.scale_width, Qt.SmoothTransformation)
        self.logo_label.setPixmap(pixmap)