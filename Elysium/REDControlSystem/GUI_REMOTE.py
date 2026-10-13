"""
GUI REMOTE

Read-only telemetry sharing between the operator ("host") GUI and any number of
viewer devices.

    Teensy --UDP/Ethernet-- Host GUI (GUIController) --TCP-- Viewers (read-only)

The host is the only thing that ever talks to the Teensy. TelemetryServer
mirrors the controller's signals out to viewers as newline-delimited JSON; it
never accepts commands. A viewer that sends anything other than the handshake
or a ping is logged and counted, nothing more.

Wire format (one JSON object per line, UTF-8):

  viewer -> host   {"type":"hello","token":"...","name":"laptop-2","v":1}
  viewer -> host   {"type":"ping"}                                (optional)
  host   -> viewer {"type":"snapshot", ...}   full state, sent once after hello
  host   -> viewer {"type":"sensors","t":ts,"v":{"P1":12.3,...}}  <= SENSOR_HZ
  host   -> viewer {"type":"valve","name":"NCS1","state":"OPEN"}
  host   -> viewer {"type":"actuator","name":"MV-1","pct":50.0}
  host   -> viewer {"type":"mode","mode":"MANUAL"}
  host   -> viewer {"type":"abort","abort_type":..,"reason":..,"state_id":..}
  host   -> viewer {"type":"warnings","messages":[...]}
  host   -> viewer {"type":"status","text":"..."}
  host   -> viewer {"type":"link","connected":true,"reason":""}   Teensy link
  host   -> viewer {"type":"calc","values":{...}}
  host   -> viewer {"type":"project","name":..,"filename":..,"text":..}
  host   -> viewer {"type":"hb","t":ts}                           1 Hz
  host   -> viewer {"type":"error","reason":"bad token"}          then closes

A viewer that cannot keep up (its send queue overflows or a send stalls) is
dropped rather than slowing the host; it reconnects and gets a fresh snapshot.

ViewerLink (bottom of file) is the matching client. It has no Qt dependency so
it can be used from tests or non-Qt tools.
"""

import json
import os
import socket
import threading
import time
from collections import deque
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

PROTOCOL_VERSION = 1
DEFAULT_PORT = 8900

SENSOR_HZ = 10            # max sensor-batch rate pushed to viewers
HEARTBEAT_S = 1.0         # host liveness ping to viewers
CLIENT_QUEUE_MAX = 2000   # messages; overflow -> client dropped, must resync
SEND_TIMEOUT_S = 5.0      # a send stalled this long drops the client
HELLO_TIMEOUT_S = 5.0
STALE_AFTER_S = 3.5       # viewer-side: no host traffic for this long -> STALE


def encode_msg(msg: dict) -> bytes:
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")


