"""
Headless end-to-end test of host -> viewer telemetry sharing.

Runs the real GUIController against the Virtual Teensy 3 simulator (headless,
UDP on localhost), starts a TelemetryServer, and attaches several ViewerLinks.

    python test_remote.py

Needs only PyQt5 (offscreen platform); no display and no hardware.
"""
import os
import socket
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "Virtual_Teensy_3"))

from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget   # noqa: E402

# The controller pops modal dialogs on aborts; they would block a headless run.
for _name in ("critical", "warning", "information", "question"):
    setattr(QMessageBox, _name, staticmethod(lambda *a, **k: QMessageBox.Ok))

from GUI_CONTROLLER import GUIController, GuiMode          # noqa: E402
from GUI_REMOTE import (TelemetryServer, ViewerLink, ViewerState,   # noqa: E402
                        encode_msg)
from PROJECT_LOADER import load_project                    # noqa: E402
from vt_comms import VTComms                               # noqa: E402

VT_PORT = 18889
TOKEN = "test-token"
PROJECT = os.path.join(HERE, "PIDs", "Elysium.red")

app = QApplication.instance() or QApplication(sys.argv)


def pump(seconds: float = 0.2, until=None, timeout: float = 5.0) -> bool:
    """Run the Qt event loop; with `until`, return as soon as it is true."""
    end = time.monotonic() + (timeout if until else seconds)
    while time.monotonic() < end:
        app.processEvents()
        if until and until():
            return True
        time.sleep(0.01)
    return until() if until else True


class Viewer:
    def __init__(self, port, token=TOKEN, name="v"):
        self.state = ViewerState()
        self.link = ViewerLink("127.0.0.1", port, token, name,
                               on_message=self.state.apply, reconnect=False)
        self.link.start()

    def stop(self):
        self.link.stop()


class RemoteTelemetryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vt = VTComms(port=VT_PORT)
        assert cls.vt.start()
        cls.ctl = GUIController(QWidget())
        project = load_project(PROJECT)
        assert project is not None, "could not load test project"
        cls.ctl.load_project(project, PROJECT)

        cls.ctl.ethernet_client.connect("127.0.0.1", VT_PORT)
        assert pump(until=lambda: cls.ctl.ethernet_client.connected, timeout=8), \
            "controller never connected to the virtual Teensy"
        pump(0.3)
        cls.server = TelemetryServer(cls.ctl, host="127.0.0.1", port=0, token=TOKEN)
        cls.port = cls.server.start()
        cls.viewers = []

    @classmethod
    def tearDownClass(cls):
        for v in cls.viewers:
            v.stop()
        cls.server.stop()
        cls.ctl.ethernet_client.disconnect("test done")
        cls.vt.stop()

    def viewer(self, **kw):
        v = Viewer(self.port, **kw)
        self.viewers.append(v)
        return v

    def live(self, v):
        self.assertTrue(pump(until=lambda: v.state.snapshots > 0), "no snapshot")

    # --------------------------------------------------------------------------------------------------------------

    def test_01_snapshot_and_project(self):
        v = self.viewer()
        self.live(v)
        self.assertEqual(v.state.link, "LIVE")
        self.assertEqual(v.state.mode, self.ctl.mode)
        self.assertTrue(v.state.host_link)
        self.assertEqual(sorted(v.state.valves), sorted(self.ctl.valve_states))
        self.assertIsNotNone(v.state.project)
        self.assertIn("text", v.state.project)
        self.assertTrue(v.state.project["text"])

    def test_02_sensor_stream_follows_slider(self):
        v = self.viewer()
        self.live(v)
        self.vt.update_sensor("P1", 123.5)
        ok = pump(until=lambda: abs(v.state.sensors.get("P1", 0) - 123.5) < 0.01)
        self.assertTrue(ok, f"viewer P1={v.state.sensors.get('P1')}")
        self.vt.update_sensor("P1", 42.0)
        self.assertTrue(pump(until=lambda: abs(v.state.sensors.get("P1", 0) - 42.0) < 0.01))

    def test_03_sensor_rate_is_throttled(self):
        v = self.viewer()
        self.live(v)
        before = v.state.messages
        pump(2.0)
        rate = (v.state.messages - before) / 2.0
        # Teensy streams at ~100 Hz per channel; viewers must get far fewer messages.
        self.assertLess(rate, 25, f"viewer msg rate {rate:.0f}/s")
        self.assertGreater(rate, 5, f"viewer msg rate {rate:.0f}/s (stream stalled?)")

    def test_04_valve_change_reaches_all_viewers(self):
        vs = [self.viewer(name=f"v{i}") for i in range(3)]
        for v in vs:
            self.live(v)
        self.ctl._set_mode(GuiMode.MANUAL, "test")
        name = sorted(self.ctl.valve_states)[0]
        want_open = not self.ctl.valve_states[name]
        self.ctl.toggle_valve(name, want_open)
        want = "OPEN" if want_open else "CLOSED"
        for v in vs:
            self.assertTrue(pump(until=lambda v=v: v.state.valves.get(name) == want),
                            f"{name} -> {want} not seen; has {v.state.valves.get(name)}")
        self.ctl.toggle_valve(name, not want_open)
        pump(until=lambda: self.ctl.valve_states[name] == (not want_open))

    def test_05_mode_and_abort_propagate(self):
        v = self.viewer()
        self.live(v)
        self.ctl._set_mode(GuiMode.LOCKED, "test")
        self.assertTrue(pump(until=lambda: v.state.mode == "LOCKED"))
        self.ctl.signals.abort_triggered.emit("manual_abort", "unit test abort", "")
        self.assertTrue(pump(until=lambda: v.state.abort is not None), "abort not seen")
        self.assertEqual(v.state.abort["reason"], "unit test abort")
        self.assertTrue(pump(until=lambda: v.state.mode == "ABORT"))

    def test_06_late_joiner_gets_current_state(self):
        self.vt.update_sensor("P2", 77.0)
        pump(until=lambda: abs(self.ctl.current_sensor_values.get("P2", 0) - 77.0) < 0.01)
        late = self.viewer(name="late")
        self.live(late)
        self.assertAlmostEqual(late.state.sensors.get("P2", 0), 77.0, places=1)
        self.assertEqual(late.state.mode, self.ctl.mode)

    def test_07_bad_token_rejected_and_gets_no_data(self):
        bad = Viewer(self.port, token="wrong", name="intruder")
        self.assertTrue(pump(until=lambda: bad.state.link == "REJECTED"), bad.state.link)
        self.assertEqual(bad.state.snapshots, 0)
        self.assertEqual(bad.state.last_error, "bad token")
        bad.stop()

    def test_08_viewer_cannot_command(self):
        """A hostile viewer sending command-shaped messages changes nothing."""
        self.ctl._set_mode(GuiMode.MANUAL, "test")
        name = sorted(self.ctl.valve_states)[0]
        before = dict(self.ctl.valve_states)
        rejected_before = self.server.rejected_count
        s = socket.create_connection(("127.0.0.1", self.port))
        s.sendall(encode_msg({"type": "hello", "token": TOKEN, "name": "evil"}))
        for msg in ({"type": "valve", "name": name, "state": "OPEN"},
                    {"type": "command", "cmd": "OPEN", "target": name},
                    {"type": "mode", "mode": "MANUAL"}):
            s.sendall(encode_msg(msg))
        s.sendall(b"not json at all\n")
        self.assertTrue(pump(until=lambda: self.server.rejected_count >= rejected_before + 4),
                        f"rejected {self.server.rejected_count - rejected_before}/4")
        pump(0.5)
        self.assertEqual(self.ctl.valve_states, before)
        self.assertFalse(self.ctl.pending_valve_commands)
        s.close()

    def test_09_stalled_viewer_does_not_block_host(self):
        """A viewer that connects and never reads must not slow the host or
        other viewers."""
        stalled = socket.create_connection(("127.0.0.1", self.port))
        stalled.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
        stalled.sendall(encode_msg({"type": "hello", "token": TOKEN, "name": "stalled"}))
        good = self.viewer(name="good")
        self.live(good)
        t0 = time.monotonic()
        n0 = good.state.messages
        for i in range(300):             # hammer events well past any socket buffer
            self.server._broadcast({"type": "status", "text": "x" * 2000})
        pump(1.0)
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 3.0, "host stalled by a non-reading viewer")
        self.assertGreater(good.state.messages - n0, 100, "good viewer starved")
        stalled.close()

    def test_10_viewer_disconnect_reconnect_and_count(self):
        v = self.viewer(name="counted")
        self.live(v)
        self.assertTrue(pump(until=lambda: self.server.viewer_count >= 1))
        v.stop()
        gone = pump(until=lambda: self.server.viewer_count == 0, timeout=3)
        # other viewers from earlier tests may still be attached; just confirm count dropped
        self.assertTrue(gone or self.server.viewer_count < len(self.viewers))
        again = Viewer(self.port, name="back")
        self.viewers.append(again)
        self.live(again)

    def test_11_stale_detection_when_host_goes_quiet(self):
        v = Viewer(self.port, name="stale-check")
        self.viewers.append(v)
        self.live(v)
        # Silence everything the host emits: its own timers and the controller's
        # 10 Hz calc-channel broadcast (which would otherwise keep the link busy).
        self.server._hb_timer.stop()
        self.server._flush_timer.stop()
        self.ctl._calc_timer.stop()
        self.assertTrue(pump(until=lambda: v.state.link == "STALE", timeout=8),
                        f"link={v.state.link}")
        self.server._hb_timer.start()
        self.server._flush_timer.start()
        self.ctl._calc_timer.start(100)
        self.assertTrue(pump(until=lambda: v.state.link == "LIVE", timeout=5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
