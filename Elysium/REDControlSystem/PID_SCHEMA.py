# PID_SCHEMA.py

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List

COMP_VALVE          = "valve"           # on/off solenoid or ball valve
COMP_THROTTLE_VALVE = "throttle_valve"  # proportional / globe valve
COMP_PRESSURE       = "pressure"        # pressure transducer
COMP_TEMPERATURE    = "temperature"     # thermocouple
COMP_LOAD_CELL      = "load_cell"       # load cell (force sensor)
COMP_TANK           = "tank"            # propellant tank or pressurant bottle
COMP_INJECTOR       = "injector"        # engine injector / combustion chamber
COMP_ORIFICE        = "orifice"         # fixed flow restriction
COMP_FILTER         = "filter"          # inline filter
COMP_REGULATOR      = "regulator"       # pressure regulator
COMP_CHECK_VALVE    = "check_valve"     # check / non-return valve
COMP_RELIEF_VALVE   = "relief_valve"    # safety / relief valve
COMP_LABEL          = "label"           # free text annotation
COMP_JUNCTION       = "junction"        # pipe tee / junction node
COMP_BALL_VALVE     = "ball_valve"
COMP_PSV            = "psv"             # Pressure Safety Valve
COMP_PRV            = "prv"             # Pressure Relief Valve
COMP_SOLENOID       = "solenoid"
COMP_GLOBE_VALVE    = "globe_valve"
COMP_REDUCER        = "reducer"
COMP_IGNITER        = "igniter" 


COMPONENT_TYPES = [
    COMP_VALVE, COMP_THROTTLE_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_TANK, COMP_INJECTOR, COMP_ORIFICE, COMP_FILTER,
    COMP_REGULATOR, COMP_CHECK_VALVE, COMP_RELIEF_VALVE, COMP_LABEL, COMP_JUNCTION, COMP_BALL_VALVE,
    COMP_PSV, COMP_PRV, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_REDUCER, COMP_IGNITER,
]

FLUID_OXIDIZER   = "oxidizer"    # blue
FLUID_FUEL       = "fuel"        # red
FLUID_PRESSURANT = "pressurant"  # yellow
FLUID_PURGE      = "purge"       # green
FLUID_GENERIC    = "generic"     # grey

FLUID_COLORS = {
    FLUID_OXIDIZER:   "#2979ff",
    FLUID_FUEL:       "#f44336",
    FLUID_PRESSURANT: "#ffd600",
    FLUID_PURGE:      "#00c853",
    FLUID_GENERIC:    "#888888",
}


@dataclass
class HardwareBinding:
    relay:   Optional[int] = None   # relay / digital-out index
    adc:     Optional[int] = None   # ADC channel index
    globe:   Optional[int] = None   # globe valve stepper index

    def to_dict(self):
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(d: dict) -> "HardwareBinding":
        return HardwareBinding(
            relay = d.get("relay"),
            adc   = d.get("adc"),
            globe = d.get("globe"),
        )


@dataclass
class Component:
    id:       str                              # unique, e.g. "valve_1"
    type:     str                              # one of COMPONENT_TYPES
    label:    str             = ""             # human-readable display name
    hardware: HardwareBinding = field(default_factory=HardwareBinding)
    extras:   dict            = field(default_factory=dict)
    rotation: int             = 0
    hide_lbl: bool            = False

    def to_dict(self):
        return {
            "id":       self.id,
            "type":     self.type,
            "label":    self.label,
            "hardware": self.hardware.to_dict(),
            "extras":   self.extras,
            "rotation": self.rotation,
            "hide_lbl": self.hide_lbl,
        }

    @staticmethod
    def from_dict(d: dict) -> "Component":
        return Component(
            id       = d["id"],
            type     = d["type"],
            label    = d.get("label", d["id"]),
            hardware = HardwareBinding.from_dict(d.get("hardware", {})),
            extras   = d.get("extras", {}),
            rotation = d.get("rotation", 0),
            hide_lbl = d.get("hide_lbl", False),
        )


@dataclass
class Connection:
    from_id: str
    to_id:   str
    fluid:   str = FLUID_GENERIC

    def to_dict(self):
        return {"from": self.from_id, "to": self.to_id, "fluid": self.fluid}

    @staticmethod
    def from_dict(d: dict) -> "Connection":
        return Connection(
            from_id = d["from"],
            to_id   = d["to"],
            fluid   = d.get("fluid", FLUID_GENERIC),
        )


