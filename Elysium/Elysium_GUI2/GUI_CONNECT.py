from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QScrollArea, QDialog, QLabel,
    QDialogButtonBox, QHBoxLayout, QLineEdit, QCheckBox, QFrame, QMessageBox, QGroupBox
)
from PyQt5.QtGui import QFont
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from GUI_COMMS import EthernetClient

class ConnectionWidget(QWidget):
    def __init__(self, ethernet_client: EthernetClient):
        super().__init__()
        self.ethernet_client = ethernet_client
        
        eth_layout = QVBoxLayout()

        self.conn_status_label = QLabel("Not connected")
        self.conn_status_label.setAlignment(Qt.AlignCenter)
        # self.conn_status_label.setFont(QFont("Arial", 10, QFont.Bold))
        eth_layout.addWidget(self.conn_status_label)

        eth_input_layout = QHBoxLayout()
        
        self.ip_input = QLineEdit("192.168.1.174")
        self.port_input = QLineEdit("8888")
        
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.connect_ethernet)

        eth_input_layout.addWidget(QLabel("IP Address:"))
        eth_input_layout.addWidget(self.ip_input)
        eth_input_layout.addWidget(QLabel("Port:"))
        eth_input_layout.addWidget(self.port_input)
        eth_input_layout.addWidget(connect_btn)
        eth_layout.addLayout(eth_input_layout)

        self.setLayout(eth_layout)



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

        # Here we define the behavior we want from from the connection thread when
        # it completes or times out
        def connection_callback(success):
            if success:
                self.conn_status_label.setText("Connected successfully")
            else:
                self.conn_status_label.setText("Connection failed")
        
        # Use asynchronous connection to avoid blocking the UI
        self.ethernet_client.connect(ip, port, connection_callback)

