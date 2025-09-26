from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QLineEdit
from PyQt5.QtCore import Qt

from GUI_CONTROLLER import GUIController

"""
ConnectionWindow

This window will display a set of options which will allow the user to establish a connection to the engine MCU

INPUT DEPENDENCIES:
    EthernetClient.connect(ip, port, callback)
        This window will update its connection label based on the results of the ethernet client's connection attempt

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

        self.conn_status_label = QLabel("Not Connected")
        eth_layout.addWidget(self.conn_status_label)

        eth_input_layout = QHBoxLayout()
        eth_input_layout.setContentsMargins(0, 0, 0, 0)
        eth_input_layout.setSpacing(10)
        
        self.ip_input = QLineEdit("192.168.1.174")
        self.port_input = QLineEdit("8888")
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ethernet)

        eth_input_layout.addWidget(QLabel("IP Address:"))
        eth_input_layout.addWidget(self.ip_input)
        eth_input_layout.addWidget(QLabel("Port:"))
        eth_input_layout.addWidget(self.port_input)
        eth_input_layout.addWidget(self.connect_btn)
        eth_layout.addLayout(eth_input_layout)

        self.setLayout(eth_layout)

    def connect_action(self):
        self.conn_status_label.setText("Connected Successfully")
        self.connect_btn.setEnabled(False)

    def disconnect_action(self):
        self.connect_btn.setEnabled(True)

        if self.conn_status_label.text() == "Connecting...":
            self.conn_status_label.setText("Connection Failed")
        else:
            self.conn_status_label.setText("Disconnected")

    def connect_ethernet(self):
        # Get the IP and port from the input fields
        ip = self.ip_input.text().strip()
        port_text = self.port_input.text().strip()
        if not port_text.isdigit():
            self.conn_status_label.setText("Port must be a number")
            return
        port = int(port_text)
    
        # Update the UI to show connecting state
        self.conn_status_label.setText("Connecting...")

        # Use asynchronous connection to avoid blocking the UI
        self.controller.ethernet_client.connect(ip, port)

