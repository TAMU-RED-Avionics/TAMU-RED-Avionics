# GUI_VALVE_CONTROL.py
# This window showcases an array of buttons for various valve control related functions
# Each named valve will open when the valve state is clicked in the GUI.
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSizePolicy

class ValveControlWindow(QWidget):
    def __init__(self, parent=None, show_fire_sequence_dialog: ()=None, apply_valve_state: (str)=None):
        super().__init__(parent)

        top_layout = QVBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(10)

        operations_layout = QHBoxLayout()
        operations_layout.setContentsMargins(0, 0, 0, 0)
        operations_layout.setSpacing(10)

        self.fire_sequence_btn = QPushButton("Auto Fire Sequence")
        self.fire_sequence_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.fire_sequence_btn.clicked.connect(show_fire_sequence_dialog)

        top_layout.addWidget(self.fire_sequence_btn, stretch=1)

        current_column_layout = QVBoxLayout()
        current_column_layout.setContentsMargins(0, 0, 0, 0)
        current_column_layout.setSpacing(10)

        if show_fire_sequence_dialog and apply_valve_state:
            for op in self.valve_states:
                if op in ["Fire", "Kill and Vent"]:
                    continue
                
                btn = QPushButton(op)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                btn.clicked.connect(lambda checked, o=op: apply_valve_state(o))
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


    valve_states = {
        "Open Oxidizer": ["LA-BV1"],
        "Oxidizer Fill": ["NCS3", "NCS2", "LA-BV1"],
        "Oxidizer Leak Check": ["LA-BV1"],
        "Oxidizer Leak Check Fill": ["NCS1", "LA-BV1"],
        "Close Oxidizer": ["NCS3", "LA-BV1"],
        "Oxidizer Vent": ["GV-1", "NCS2", "NCS3", "LA-BV1"],


        "Open Pressure": ["LA-BV1"],
        "Fuel Fill 1": ["NCS5", "NCS6", "LA-BV1"],
        "Fuel Leak Check": ["LA-BV1"],
        "Fuel Leak Check Fill": ["NCS1", "LA-BV1"],
        "Close Pressure 1": ["LA-BV1"],
        "Vent Pressure": ["NCS1", "NCS3", "LA-BV1"],
        
        
        "Postfire Purge": ["NCS1", "GV-1", "LA-BV1"],
        "Fuel Fill 2": ["NCS5", "LA-BV1"],
        "Prefire Purge 1": ["GV-1", "LA-BV1"],
        "Prefire Purge 2": ["GV-1", "LA-BV1"],
        "Close Pressure 2": ["NCS3", "LA-BV1"],
        "Power down": [],

        "Fire": ["GV-1", "GV-2", "NCS1", "LA-BV1"],
        "Kill and Vent": ["NCS3", "GV-1", "GV-2", "LA-BV1"],
    }

    