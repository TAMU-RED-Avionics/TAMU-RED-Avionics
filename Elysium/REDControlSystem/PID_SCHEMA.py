# PID_SCHEMA.py

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Optional, List

COMP_VALVE          = "valve"           # RED-001 3.3: Manual Valve
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
COMP_RELIEF_VALVE   = "relief_valve"    # RED-001 3.3: Relief Valve (RV)
COMP_LABEL          = "label"           # free text annotation
COMP_JUNCTION       = "junction"        # pipe tee / junction node
COMP_BALL_VALVE     = "ball_valve"
COMP_PSV            = "psv"             # Pressure Safety Valve
COMP_PRV            = "prv"             # Pressure Relief Valve
COMP_SOLENOID       = "solenoid"        # RED-001 3.3: Solenoid Valve
COMP_GLOBE_VALVE    = "globe_valve"
COMP_REDUCER        = "reducer"         # RED-001 3.3: Reducer
COMP_IGNITER        = "igniter"

# --- RED-001 3.3 standardized P&ID parts -----------------------------------
COMP_ACTUATED_VALVE     = "actuated_valve"      # Actuated Valve (no limit)
COMP_ACTUATED_VALVE_LS  = "actuated_valve_ls"   # Actuated Valve (with limit)
COMP_NEEDLE_VALVE       = "needle_valve"        # Needle Valve
COMP_THREE_WAY_VALVE    = "three_way_valve"     # 3-Way Valve
COMP_EP_THROTTLE_VALVE  = "ep_throttle_valve"   # Electro-Pneumatic Throttle Valve
COMP_BURST_DISK         = "burst_disk"          # Burst Disk (BD)
COMP_BULKHEAD           = "bulkhead"            # Bulkhead (BH)
COMP_QUICK_DISCONNECT   = "quick_disconnect"    # Quick Disconnect (QD)
COMP_CAP_PLUG           = "cap_plug"            # Cap/Plug
COMP_HAND_REGULATOR     = "hand_regulator"      # Hand Regulator (R)
COMP_DOME_REGULATOR     = "dome_regulator"      # Dome Regulator (R)
COMP_EP_CONVERTER       = "ep_converter"        # Electro-Pneumatic Converter
COMP_PUMP               = "pump"                # Pump (P)
COMP_PRESSURE_GAUGE     = "pressure_gauge"      # Pressure Gauge (PG)
COMP_DIFF_PRESSURE      = "diff_pressure"       # Differential Pressure Transducer (DP)
COMP_FLOW_METER         = "flow_meter"          # Flow Meter (FM)
COMP_TO_ATMOSPHERE      = "to_atmosphere"       # To Atmosphere vent
COMP_FLEX_HOSE          = "flex_hose"           # Flex Hose (H)
COMP_BELLOWS            = "bellows"             # Bellow (B)
COMP_HEAT_EXCHANGER     = "heat_exchanger"      # Heat Exchanger (HEX)
COMP_PANEL              = "panel"               # Panel / description container

# Types the operator can command through a hardware relay (Binding): used to build the
# controller's valve table, the live-view click popups and the Abort Config valve lists.
# Passive parts (check valves, PSV/PRV, hand regulators, ...) are deliberately not here.
COMMANDABLE_VALVE_TYPES = (
    COMP_VALVE, COMP_THROTTLE_VALVE, COMP_BALL_VALVE, COMP_GLOBE_VALVE,
    COMP_SOLENOID, COMP_IGNITER, COMP_ACTUATED_VALVE, COMP_ACTUATED_VALVE_LS,
    COMP_EP_THROTTLE_VALVE, COMP_THREE_WAY_VALVE, COMP_PUMP,
)


