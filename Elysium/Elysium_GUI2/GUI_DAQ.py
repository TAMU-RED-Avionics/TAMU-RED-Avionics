# GUI_DAQ.py
import csv
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QLabel, QHBoxLayout, QLineEdit, QCheckBox, QMessageBox
from PyQt5.QtCore import QDateTime

class DAQWindow(QWidget):
    def __init__(self, controller):
        super().__init__()

        self.controller = controller
        # self.file = None
        # self.csv_writer = None
        # self.throttling_enabled = False
        # self.gimbaling_enabled = False

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Filename input
        self.csv_input_layout = QHBoxLayout()
        self.csv_input_layout.setContentsMargins(10, 0, 10, 0)
        self.csv_input_layout.setSpacing(10)

        self.filename_label = QLabel("Enter CSV filename:")
        self.csv_input_layout.addWidget(self.filename_label)

        self.filename_input = QLineEdit()
        self.csv_input_layout.addWidget(self.filename_input)
        self.layout.addLayout(self.csv_input_layout)
    
        self.buttons_layout = QHBoxLayout()
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setSpacing(10)

        # Recording controls
        self.buttons_recording_layout = QVBoxLayout()
        self.buttons_recording_layout.setContentsMargins(0, 0, 0, 0)

        self.start_button = QPushButton("Start Recording")
        self.start_button.clicked.connect(self.start_recording_daq)
        self.buttons_recording_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recording_daq)
        self.buttons_recording_layout.addWidget(self.stop_button)

        # Valve controls
        self.buttons_valve_layout = QVBoxLayout()
        self.buttons_valve_layout.setContentsMargins(0, 0, 0, 0)

        self.manual_btn = QPushButton("Manual Valve Control")
        self.manual_btn.clicked.connect(self.controller.show_manual_valve_control)
        self.buttons_valve_layout.addWidget(self.manual_btn)

        self.abort_config_btn = QPushButton("Abort Configuration")
        self.abort_config_btn.clicked.connect(self.controller.show_abort_control)
        self.buttons_valve_layout.addWidget(self.abort_config_btn)


        # Throttling and Gimbaling controls (Req 26)
        self.buttons_throttle_gimbal_layout = QVBoxLayout()
        self.buttons_throttle_gimbal_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_throttle_gimbal_layout.setSpacing(0)

        self.throttling_btn = QPushButton("Enable Throttling")
        self.throttling_btn.clicked.connect(self.toggle_throttling_daq)
        self.buttons_throttle_gimbal_layout.addWidget(self.throttling_btn)

        self.gimbaling_btn = QPushButton("Enable Gimbaling")
        self.gimbaling_btn.clicked.connect(self.toggle_gimbaling_daq)
        self.buttons_throttle_gimbal_layout.addWidget(self.gimbaling_btn)

        # Final Configuration
        self.buttons_layout.addLayout(self.buttons_recording_layout)
        self.buttons_layout.addLayout(self.buttons_valve_layout)
        self.buttons_layout.addLayout(self.buttons_throttle_gimbal_layout)
        self.layout.addLayout(self.buttons_layout)

        self.setLayout(self.layout)

    def toggle_throttling_daq(self, state):
        self.controller.toggle_throttling()

        self.throttling_btn.setText("Disable Throttling" if self.controller.throttling_enabled else "Enable Throttling")

    def toggle_gimbaling_daq(self, state):
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