class _ClientConn:
    """One connected viewer: a socket, a bounded outgoing queue, and a writer
    thread. Nothing here ever blocks the host's GUI thread."""

    def __init__(self, sock: socket.socket, addr, server: "TelemetryServer"):
        self.sock = sock
        self.addr = addr
        self.server = server
        self.name = f"{addr[0]}:{addr[1]}"
        self.authed = False
        self.alive = True
        self.out = deque()
        self.cv = threading.Condition()

    def enqueue(self, data: bytes) -> bool:
        """Queue bytes for sending. False (and the client is dropped) if the
        queue is full."""
        with self.cv:
            if not self.alive:
                return False
            if len(self.out) >= CLIENT_QUEUE_MAX:
                overflow = True
            else:
                overflow = False
                self.out.append(data)
                self.cv.notify()
        if overflow:
            self.close("send queue overflow (viewer too slow)")
            return False
        return True

    def close(self, reason: str = ""):
        with self.cv:
            if not self.alive:
                return
            self.alive = False
            self.cv.notify_all()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        self.server._client_closed(self, reason)

    def writer_loop(self):
        self.sock.settimeout(SEND_TIMEOUT_S)
        while True:
            with self.cv:
                while self.alive and not self.out:
                    self.cv.wait()
                if not self.alive:
                    return
                data = self.out.popleft()
            try:
                self.sock.sendall(data)
            except (OSError, socket.timeout) as exc:
                self.close(f"send failed: {exc}")
                return

    def reader_loop(self):
        """Handshake, then discard. Viewers cannot command anything."""
        self.sock.settimeout(HELLO_TIMEOUT_S)
        buf = b""
        try:
            while self.alive:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if len(buf) > 65536:
                    self.server._reject(self, "oversized message")
                    break
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not self._handle_line(line):
                        self.close("handshake failed")
                        return
                if self.authed:
                    self.sock.settimeout(None)
        except (OSError, socket.timeout):
            pass
        self.close("viewer disconnected")

    def _handle_line(self, line: bytes) -> bool:
        if not line.strip():
            return True
        try:
            msg = json.loads(line.decode("utf-8"))
            mtype = msg.get("type") if isinstance(msg, dict) else None
        except (ValueError, UnicodeDecodeError):
            mtype = None
        if not self.authed:
            if mtype != "hello":
                self.enqueue(encode_msg({"type": "error", "reason": "hello expected"}))
                return False
            expected = self.server.token
            if expected and msg.get("token") != expected:
                self.enqueue(encode_msg({"type": "error", "reason": "bad token"}))
                self.server._reject(self, "bad token")
                self._flush_then_close()
                return True
            self.name = str(msg.get("name") or self.name)[:64]
            self.authed = True
            self.server._client_authed(self)
            return True
        if mtype == "ping":
            return True
        # Anything else from a viewer is a command attempt; it is never executed.
        self.server._reject(self, f"ignored message type {mtype!r}")
        return True

    def _flush_then_close(self):
        # Give the writer a moment to deliver the error line, then close.
        def later():
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                with self.cv:
                    if not self.out:
                        break
                time.sleep(0.02)
            self.close("rejected")
        threading.Thread(target=later, daemon=True).start()


