# GUI_DAQ.py
import csv
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QDialog, QLabel, QHBoxLayout, QLineEdit, QCheckBox, QMessageBox
from PyQt5.QtCore import QDateTime

class GUI_DAQ_Window(QWidget):
    def __init__(self, controller=None):
        super().__init__()

        self.controller = controller
        self.file = None
        self.csv_writer = None
        self.throttling_enabled = False
        self.gimbaling_enabled = False

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
        self.start_button.clicked.connect(self.start_recording)
        self.buttons_recording_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Recording")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_recording)
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
        self.throttling_btn.clicked.connect(self.toggle_throttling)
        self.buttons_throttle_gimbal_layout.addWidget(self.throttling_btn)

        self.gimbaling_btn = QPushButton("Enable Gimbaling")
        self.gimbaling_btn.clicked.connect(self.toggle_gimbaling)
        self.buttons_throttle_gimbal_layout.addWidget(self.gimbaling_btn)

        # Final Configuration
        self.buttons_layout.addLayout(self.buttons_recording_layout)
        self.buttons_layout.addLayout(self.buttons_valve_layout)
        self.buttons_layout.addLayout(self.buttons_throttle_gimbal_layout)
        self.layout.addLayout(self.buttons_layout)

        self.setLayout(self.layout)

    def toggle_throttling(self, state):
        self.throttling_enabled = not self.throttling_enabled

        self.throttling_btn.setText("Disable Throttling" if self.throttling_enabled else "Enable Throttling")

        print("GUI_DAQ.py toggling throttling")

        status = "ENABLED" if self.throttling_enabled else "DISABLED"
        self.controller.log_event(f"THROTTLING:{status}")

    def toggle_gimbaling(self, state):
        
        self.gimbaling_enabled = not self.gimbaling_enabled

        self.gimbaling_btn.setText("Disable Gimbaling" if self.gimbaling_enabled else "Enable Gimbaling")
        
        print("GUI_DAQ.py toggling gimbaling")

        status = "ENABLED" if self.gimbaling_enabled else "DISABLED"
        self.controller.log_event(f"GIMBALING:{status}")

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
            self.controller.log_event("RECORDING:START")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create file: {str(e)}")

    def stop_recording(self):
        if self.file:
            self.controller.log_event("RECORDING:STOP")

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
        
        if self.controller.sensor_grid:
            self.controller.sensor_grid.handle_data_line(sensor_data)

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
