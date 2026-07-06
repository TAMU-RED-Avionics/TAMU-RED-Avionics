from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QLineEdit,
    QMessageBox,
)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt
from pyqtspinner import WaitingSpinner          # pip install pyqtspinner (later on we should have install scripts that do this automatically)

from GUI_CONTROLLER import GUIController

"""
ConnectionWindow

This window will display a set of options which will allow the user to establish a connection to the engine MCU

INPUT DEPENDENCIES:
    GUIController.signals.connected()
        When the system's ethernet client connects, this view must update the status label and 
        the connect button

    GUIController.singals.disconnected(reason)
        When the system disconnects for any reason, the status label and connect button must update

OUTPUT DEPENDENCIES:
    EthernetClient.connect(ip, port, callback)
        The connect button will call the ethernet client's connection function, updating the ethernet client's state accordingly

"""
class ConnectionWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.connected.connect(self.connect_action)
        self.controller.signals.disconnected.connect(self.disconnect_action)
        
        eth_layout = QVBoxLayout()
        eth_layout.setContentsMargins(0, 0, 0, 0)
        eth_layout.setSpacing(10)

        conn_status_layout = QHBoxLayout()
        conn_status_layout.setContentsMargins(0, 0, 0, 0)
        conn_status_layout.setSpacing(10)

        self.spinner_container = QLabel()
        self.spinner_container.setFixedSize(30, 30)
        self.spinner = WaitingSpinner(
            self.spinner_container,
            roundness = 0,
            fade = 73.0,
            radius = 5,
            lines = 10,
            line_length = 5,
            line_width = 2,
            speed = 0.83,
            color = QColor(0, 0, 0)
        )

        self.conn_status_label = QLabel("Not Connected")

        conn_status_layout.addWidget(self.spinner_container)
        self.spinner_container.setVisible(False)

        conn_status_layout.addWidget(self.conn_status_label)

        eth_layout.addLayout(conn_status_layout)

        eth_input_layout = QHBoxLayout()
        eth_input_layout.setContentsMargins(0, 0, 0, 0)
        eth_input_layout.setSpacing(10)
        
        self.ip_input = QLineEdit("192.168.1.174")
        self.ip_input.setMinimumWidth(165)
        self.port_input = QLineEdit("8888")
        self.port_input.setMinimumWidth(60)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ethernet)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self._confirm_disconnect)
        self.disconnect_btn.setVisible(False)

        eth_input_layout.addWidget(QLabel("IP Address:"))
        eth_input_layout.addWidget(self.ip_input)
        eth_input_layout.addWidget(QLabel("Port:"))
        eth_input_layout.addWidget(self.port_input)
        eth_input_layout.addWidget(self.connect_btn)
        eth_input_layout.addWidget(self.disconnect_btn)
        eth_layout.addLayout(eth_input_layout)

        self.setLayout(eth_layout)

    def connect_action(self):
        self.spinner.stop()
        self.spinner_container.setVisible(False)

        self.conn_status_label.setText("Connected Successfully")
        self.connect_btn.setEnabled(False)
        self.connect_btn.setVisible(False)
        self.disconnect_btn.setVisible(True)

    def _confirm_disconnect(self):
        reply = QMessageBox.question(
            self, "Safe Disconnect",
            "Disconnect from the controller?\n\n"
            "A safe-mode notice (SFE) will be sent to the MCU first, so the "
            "hardware knows the ground station is leaving on purpose and can "
            "be powered down or serviced.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            self.controller.request_safe_disconnect()

    def disconnect_action(self, reason=""):
        self.spinner.stop()
        self.spinner_container.setVisible(False)

        self.connect_btn.setEnabled(True)
        self.connect_btn.setVisible(True)
        self.disconnect_btn.setVisible(False)

        if self.conn_status_label.text() == "Connecting...":
            message = "Connection Failed"
            if reason:
                message += f": {reason}"
            self.conn_status_label.setText(message)
        else:
            message = "Disconnected"
            if reason:
                message += f": {reason}"
            self.conn_status_label.setText(message)

    def connect_ethernet(self):
        # Get the IP and port from the input fields
        ip = self.ip_input.text().strip()
        port_text = self.port_input.text().strip()
        if not port_text.isdigit():
            self.conn_status_label.setText("Port must be a number")
            return
        port = int(port_text)
    
        # Update the UI to show connecting state
        self.spinner_container.setVisible(True)
        self.spinner.start()

        self.conn_status_label.setText("Connecting...")

        # Use asynchronous connection to avoid blocking the UI
        self.controller.ethernet_client.connect(ip, port)