class TelemetryServer(QObject):
    """Mirrors a GUIController's state to read-only viewers over TCP.

    Construct on the Qt main thread after the controller exists, then call
    start(). The server never calls into the controller except to read state,
    and never on any thread but the main one.
    """

    clients_changed = pyqtSignal(int)     # number of authenticated viewers
    log = pyqtSignal(str)
    _snapshot_wanted = pyqtSignal(object)  # reader thread -> main thread hop

    def __init__(self, controller, host: str = "0.0.0.0", port: int = DEFAULT_PORT,
                 token: str = "", parent=None):
        super().__init__(parent)
        self.controller = controller
        self.host = host
        self.port = port
        self.token = token
        self.rejected_count = 0

        self._listener: Optional[socket.socket] = None
        self._accept_thread: Optional[threading.Thread] = None
        self._clients: list[_ClientConn] = []
        self._lock = threading.Lock()
        self._running = False

        self._pending_sensors: dict = {}
        self._pending_ts = 0.0
        self._last_project_path = None

        self._snapshot_wanted.connect(self._send_snapshot)
        self._flush_timer = QTimer(self)
        self._flush_timer.timeout.connect(self._flush_sensors)
        self._hb_timer = QTimer(self)
        self._hb_timer.timeout.connect(self._heartbeat)

    # LIFECYCLE ----------------------------------------------------------------------------------------------------

    def start(self) -> int:
        """Start listening. Returns the bound port (useful with port=0)."""
        if self._running:
            return self.port
        ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        ls.bind((self.host, self.port))
        ls.listen(16)
        self.port = ls.getsockname()[1]
        self._listener = ls
        self._running = True
        self._accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._accept_thread.start()

        s = self.controller.signals
        s.sensor_updated.connect(self._on_sensor)
        s.valve_updated.connect(self._on_valve)
        s.actuator_updated.connect(self._on_actuator)
        s.mode_changed.connect(self._on_mode)
        s.abort_triggered.connect(self._on_abort)
        s.warnings_changed.connect(self._on_warnings)
        s.system_status.connect(self._on_status)
        s.connected.connect(self._on_link_up)
        s.disconnected.connect(self._on_link_down)
        s.calc_values_changed.connect(self._on_calc)

        self._flush_timer.start(int(1000 / SENSOR_HZ))
        self._hb_timer.start(int(HEARTBEAT_S * 1000))
        self.log.emit(f"Telemetry server listening on {self.host}:{self.port}"
                      + (" (token required)" if self.token else " (NO TOKEN)"))
        return self.port

    def stop(self):
        if not self._running:
            return
        self._running = False
        self._flush_timer.stop()
        self._hb_timer.stop()
        s = self.controller.signals
        for sig, slot in (
            (s.sensor_updated, self._on_sensor), (s.valve_updated, self._on_valve),
            (s.actuator_updated, self._on_actuator), (s.mode_changed, self._on_mode),
            (s.abort_triggered, self._on_abort), (s.warnings_changed, self._on_warnings),
            (s.system_status, self._on_status), (s.connected, self._on_link_up),
            (s.disconnected, self._on_link_down), (s.calc_values_changed, self._on_calc),
        ):
            try:
                sig.disconnect(slot)
            except TypeError:
                pass
        try:
            self._listener.close()
        except OSError:
            pass
        with self._lock:
            clients = list(self._clients)
        for c in clients:
            c.close("server stopped")

    @property
    def viewer_count(self) -> int:
        with self._lock:
            return sum(1 for c in self._clients if c.authed and c.alive)

    # NETWORK THREADS ----------------------------------------------------------------------------------------------

    def _accept_loop(self):
        while self._running:
            try:
                sock, addr = self._listener.accept()
            except OSError:
                break
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            conn = _ClientConn(sock, addr, self)
            with self._lock:
                self._clients.append(conn)
            threading.Thread(target=conn.writer_loop, daemon=True).start()
            threading.Thread(target=conn.reader_loop, daemon=True).start()

    def _client_authed(self, conn: _ClientConn):
        # Called from the client's reader thread. The snapshot reads controller
        # state, so it is built on the main thread via a queued signal.
        self.log.emit(f"Viewer connected: {conn.name} ({conn.addr[0]})")
        self._snapshot_wanted.emit(conn)

    def _client_closed(self, conn: _ClientConn, reason: str):
        with self._lock:
            if conn in self._clients:
                self._clients.remove(conn)
        if conn.authed:
            self.log.emit(f"Viewer left: {conn.name} ({reason})")
            self.clients_changed.emit(self.viewer_count)

    def _reject(self, conn: _ClientConn, why: str):
        self.rejected_count += 1
        self.log.emit(f"Viewer {conn.name} rejected: {why}")

    # BROADCAST (main thread) --------------------------------------------------------------------------------------

    def _broadcast(self, msg: dict):
        data = encode_msg(msg)
        with self._lock:
            targets = [c for c in self._clients if c.authed and c.alive]
        for c in targets:
            c.enqueue(data)

    def _send_snapshot(self, conn: _ClientConn):
        if not conn.alive:
            return
        ctl = self.controller
        warnings = list(getattr(ctl, "_active_warnings", {}).values())
        snap = {
            "type": "snapshot",
            "v": PROTOCOL_VERSION,
            "t": time.time(),
            "mode": ctl.mode,
            "safe_applied": ctl.safe_applied,
            "link": bool(getattr(ctl.ethernet_client, "connected", False)),
            "valves": dict(ctl.valve_states),
            "actuators": dict(ctl.actuator_positions),
            "sensors": dict(ctl.current_sensor_values),
            "calc": {k: v for k, v in ctl.calc_values.items()},
            "warnings": warnings,
            "project": self._project_payload(),
        }
        conn.enqueue(encode_msg(snap))
        self.clients_changed.emit(self.viewer_count)

    def _project_payload(self) -> Optional[dict]:
        path = getattr(self.controller, "project_path", None)
        project = getattr(self.controller, "project", None)
        if not path or not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return None
        return {
            "name": getattr(project, "name", os.path.basename(path)),
            "filename": os.path.basename(path),
            "text": text,
        }

    def _on_sensor(self, name: str, value: float, ts: float):
        self._pending_sensors[name] = value
        self._pending_ts = ts

    def _flush_sensors(self):
        if self._pending_sensors:
            batch, self._pending_sensors = self._pending_sensors, {}
            self._broadcast({"type": "sensors", "t": self._pending_ts, "v": batch})

    def _on_valve(self, name: str, state: str):
        self._broadcast({"type": "valve", "name": name, "state": state})

    def _on_actuator(self, name: str, pct: float):
        self._broadcast({"type": "actuator", "name": name, "pct": pct})

    def _on_mode(self, mode: str):
        self._broadcast({"type": "mode", "mode": mode})

    def _on_abort(self, abort_type: str, reason: str, state_id: str):
        self._broadcast({"type": "abort", "abort_type": abort_type,
                         "reason": reason, "state_id": state_id})

    def _on_warnings(self, messages: list):
        self._broadcast({"type": "warnings", "messages": list(messages)})

    def _on_status(self, text: str):
        self._broadcast({"type": "status", "text": text})

    def _on_link_up(self):
        self._broadcast({"type": "link", "connected": True, "reason": ""})

    def _on_link_down(self, reason: str):
        self._broadcast({"type": "link", "connected": False, "reason": reason})

    def _on_calc(self, values: dict):
        self._broadcast({"type": "calc", "values": values})

    def _heartbeat(self):
        self._broadcast({"type": "hb", "t": time.time()})
        # The controller has no project-changed signal, so notice a switch here.
        path = getattr(self.controller, "project_path", None)
        if path != self._last_project_path:
            self._last_project_path = path
            payload = self._project_payload()
            if payload:
                self._broadcast({"type": "project", **payload})


