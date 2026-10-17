"""Headless tests for the P&ID editor canvas: dragging pipe handles and selecting text labels.
   python test_pipe_edit.py"""
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtCore import QEvent, QPoint, QPointF, Qt                 # noqa: E402
from PyQt5.QtGui import QMouseEvent                                  # noqa: E402
from PyQt5.QtTest import QTest                                       # noqa: E402
from PyQt5.QtWidgets import QApplication                             # noqa: E402

from PID_EDITOR import PIDEditorWindow                               # noqa: E402
from PID_RENDERER import world_rect                                  # noqa: E402
from PID_SCHEMA import (COMP_LABEL, COMP_TANK, COMP_THROTTLE_VALVE, COMP_CHECK_VALVE, Component, LayoutPoint,   # noqa: E402
                        PIDProject, PipeLine)

app = QApplication.instance() or QApplication(sys.argv)


def axis_aligned(pts):
    return all(abs(a.x - b.x) < 0.5 or abs(a.y - b.y) < 0.5 for a, b in zip(pts, pts[1:]))


class PipeEditTest(unittest.TestCase):
    def setUp(self):
        self.proj = PIDProject()
        self.proj.add_line(PipeLine(id="straight", points=[LayoutPoint(100, 200), LayoutPoint(300, 200)]))
        self.proj.add_line(PipeLine(id="elbow", points=[LayoutPoint(100, 400), LayoutPoint(300, 400),
                                                        LayoutPoint(300, 500)]))
        self.proj.add_component(Component(id="TK", type=COMP_TANK, label="TK"), 600, 300)
        self.proj.add_component(Component(id="LBL", type=COMP_LABEL, label="1500 psig  note"), 600, 270)
        self.ed = PIDEditorWindow()
        self.ed.resize(1500, 900)
        self.ed.show()
        self.ed._project = self.proj
        self.cv = self.ed.canvas
        self.cv.set_project(self.proj)
        self.cv.fit_view()
        app.processEvents()

    def scr(self, wx, wy):
        return QPoint(round((wx + self.cv._pan.x()) * self.cv._zoom),
                      round((wy + self.cv._pan.y()) * self.cv._zoom))

    def drag(self, frm, to, mods=Qt.NoModifier):
        QTest.mousePress(self.cv, Qt.LeftButton, mods, self.scr(*frm))
        QApplication.sendEvent(self.cv, QMouseEvent(QEvent.MouseMove, QPointF(self.scr(*to)),
                                                    Qt.NoButton, Qt.LeftButton, mods))
        QTest.mouseRelease(self.cv, Qt.LeftButton, mods, self.scr(*to))
        app.processEvents()

    def select(self, line):
        self.cv._selected_lines = {line.id}
        self.cv.update()
        app.processEvents()

    def pipe(self, n_pts, horizontal=None):
        return next(l for l in self.proj.lines if len(l.points) == n_pts)

    def test_dragging_an_end_lengthens_the_pipe_without_going_off_axis(self):
        line = self.pipe(2, horizontal=True)
        a, b = line.points
        self.select(line)
        sign = 1 if b.x > a.x else -1
        self.drag((b.x, b.y), (b.x + sign * 60, b.y + 30))          # also 30 sideways
        self.assertEqual((a.x, a.y), (line.points[0].x, line.points[0].y))
        self.assertAlmostEqual(line.points[1].y, a.y, delta=0.5)    # stays horizontal
        self.assertGreaterEqual(abs(line.points[1].x - line.points[0].x), 50)

    def test_shift_drag_moves_an_end_freely(self):
        line = self.pipe(2, horizontal=True)
        a, b = line.points
        self.select(line)
        self.drag((b.x, b.y), (b.x, b.y + 40), Qt.ShiftModifier)
        self.assertGreater(abs(line.points[1].y - a.y), 20)

    def test_segment_handle_slides_the_whole_segment_sideways(self):
        line = self.pipe(2, horizontal=True)
        a, b = line.points
        self.select(line)
        y0 = a.y
        self.drag(((a.x + b.x) / 2, y0), ((a.x + b.x) / 2 + 25, y0 + 40))
        self.assertAlmostEqual(line.points[0].y, line.points[1].y, delta=0.5)
        self.assertGreater(abs(line.points[0].y - y0), 20)
        self.assertAlmostEqual(line.points[0].x, a.x, delta=0.5)    # only moved sideways

    def test_dragging_a_corner_keeps_the_pipe_orthogonal(self):
        line = self.pipe(3)
        c = line.points[1]
        self.select(line)
        self.drag((c.x, c.y), (c.x + 40, c.y + 30))
        self.assertTrue(axis_aligned(line.points))

    def test_dragging_without_a_selected_pipe_does_not_edit_it(self):
        line = self.pipe(2, horizontal=True)
        before = [(p.x, p.y) for p in line.points]
        self.cv._selected_lines.clear()
        self.drag((line.points[1].x, line.points[1].y), (line.points[1].x + 60, line.points[1].y))
        self.assertEqual(before, [(p.x, p.y) for p in line.points])

    # -- text labels --------------------------------------------------------------
    def label_center(self):
        c = self.proj.components["LBL"]
        return world_rect(self.proj.layout["LBL"], c.type, c, self.cv._zoom).center()

    def test_clicking_a_labels_text_selects_it_even_over_another_component(self):
        ctr = self.label_center()
        self.assertEqual(self.cv._comp_at(ctr), "LBL")      # text sits on top of the tank
        QTest.mouseClick(self.cv, Qt.LeftButton, Qt.NoModifier, self.scr(ctr.x(), ctr.y()))
        self.assertEqual(self.cv._selected_comps, {"LBL"})
        self.assertEqual(self.ed.prop_panel._comp_id, "LBL")        # so its text can be edited

    def test_a_label_can_be_dragged(self):
        ctr = self.label_center()
        x0, y0 = self.proj.layout["LBL"].x, self.proj.layout["LBL"].y
        self.drag((ctr.x(), ctr.y()), (ctr.x() + 40, ctr.y() + 20))
        self.assertEqual((self.proj.layout["LBL"].x - x0, self.proj.layout["LBL"].y - y0), (40, 20))

    # -- component name labels ------------------------------------------------------
    def test_a_selected_components_name_label_can_be_moved_and_reset(self):
        from PID_RENDERER import Renderer
        self.proj.add_component(Component(id="CV", type=COMP_CHECK_VALVE, label="NRV-1"), 300, 300)
        self.cv._selected_comps = set()
        ctr = Renderer.label_rect(self.proj.layout["CV"], self.proj.components["CV"], self.cv._zoom).center()
        self.drag((ctr.x(), ctr.y()), (ctr.x() + 30, ctr.y() + 10))
        self.assertNotIn("label_offset", self.proj.components["CV"].extras)    # locked until selected
        self.cv._selected_comps = {"CV"}
        self.drag((ctr.x(), ctr.y()), (ctr.x() + 30, ctr.y() + 10))
        self.assertEqual(self.proj.components["CV"].extras["label_offset"], [30.0, 10.0])
        self.assertEqual((self.proj.layout["CV"].x, self.proj.layout["CV"].y), (300, 300))   # symbol stays put
        ctr = Renderer.label_rect(self.proj.layout["CV"], self.proj.components["CV"], self.cv._zoom).center()
        p = self.scr(ctr.x(), ctr.y())
        QTest.mouseDClick(self.cv, Qt.LeftButton, Qt.NoModifier, p)
        self.assertNotIn("label_offset", self.proj.components["CV"].extras)

    # -- symbols ------------------------------------------------------------------
    def test_plain_throttle_valve_type_is_drawn(self):
        """The importer used to produce this type, which had no drawing code (it vanished)."""
        from PyQt5.QtGui import QImage, QPainter
        from PID_RENDERER import Renderer
        comp = Component(id="TV", type=COMP_THROTTLE_VALVE, label="TV")
        img = QImage(200, 200, QImage.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        Renderer.draw(p, comp, LayoutPoint(100, 120), show_label=False)
        p.end()
        drawn = sum(1 for x in range(200) for y in range(200) if img.pixelColor(x, y).alpha() > 0)
        self.assertGreater(drawn, 100)

    # -- flip ---------------------------------------------------------------------
    @staticmethod
    def _alpha(comp):
        import numpy as np
        from PyQt5.QtGui import QImage, QPainter
        from PID_RENDERER import Renderer
        img = QImage(160, 160, QImage.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        Renderer.draw(p, comp, LayoutPoint(80, 80), show_label=False)
        p.end()
        ptr = img.bits()
        ptr.setsize(img.byteCount())
        return np.frombuffer(ptr, np.uint8).reshape(160, 160, 4)[:, :, 3].astype(int)

    def test_flip_draws_the_left_right_mirror_image(self):
        import numpy as np
        comp = Component(id="CV", type=COMP_CHECK_VALVE, label="CV")
        plain = self._alpha(comp)
        comp.flip = True
        flipped = self._alpha(comp)
        mirror = plain[:, ::-1]
        self.assertFalse(np.array_equal(plain, flipped))
        self.assertLess(np.abs(mirror - flipped).sum(), 0.08 * flipped.sum())     # antialiasing only
        comp.rotation = 90                       # still a left-right mirror of the rotated symbol
        rotated_flipped = self._alpha(comp)
        comp.flip = False
        rotated = self._alpha(comp)
        self.assertLess(np.abs(rotated[:, ::-1] - rotated_flipped).sum(), 0.08 * rotated_flipped.sum())

    def test_flip_button_and_key_toggle_components_but_not_text_labels(self):
        self.proj.add_component(Component(id="CV", type=COMP_CHECK_VALVE, label="CV"), 100, 100)
        self.cv._selected_comps = {"CV", "LBL"}
        self.ed._flip_selected()
        self.assertTrue(self.proj.components["CV"].flip)
        self.assertFalse(self.proj.components["LBL"].flip)         # mirrored text would be unreadable
        QTest.keyClick(self.ed, Qt.Key_M)
        self.assertFalse(self.proj.components["CV"].flip)

    def test_flip_is_saved_and_reloaded(self):
        comp = Component(id="CV", type=COMP_CHECK_VALVE, label="CV", flip=True)
        self.proj.add_component(comp, 100, 100)
        again = PIDProject.from_dict(self.proj.to_dict())
        self.assertTrue(again.components["CV"].flip)
        self.assertFalse(again.components["LBL"].flip)


if __name__ == "__main__":
    unittest.main(verbosity=2)
