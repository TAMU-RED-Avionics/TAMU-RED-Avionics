"""
GUI_SHARE

Read-only live-data sharing between GUIs.

    ShareServer   - runs in the GUI that is connected to the Teensy (the controller).
                    Listens on a TCP port and streams what the controller sees to any
                    number of viewers: the project, sensor values, valve / actuator
                    states, mode, warnings and abort alerts.
    ViewerClient  - runs in a GUI set to "Viewer" mode. Connects to a controller's
                    share port and turns the stream back into messages.

The link is strictly one-way. The server writes and never acts on anything a viewer
sends (incoming bytes are discarded), so a viewer cannot command anything - only the GUI
holding the Teensy link can. Messages are newline-delimited JSON ("t" is the type).

Both classes are plain Qt objects living on the GUI thread; they know nothing about
GUIController (GUIController wires them up), so this module has no side effects.
"""
import json
from typing import Callable

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

PROTOCOL_VERSION = 1
DEFAULT_SHARE_PORT = 9000
SENSOR_FLUSH_MS = 50                 # sensor samples are batched and sent at 20 Hz
MAX_BACKLOG_BYTES = 4 * 1024 * 1024  # drop a viewer that can't keep up
HELLO_TIMEOUT_MS = 5000


def _encode(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


class ShareServer(QObject):
    viewers_changed = pyqtSignal(int)

    def __init__(self, snapshot: Callable[[], dict], parent=None):
        super().__init__(parent)
        self._snapshot = snapshot            # () -> hello message for a new viewer
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._clients: list = []
        self._sensor_buf: list = []
        self._timer = QTimer(self)
        self._timer.setInterval(SENSOR_FLUSH_MS)
        self._timer.timeout.connect(self._flush_sensors)
        self.last_error = ""

    # -- lifecycle -----------------------------------------------------------
    @property
    def listening(self) -> bool:
        return self._server.isListening()

    @property
    def port(self) -> int:
        return self._server.serverPort() if self.listening else 0

    @property
    def viewer_count(self) -> int:
        return len(self._clients)

    def start(self, port: int = DEFAULT_SHARE_PORT) -> bool:
        self.stop()
        if not self._server.listen(QHostAddress.Any, int(port)):
            self.last_error = self._server.errorString()
            return False
        self.last_error = ""
        self._timer.start()
        return True

    def stop(self):
        self._timer.stop()
        self._sensor_buf.clear()
        for sock in list(self._clients):
            self._drop(sock)
        if self._server.isListening():
            self._server.close()

    # -- publishing ----------------------------------------------------------
    def broadcast(self, msg: dict):
        if not self._clients:
            return
        data = _encode(msg)
        for sock in list(self._clients):
            self._send(sock, data)

    def publish_sensor(self, name: str, value: float):
        if self._clients:
            self._sensor_buf.append([name, value])

    def _flush_sensors(self):
        if self._sensor_buf:
            batch, self._sensor_buf = self._sensor_buf, []
            self.broadcast({"t": "s", "d": batch})

    # -- internals -----------------------------------------------------------
    def _send(self, sock: QTcpSocket, data: bytes):
        if sock.bytesToWrite() > MAX_BACKLOG_BYTES:
            self._drop(sock)
            return
        sock.write(data)

    def _on_new_connection(self):
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            sock.readyRead.connect(sock.readAll)             # viewers are read-only: discard input
            sock.disconnected.connect(lambda s=sock: self._drop(s))
            self._clients.append(sock)
            self._send(sock, _encode(self._snapshot()))
            self.viewers_changed.emit(len(self._clients))

    def _drop(self, sock: QTcpSocket):
        if sock in self._clients:
            self._clients.remove(sock)
            try:
                self.viewers_changed.emit(len(self._clients))
            except RuntimeError:        # server already torn down (app shutting down)
                pass
        try:
            sock.abort()
            sock.deleteLater()
        except RuntimeError:
            pass


class ViewerClient(QObject):
    message = pyqtSignal(dict)      # every decoded message (hello included)
    linked = pyqtSignal()           # first message (hello) received: the link is usable
    failed = pyqtSignal(str)        # could not connect, or the link was lost

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sock = QTcpSocket(self)
        self._sock.readyRead.connect(self._on_ready)
        self._sock.error.connect(self._on_error)
        self._sock.disconnected.connect(self._on_disconnected)
        self._buf = b""
        self._got_hello = False
        self._wanted = False
        self._hello_timer = QTimer(self)
        self._hello_timer.setSingleShot(True)
        self._hello_timer.setInterval(HELLO_TIMEOUT_MS)
        self._hello_timer.timeout.connect(lambda: self._fail("no response from the controller"))

    @property
    def connected(self) -> bool:
        return self._got_hello and self._sock.state() == QTcpSocket.ConnectedState

    def connect_to(self, host: str, port: int):
        self._reset()
        self._wanted = True
        self._hello_timer.start()
        self._sock.connectToHost(host, int(port))

    def disconnect_from_controller(self):
        was_up = self._got_hello
        self._reset()
        if was_up:
            self.failed.emit("Disconnected")

    # -- internals -----------------------------------------------------------
    def _reset(self):
        self._wanted = False
        self._got_hello = False
        self._buf = b""
        self._hello_timer.stop()
        self._sock.abort()

    def _fail(self, reason: str):
        if not self._wanted:
            return
        self._reset()
        self.failed.emit(reason)

    def _on_error(self, _err):
        self._fail(self._sock.errorString())

    def _on_disconnected(self):
        self._fail("the controller closed the link")

    def _on_ready(self):
        self._buf += bytes(self._sock.readAll())
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            self.message.emit(msg)
            if not self._got_hello and msg.get("t") == "hello":
                self._got_hello = True
                self._hello_timer.stop()
                self.linked.emit()
