from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QLineEdit,
    QMessageBox, QDialog, QRadioButton, QCheckBox, QSpinBox, QDialogButtonBox,
)
from PyQt5.QtGui import QColor
from PyQt5.QtNetwork import QNetworkInterface, QAbstractSocket
from pyqtspinner import WaitingSpinner          # pip install pyqtspinner

from GUI_CONTROLLER import GUIController
from GUI_SHARE import DEFAULT_SHARE_PORT


class NetworkDialog(QDialog):
    """Controller / Viewer mode and live-data sharing.

    Controller (normal): this GUI talks to the Teensy and can optionally share its live
    data, read-only, with viewer GUIs. Viewer: this GUI connects to a controller GUI
    instead of the Teensy and can command nothing."""

    def __init__(self, controller: GUIController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Network / View Mode")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)

        self._ctrl_radio = QRadioButton("Controller (connects to the Teensy, can control)")
        self._view_radio = QRadioButton("Viewer (read-only; connects to a controller GUI)")
        lay.addWidget(self._ctrl_radio)
        lay.addWidget(self._view_radio)
        self._busy_note = QLabel("Disconnect first to change mode.")
        self._busy_note.setStyleSheet("color: #e37400;")
        lay.addWidget(self._busy_note)

        lay.addSpacing(8)
        self._share_cb = QCheckBox("Share live data with viewers (read-only)")
        lay.addWidget(self._share_cb)
        row = QHBoxLayout()
        row.addWidget(QLabel("Share port:"))
        self._port = QSpinBox()
        self._port.setRange(1024, 65535)
        self._port.setValue(DEFAULT_SHARE_PORT)
        row.addWidget(self._port)
        row.addStretch()
        lay.addLayout(row)
        self._share_status = QLabel()
        self._share_status.setWordWrap(True)
        lay.addWidget(self._share_status)

        self._viewer_hint = QLabel(
            "In Viewer mode, enter the controller GUI's IP address and share port in the "
            "connection panel, then Connect.")
        self._viewer_hint.setWordWrap(True)
        lay.addWidget(self._viewer_hint)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        lay.addWidget(buttons)

        self._ctrl_radio.toggled.connect(self._on_mode_toggled)
        self._share_cb.toggled.connect(self._on_share_toggled)
        controller.share_server.viewers_changed.connect(lambda _n: self._refresh())
        self._refresh()

    def _link_busy(self) -> bool:
        return bool(self.controller.ethernet_client.connected or self.controller.viewer.connected)

    def _lan_addresses(self) -> str:
        addrs = [a.toString() for a in QNetworkInterface.allAddresses()
                 if a.protocol() == QAbstractSocket.IPv4Protocol and not a.isLoopback()]
        return ", ".join(addrs) or "unknown"

    def _refresh(self):
        c = self.controller
        for w in (self._ctrl_radio, self._view_radio, self._share_cb):
            w.blockSignals(True)
        self._ctrl_radio.setChecked(not c.view_only)
        self._view_radio.setChecked(c.view_only)
        self._share_cb.setChecked(c.share_server.listening)
        for w in (self._ctrl_radio, self._view_radio, self._share_cb):
            w.blockSignals(False)
        busy = self._link_busy()
        self._ctrl_radio.setEnabled(not busy)
        self._view_radio.setEnabled(not busy)
        self._busy_note.setVisible(busy)
        self._share_cb.setEnabled(not c.view_only)
        self._port.setEnabled(not c.view_only and not c.share_server.listening)
        self._viewer_hint.setVisible(c.view_only)
        if c.share_server.listening:
            self._share_status.setText(
                f"Sharing on port {c.share_server.port} - {c.share_server.viewer_count} viewer(s) "
                f"connected. Viewers connect to: {self._lan_addresses()}")
        elif c.share_server.last_error:
            self._share_status.setText(f"Could not share: {c.share_server.last_error}")
        else:
            self._share_status.setText("")

    def _on_mode_toggled(self, controller_selected: bool):
        self.controller.set_view_only(not controller_selected)
        self._refresh()

    def _on_share_toggled(self, on: bool):
        if on:
            self.controller.start_sharing(self._port.value())
        else:
            self.controller.stop_sharing()
        self._refresh()

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
        self.controller.signals.view_only_changed.connect(self._on_view_only_changed)
        self._addr = {False: ("192.168.1.174", "8888"), True: ("", str(DEFAULT_SHARE_PORT))}
        
        eth_layout = QVBoxLayout()
        eth_layout.setContentsMargins(0, 0, 0, 0)
        eth_layout.setSpacing(4)

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
        conn_status_layout.addStretch()

        eth_input_layout = QHBoxLayout()
        eth_input_layout.setContentsMargins(0, 0, 0, 0)
        eth_input_layout.setSpacing(10)
        
        self.ip_input = QLineEdit("192.168.1.174")
        self.ip_input.setMinimumWidth(130)
        self.port_input = QLineEdit("8888")
        self.port_input.setMinimumWidth(60)
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_ethernet)

        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.clicked.connect(self._confirm_disconnect)
        self.disconnect_btn.setVisible(False)

        eth_input_layout.addWidget(QLabel("IP:"))
        eth_input_layout.addWidget(self.ip_input)
        eth_input_layout.addWidget(QLabel("Port:"))
        eth_input_layout.addWidget(self.port_input)

        # Stacked: status + connect/disconnect on top, address fields below, so the
        # action bar doesn't need to be as wide.
        self.net_btn = QPushButton("⚙")
        self.net_btn.setToolTip("Controller / Viewer mode and live-data sharing")
        self.net_btn.setFixedWidth(28)
        self.net_btn.clicked.connect(self._open_network_dialog)
        conn_status_layout.addWidget(self.net_btn)
        conn_status_layout.addWidget(self.connect_btn)
        conn_status_layout.addWidget(self.disconnect_btn)
        eth_layout.addLayout(conn_status_layout)
        eth_layout.addLayout(eth_input_layout)

        self.setLayout(eth_layout)

    def _open_network_dialog(self):
        NetworkDialog(self.controller, self).exec_()

    def _on_view_only_changed(self, view_only: bool):
        """Each mode keeps its own address: Teensy IP/port vs the controller GUI's."""
        self._addr[not view_only] = (self.ip_input.text(), self.port_input.text())
        ip, port = self._addr[view_only]
        self.ip_input.setText(ip)
        self.port_input.setText(port)
        self.ip_input.setPlaceholderText("controller GUI IP" if view_only else "")
        self.conn_status_label.setText("Viewer mode (read-only)" if view_only else "Not Connected")

    def connect_action(self):
        self.spinner.stop()
        self.spinner_container.setVisible(False)

        self.conn_status_label.setText(
            "Viewing (read-only)" if self.controller.view_only else "Connected Successfully")
        self.connect_btn.setEnabled(False)
        self.connect_btn.setVisible(False)
        self.disconnect_btn.setVisible(True)

    def _confirm_disconnect(self):
        if self.controller.view_only:
            self.controller.viewer.disconnect_from_controller()     # nothing to safe: just stop viewing
            return
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
        if self.controller.view_only:
            self.controller.viewer.connect_to(ip, port)
        else:
            self.controller.ethernet_client.connect(ip, port)