@dataclass
class LayoutPoint:
    x: float
    y: float

    def to_dict(self):
        return {"x": self.x, "y": self.y}

    @staticmethod
    def from_dict(d: dict) -> "LayoutPoint":
        return LayoutPoint(x=float(d["x"]), y=float(d["y"]))


@dataclass
class PipeLine:
    id:       str
    points:   list                                          # list of LayoutPoint
    fluid:    str           = FLUID_GENERIC
    connects: list          = field(default_factory=list)   # [from_id, to_id]
    dotted:   bool          = False

    def to_dict(self):
        return {
            "id":       self.id,
            "points":   [p.to_dict() for p in self.points],
            "fluid":    self.fluid,
            "connects": self.connects,
            "dotted":   self.dotted,
        }

    @staticmethod
    def from_dict(d: dict) -> "PipeLine":
        return PipeLine(
            id       = d["id"],
            points   = [LayoutPoint.from_dict(p) for p in d["points"]],
            fluid    = d.get("fluid", FLUID_GENERIC),
            connects = d.get("connects", []),
            dotted   = d.get("dotted", False)
        )


@dataclass
class SystemParameters:
    tank_volume: float = 0.0   # litres (optional, informational)
    notes:       str   = ""

    # System-wide pressure backstop, independent of per-sensor thresholds:
    # a warning fires on any PT at/above system_meop; an abort fires at
    # 0.95 * system_mawp. None means "not configured / disabled".
    system_mawp: Optional[float] = None
    system_meop: Optional[float] = None

    # Optional custom message templates for the system-limit warning/abort.
    # {SENSOR} tokens are substituted with that sensor's live value; special
    # tokens {value}/{threshold}/{limit} are also available. Blank = default
    # wording (built in GUIController).
    system_mawp_message: str = ""
    system_meop_message: str = ""

    # Length (seconds) of the pre-ignition terminal-count hold used by
    # show_fire_sequence_dialog().
    terminal_count_s: float = 10.0

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "SystemParameters":
        def _f(key):
            return float(d[key]) if d.get(key) is not None else None
        return SystemParameters(
            tank_volume          = float(d.get("tank_volume", 0)),
            notes                = d.get("notes", ""),
            system_mawp          = _f("system_mawp"),
            system_meop          = _f("system_meop"),
            system_mawp_message  = d.get("system_mawp_message", ""),
            system_meop_message  = d.get("system_meop_message", ""),
            terminal_count_s     = float(d.get("terminal_count_s", 10.0)),
        )


# ---------------------------------------------------------------------------
# Sensor threshold bands - stored inside Component.extras["thresholds"]
# ---------------------------------------------------------------------------
# Each field is Optional[float].  None means "not configured / disabled".
#
# Band hierarchy (highest → lowest severity):
#   above_mawp   → typically "abort"
#   above_meop   → typically "warn" or "open_valve"
#   above_relief → typically "open_valve" (auto-vent via a named valve)
#
# For open_valve actions:
#   target_valve      – valve component ID to open
#   close_valve_below – re-close that valve once the value drops below this
#
@dataclass
class SensorThresholds:
    # ---- absolute limits -------------------------------------------------
    mawp:          Optional[float] = None   # abort threshold (hard limit)
    meop:          Optional[float] = None   # expected operating max
    relief:        Optional[float] = None   # opens a relief / vent valve

    # ---- actions per band ------------------------------------------------
    mawp_action:    str = "abort"       # "abort" | "warn" | "open_valve"
    meop_action:    str = "warn"
    relief_action:  str = "open_valve"  # almost always open_valve

    # ---- open_valve details (used by relief_action / meop_action) --------
    target_valve:       str            = ""    # component ID of the valve to open
    close_valve_below:  Optional[float]= None  # hysteresis close threshold

    # ---- soak time (ms) before triggering - per-sensor ------------------
    soak_ms: int = 0

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items()}

    @staticmethod
    def from_dict(d: dict) -> "SensorThresholds":
        def _f(key): return float(d[key]) if d.get(key) is not None else None
        return SensorThresholds(
            mawp              = _f("mawp"),
            meop              = _f("meop"),
            relief            = _f("relief"),
            mawp_action       = d.get("mawp_action",   "abort"),
            meop_action       = d.get("meop_action",   "warn"),
            relief_action     = d.get("relief_action", "open_valve"),
            target_valve      = d.get("target_valve",  ""),
            close_valve_below = _f("close_valve_below"),
            soak_ms           = int(d.get("soak_ms", 0)),
        )


