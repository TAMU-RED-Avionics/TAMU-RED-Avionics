"""Headless tests for the Live Data tab (GUI_LIVEDATA.py).   python test_livedata.py"""
import math
import os
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import Qt, QDateTime                       # noqa: E402
from PyQt5.QtTest import QTest                               # noqa: E402
from PyQt5.QtWidgets import QApplication, QWidget            # noqa: E402
from matplotlib.backend_bases import MouseEvent              # noqa: E402

from GUI_CONTROLLER import GUIController                     # noqa: E402
from GUI_LIVEDATA import LiveDataPage, CMD_SUFFIX            # noqa: E402
from PROJECT_LOADER import load_project                      # noqa: E402

PROJECT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PIDs", "Elysium.red")
app = QApplication.instance() or QApplication(sys.argv)


def now():
    return QDateTime.currentMSecsSinceEpoch() / 1000.0


class LiveDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ctl = GUIController(QWidget())
        cls.ctl.load_project(load_project(PROJECT), PROJECT)
        cls.page = LiveDataPage(cls.ctl)
        cls.page.resize(1100, 650)
        cls.page.show()
        cls.pt = cls.ctl.pt_keys[0]
        cls.tc = cls.ctl.tc_keys[0] if cls.ctl.tc_keys else cls.ctl.pt_keys[1]
        cls.valve = sorted(cls.ctl.valve_states)[0]

    def setUp(self):
        p = self.page
        p.window_combo.setCurrentIndex(1)           # 30 s
        p.clear_data()
        for r in p._rows.values():
            r.check.setChecked(False)
        p._axis_choice.clear()
        p._on_selection_changed()

    def feed(self, seconds=12.0, hz=100):
        """Back-dated synthetic stream so we have `seconds` of history right now."""
        t_end = now()
        n = int(seconds * hz)
        for i in range(n):
            ts = t_end - seconds + i / hz
            x = ts - (t_end - seconds)
            self.ctl.signals.sensor_updated.emit(self.pt, 500 + 400 * math.sin(x), ts)
            self.ctl.signals.sensor_updated.emit(self.tc, 20 + 3 * x, ts)
        app.processEvents()

    def tick(self):
        app.processEvents()
        self.page.render()
        app.processEvents()

    def drag(self, ax, x0, y0, x1, y1):
        c = self.page.canvas
        a, b = ax.transData.transform((x0, y0)), ax.transData.transform((x1, y1))
        for n, pt in (("button_press_event", a), ("motion_notify_event", b), ("button_release_event", b)):
            c.callbacks.process(n, MouseEvent(n, c, pt[0], pt[1], button=1))

    def test_series_list_from_project(self):
        self.assertIn(self.pt, self.page._rows)
        self.assertIn(self.valve + CMD_SUFFIX, self.page._rows)

    def test_default_axis_split_by_unit(self):
        p = self.page
        p._rows[self.pt].check.setChecked(True)
        p._rows[self.tc].check.setChecked(True)
        self.assertEqual(p._axis_of(self.pt), "A")
        if self.tc.startswith("TC"):
            self.assertEqual(p._axis_of(self.tc), "B")       # different unit -> right axis
        p._toggle_axis(self.pt)
        self.assertEqual(p._axis_of(self.pt), "B")
        self.assertIs(p._lines[self.pt].axes, p.ax_b)

    def test_live_follow_then_drag_zoom_back_home(self):
        p = self.page
        p._rows[self.pt].check.setChecked(True)
        self.feed(12)
        self.tick()
        self.assertTrue(p._following)
        x0, x1 = p.ax_a.get_xlim()
        self.assertAlmostEqual(x1 - x0, 30.0, places=3)
        # shrink the window to 10 s, then zoom into ~1 s of it
        p.window_combo.setCurrentIndex(0)
        self.tick()
        x0, x1 = p.ax_a.get_xlim()
        self.drag(p.ax_a, x1 - 6.0, 400, x1 - 5.1, 900)
        self.tick()
        zx0, zx1 = p.ax_a.get_xlim()
        self.assertFalse(p._following)
        self.assertAlmostEqual(zx1 - zx0, 0.9, delta=0.05)
        self.assertEqual(len(p._zoom_stack), 1)
        n_before = len(p._series[self.pt].ts)
        self.feed(0.5)                                    # data keeps recording while zoomed...
        self.tick()
        self.assertGreater(len(p._series[self.pt].ts), n_before)
        self.assertEqual(p.ax_a.get_xlim(), (zx0, zx1))   # ...but the zoomed view stays put
        # zoom again, then step back out one level at a time
        lo, hi = p.ax_a.get_ylim()
        self.drag(p.ax_a, zx0 + 0.2, lo + 0.1 * (hi - lo), zx0 + 0.5, hi - 0.1 * (hi - lo))
        self.tick()
        self.assertEqual(len(p._zoom_stack), 2)
        QTest.keyClick(p.canvas, Qt.Key_Z, Qt.ControlModifier)
        self.tick()
        self.assertAlmostEqual(p.ax_a.get_xlim()[1] - p.ax_a.get_xlim()[0], 0.9, delta=0.05)
        QTest.keyClick(p.canvas, Qt.Key_Backspace)
        self.tick()
        self.assertTrue(p._following)                     # back to the live view
        # Home from a deep zoom
        lo, hi = p.ax_a.get_ylim()
        xa, xb = p.ax_a.get_xlim()
        self.drag(p.ax_a, xa + 2, lo + 0.2 * (hi - lo), xa + 4, hi - 0.2 * (hi - lo))
        self.tick()
        self.assertFalse(p._following)
        QTest.keyClick(p.canvas, Qt.Key_Home)
        self.tick()
        self.assertTrue(p._following)
        self.assertEqual(p._zoom_stack, [])

    def test_pause_freezes_view(self):
        p = self.page
        p._rows[self.pt].check.setChecked(True)
        self.feed(5)
        self.tick()
        p._toggle_pause()
        frozen = p.ax_a.get_xlim()
        time.sleep(0.3)
        self.tick()
        self.assertEqual(p.ax_a.get_xlim(), frozen)
        p._toggle_pause()
        self.assertTrue(p._following)

    def test_independent_y_axes_and_hover(self):
        p = self.page
        p._rows[self.pt].check.setChecked(True)      # ~100..900 psi
        p._rows[self.tc].check.setChecked(True)
        p._axis_choice[self.tc] = "B"
        p._on_selection_changed()
        self.feed(12)
        self.tick()
        ya, yb = p.ax_a.get_ylim(), p.ax_b.get_ylim()
        self.assertGreater(ya[1] - ya[0], 500)       # A scaled to the PT...
        self.assertLess(yb[1] - yb[0], 100)          # ...B scaled to the temperature, not squashed
        # hover directly over a point on the B-axis line
        line = p._lines[self.tc]
        t, v = line.get_data()
        i = len(t) // 2
        px, py = p.ax_b.transData.transform((t[i], v[i]))
        p.canvas.callbacks.process("motion_notify_event",
                                   MouseEvent("motion_notify_event", p.canvas, px + 2, py + 1))
        self.assertTrue(p._annot.get_visible())
        self.assertIn(self.tc, p._annot.get_text())
        self.assertIn("[B]", p._annot.get_text())
        p.canvas.callbacks.process("motion_notify_event",
                                   MouseEvent("motion_notify_event", p.canvas, 1, 1))
        self.assertFalse(p._annot.get_visible())

    def test_commanded_signal_step_trace(self):
        p = self.page
        key = self.valve + CMD_SUFFIX
        p._rows[self.pt].check.setChecked(True)
        p._rows[key].check.setChecked(True)
        self.assertEqual(p._axis_of(key), "B")       # 0/1 vs psi -> own axis
        self.feed(12)
        t = now()
        self.ctl.signals.command_sent.emit(self.valve, 1.0, t - 8.0)
        self.ctl.signals.command_sent.emit(self.valve, 0.0, t - 4.0)
        self.tick()
        tt, vv = p._lines[key].get_data()
        self.assertEqual(sorted(set(vv.tolist())), [0.0, 1.0])
        self.assertEqual(p._lines[key].get_drawstyle(), "steps-post")
        self.assertGreaterEqual(tt[-1], p.ax_a.get_xlim()[1] - 1e-6)   # held to the right edge

    def test_real_controller_emits_command_signal(self):
        got = []
        self.ctl.signals.command_sent.connect(lambda n, v, t: got.append((n, v)))
        self.ctl.ethernet_client.send_valve_command = lambda *a, **k: None
        self.ctl._drive_valve(self.valve, True, force=True)
        self.ctl.pending_valve_commands.clear()
        self.assertIn((self.valve, 1.0), got)

    def test_dense_window_is_decimated_but_keeps_peaks(self):
        p = self.page
        p._rows[self.pt].check.setChecked(True)
        t_end = now()
        for i in range(60000):                        # 10 minutes at 100 Hz, one spike
            v = 1000.0 if i == 30000 else 10.0
            self.ctl.signals.sensor_updated.emit(self.pt, v, t_end - 600 + i / 100)
        p.window_combo.setCurrentIndex(3)             # 5 min
        p.zoom_home()
        self.tick()
        p.window_combo.setCurrentIndex(4)             # All
        self.tick()
        t, v = p._lines[self.pt].get_data()
        self.assertLessEqual(len(t), 3100)
        self.assertEqual(v.max(), 1000.0)

    def test_dark_mode_toggle_and_clear(self):
        p = self.page
        p._rows[self.pt].check.setChecked(True)
        self.feed(3)
        p.set_dark_mode(False)
        p.set_dark_mode(True)
        self.assertIn(self.pt, p._lines)
        p.clear_data()
        self.assertIsNone(p._t0)
        self.assertEqual(len(p._series[self.pt].ts), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
