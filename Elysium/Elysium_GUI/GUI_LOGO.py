# GUI_LOGO.py
# This file displays the RED logo with some scaling
from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt

class LogoWindow(QWidget):
    def __init__(self, scale_width=120):
        super().__init__()
        self.scale_width = scale_width

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self.logo_label = QLabel(self)
        self.set_light_image()

        self.logo_label.setScaledContents(True)
        scaled_size = self.pixmap.scaledToWidth(self.scale_width, mode=Qt.SmoothTransformation).size()
        self.logo_label.setFixedSize(scaled_size)
        self.logo_label.setAlignment(Qt.AlignLeading)

        layout.addWidget(self.logo_label)
    
    def set_dark_image(self):
        self.pixmap = QPixmap("RED Logo White.png")
        self.logo_label.setPixmap(self.pixmap)

    def set_light_image(self):
        self.pixmap = QPixmap("RED Logo Maroon.png")
        self.logo_label.setPixmap(self.pixmap)