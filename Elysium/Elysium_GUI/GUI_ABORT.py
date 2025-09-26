from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton

from GUI_CONTROLLER import GUIController

"""
AbortWindow

This window will display a massive abort button which will will trigger the engine system to stop fire
and close valves. It must update the GUI state with the controller when a manual abort or safe state is triggered
as well as update itself based on whether the engine automatically aborts itself

INPUT DEPENDENCIES:
    GUIController.signals.abort_triggered(abort_type, reason)
        Aborts can be caused by either the button in this window being pressed as well as 
        the engine automatically hitting an abort state, therefore this window must update its 
        safe state button based on this signal, rather than a local function attached to the button

OUTPUT DEPENDENCIES:
    GUIController.trigger_manual_abort()
        When the abort button in this window is updated, the state within the   controller must update 
        accordingly. The controller emits the abort signal, which this window will receive and update to.
    
    GUIController.confirm_safe_state()
        When the safe state button is pressed, it must update the state of the controller accordingly
        Unlike the abort condition, a safe state is only confirmed by the local button in this window,
        so there is no need for an input dependency back from the controller
    
"""
class AbortWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.connected.connect(self.connect_action)
        self.controller.signals.disconnected.connect(self.disconnect_action)
        self.controller.signals.abort_triggered.connect(self.abort_action)
        self.controller.signals.safe_state.connect(self.safe_state_action)

        layout = QVBoxLayout()
        # layout.setContentsMargins(10, 10, 10, 10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.manual_abort_btn = QPushButton("MANUAL ABORT")
        self.manual_abort_btn.setObjectName("manual_abort_btn")
        # self.manual_abort_btn.setStyleSheet("""background-color: red; color: white; font-weight: bold; font-size: 20pt; min-height: 80px;""")
        self.manual_abort_btn.setStyleSheet("""
            QPushButton {
                background-color: red;
                color: white;
                font-weight: bold;
                font-size: 20pt;
                min-height: 80px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #700000; }
            QPushButton:pressed { background-color: #500000; }
            QPushButton:disabled { background-color: #700000; }
        """)

        # This will trigger the signal, which will spin around and trigger self.abort_action here
        self.manual_abort_btn.clicked.connect(self.controller.trigger_manual_abort)
        self.manual_abort_btn.setEnabled(False)
        layout.addWidget(self.manual_abort_btn)

        self.safe_state_btn = QPushButton("CONFIRM SAFE STATE")
        self.safe_state_btn.setObjectName("safe_state_btn")
        # self.safe_state_btn.setStyleSheet("""background-color: green; color: white; min-height: 25px;""")
        self.safe_state_btn.setStyleSheet("""
            QPushButton {
                background-color: #009900;
                color: white;
                font-weight: bold;
                font-size: 16pt;
                min-height: 25px;
            }
            QPushButton:hover { background-color: #006600; }
            QPushButton:pressed { background-color: #005500; }
            QPushButton:disabled { background-color: #005500; }
        """)

        self.safe_state_btn.clicked.connect(self.controller.confirm_safe_state)
        self.safe_state_btn.setEnabled(False)
        layout.addWidget(self.safe_state_btn)

        self.setLayout(layout)

    def connect_action(self):
        self.safe_state_btn.setEnabled(True)

    def disconnect_action(self):
        self.safe_state_btn.setEnabled(False)

    def abort_action(self):
        self.safe_state_btn.setVisible(True)
        self.manual_abort_btn.setEnabled(False)

        # self.controller.trigger_manual_abort()
        # self.manual_abort_btn.setStyleSheet("""
        #         background-color: darkred; 
        #         color: gray; 
        #         font-weight: bold; 
        #         font-size: 20pt;
        #         min-height: 80px;
        #     """)
    
    # Updates the controller and the local window when a safe state is commanded
    def safe_state_action(self):            
        self.safe_state_btn.setVisible(False)
        self.manual_abort_btn.setEnabled(True)

        # self.manual_abort_btn.setStyleSheet("""
        #         background-color: red; 
        #         color: white; 
        #         font-weight: bold; 
        #         font-size: 20pt;
        #         min-height: 80px;
        #     """)