# ---------------------------------------------------------------------------
# Abort / logic rules - stored in PIDProject.rules
# ---------------------------------------------------------------------------
# condition_type choices:
#   "above_mawp"    – sensor value > SensorThresholds.mawp
#   "below_mawp"    – sensor value < SensorThresholds.mawp   (for load cells etc.)
#   "above_meop"    – sensor value > SensorThresholds.meop
#   "above_relief"  – sensor value > SensorThresholds.relief
#   "expression"    – arbitrary Python-safe expression evaluated against
#                     current_sensor_values dict  (e.g. "P8 > P7")
#
# action choices:
#   "abort"         – triggers full system abort
#   "warn"          – emits a UI warning, no valve change
#   "open_valve"    – opens target_valve; auto-closes when close_valve_below is met
#
@dataclass
class AbortRule:
    id:               str
    condition_type:   str           # see above
    action:           str = "abort" # "abort" | "warn" | "open_valve"
    enabled:          bool = True

    # For sensor-threshold rules - which sensor this rule watches
    sensor_id:        str = ""      # Component id of the sensor (or hw_id label)

    # For expression-based rules (condition_type == "expression")
    expression:       str = ""      # e.g. "P8 > P7"
    description:      str = ""      # human-readable label shown in UI

    # Custom abort/warn message template, e.g. "P5 ({P5}) > P3 ({P3}) for
    # {soak_ms}ms". {TOKEN} is replaced with that sensor's live value if TOKEN
    # matches a known sensor name, or with {soak_ms}/{expression}/{description}
    # for those special keywords. Blank = fall back to description/expression.
    message_template: str = ""

    # For open_valve action
    target_valve:       str            = ""    # valve component/hw id to open
    close_valve_below:  Optional[float]= None  # re-close threshold

    # Soak time (ms) - violation must persist this long before firing
    soak_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "condition_type":   self.condition_type,
            "action":           self.action,
            "enabled":          self.enabled,
            "sensor_id":        self.sensor_id,
            "expression":       self.expression,
            "description":      self.description,
            "message_template": self.message_template,
            "target_valve":     self.target_valve,
            "close_valve_below": self.close_valve_below,
            "soak_ms":          self.soak_ms,
        }

    @staticmethod
    def from_dict(d: dict) -> "AbortRule":
        cvb = d.get("close_valve_below")
        return AbortRule(
            id               = d["id"],
            condition_type   = d.get("condition_type", d.get("condition", "expression")),
            action           = d.get("action", "abort"),
            message_template = d.get("message_template", ""),
            enabled          = d.get("enabled", True),
            sensor_id        = d.get("sensor_id", ""),
            expression       = d.get("expression", d.get("condition", "")),
            description      = d.get("description", ""),
            target_valve     = d.get("target_valve", ""),
            close_valve_below= float(cvb) if cvb is not None else None,
            soak_ms          = int(d.get("soak_ms", 0)),
        )


@dataclass
class SequenceStep:
    name:        str         = "State"
    time_offset: float       = 0.0                          # seconds from sequence auto-start
    open_valves: List[str]   = field(default_factory=list)  # component IDs that are OPEN in this step
    # Marks this step as the terminal-count hold. show_fire_sequence_dialog()
    # requires at least one step with this flag before it will run.
    is_terminal_count: bool  = False

    def to_dict(self):
        return {
            "name":              self.name,
            "time_offset":       self.time_offset,
            "open_valves":       self.open_valves,
            "is_terminal_count": self.is_terminal_count,
        }

    @staticmethod
    def from_dict(d: dict) -> "SequenceStep":
        return SequenceStep(
            name              = d.get("name", d.get("label", "State")),
            time_offset       = float(d.get("time_offset", d.get("time", 0.0))),
            open_valves       = d.get("open_valves", []),
            is_terminal_count = bool(d.get("is_terminal_count", False)),
        )