COMPONENT_TYPES = [
    COMP_VALVE, COMP_THROTTLE_VALVE, COMP_PRESSURE, COMP_TEMPERATURE,
    COMP_LOAD_CELL, COMP_TANK, COMP_INJECTOR, COMP_ORIFICE, COMP_FILTER,
    COMP_REGULATOR, COMP_CHECK_VALVE, COMP_RELIEF_VALVE, COMP_LABEL, COMP_JUNCTION, COMP_BALL_VALVE,
    COMP_PSV, COMP_PRV, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_REDUCER, COMP_IGNITER,
    COMP_ACTUATED_VALVE, COMP_ACTUATED_VALVE_LS, COMP_NEEDLE_VALVE, COMP_THREE_WAY_VALVE,
    COMP_EP_THROTTLE_VALVE, COMP_BURST_DISK, COMP_BULKHEAD, COMP_QUICK_DISCONNECT,
    COMP_CAP_PLUG, COMP_HAND_REGULATOR, COMP_DOME_REGULATOR, COMP_EP_CONVERTER,
    COMP_PUMP, COMP_PRESSURE_GAUGE, COMP_DIFF_PRESSURE, COMP_FLOW_METER,
    COMP_TO_ATMOSPHERE, COMP_FLEX_HOSE, COMP_BELLOWS, COMP_HEAT_EXCHANGER, COMP_PANEL,
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
    flip:     bool            = False          # mirrored left-right (as seen on screen), applied before rotation

    def to_dict(self):
        return {
            "id":       self.id,
            "type":     self.type,
            "label":    self.label,
            "hardware": self.hardware.to_dict(),
            "extras":   self.extras,
            "rotation": self.rotation,
            "hide_lbl": self.hide_lbl,
            "flip":     self.flip,
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
            flip     = d.get("flip", False),
        )


# ---------------------------------------------------------------------------
# Proportional actuator spec - stored in Component.extras["actuator"]
# ---------------------------------------------------------------------------
# Any valve-type component can carry this to become a *positioned* actuator
# (modulating valve, RC servo, ...) instead of a plain open/close relay. It
# describes only what the GUI needs: the commandable range, which position is
# "safe", and what "open" means for sequences/rules that only know open/closed.
# HOW the position is physically produced (4-20mA via a PWM->analog card, RC
# servo pulse, stepper...) is the firmware's business - the GUI just sends a
# position (PKT_POS) to the component's hardware.relay ID.
#
#   "actuator": {
#       "min_pct": 0, "max_pct": 100,     commandable range, % of stroke
#       "safe_pct": 0,                    position used by abort / "close"
#       "open_pct": 100,                  position used by "open" (sequences, rules)
#       "unit": "%",                      display suffix
#       "presets": [0, 25, 50, 75, 100],  quick-set buttons in the popup
#       "step": 1                         slider / spinbox increment
#   }
@dataclass
class ActuatorSpec:
    min_pct:  float = 0.0
    max_pct:  float = 100.0
    safe_pct: float = 0.0
    open_pct: float = 100.0
    unit:     str   = "%"
    presets:  list  = field(default_factory=lambda: [0, 25, 50, 75, 100])
    step:     float = 1.0

    def clamp(self, pct: float) -> float:
        return max(self.min_pct, min(self.max_pct, float(pct)))

    def is_off_safe(self, pct: float) -> bool:
        """True when the actuator is meaningfully away from its safe position
        (what the rest of the app treats as 'open')."""
        return abs(pct - self.safe_pct) > 0.5

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ActuatorSpec":
        def _f(key, default):
            try:
                return float(d.get(key, default))
            except (TypeError, ValueError):
                return default
        lo, hi = _f("min_pct", 0.0), _f("max_pct", 100.0)
        if hi < lo:
            lo, hi = hi, lo
        spec = ActuatorSpec(
            min_pct  = lo,
            max_pct  = hi,
            safe_pct = _f("safe_pct", 0.0),
            open_pct = _f("open_pct", hi),
            unit     = str(d.get("unit", "%")),
            presets  = [float(x) for x in d.get("presets", [0, 25, 50, 75, 100])
                        if isinstance(x, (int, float))],
            step     = max(0.01, _f("step", 1.0)),
        )
        spec.safe_pct = spec.clamp(spec.safe_pct)
        spec.open_pct = spec.clamp(spec.open_pct)
        return spec


def get_actuator_spec(comp: "Component") -> Optional[ActuatorSpec]:
    """Return the component's ActuatorSpec, or None for plain on/off valves.

    An explicit extras["actuator"] dict wins (set "enabled": false to opt out);
    the throttle-valve types are proportional by definition, so they get the
    default 0-100% spec when none is given."""
    raw = comp.extras.get("actuator")
    if isinstance(raw, dict):
        return ActuatorSpec.from_dict(raw) if raw.get("enabled", True) else None
    if comp.type in (COMP_THROTTLE_VALVE, COMP_EP_THROTTLE_VALVE):
        return ActuatorSpec()
    return None


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

    # Abort state (see PIDProject.abort_states) applied when the system MAWP
    # backstop trips; "" = the default abort state. And the "approaching MAWP"
    # warning level, as a percentage of system_mawp, where the operator is told
    # to clear the area before the auto-action.
    system_mawp_state: str   = ""
    system_prewarn_pct: float = 90.0

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
            system_mawp_state    = d.get("system_mawp_state", ""),
            system_prewarn_pct   = float(d.get("system_prewarn_pct", 90.0)),
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

    # Which named abort state an "abort" action applies ("" = default abort)
    mawp_state:     str = ""
    meop_state:     str = ""
    relief_state:   str = ""

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
            mawp_state        = d.get("mawp_state", ""),
            meop_state        = d.get("meop_state", ""),
            relief_state      = d.get("relief_state", ""),
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

    # Named abort state an "abort" action applies ("" = default abort)
    abort_state: str = ""

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "abort_state":      self.abort_state,
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
            abort_state      = d.get("abort_state", ""),
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


@dataclass
class AbortState:
    """A named valve configuration the system is driven to on an abort.

    valves maps component id -> True (open); anything missing is closed. The
    project's default state (id DEFAULT_ABORT_ID) doubles as the Safe State
    preset. confirmed=False means the operator hasn't reviewed it yet.
    """
    id:        str
    name:      str
    valves:    dict = field(default_factory=dict)
    confirmed: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "valves": dict(self.valves),
                "confirmed": self.confirmed}

    @staticmethod
    def from_dict(d: dict) -> "AbortState":
        return AbortState(
            id        = d["id"],
            name      = d.get("name", d["id"]),
            valves    = {k: bool(v) for k, v in d.get("valves", {}).items()},
            confirmed = bool(d.get("confirmed", False)),
        )


