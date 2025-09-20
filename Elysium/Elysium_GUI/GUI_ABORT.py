from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton

from GUI_CONTROLLER import GUIController

"""
AbortWindow

This window will display a massive abort button which will will trigger the engine system to stop fire
and close valves. It must update the GUI state with the controller when a manual abort or safe state is triggered
as well as update itself based on whether the engine automatically aborts itself

INPUT DEPENDENCIES:
    GUIController.comms_signals.abort_triggered(abort_type, reason)
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

        layout = QVBoxLayout()
        # layout.setContentsMargins(10, 10, 10, 10)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.manual_abort_btn = QPushButton("MANUAL ABORT")
        self.manual_abort_btn.setStyleSheet("""background-color: red; color: white; font-weight: bold; font-size: 20pt; min-height: 80px;""")
        self.manual_abort_btn.clicked.connect(self.controller.trigger_manual_abort)
        layout.addWidget(self.manual_abort_btn)

        self.safe_state_btn = QPushButton("CONFIRM SAFE STATE")
        self.safe_state_btn.setStyleSheet("""background-color: green; color: white; font-weight: bold; font-size: 16pt; min-height: 30px;""")
        self.safe_state_btn.clicked.connect(self.safe_state_callback)
        self.safe_state_btn.setVisible(False)
        layout.addWidget(self.safe_state_btn)

        # Update the safe state button when an abort is triggered for any reason
        self.controller.comms_signals.abort_triggered.connect(lambda: self.safe_state_btn.setVisible(True))
        
        self.setLayout(layout)

    # Updates the controller and the local window when a safe state is commanded
    def safe_state_callback(self):
        self.controller.confirm_safe_state
        self.safe_state_btn.setVisible(False)
