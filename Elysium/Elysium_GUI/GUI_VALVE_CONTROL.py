# GUI_VALVE_CONTROL.py
# This window showcases an array of buttons for various valve control related functions
# Each named valve will open when the valve state is clicked in the GUI.
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy

from GUI_CONTROLLER import GUIController

"""
Valve Control Window

This window displays a list of buttons that will control the valves, these are not one to one valve controls,
rather a series of more complex actions that often manipulate multiple valves at the same time

INPUT DEPENDENCIES:
    abort action - TODO
    safe state action - TODO

OUTPUT DEPENDENCIES:
    GUIController.apply_valve_state(op)
        When a button in this window is pressed, it must update the state inside the GUIController
        Thankfully this view does not need to update itself due to any of these changes

    GUIController.show_fire_sequence_dialog()
        A dedicated button will trigger the controller to present a dialog window that will walk 
        through the fire procedure
"""
class ValveControlWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.comms_signals.abort_triggered.connect(self.abort_action)
        self.controller.gui_signals.safe_state.connect(self.safe_state_action)

        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        operations_layout = QHBoxLayout()
        operations_layout.setContentsMargins(0, 0, 0, 0)
        operations_layout.setSpacing(10)

        self.fire_sequence_btn = QPushButton("Auto Fire Sequence")
        self.fire_sequence_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fire_sequence_btn.clicked.connect(controller.show_fire_sequence_dialog)

        top_layout.addWidget(self.fire_sequence_btn, stretch=1)

        current_column_layout = QVBoxLayout()
        current_column_layout.setContentsMargins(0, 0, 0, 0)
        current_column_layout.setSpacing(10)

        for op in self.controller.valve_operation_states:
            if op in ["Fire", "Kill and Vent"]:
                continue
            
            btn = QPushButton(op)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

            # This is defined as a lambda function because it requires an argument, and simply writing
            # controller.apply_valve_state(op) would call that function upon creation, not upon press
            # The lambda closure is defining a new function where op can be passed into the controller's function
            btn.clicked.connect(lambda checked, o=op: controller.apply_valve_state(o))

            current_column_layout.addWidget(btn)

            # Go to the next column if this one is an end cap
            if op in ["Oxidizer Vent", "Vent Pressure"]:
                operations_layout.addLayout(current_column_layout)
                current_column_layout = QVBoxLayout()
                current_column_layout.setContentsMargins(0, 0, 0, 0)
                current_column_layout.setSpacing(10)

        operations_layout.addLayout(current_column_layout)
        top_layout.addLayout(operations_layout, stretch=6)

        self.setLayout(top_layout)

    def abort_action(self):
        # Disable valve state buttons
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(False)

    def safe_state_action(self):
        # Enable valve state buttons
        for btn in self.findChildren(QPushButton):
            btn.setEnabled(True)