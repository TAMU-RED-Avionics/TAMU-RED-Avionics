# GUI_ABORT.py
# This window displays an abort button, with a confirmation button that pops up if a safe state is entered
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton

class AbortWindow(QWidget):
    def __init__(self, manual_abort_callback: ()=None, safe_state_callback: ()=None):
        super().__init__()

        layout = QVBoxLayout()
        # layout.setContentsMargins(10, 10, 10, 10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.manual_abort_btn = QPushButton("MANUAL ABORT")
        self.manual_abort_btn.setStyleSheet("""background-color: red; color: white; font-weight: bold; font-size: 20pt; min-height: 80px;""")
        self.manual_abort_btn.clicked.connect(manual_abort_callback)
        layout.addWidget(self.manual_abort_btn)

        self.safe_state_btn = QPushButton("CONFIRM SAFE STATE")
        self.safe_state_btn.setStyleSheet("""background-color: green; color: white; font-weight: bold; font-size: 16pt; min-height: 60px;""")
        self.safe_state_btn.clicked.connect(safe_state_callback)
        self.safe_state_btn.setVisible(False)
        layout.addWidget(self.safe_state_btn)

        self.setLayout(layout)