DEFAULT_ABORT_ID = "default"


# ---------------------------------------------------------------------------
# Automated actuation - stored in PIDProject.actuation_plans
# ---------------------------------------------------------------------------
# An operator-run list of steps for valve actuation too fast or too precise to do by
# hand (e.g. a controlled vent). Steps run in order; each step waits for its
# conditions, then sends all of its actions at once. Conditions:
#   "time"   - `seconds` elapsed since the previous step fired (or since Start)
#   "sensor" - sensor `sensor` (component id) is `op` (">" | "<") `value`
# A step with no conditions fires as soon as the previous one has; with several,
# `match` says whether "any" (whichever happens first) or "all" must be true.
# Valves and sensors are stored by component id and resolved to hardware ids at run
# time, the same way abort states store their valves.
ACT_COND_TIME   = "time"
ACT_COND_SENSOR = "sensor"


@dataclass
class ActuationCondition:
    kind:    str   = ACT_COND_TIME
    seconds: float = 0.5        # time: delay after the previous step
    sensor:  str   = ""         # sensor: component id
    op:      str   = ">"        # sensor: ">" | "<"
    value:   float = 0.0        # sensor: threshold, in the sensor's display units

    def to_dict(self) -> dict:
        if self.kind == ACT_COND_TIME:
            return {"kind": self.kind, "seconds": self.seconds}
        return {"kind": self.kind, "sensor": self.sensor, "op": self.op, "value": self.value}

    @staticmethod
    def from_dict(d: dict) -> "ActuationCondition":
        kind = d.get("kind", ACT_COND_TIME)
        return ActuationCondition(
            kind    = kind if kind in (ACT_COND_TIME, ACT_COND_SENSOR) else ACT_COND_TIME,
            seconds = max(0.0, float(d.get("seconds", 0.5))),
            sensor  = d.get("sensor", ""),
            op      = d.get("op", ">") if d.get("op") in (">", "<") else ">",
            value   = float(d.get("value", 0.0)),
        )


@dataclass
class ActuationAction:
    valve: str  = ""            # component id
    open:  bool = True          # True = open, False = close

    def to_dict(self) -> dict:
        return {"valve": self.valve, "open": self.open}

    @staticmethod
    def from_dict(d: dict) -> "ActuationAction":
        return ActuationAction(valve=d.get("valve", ""), open=bool(d.get("open", True)))


@dataclass
class ActuationStep:
    conditions: list = field(default_factory=list)   # list[ActuationCondition]; empty = immediately
    actions:    list = field(default_factory=list)   # list[ActuationAction]
    match:      str  = "any"                          # "any" | "all"

    def to_dict(self) -> dict:
        return {"match": self.match,
                "conditions": [c.to_dict() for c in self.conditions],
                "actions": [a.to_dict() for a in self.actions]}

    @staticmethod
    def from_dict(d: dict) -> "ActuationStep":
        return ActuationStep(
            conditions = [ActuationCondition.from_dict(c) for c in d.get("conditions", [])],
            actions    = [ActuationAction.from_dict(a) for a in d.get("actions", [])],
            match      = "all" if d.get("match") == "all" else "any",
        )


