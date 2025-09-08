# GUI_ABORT.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton

class AbortWindow(QWidget):
    def __init__(self, trigger_manual_abort: ()=None, confirm_safe_state: ()=None):
        super().__init__()

        self.trigger_manual_abort=trigger_manual_abort
        self.confirm_safe_state=confirm_safe_state

        layout = QVBoxLayout()
        # layout.setContentsMargins(10, 10, 10, 10)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(10)
        
        self.manual_abort_btn = QPushButton("MANUAL ABORT")
        self.manual_abort_btn.setStyleSheet("""background-color: red; color: white; font-weight: bold; font-size: 20pt; min-height: 80px;""")
        self.manual_abort_btn.clicked.connect(self.trigger_manual_abort)
        layout.addWidget(self.manual_abort_btn)

        self.safe_state_btn = QPushButton("CONFIRM SAFE STATE")
        self.safe_state_btn.setStyleSheet("""background-color: green; color: white; font-weight: bold; font-size: 16pt; min-height: 60px;""")
        self.safe_state_btn.clicked.connect(self.confirm_safe_state)
        self.safe_state_btn.setVisible(False)
        layout.addWidget(self.safe_state_btn)

        self.setLayout(layout)