# ---------------------------------------------------------------------------
# Calculated performance channel - Mdot / Thrust user-defined formulas
# ---------------------------------------------------------------------------
# Each channel is a Python-safe expression evaluated against live sensor names
# (hw_id/label, e.g. P1, P8, TC1, LC1) plus user-defined constants and the
# helpers sqrt / abs / min / max / pow / G0 (32.174 ft/s^2).
#
# role choices (string):
#   "mdot_fuel"  – summed into Total Mdot
#   "mdot_ox"    – summed into Total Mdot
#   "thrust"     – summed and used with Total Mdot to compute Isp
#   "custom"     – displayed but not aggregated
#
@dataclass
class CalcChannel:
    id:         str
    label:      str   = "Channel"
    role:       str   = "custom"      # see role choices above
    unit:       str   = ""
    expression: str   = ""
    constants:  dict  = field(default_factory=dict)
    enabled:    bool  = True

    def to_dict(self) -> dict:
        return {
            "id":         self.id,
            "label":      self.label,
            "role":       self.role,
            "unit":       self.unit,
            "expression": self.expression,
            "constants":  self.constants,
            "enabled":    self.enabled,
        }

    @staticmethod
    def from_dict(d: dict) -> "CalcChannel":
        return CalcChannel(
            id         = d["id"],
            label      = d.get("label",      "Channel"),
            role       = d.get("role",       "custom"),
            unit       = d.get("unit",       ""),
            expression = d.get("expression", ""),
            constants  = d.get("constants",  {}),
            enabled    = bool(d.get("enabled", True)),
        )


# ---------------------------------------------------------------------------
# Named sequence - wraps a list of SequenceSteps with an id and display name
# so multiple independent fire sequences can coexist in one project.
# ---------------------------------------------------------------------------
@dataclass
class NamedSequence:
    id:    str
    name:  str              = "Default"
    steps: List[SequenceStep] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id":    self.id,
            "name":  self.name,
            "steps": [s.to_dict() for s in self.steps],
        }

    @staticmethod
    def from_dict(d: dict) -> "NamedSequence":
        return NamedSequence(
            id    = d["id"],
            name  = d.get("name", "Default"),
            steps = [SequenceStep.from_dict(s) for s in d.get("steps", [])],
        )


