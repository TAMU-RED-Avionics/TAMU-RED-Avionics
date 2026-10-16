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
from GUI_LIVEDATA import LiveDataPage            # noqa: E402
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
        cls.page.resize(1200, 750)
        cls.page.show()
        cls.pt = cls.ctl.pt_keys[0]
        cls.tc = cls.ctl.tc_keys[0] if cls.ctl.tc_keys else cls.ctl.pt_keys[1]
        cls.valve = sorted(cls.ctl.valve_states)[0]

    def setUp(self):
        p = self.page
        p.window_combo.setCurrentIndex(1)           # 30 s
        p.clear_data()
        p._set_all(list(p._rows), False)
        for pid in ("pt", "tc", "lc", "cmd"):
            p.set_panel_visible(pid, True)

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

    def drag(self, panel, x0, y0, x1, y1):
        c = panel.canvas
        a, b = panel.ax.transData.transform((x0, y0)), panel.ax.transData.transform((x1, y1))
        for n, pt in (("button_press_event", a), ("motion_notify_event", b), ("button_release_event", b)):
            c.callbacks.process(n, MouseEvent(n, c, pt[0], pt[1], button=1))

    def tick_sensor(self, key):
        self.page._rows[key].setChecked(True)

    # -- sensors / select all --------------------------------------------------------------
    def test_series_list_from_project(self):
        p = self.page
        self.assertIn(self.pt, p._rows)
        self.assertEqual(set(p.panels["pt"].keys), set(self.ctl.pt_keys))
        self.assertEqual(set(p.panels["tc"].keys), set(self.ctl.tc_keys))

    def test_select_all_and_none_per_type(self):
        p = self.page
        p._set_all(self.ctl.pt_keys, True)
        self.assertTrue(all(p._rows[k].isChecked() for k in self.ctl.pt_keys))
        self.assertFalse(any(p._rows[k].isChecked() for k in self.ctl.tc_keys))   # other types untouched
        self.assertEqual(set(p.panels["pt"].lines), set(self.ctl.pt_keys))
        self.assertEqual(p.panels["tc"].lines, {})
        p._set_all(self.ctl.pt_keys, False)
        self.assertEqual(p.panels["pt"].lines, {})

    def test_all_button_in_sidebar_ticks_the_group(self):
        from PyQt5.QtWidgets import QToolButton
        p = self.page
        all_btns = [b for b in p._list_host.findChildren(QToolButton) if b.text() == "All" and b.isEnabled()]
        self.assertGreaterEqual(len(all_btns), 2)
        all_btns[0].click()                          # first group = pressure transducers
        self.assertTrue(all(p._rows[k].isChecked() for k in self.ctl.pt_keys))

    def test_show_all_sensors_button(self):
        p = self.page
        p.set_panel_visible("tc", False)
        p.all_btn.click()
        self.assertTrue(all(cb.isChecked() for cb in p._rows.values()))
        self.assertTrue(p.panel_visible("tc"))
        for pid, keys in (("pt", self.ctl.pt_keys), ("tc", self.ctl.tc_keys), ("lc", self.ctl.lc_keys)):
            self.assertEqual(set(p.panels[pid].lines), set(keys))

    def test_each_type_only_in_its_own_panel(self):
        p = self.page
        self.tick_sensor(self.pt)
        self.tick_sensor(self.tc)
        self.assertEqual(list(p.panels["pt"].lines), [self.pt])
        if self.tc not in self.ctl.pt_keys:
            self.assertEqual(list(p.panels["tc"].lines), [self.tc])

    # -- panel grid ------------------------------------------------------------------------
    def cell(self, pid):
        w = self.page._widget(pid)
        idx = self.page._grid.indexOf(w)
        return self.page._grid.getItemPosition(idx)       # (row, col, rowspan, colspan)

    def test_starts_as_2x2_grid(self):
        p = self.page
        self.assertEqual(self.cell("pt")[:2], (0, 0))
        self.assertEqual(self.cell("tc")[:2], (0, 1))
        self.assertEqual(self.cell("lc")[:2], (1, 0))
        self.assertEqual(self.cell("cmd")[:2], (1, 1))

    def test_remove_and_add_panels_reflow(self):
        p = self.page
        p.set_panel_visible("lc", False)                  # 3 left: third spans the bottom row
        self.assertFalse(p._widget("lc").isVisible())
        self.assertEqual(self.cell("cmd"), (1, 0, 1, 2))
        p.set_panel_visible("tc", False)                  # 2 left: side by side
        self.assertEqual(self.cell("pt")[:2], (0, 0))
        self.assertEqual(self.cell("cmd")[:2], (0, 1))
        p.set_panel_visible("cmd", False)                 # 1 left: full screen
        self.assertEqual(self.cell("pt"), (0, 0, 1, 1))
        p._grid.activate()
        app.processEvents()
        self.assertGreater(p.panels["pt"].width(), p._grid_host.width() * 0.9)
        p.set_panel_visible("pt", False)                  # none: placeholder
        self.assertTrue(p._empty_lbl.isVisible())
        p.set_panel_visible("lc", True)
        self.assertTrue(p.panels["lc"].isVisible())
        self.assertFalse(p._empty_lbl.isVisible())

    def test_panel_buttons_and_close_buttons_stay_in_sync(self):
        p = self.page
        p._panel_btns["tc"].click()
        self.assertFalse(p.panel_visible("tc"))
        p.set_panel_visible("tc", True)
        self.assertTrue(p._panel_btns["tc"].isChecked())
        from PyQt5.QtWidgets import QToolButton
        close = [b for b in p.panels["lc"].findChildren(QToolButton) if b.text() == "✕"][0]
        close.click()
        self.assertFalse(p.panel_visible("lc"))
        self.assertFalse(p._panel_btns["lc"].isChecked())

    # -- time / zoom -----------------------------------------------------------------------
    def test_live_follow_then_drag_zoom_back_home(self):
        p = self.page
        panel = p.panels["pt"]
        self.tick_sensor(self.pt)
        self.feed(12)
        self.tick()
        self.assertTrue(p._following)
        x0, x1 = panel.ax.get_xlim()
        self.assertAlmostEqual(x1 - x0, 30.0, places=3)
        p.window_combo.setCurrentIndex(0)                 # 10 s
        self.tick()
        x0, x1 = panel.ax.get_xlim()
        self.drag(panel, x1 - 6.0, 400, x1 - 5.1, 900)
        self.tick()
        zx0, zx1 = panel.ax.get_xlim()
        self.assertFalse(p._following)
        self.assertAlmostEqual(zx1 - zx0, 0.9, delta=0.05)
        self.assertEqual(len(p._zoom_stack), 1)
        n_before = len(p._series[self.pt].ts)
        self.feed(0.5)                                    # data keeps recording while zoomed...
        self.tick()
        self.assertGreater(len(p._series[self.pt].ts), n_before)
        self.assertEqual(panel.ax.get_xlim(), (zx0, zx1))  # ...but the zoomed view stays put
        lo, hi = panel.ax.get_ylim()
        self.drag(panel, zx0 + 0.2, lo + 0.1 * (hi - lo), zx0 + 0.5, hi - 0.1 * (hi - lo))
        self.tick()
        self.assertEqual(len(p._zoom_stack), 2)
        QTest.keyClick(p, Qt.Key_Z, Qt.ControlModifier)
        self.tick()
        self.assertAlmostEqual(panel.ax.get_xlim()[1] - panel.ax.get_xlim()[0], 0.9, delta=0.05)
        QTest.keyClick(p, Qt.Key_Backspace)
        self.tick()
        self.assertTrue(p._following)
        xa, xb = panel.ax.get_xlim()
        lo, hi = panel.ax.get_ylim()
        self.drag(panel, xa + 2, lo + 0.2 * (hi - lo), xa + 4, hi - 0.2 * (hi - lo))
        self.tick()
        self.assertFalse(p._following)
        QTest.keyClick(p, Qt.Key_Home)
        self.tick()
        self.assertTrue(p._following)
        self.assertEqual(p._zoom_stack, [])

    def test_zoom_time_is_shared_but_y_is_per_panel(self):
        p = self.page
        self.tick_sensor(self.pt)
        self.tick_sensor(self.tc)
        self.feed(12)
        self.tick()
        pt, tc = p.panels["pt"], p.panels["tc"]
        self.assertGreater(len(tc.lines), 0)
        x0, x1 = pt.ax.get_xlim()
        lo, hi = pt.ax.get_ylim()
        self.drag(pt, x1 - 6.0, lo + 0.3 * (hi - lo), x1 - 5.0, hi - 0.3 * (hi - lo))
        self.tick()
        self.assertEqual(pt.ax.get_xlim(), tc.ax.get_xlim())          # time follows in every plot
        self.assertIn("pt", p._manual_view["y"])
        self.assertNotIn("tc", p._manual_view["y"])                   # y only fixed where dragged
        tlo, thi = tc.ax.get_ylim()
        self.assertLess(thi - tlo, 100)                               # temperature autoscaled, not squashed
        p.zoom_home()
        self.tick()
        self.assertTrue(p._following)

    def test_pause_freezes_view(self):
        p = self.page
        panel = p.panels["pt"]
        self.tick_sensor(self.pt)
        self.feed(5)
        self.tick()
        p._toggle_pause()
        frozen = panel.ax.get_xlim()
        time.sleep(0.3)
        self.tick()
        self.assertEqual(panel.ax.get_xlim(), frozen)
        p._toggle_pause()
        self.assertTrue(p._following)

    def test_hover_readout(self):
        p = self.page
        panel = p.panels["pt"]
        self.tick_sensor(self.pt)
        self.feed(12)
        self.tick()
        t, v = panel.lines[self.pt].get_data()
        i = len(t) // 2
        px, py = panel.ax.transData.transform((t[i], v[i]))
        panel.canvas.callbacks.process("motion_notify_event",
                                       MouseEvent("motion_notify_event", panel.canvas, px + 2, py + 1))
        self.assertTrue(panel.annot.get_visible())
        self.assertIn(self.pt, panel.annot.get_text())
        panel.canvas.callbacks.process("motion_notify_event",
                                       MouseEvent("motion_notify_event", panel.canvas, 1, 1))
        self.assertFalse(panel.annot.get_visible())

    def test_dense_window_is_decimated_but_keeps_peaks(self):
        p = self.page
        panel = p.panels["pt"]
        self.tick_sensor(self.pt)
        t_end = now()
        for i in range(60000):                        # 10 minutes at 100 Hz, one spike
            v = 1000.0 if i == 30000 else 10.0
            self.ctl.signals.sensor_updated.emit(self.pt, v, t_end - 600 + i / 100)
        p.window_combo.setCurrentIndex(4)             # All
        self.tick()
        t, v = panel.lines[self.pt].get_data()
        self.assertLessEqual(len(t), 3100)
        self.assertEqual(v.max(), 1000.0)

    # -- command log -----------------------------------------------------------------------
    def test_command_log_records_commands(self):
        p = self.page
        t = now()
        self.ctl.signals.command_sent.emit(self.valve, 1.0, t)
        self.ctl.signals.command_sent.emit(self.valve, 0.0, t + 2.0)
        tbl = p.cmd_panel.table
        self.assertEqual(tbl.rowCount(), 2)
        self.assertIn("OPEN", tbl.item(0, 2).text())
        self.assertIn(self.valve.strip(), tbl.item(0, 2).text())
        self.assertIn("CLOSE", tbl.item(1, 2).text())
        self.assertAlmostEqual(float(tbl.item(1, 1).text()) - float(tbl.item(0, 1).text()), 2.0, places=2)

    def test_real_controller_emits_command_signal(self):
        got = []
        self.ctl.signals.command_sent.connect(lambda n, v, t: got.append((n, v)))
        self.ctl.ethernet_client.send_valve_command = lambda *a, **k: None
        self.ctl._drive_valve(self.valve, True, force=True)
        self.ctl.pending_valve_commands.clear()
        self.assertIn((self.valve, 1.0), got)
        self.assertGreaterEqual(self.page.cmd_panel.table.rowCount(), 1)

    def test_clear_data_clears_plots_and_log(self):
        p = self.page
        self.tick_sensor(self.pt)
        self.feed(3)
        self.ctl.signals.command_sent.emit(self.valve, 1.0, now())
        p.clear_data()
        self.assertIsNone(p._t0)
        self.assertEqual(len(p._series[self.pt].ts), 0)
        self.assertEqual(p.cmd_panel.table.rowCount(), 0)

    def test_dark_mode_toggle(self):
        p = self.page
        self.tick_sensor(self.pt)
        self.feed(3)
        p.set_dark_mode(False)
        p.set_dark_mode(True)
        self.assertIn(self.pt, p.panels["pt"].lines)


if __name__ == "__main__":
    unittest.main(verbosity=2)
