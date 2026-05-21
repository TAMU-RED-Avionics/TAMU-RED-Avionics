from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QSizePolicy, QGridLayout

from GUI_CONTROLLER import GUIController

"""
DAQWindow

This window displays options for configuring and turning on data acquisition logging.
It also contains buttons for gimbaling and throttling control.

The filename is now auto-generated from the loaded project using the convention:
    {ProjectName}{Version}_{MMDDYYYY}_test{N}.xlsx
No manual filename entry is needed or allowed.

INPUT DEPENDENCIES:
    GUIController.signals.abort_triggered()
        This window must disable all non-logging related buttons when an abort happens

    GUIController.signals.safe_state()
        This window re-unlocks buttons when the system enters back into a safe state

OUTPUT DEPENDENCIES:
    GUIController.start_recording()
        When the start recording button is pressed, the controller auto-names and begins logging

    GUIController.stop_recording()
        When the stop recording button is pressed, the controller saves and closes the xlsx file

    GUIController.show_manual_valve_control()
        Opens the manual valve control overlay

    GUIController.show_abort_control()
        Opens the abort configuration overlay

    GUIController.toggle_throttling()
        Toggles throttling state in the controller

    GUIController.toggle_gimbaling()
        Toggles gimbaling state in the controller
"""
class DAQWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.abort_triggered.connect(self.abort_action)
        self.controller.signals.safe_state.connect(self.safe_state_action)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # --- Auto-generated filename preview ---
        filename_row = QHBoxLayout()
        filename_row.setContentsMargins(0, 0, 0, 0)
        filename_row.setSpacing(8)
        filename_row.addWidget(QLabel("Output file:"))
        self.filename_preview = QLabel(self._get_preview())
        self.filename_preview.setStyleSheet("color: #555; font-style: italic;")
        filename_row.addWidget(self.filename_preview)
        filename_row.addStretch()
        main_layout.addLayout(filename_row)

        # --- Buttons grid ---
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

        main_layout.addLayout(self.buttons_layout)
        self.setLayout(main_layout)

    def _get_preview(self) -> str:
        """Ask the controller what the next filename will be, without creating it."""
        try:
            return self.controller.get_next_filename()
        except Exception:
            return "(will be generated on start)"

    def toggle_throttling_daq(self):
        self.controller.toggle_throttling()
        self.throttling_btn.setText(
            "Disable Throttling" if self.controller.throttling_enabled else "Enable Throttling"
        )

    def toggle_gimbaling_daq(self):
        self.controller.toggle_gimbaling()
        self.gimbaling_btn.setText(
            "Disable Gimbaling" if self.controller.gimbaling_enabled else "Enable Gimbaling"
        )

    def start_recording_daq(self):
        if self.controller.start_recording():
            # Show the actual filename that was just opened
            self.filename_preview.setText(self.controller._xlsx_path.split("/")[-1].split("\\")[-1])
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

    def stop_recording_daq(self):
        self.controller.stop_recording()
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        # Refresh preview for the next would-be file
        self.filename_preview.setText(self._get_preview())

    def abort_action(self):
        self.manual_btn.setEnabled(False)
        self.throttling_btn.setEnabled(False)
        self.gimbaling_btn.setEnabled(False)

    def safe_state_action(self):
        self.manual_btn.setEnabled(True)
        self.throttling_btn.setEnabled(True)
        self.gimbaling_btn.setEnabled(True)