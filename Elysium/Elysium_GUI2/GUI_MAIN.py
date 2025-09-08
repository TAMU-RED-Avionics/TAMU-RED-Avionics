# GUI_MAIN.py
# This file is the starting point for the Elysium2 GUI
import sys
from PyQt5.QtWidgets import QApplication
from GUI_LAYOUT import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
