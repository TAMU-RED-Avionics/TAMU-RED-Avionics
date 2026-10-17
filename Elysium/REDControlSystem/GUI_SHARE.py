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
sends after its handshake (incoming bytes are discarded), so a viewer cannot command
anything - only the GUI holding the Teensy link can. Messages are newline-delimited
JSON ("t" is the type).

Handshake: the viewer opens with {"t":"auth","token":...,"name":...}. With a token set
on the server, a wrong token gets {"t":"error","reason":...} and the socket is closed;
a viewer that sends nothing within HELLO_TIMEOUT_MS is dropped. Only then does it get
the "hello" snapshot and start receiving the stream.

Liveness: the server sends {"t":"hb"} every HEARTBEAT_MS. A viewer that hears nothing
for STALE_AFTER_S reports itself stale (frozen data must not look live), and a viewer
that loses an established link keeps retrying every RECONNECT_MS, getting a fresh
snapshot when it is back. A viewer that falls MAX_BACKLOG_BYTES behind is dropped
rather than slowing the controller; it reconnects and resyncs.

Both classes are plain Qt objects living on the GUI thread; they know nothing about
GUIController (GUIController wires them up), so this module has no side effects.
"""
import json
import socket
import time
from typing import Callable, Dict, List

from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

PROTOCOL_VERSION = 1
DEFAULT_SHARE_PORT = 9000
SENSOR_FLUSH_MS = 50                 # sensor samples are batched and sent at 20 Hz
MAX_BACKLOG_BYTES = 4 * 1024 * 1024  # drop a viewer that can't keep up
HELLO_TIMEOUT_MS = 5000
MAX_HANDSHAKE_BYTES = 4096
HEARTBEAT_MS = 1000                  # controller liveness ping to viewers
STALE_AFTER_S = 3.5                  # viewer-side: no controller traffic for this long -> stale
RECONNECT_MS = 2000                  # viewer-side: retry interval after losing a live link


def _encode(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


class ShareServer(QObject):
    viewers_changed = pyqtSignal(int)

    def __init__(self, snapshot: Callable[[], dict], parent=None):
        super().__init__(parent)
        self._snapshot = snapshot            # () -> hello message for a new viewer
        self.token = ""                      # shared secret viewers must present ("" = open)
        self.rejected_count = 0
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._clients: list = []             # authenticated viewers: the only ones streamed to
        self._names: Dict[QTcpSocket, str] = {}
        self._pending: Dict[QTcpSocket, bytearray] = {}    # connected, handshake not yet seen
        self._sensor_buf: list = []
        self._timer = QTimer(self)
        self._timer.setInterval(SENSOR_FLUSH_MS)
        self._timer.timeout.connect(self._flush_sensors)
        self._hb_timer = QTimer(self)
        self._hb_timer.setInterval(HEARTBEAT_MS)
        self._hb_timer.timeout.connect(lambda: self.broadcast({"t": "hb"}))
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

    @property
    def viewer_names(self) -> List[str]:
        return [self._names.get(s, "?") for s in self._clients]

    def start(self, port: int = DEFAULT_SHARE_PORT) -> bool:
        self.stop()
        if not self._server.listen(QHostAddress.Any, int(port)):
            self.last_error = self._server.errorString()
            return False
        self.last_error = ""
        self._timer.start()
        self._hb_timer.start()
        return True

    def stop(self):
        self._timer.stop()
        self._hb_timer.stop()
        self._sensor_buf.clear()
        for sock in list(self._pending) + list(self._clients):
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
            self._pending[sock] = bytearray()
            sock.readyRead.connect(lambda s=sock: self._on_ready(s))
            sock.disconnected.connect(lambda s=sock: self._drop(s))
            QTimer.singleShot(HELLO_TIMEOUT_MS, lambda s=sock: self._expire(s))

    def _expire(self, sock: QTcpSocket):
        if sock in self._pending:           # never completed the handshake
            self._drop(sock)

    def _on_ready(self, sock: QTcpSocket):
        data = bytes(sock.readAll())
        buf = self._pending.get(sock)
        if buf is None:
            return                          # authenticated viewers are read-only: discard input
        buf += data
        if b"\n" not in buf:
            if len(buf) > MAX_HANDSHAKE_BYTES:
                self._drop(sock)
            return
        line = bytes(buf).split(b"\n", 1)[0]
        try:
            msg = json.loads(line)
        except ValueError:
            msg = None
        if not isinstance(msg, dict) or msg.get("t") != "auth":
            self._reject(sock, "bad handshake")
        elif self.token and msg.get("token", "") != self.token:
            self._reject(sock, "bad token")
        else:
            del self._pending[sock]
            self._clients.append(sock)
            self._names[sock] = str(msg.get("name", "") or "viewer")[:40]
            self._send(sock, _encode(self._snapshot()))
            self.viewers_changed.emit(len(self._clients))

    def _reject(self, sock: QTcpSocket, reason: str):
        self.rejected_count += 1
        self._pending.pop(sock, None)
        sock.write(_encode({"t": "error", "reason": reason}))
        sock.disconnectFromHost()           # closes once the error has been flushed

    def _drop(self, sock: QTcpSocket):
        self._pending.pop(sock, None)
        if sock in self._clients:
            self._clients.remove(sock)
            self._names.pop(sock, None)
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
    message = pyqtSignal(dict)          # every decoded message (hello included)
    linked = pyqtSignal()               # hello received: the link is usable (again, after a reconnect)
    failed = pyqtSignal(str)            # could not connect, was refused, or the user disconnected
    stale_changed = pyqtSignal(bool, str)   # (True, why) while the data can't be trusted, (False, "") when live

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sock = QTcpSocket(self)
        self._sock.connected.connect(self._on_socket_connected)
        self._sock.readyRead.connect(self._on_ready)
        self._sock.error.connect(self._on_error)
        self._sock.disconnected.connect(self._on_disconnected)
        self._buf = b""
        self._got_hello = False
        self._wanted = False
        self._retrying = False          # a live link was lost; trying to get it back
        self._stale = False
        self._last_rx = 0.0
        self._host, self._port, self._token, self._name = "", 0, "", ""
        self._hello_timer = QTimer(self)
        self._hello_timer.setSingleShot(True)
        self._hello_timer.setInterval(HELLO_TIMEOUT_MS)
        self._hello_timer.timeout.connect(lambda: self._fail("no response from the controller"))
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.setInterval(RECONNECT_MS)
        self._retry_timer.timeout.connect(self._attempt)
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(500)
        self._watchdog.timeout.connect(self._check_stale)

    @property
    def connected(self) -> bool:
        return self._got_hello and self._sock.state() == QTcpSocket.ConnectedState

    def connect_to(self, host: str, port: int, token: str = "", name: str = ""):
        self._reset()
        self._wanted = True
        self._host, self._port, self._token = host, int(port), token
        self._name = name or socket.gethostname()
        self._attempt()

    def disconnect_from_controller(self):
        was_up = self._got_hello or self._retrying
        self._reset()
        if was_up:
            self.failed.emit("Disconnected")

    # -- internals -----------------------------------------------------------
    def _attempt(self):
        self._hello_timer.start()
        self._sock.abort()
        self._sock.connectToHost(self._host, self._port)

    def _on_socket_connected(self):
        self._sock.write(_encode({"t": "auth", "token": self._token,
                                  "name": self._name, "v": PROTOCOL_VERSION}))

    def _reset(self):
        self._wanted = False
        self._retrying = False
        self._got_hello = False
        self._buf = b""
        self._hello_timer.stop()
        self._retry_timer.stop()
        self._watchdog.stop()
        self._set_stale(False, "")
        self._sock.abort()

    def _set_stale(self, stale: bool, why: str):
        if stale != self._stale or (stale and why):
            self._stale = stale
            self.stale_changed.emit(stale, why)

    def _fail(self, reason: str, retry: bool = True):
        if not self._wanted:
            return
        if retry and (self._got_hello or self._retrying):
            # A link that was up: keep the session, flag the data as untrustworthy and
            # keep trying; the controller sends a fresh snapshot when we are back.
            self._retrying = True           # before abort(): it re-enters via disconnected
            self._got_hello = False
            self._buf = b""
            self._hello_timer.stop()
            self._sock.abort()
            self._set_stale(True, f"link lost ({reason}) - reconnecting...")
            self._retry_timer.start()
            return
        self._reset()
        self.failed.emit(reason)

    def _check_stale(self):
        if self._got_hello and time.monotonic() - self._last_rx > STALE_AFTER_S:
            self._set_stale(True, f"no data from the controller for {STALE_AFTER_S:g}+ s")

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
            if msg.get("t") == "error":             # refused (e.g. bad token): don't retry
                self._fail(str(msg.get("reason", "refused by the controller")), retry=False)
                return
            self._last_rx = time.monotonic()
            if self._stale and self._got_hello:
                self._set_stale(False, "")
            if msg.get("t") == "hb":
                continue
            self.message.emit(msg)
            if not self._got_hello and msg.get("t") == "hello":
                self._got_hello = True
                self._retrying = False
                self._hello_timer.stop()
                self._watchdog.start()
                self._set_stale(False, "")
                self.linked.emit()