class PIDProject:

    VERSION = "1.0"

    def __init__(self, name: str = "Untitled Project"):
        self.name:               str              = name
        self.version:            str              = self.VERSION
        self.components:         dict             = {}    # id -> Component
        self.connections:        list             = []    # list[Connection]
        self.layout:             dict             = {}    # id -> LayoutPoint
        self.lines:              list             = []    # list[PipeLine]
        self.parameters:         SystemParameters = SystemParameters()
        self.rules:              list             = []    # list[AbortRule]

        # --- Legacy flat sequence list (kept for backward-compat read paths) ---
        self.sequence:           list             = []    # list[SequenceStep]

        # --- Named sequences (new multi-sequence support) ---------------------
        self.sequences:          list             = []    # list[NamedSequence]
        self.active_sequence_id: str              = ""

        # --- Calculated performance channels ----------------------------------
        self.calc_channels:      list             = []    # list[CalcChannel]

    def add_component(self, comp: Component, x: float = 0, y: float = 0):
        self.components[comp.id] = comp
        self.layout[comp.id] = LayoutPoint(x, y)

    def move_component(self, comp_id: str, x: float, y: float):
        self.layout[comp_id] = LayoutPoint(x, y)

    def remove_component(self, comp_id: str):
        self.components.pop(comp_id, None)
        self.layout.pop(comp_id, None)
        self.connections = [c for c in self.connections
                            if c.from_id != comp_id and c.to_id != comp_id]
        self.lines = [l for l in self.lines if comp_id not in l.connects]

    def add_connection(self, from_id: str, to_id: str, fluid: str = FLUID_GENERIC):
        for c in self.connections:
            if c.from_id == from_id and c.to_id == to_id:
                return
        self.connections.append(Connection(from_id, to_id, fluid))

    def add_line(self, line: PipeLine):
        existing_ids = {l.id for l in self.lines}
        if not line.id or line.id in existing_ids:
            base = "line"
            next_idx = 0
            while f"{base}_{next_idx}" in existing_ids:
                next_idx += 1
            line.id = f"{base}_{next_idx}"
        self.lines.append(line)

    def remove_line(self, line_id: str):
        self.lines = [l for l in self.lines if l.id != line_id]

    def add_abort_rule(self, rule: AbortRule):
        self.rules.append(rule)

    def add_sequence_step(self, step: SequenceStep):
        """Append to the legacy flat sequence list (backward-compat)."""
        self.sequence.append(step)
        self.sequence.sort(key=lambda s: getattr(s, "time_offset", getattr(s, "time", 0.0)))

    def add_sequence(self, name: str) -> "NamedSequence":
        """Create and register a new named sequence, returning it."""
        import uuid
        seq = NamedSequence(id=f"seq_{uuid.uuid4().hex[:8]}", name=name)
        self.sequences.append(seq)
        if not self.active_sequence_id:
            self.active_sequence_id = seq.id
        return seq

    def remove_sequence(self, seq_id: str):
        """Remove a named sequence by id. Does not remove the last one."""
        self.sequences = [s for s in self.sequences if s.id != seq_id]
        if self.active_sequence_id == seq_id:
            self.active_sequence_id = self.sequences[0].id if self.sequences else ""

    def get_active_sequence(self) -> "NamedSequence | None":
        """Return the NamedSequence matching active_sequence_id, or None if
        it isn't set / doesn't match anything (e.g. a stale id left over
        after the active sequence was removed)."""
        return next((s for s in self.sequences if s.id == self.active_sequence_id), None)

    def valve_ids(self) -> list:
        return [cid for cid, c in self.components.items()
                if c.type in (COMP_VALVE, COMP_THROTTLE_VALVE)]

    def sensor_ids(self) -> list:
        return [cid for cid, c in self.components.items()
                if c.type in (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL)]

    def to_dict(self) -> dict:
        return {
            "name":               self.name,
            "version":            self.version,
            "components":         [c.to_dict() for c in self.components.values()],
            "connections":        [c.to_dict() for c in self.connections],
            "layout":             {cid: pt.to_dict() for cid, pt in self.layout.items()},
            "lines":              [l.to_dict() for l in self.lines],
            "parameters":         self.parameters.to_dict(),
            "rules":              [r.to_dict() for r in self.rules],
            # Legacy flat sequence kept for backward-compat readers
            "sequence":           [s.to_dict() for s in self.sequence],
            # New multi-sequence support
            "sequences":          [s.to_dict() for s in self.sequences],
            "active_sequence_id": self.active_sequence_id,
            # Calculated performance channels
            "calc_channels":      [c.to_dict() for c in self.calc_channels],
        }

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load(path: str) -> "PIDProject":
        try:
            with open(path, encoding="utf-8-sig") as f:
                d = json.load(f)
        except UnicodeDecodeError:
            with open(path, encoding="latin-1") as f:
                d = json.load(f)
        proj = PIDProject(name=d.get("name", os.path.basename(path)))
        proj.version = d.get("version", "1.0")
 
        for cd in d.get("components", []):
            c = Component.from_dict(cd)
            proj.components[c.id] = c
 
        for conn in d.get("connections", []):
            proj.connections.append(Connection.from_dict(conn))
 
        for cid, pt in d.get("layout", {}).items():
            proj.layout[cid] = LayoutPoint.from_dict(pt)
 
        for ld in d.get("lines", []):
            proj.lines.append(PipeLine.from_dict(ld))

        seen_ids = set()
        for line in proj.lines:
            if line.id not in seen_ids:
                seen_ids.add(line.id)
                continue
            next_idx = 0
            while f"line_{next_idx}" in seen_ids:
                next_idx += 1
            line.id = f"line_{next_idx}"
            seen_ids.add(line.id)
 
        proj.parameters = SystemParameters.from_dict(d.get("parameters", {}))
 
        for rd in d.get("rules", []):
            proj.rules.append(AbortRule.from_dict(rd))
 
        # Legacy flat sequence list
        for sd in d.get("sequence", []):
            proj.sequence.append(SequenceStep.from_dict(sd))

        # Named sequences (new format)
        for seqd in d.get("sequences", []):
            proj.sequences.append(NamedSequence.from_dict(seqd))

        # If the file has no named sequences yet but has a legacy flat sequence,
        # promote it to a single named sequence called "Default" for continuity.
        if not proj.sequences and proj.sequence:
            default_seq = NamedSequence(
                id    = "seq_default",
                name  = "Default",
                steps = list(proj.sequence),
            )
            proj.sequences.append(default_seq)

        proj.active_sequence_id = d.get("active_sequence_id", "")
        # Fall back to first sequence if active_sequence_id is missing OR
        # stale (doesn't match any loaded sequence - e.g. that sequence was
        # since deleted).
        if proj.get_active_sequence() is None and proj.sequences:
            proj.active_sequence_id = proj.sequences[0].id

        # Calculated performance channels
        for cd in d.get("calc_channels", []):
            proj.calc_channels.append(CalcChannel.from_dict(cd))

        return proj
 
    @staticmethod
    def new_empty(name: str = "New Project") -> "PIDProject":
        return PIDProject(name=name)