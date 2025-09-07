from PyQt5.QtWidgets import QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

class LogoWidget(QWidget):
    def __init__(self, image_path="RED_logo.png", scale_width=120):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        # self.setStyleSheet("background-color: black;")

        self.logo_label = QLabel()
        pixmap = QPixmap(image_path)

        if pixmap.isNull():
            self.logo_label.setText("Logo not found.")
        else:
            pixmap = pixmap.scaledToWidth(scale_width, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)

        self.logo_label.setAlignment(Qt.AlignLeading)
        layout.addWidget(self.logo_label)

    def setAlignment(self, alignment):
        self.logo_label.setAlignment(alignment)