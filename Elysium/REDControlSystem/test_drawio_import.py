"""Tests for the draw.io importer (DRAWIO_IMPORT.py), on a small inline diagram.   python test_drawio_import.py

Each case is something that went wrong on the real Elysium 2.0 P&ID."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from DRAWIO_IMPORT import import_drawio                                  # noqa: E402

VALVE = "shape=mxgraph.pid2valves.valve;valveType=gate;"
DIAGRAM = f"""<mxfile><diagram name="P1"><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>

<object label="" _01_Description="Part of the K-bottle" id="kvalve">
  <mxCell style="{VALVE}actuator=man;rotation=-90;" vertex="1" parent="1"><mxGeometry x="100" y="100" width="40" height="40" as="geometry"/></mxCell></object>

<object label="" _01_Description="3/4 NPT throttling V-Port Ball Valve" _02_Valve_Description="3/4 Ball Valve" id="tv">
  <mxCell style="group" vertex="1" connectable="0" parent="1"><mxGeometry x="300" y="100" width="40" height="40" as="geometry"/></mxCell></object>

<object label="" _01_Decsription="Double Acting Ball Valve" _02_Valve_Description="Swagelok 3 Piece Ball Valve" _06_Solenoid_Description="5/2 Solenoid Valve" id="mov">
  <mxCell style="group" vertex="1" connectable="0" parent="1"><mxGeometry x="500" y="100" width="40" height="40" as="geometry"/></mxCell></object>
<mxCell id="mov_txt" value="MOV" style="text;html=1;" vertex="1" parent="1"><mxGeometry x="545" y="110" width="40" height="14" as="geometry"/></mxCell>

<object label="" _01_Decsription="1' Long 1/4 JIC Hose" id="hose">
  <mxCell style="group" vertex="1" connectable="0" parent="1"><mxGeometry x="100" y="300" width="40" height="20" as="geometry"/></mxCell></object>

<mxCell id="tank" value="" style="shape=mxgraph.pid.vessels.tank;" vertex="1" parent="1"><mxGeometry x="300" y="300" width="80" height="160" as="geometry"/></mxCell>
<mxCell id="tank_txt" value="NT-1101 GN2" style="text;html=1;" vertex="1" parent="1"><mxGeometry x="300" y="340" width="80" height="40" as="geometry"/></mxCell>

<mxCell id="gauge" value="" style="shape=sumEllipse;" vertex="1" parent="1"><mxGeometry x="500" y="300" width="20" height="20" as="geometry"/></mxCell>
<mxCell id="reducer" value="" style="shape=mxgraph.pid.piping.concentric_reducer;" vertex="1" parent="1"><mxGeometry x="540" y="300" width="20" height="20" as="geometry"/></mxCell>
<mxCell id="gauge_txt" value="NPG-1101" style="text;html=1;" vertex="1" parent="1"><mxGeometry x="525" y="300" width="30" height="14" as="geometry"/></mxCell>

<object label="" id="vent"><mxCell style="group;rotation=-90;" vertex="1" connectable="0" parent="1"><mxGeometry x="700" y="100" width="20" height="20" as="geometry"/></mxCell></object>
<mxCell id="v1" style="endArrow=none;dashed=1;" edge="1" parent="vent"><mxGeometry relative="1" as="geometry"><mxPoint x="10" y="20" as="sourcePoint"/><mxPoint x="10" as="targetPoint"/></mxGeometry></mxCell>
<mxCell id="v2" style="endArrow=none;dashed=1;" edge="1" parent="vent"><mxGeometry relative="1" as="geometry"><mxPoint x="10" y="20" as="sourcePoint"/><mxPoint as="targetPoint"/></mxGeometry></mxCell>
<mxCell id="v3" style="endArrow=none;dashed=1;" edge="1" parent="vent"><mxGeometry relative="1" as="geometry"><mxPoint x="10" y="20" as="sourcePoint"/><mxPoint x="20" as="targetPoint"/></mxGeometry></mxCell>

<mxCell id="pump" value="" style="shape=mxgraph.pid.pumps.centrifugal_pump_1;flipH=1;" vertex="1" parent="1"><mxGeometry x="700" y="300" width="40" height="40" as="geometry"/></mxCell>
</root></mxGraphModel></diagram></mxfile>"""


class ImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.NamedTemporaryFile("w", suffix=".drawio", delete=False) as f:
            f.write(DIAGRAM)
        cls.project, cls.report = import_drawio(f.name)
        os.unlink(f.name)

    def comp(self, label_or_id):
        for c in self.project.components.values():
            if label_or_id in (c.label, c.id):
                return c
        self.fail(f"nothing called {label_or_id!r}: {[(c.id, c.label) for c in self.project.components.values()]}")

    def of_type(self, ctype):
        return [c for c in self.project.components.values() if c.type == ctype]

    def test_a_plain_valve_stays_a_valve_even_if_described_as_part_of_a_bottle(self):
        self.assertEqual(self.comp("V_1").type, "valve")             # used to become a tank
        self.assertEqual(len(self.of_type("tank")), 1)

    def test_throttling_valve_becomes_the_ep_throttle_type(self):
        self.assertEqual(self.of_type("ep_throttle_valve")[0].id, "EPTV_1")
        self.assertEqual(self.of_type("throttle_valve"), [])         # the plain type had no symbol

    def test_the_valve_body_decides_not_the_solenoid_pilot(self):
        mov = self.comp("MOV")
        self.assertEqual(mov.type, "ball_valve")                     # used to become a solenoid
        self.assertEqual(self.of_type("solenoid"), [])

    def test_a_typo_in_a_property_name_does_not_drop_the_part(self):
        self.assertEqual(len(self.of_type("flex_hose")), 1)          # "_01_Decsription" was ignored

    def test_the_fluid_after_a_tag_is_not_part_of_the_tag(self):
        tank = self.of_type("tank")[0]
        self.assertEqual(tank.label, "NT-1101")
        self.assertIn("GN2", tank.extras.get("notes", ""))

    def test_a_tag_goes_to_a_symbol_of_the_right_kind_not_just_the_nearest(self):
        self.assertEqual(self.of_type("pressure_gauge")[0].label, "NPG-1101")
        self.assertNotEqual(self.of_type("reducer")[0].label, "NPG-1101")   # the reducer is nearer

    def test_a_valve_name_like_MOV_labels_the_valve(self):
        self.assertEqual(self.comp("MOV").type, "ball_valve")
        self.assertEqual([c for c in self.of_type("label") if c.label == "MOV"], [])

    def test_a_group_of_dashed_lines_is_a_vent_component_not_loose_pipes(self):
        self.assertEqual(len(self.of_type("to_atmosphere")), 1)
        self.assertEqual(self.project.lines, [])

    def test_flipH_is_carried_over(self):
        self.assertTrue(self.of_type("pump")[0].flip)
        self.assertFalse(self.comp("V_1").flip)

    def test_every_component_can_be_traced_to_its_drawio_shape(self):
        for cid, c in self.project.components.items():
            if c.type != "label":
                self.assertIn(cid, self.report.sources)


if __name__ == "__main__":
    unittest.main(verbosity=2)
