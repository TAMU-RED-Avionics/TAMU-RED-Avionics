from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QLineEdit, QSizePolicy, QGridLayout

from GUI_CONTROLLER import GUIController

"""
DAQWindow

This window displays some options for configuring and turning on the data acquisition logging.
It also contains some buttons for gimbaling and throttling control.

INPUT DEPENDENCIES:
    GUIController.signals.abort_triggered()
        This window must disable all non-logging related buttons when an abort happens

    GUIController.signals.safe_state()
        This window re-unlocks buttons when the system enters back into a safe state

OUTPUT DEPENDENCIES:
    GUIController.start_recording(filename)
        When the start recording button is pressed, it must cause the controller to begin logging events that occur

    GUIController.stop_recording()
        When the stop recording button is pressed, the controller must stop its event logging

    GUIController.show_manual_valve_control()
        A button in this window will cause the controller to bring up an overlay window that allows the user to select
        and control each valve independently and manually

    GUIController.show_abort_control()
        A button in this window will cause the controller to bring up an overlay window that lets the user
        control which abort conditions are live in the system

    GUIController.toggle_throttling()
        The toggle throttling button must update the state in the controller accordingly
    
    GUIController.toggle_gimbaling()
        The toggle gimbaling butotn must update the state in the controller accordingly

"""
class DAQWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.enter_lockout.connect(self.enter_lockout_action)
        self.controller.signals.exit_lockout.connect(self.exit_lockout_action)

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Filename input
        self.csv_input_layout = QHBoxLayout()
        self.csv_input_layout.setContentsMargins(0, 0, 0, 0)
        self.csv_input_layout.setSpacing(10)

        self.filename_label = QLabel("Enter CSV filename:")
        self.csv_input_layout.addWidget(self.filename_label)

        self.filename_input = QLineEdit()
        self.csv_input_layout.addWidget(self.filename_input)
        self.layout.addLayout(self.csv_input_layout)
    
        self.buttons_layout = QGridLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setSpacing(10)

        # Recording controls
        self.start_button = QPushButton("Start Recording")
        self.start_button.clicked.connect(self.start_recording_daq)
        self.start_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.start_button.setEnabled(True)
        self.buttons_layout.addWidget(self.start_button, 1, 1)

        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.clicked.connect(self.stop_recording_daq)
        self.stop_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.stop_button.setEnabled(False)
        self.buttons_layout.addWidget(self.stop_button, 2, 1)

        # Valve controls
        self.abort_config_btn = QPushButton("Abort Configuration")
        self.abort_config_btn.clicked.connect(self.controller.show_abort_control)
        self.abort_config_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.abort_config_btn.setEnabled(True)
        self.buttons_layout.addWidget(self.abort_config_btn, 1, 2)

        self.manual_btn = QPushButton("Manual Valve Control")
        self.manual_btn.clicked.connect(self.controller.show_manual_valve_control)
        self.manual_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.manual_btn.setEnabled(False)
        self.buttons_layout.addWidget(self.manual_btn, 2, 2)

        # Throttling and Gimbaling controls (Req 26)
        self.throttling_btn = QPushButton("Enable Throttling")
        self.throttling_btn.clicked.connect(self.toggle_throttling_daq)
        self.throttling_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.throttling_btn.setEnabled(False)
        self.buttons_layout.addWidget(self.throttling_btn, 1, 3)

        self.gimbaling_btn = QPushButton("Enable Gimbaling")
        self.gimbaling_btn.clicked.connect(self.toggle_gimbaling_daq)
        self.gimbaling_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.gimbaling_btn.setEnabled(False)
        self.buttons_layout.addWidget(self.gimbaling_btn, 2, 3)

        # Final Configuration
        self.layout.addLayout(self.buttons_layout)

        self.setLayout(self.layout)

    def toggle_throttling_daq(self):
        self.controller.toggle_throttling()

        self.throttling_btn.setText("Disable Throttling" if self.controller.throttling_enabled else "Enable Throttling")

    def toggle_gimbaling_daq(self):
        self.controller.toggle_gimbaling()

        self.gimbaling_btn.setText("Disable Gimbaling" if self.controller.gimbaling_enabled else "Enable Gimbaling")

    def start_recording_daq(self):
        filename = self.filename_input.text().strip()
        if self.controller.start_recording(filename):
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

    def stop_recording_daq(self):
        self.controller.stop_recording()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def enter_lockout_action(self):
        self.manual_btn.setEnabled(False)
        self.throttling_btn.setEnabled(False)
        self.gimbaling_btn.setEnabled(False)

    def exit_lockout_action(self):
        self.manual_btn.setEnabled(True)
        self.throttling_btn.setEnabled(True)
        self.gimbaling_btn.setEnabled(True)