@dataclass
class ActuationPlan:
    id:    str
    name:  str  = "Automated Actuation"
    steps: list = field(default_factory=list)        # list[ActuationStep]

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "steps": [s.to_dict() for s in self.steps]}

    @staticmethod
    def from_dict(d: dict) -> "ActuationPlan":
        return ActuationPlan(
            id    = d["id"],
            name  = d.get("name", "Automated Actuation"),
            steps = [ActuationStep.from_dict(s) for s in d.get("steps", [])],
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

        # --- Named abort states ---------------------------------------------
        # Valve configurations the system is driven to on an abort. Always
        # contains the default state (DEFAULT_ABORT_ID), which is also the Safe
        # State preset. Rules / thresholds pick a state by id ("" = default).
        self.abort_states: list = [AbortState(DEFAULT_ABORT_ID, "Default Abort")]

        # --- Legacy flat sequence list (kept for backward-compat read paths) ---
        self.sequence:           list             = []    # list[SequenceStep]

        # --- Named sequences (new multi-sequence support) ---------------------
        self.sequences:          list             = []    # list[NamedSequence]
        self.active_sequence_id: str              = ""

        # --- Calculated performance channels ----------------------------------
        self.calc_channels:      list             = []    # list[CalcChannel]

        # --- Automated actuation plans (Home page P&ID panel) -------------------
        self.actuation_plans:    list             = []    # list[ActuationPlan]

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

    def get_abort_state(self, state_id: str = "") -> "AbortState":
        """The named state, falling back to the default for "" / unknown ids."""
        for st in self.abort_states:
            if st.id == (state_id or DEFAULT_ABORT_ID):
                return st
        return self.default_abort_state()

    def default_abort_state(self) -> "AbortState":
        for st in self.abort_states:
            if st.id == DEFAULT_ABORT_ID:
                return st
        st = AbortState(DEFAULT_ABORT_ID, "Default Abort")
        self.abort_states.insert(0, st)
        return st

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
            "abort_states":       [s.to_dict() for s in self.abort_states],
            # Legacy flat sequence kept for backward-compat readers
            "sequence":           [s.to_dict() for s in self.sequence],
            # New multi-sequence support
            "sequences":          [s.to_dict() for s in self.sequences],
            "active_sequence_id": self.active_sequence_id,
            # Calculated performance channels
            "calc_channels":      [c.to_dict() for c in self.calc_channels],
            # Automated actuation plans
            "actuation_plans":    [p.to_dict() for p in self.actuation_plans],
        }

    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def from_dict(d: dict, name_fallback: str = "Untitled Project") -> "PIDProject":
        proj = PIDProject(name=d.get("name", name_fallback))
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

        # De-duplicate pipe line ids (older files could carry collisions)
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

        for cd in d.get("calc_channels", []):
            proj.calc_channels.append(CalcChannel.from_dict(cd))

        for pd in d.get("actuation_plans", []):
            proj.actuation_plans.append(ActuationPlan.from_dict(pd))

        # Legacy flat sequence list (kept for backward-compat readers)
        for sd in d.get("sequence", []):
            proj.sequence.append(SequenceStep.from_dict(sd))

        # Named sequences (new format); a legacy flat sequence is promoted to
        # a single "Default" named sequence for continuity.
        for seqd in d.get("sequences", []):
            proj.sequences.append(NamedSequence.from_dict(seqd))
        if not proj.sequences:
            proj.sequences.append(NamedSequence(
                id="seq_default", name="Default", steps=list(proj.sequence)))

        if "abort_states" in d:
            proj.abort_states = [AbortState.from_dict(sd) for sd in d["abort_states"]]
        elif "abort_state" in d:        # single-state files from before named aborts
            proj.abort_states = [AbortState(
                DEFAULT_ABORT_ID, "Default Abort",
                {k: bool(v) for k, v in d["abort_state"].items()},
                bool(d.get("abort_state_confirmed", False)))]
        proj.default_abort_state()      # guarantee the default exists

        proj.active_sequence_id = d.get("active_sequence_id", "")
        # Fall back to the first sequence if active_sequence_id is missing or
        # stale (doesn't match any loaded sequence).
        if proj.get_active_sequence() is None:
            proj.active_sequence_id = proj.sequences[0].id

        return proj

    @staticmethod
    def load(path: str) -> "PIDProject":
        raw = open(path, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
        d = json.loads(text)
        return PIDProject.from_dict(d, name_fallback=os.path.basename(path))

    @staticmethod
    def new_empty(name: str = "New Project") -> "PIDProject":
        return PIDProject(name=name)