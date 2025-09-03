# GUI_DAQ.py
import csv
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, 
    QMessageBox, QHBoxLayout, QCheckBox
)
from PyQt5.QtCore import QDateTime

class GUI_DAQ_Window(QWidget):
    def __init__(self, sensor_grid):
        super().__init__()
        self.sensor_grid = sensor_grid
        self.file = None
        self.csv_writer = None
        self.throttling_enabled = False
        self.gimbaling_enabled = False
        self.log_event_callback = None

        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Throttling and Gimbaling controls (Req 26)
        control_layout = QHBoxLayout()
        self.throttle_check = QCheckBox("Throttling Enabled")
        self.throttle_check.stateChanged.connect(self.toggle_throttling)
        # control_layout.addWidget(self.throttle_check)
        
        self.gimbal_check = QCheckBox("Gimbaling Enabled")
        self.gimbal_check.stateChanged.connect(self.toggle_gimbaling)
        control_layout.addWidget(self.gimbal_check)
        # self.layout.addLayout(control_layout)

        self.filename_label = QLabel("Enter CSV filename:")
        self.layout.addWidget(self.filename_label)

        self.filename_input = QLineEdit()
        self.layout.addWidget(self.filename_input)

        self.start_button = QPushButton("Start Recording")
        self.start_button.clicked.connect(self.start_recording)
        self.layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recording)
        self.layout.addWidget(self.stop_button)

        self.manual_btn = QPushButton("Manual Valve Control")
        # self.manual_btn.clicked.connect(self.show_manual_valve_control)
        self.layout.addWidget(self.manual_btn)

        self.abort_config_btn = QPushButton("Abort Configuration")
        # self.abort_config_btn.clicked.connect(self.show_abort_control)
        self.layout.addWidget(self.abort_config_btn)

        throttle_gimbal_layout = QHBoxLayout()
        # throttle_gimbal_layout.setSpacing(0)
        throttle_gimbal_layout.setContentsMargins(0, 0, 0, 0)   # To fit with the rest of the widgets
        self.throttling_btn = QPushButton("Enable Throttling")
        # self.throttling_btn.setContentsMargins(0, 0, 0, 0)  # Remove button internal margins
        # self.throttling_btn.setStyleSheet("QPushButton { margin: 0px; padding: 0px; }")  # Remove button padding
        self.throttling_btn.clicked.connect(self.toggle_throttling)
        throttle_gimbal_layout.addWidget(self.throttling_btn)
        self.gimbaling_btn = QPushButton("Enable Gimbaling")
        # self.gimbaling_btn.setContentsMargins(0, 0, 0, 0)  # Remove button internal margins
        # self.gimbaling_btn.setStyleSheet("QPushButton { margin: 0px; padding: 0px; }")  # Remove button padding
        self.gimbaling_btn.clicked.connect(self.toggle_gimbaling)
        throttle_gimbal_layout.addWidget(self.gimbaling_btn)
        self.layout.addLayout(throttle_gimbal_layout)

        self.throttle_check.stateChanged.connect(
            lambda state: self.throttling_btn.setText("Disable Throttling" if state == 2 else "Enable Throttling")
        )
        self.gimbal_check.stateChanged.connect(
            lambda state: self.gimbaling_btn.setText("Disable Gimbaling" if state == 2 else "Enable Gimbaling")
        )

        self.setLayout(self.layout)

    def toggle_throttling(self, state):
        self.throttling_enabled = state == 2
        if self.log_event_callback:
            status = "ENABLED" if self.throttling_enabled else "DISABLED"
            self.log_event_callback(f"THROTTLING:{status}")

    def toggle_gimbaling(self, state):
        self.gimbaling_enabled = state == 2
        if self.log_event_callback:
            status = "ENABLED" if self.gimbaling_enabled else "DISABLED"
            self.log_event_callback(f"GIMBALING:{status}")

    def start_recording(self):
        filename = self.filename_input.text().strip()
        if not filename:
            QMessageBox.warning(self, "Invalid Filename", "Please enter a filename")
            return
            
        if not filename.endswith(".csv"):
            filename += ".csv"
            
        # Check if file exists (Req 12)
        if os.path.exists(filename):
            reply = QMessageBox.question(self, "File Exists", 
                                        f"{filename} already exists. Overwrite?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        try:
            self.file = open(filename, "w", newline="")
            self.csv_writer = csv.writer(self.file)
            # Add columns for throttling/gimbaling (Req 26) and event logging (Req 15)
            self.csv_writer.writerow([
                "Timestamp", "TeensyTimestamp", "Throttling", "Gimbaling", 
                "SensorData", "EventType", "EventDetails"
            ])
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            if self.log_event_callback:
                self.log_event_callback("RECORDING:START")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create file: {str(e)}")

    def stop_recording(self):
        if self.file:
            if self.log_event_callback:
                self.log_event_callback("RECORDING:STOP")
            self.file.close()
            self.file = None
            self.csv_writer = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def handle_new_data(self, data_str):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
        
        # Parse teensy timestamp (first token) - Req 4
        parts = data_str.split(maxsplit=1)
        teensy_ts = parts[0] if len(parts) > 1 else ""
        sensor_data = parts[1] if len(parts) > 1 else data_str
        
        if self.csv_writer:
            self.csv_writer.writerow([
                timestamp, teensy_ts, 
                "ON" if self.throttling_enabled else "OFF",
                "ON" if self.gimbaling_enabled else "OFF",
                sensor_data, "", ""
            ])
        
        if self.sensor_grid:
            self.sensor_grid.handle_data_line(sensor_data)

    def log_event(self, event_type, event_details=""):
        """Log an event to CSV (Req 15)"""
        if not self.csv_writer:
            return
            
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz")
        self.csv_writer.writerow([
            timestamp, "", 
            "ON" if self.throttling_enabled else "OFF",
            "ON" if self.gimbaling_enabled else "OFF",
            "", event_type, event_details
        ])