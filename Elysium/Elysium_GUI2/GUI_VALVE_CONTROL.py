from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt5.QtGui import QFont

# Each named valve will open when the valve state is clicked in the GUI.

class ValveControlPanel(QWidget):
    def __init__(self, parent=None, show_fire_sequence_dialog=None, apply_valve_state=None):
        super().__init__(parent)

        # top_layout = QHBoxLayout()
        operations_layout = QVBoxLayout()

        if show_fire_sequence_dialog and apply_valve_state:
            for op in self.valve_states:
                if op in ["Pressurization", "Fire", "Kill and Vent"]:
                    continue
                btn = QPushButton(op)
                btn.setFont(QFont("Arial", 10, QFont.Bold))
                btn.setMinimumHeight(40)
                btn.clicked.connect(lambda checked, o=op: apply_valve_state(o))
                operations_layout.addWidget(btn)
                if op == "Oxidizer Fill":
                    self.fire_sequence_btn = QPushButton("Auto Fire Sequence")
                    self.fire_sequence_btn.setFont(QFont("Arial", 10, QFont.Bold))
                    self.fire_sequence_btn.setMinimumHeight(40)
                    self.fire_sequence_btn.clicked.connect(show_fire_sequence_dialog)
                    operations_layout.addWidget(self.fire_sequence_btn)

        # top_layout.addLayout(operations_layout)

        self.setLayout(operations_layout)


    valve_states = {
        "Open Pressure": ["LA-BV1"],
        "Oxidizer Leak Check Fill": ["NCS1", "LA-BV1"],
        "Oxidizer Leak Check": ["LA-BV1"],
        "Prefire Purge 1": ["GV-1", "LA-BV1"],
        "Fuel Fill 1": ["NCS5", "NCS6", "LA-BV1"],
        "Fuel Fill 2": ["NCS5", "LA-BV1"],
        "Fuel Leak Check Fill": ["NCS1", "LA-BV1"],
        "Fuel Leak Check": ["LA-BV1"],
        "Prefire Purge 2": ["GV-1", "LA-BV1"],
        "Open Oxidizer": ["LA-BV1"],
        "Oxidizer Fill": ["NCS3", "NCS2", "LA-BV1"],
        "Pressurization": ["NCS1", "LA-BV1"],
        "Fire": ["GV-1", "GV-2", "NCS1", "LA-BV1"],
        "Kill and Vent": ["NCS3", "GV-1", "GV-2", "LA-BV1"],
        "Close Oxidizer": ["NCS3", "LA-BV1"],
        "Oxidizer Vent": ["GV-1", "NCS2", "NCS3", "LA-BV1"],
        "Postfire Purge": ["NCS1", "GV-1", "LA-BV1"],
        "Close Pressure 1": ["LA-BV1"],
        "Close Pressure 2": ["NCS3", "LA-BV1"],
        "Vent Pressure": ["NCS1", "NCS3", "LA-BV1"],
        "Power down": []
    }

    