# VIEWER CLIENT ---------------------------------------------------------------------------------------------------------


class ViewerLink:
    """Viewer-side connection to a TelemetryServer. No Qt dependency.

    Runs a background thread that connects, handshakes, reads messages and
    reconnects with backoff. on_message(dict) is called from that thread for
    every host message (including the synthetic {"type":"state"} messages that
    report the link state: CONNECTING / LIVE / STALE / DISCONNECTED / REJECTED).

    There is deliberately no method for sending anything but the handshake and
    a ping: a viewer cannot command the system.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT, token: str = "",
                 name: str = "viewer", on_message: Optional[Callable[[dict], None]] = None,
                 reconnect: bool = True):
        self.host = host
        self.port = port
        self.token = token
        self.name = name
        self.on_message = on_message or (lambda m: None)
        self.reconnect = reconnect
        self.state = "DISCONNECTED"
        self._stop = threading.Event()
        self._sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self._last_rx = 0.0

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        s = self._sock
        if s is not None:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass

    def _set_state(self, state: str, detail: str = ""):
        if state != self.state:
            self.state = state
            self.on_message({"type": "state", "state": state, "detail": detail})

    def _run(self):
        backoff = 0.5
        while not self._stop.is_set():
            self._set_state("CONNECTING")
            rejected = False
            try:
                rejected = self._session()
            except (OSError, socket.timeout, ValueError) as exc:
                detail = str(exc)
            else:
                detail = "closed"
            if self._stop.is_set():
                break
            self._set_state("REJECTED" if rejected else "DISCONNECTED", detail)
            if rejected or not self.reconnect:
                break
            self._stop.wait(backoff)
            backoff = min(backoff * 2, 5.0)
        if self.state != "REJECTED":
            self._set_state("DISCONNECTED")

    def _session(self) -> bool:
        """One connection. Returns True if the host rejected us."""
        sock = socket.create_connection((self.host, self.port), timeout=5.0)
        self._sock = sock
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.sendall(encode_msg({"type": "hello", "token": self.token,
                                     "name": self.name, "v": PROTOCOL_VERSION}))
            sock.settimeout(0.5)
            buf = b""
            self._last_rx = time.monotonic()
            while not self._stop.is_set():
                try:
                    chunk = sock.recv(65536)
                except socket.timeout:
                    if (self.state == "LIVE"
                            and time.monotonic() - self._last_rx > STALE_AFTER_S):
                        self._set_state("STALE", "no data from host")
                    continue
                if not chunk:
                    return False
                self._last_rx = time.monotonic()
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    msg = json.loads(line.decode("utf-8"))
                    if msg.get("type") == "error":
                        self.on_message(msg)
                        return True
                    if msg.get("type") == "snapshot":
                        self.state = "LIVE"
                        self.on_message({"type": "state", "state": "LIVE", "detail": ""})
                    elif self.state == "STALE":
                        self._set_state("LIVE")
                    self.on_message(msg)
            return False
        finally:
            self._sock = None
            try:
                sock.close()
            except OSError:
                pass


class ViewerState:
    """Plain-Python mirror of the host's state, built by applying ViewerLink
    messages in order. The viewer UI and the tests both read from this."""

    def __init__(self):
        self.link = "DISCONNECTED"      # ViewerLink state
        self.mode = ""
        self.safe_applied = False
        self.host_link = False          # host <-> Teensy link up?
        self.valves: dict = {}
        self.actuators: dict = {}
        self.sensors: dict = {}
        self.sensor_rx: dict = {}       # name -> local monotonic time of last update
        self.calc: dict = {}
        self.warnings: list = []
        self.status = ""
        self.abort: Optional[dict] = None   # last abort message, cleared on SAFE
        self.project: Optional[dict] = None
        self.snapshots = 0
        self.messages = 0
        self.last_error = ""

    def apply(self, msg: dict):
        self.messages += 1
        t = msg.get("type")
        now = time.monotonic()
        if t == "state":
            self.link = msg["state"]
        elif t == "snapshot":
            self.snapshots += 1
            self.mode = msg.get("mode", "")
            self.safe_applied = bool(msg.get("safe_applied"))
            self.host_link = bool(msg.get("link"))
            self.valves = {k: ("OPEN" if v is True else "CLOSED" if v is False else str(v))
                           for k, v in msg.get("valves", {}).items()}
            self.actuators = dict(msg.get("actuators", {}))
            self.sensors = dict(msg.get("sensors", {}))
            self.sensor_rx = {k: now for k in self.sensors}
            self.calc = dict(msg.get("calc", {}))
            self.warnings = list(msg.get("warnings", []))
            self.project = msg.get("project")
            self.abort = None
        elif t == "sensors":
            for k, v in msg.get("v", {}).items():
                self.sensors[k] = v
                self.sensor_rx[k] = now
        elif t == "valve":
            state = msg.get("state", "")
            self.valves[msg["name"]] = state
        elif t == "actuator":
            self.actuators[msg["name"]] = msg.get("pct", 0.0)
        elif t == "mode":
            self.mode = msg.get("mode", "")
            if self.mode == "SAFE":
                self.abort = None
        elif t == "abort":
            self.abort = msg
        elif t == "warnings":
            self.warnings = list(msg.get("messages", []))
        elif t == "status":
            self.status = msg.get("text", "")
        elif t == "link":
            self.host_link = bool(msg.get("connected"))
        elif t == "calc":
            self.calc = dict(msg.get("values", {}))
        elif t == "project":
            self.project = {k: msg.get(k) for k in ("name", "filename", "text")}
        elif t == "error":
            self.last_error = msg.get("reason", "")
