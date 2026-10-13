"""
DRAWIO_IMPORT

Best-effort conversion of a draw.io (diagrams.net) P&ID into a PIDProject.

Standalone and side-effect free: import_drawio() only reads the file and builds
a *new* PIDProject in memory, returning it with an ImportReport. It never
touches an existing project or the running controller; the editor decides what
to do with the result (load it unsaved for review/customisation).

What is recognised
    - Components, from the draw.io shape style (pid2valves valve + valveType,
      tank, pump, reducer, sumEllipse gauge, P/T/L ellipses) and, for grouped
      symbols, from the object's description attributes ("... Solenoid",
      "... Hose", "... Regulator", ...).
    - Tag labels (e.g. NV-1101): free text placed next to a symbol is matched
      to the nearest unlabelled component. Other text becomes label components.
    - Pipes, from edges: waypoints are kept, fluid comes from the stroke
      colour, and each end snaps to the nearest component.

Anything it cannot classify is kept as a visible "? ..." label component and
listed in the report, so nothing is silently dropped. Hardware bindings are
not imported (draw.io tags are not firmware IDs) - bind them in the editor.
"""
import math
import re
import xml.etree.ElementTree as ET
import zlib
import base64
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

from PID_SCHEMA import (
    PIDProject, Component, PipeLine, LayoutPoint,
    FLUID_OXIDIZER, FLUID_FUEL, FLUID_PRESSURANT, FLUID_PURGE, FLUID_GENERIC,
    COMP_VALVE, COMP_BALL_VALVE, COMP_SOLENOID, COMP_GLOBE_VALVE, COMP_CHECK_VALVE,
    COMP_THROTTLE_VALVE, COMP_ACTUATED_VALVE, COMP_NEEDLE_VALVE, COMP_THREE_WAY_VALVE,
    COMP_PSV, COMP_PRV, COMP_REGULATOR, COMP_HAND_REGULATOR, COMP_DOME_REGULATOR,
    COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL, COMP_PRESSURE_GAUGE,
    COMP_DIFF_PRESSURE, COMP_FLOW_METER, COMP_TANK, COMP_PUMP, COMP_REDUCER,
    COMP_ORIFICE, COMP_FILTER, COMP_FLEX_HOSE, COMP_JUNCTION, COMP_LABEL,
    COMP_BURST_DISK, COMP_HEAT_EXCHANGER, COMP_TO_ATMOSPHERE, COMP_IGNITER,
    COMP_QUICK_DISCONNECT, COMP_BULKHEAD, COMP_CAP_PLUG,
)

GRID = 10
TAG_RE = re.compile(r"^(?:[A-Z]{1,5}-\d{2,5}[A-Za-z0-9]*|[A-Z]{2,5}_[A-Z0-9]{1,5})$")
TAG_MAX_DIST = 120.0        # px between a tag's text and its symbol
SNAP_DIST = 18.0            # px from a pipe end to a component's outline
BIG_COMPONENT = 60.0        # pipes keep their own end point on components larger than this

# renderer defaults (PID_RENDERER) used to turn draw.io sizes into scale extras
_TANK_BASE = (56.0, 100.0)

_PREFIX = {
    COMP_BALL_VALVE: "BV", COMP_SOLENOID: "SV", COMP_GLOBE_VALVE: "GV", COMP_CHECK_VALVE: "CV",
    COMP_THROTTLE_VALVE: "TV", COMP_PSV: "PSV", COMP_PRV: "PRV", COMP_REGULATOR: "REG",
    COMP_PRESSURE: "PT", COMP_TEMPERATURE: "TC", COMP_LOAD_CELL: "LC", COMP_REDUCER: "RED",
    COMP_TANK: "TK", COMP_IGNITER: "IGN", COMP_ACTUATED_VALVE: "AV", COMP_NEEDLE_VALVE: "NV",
    COMP_THREE_WAY_VALVE: "3WV", COMP_BURST_DISK: "BD", COMP_BULKHEAD: "BH",
    COMP_QUICK_DISCONNECT: "QD", COMP_CAP_PLUG: "CAP", COMP_HAND_REGULATOR: "HREG",
    COMP_DOME_REGULATOR: "DREG", COMP_PUMP: "P", COMP_PRESSURE_GAUGE: "PG",
    COMP_DIFF_PRESSURE: "DP", COMP_FLOW_METER: "FM", COMP_TO_ATMOSPHERE: "ATM",
    COMP_FLEX_HOSE: "H", COMP_HEAT_EXCHANGER: "HEX", COMP_ORIFICE: "OR", COMP_FILTER: "F",
    COMP_VALVE: "V", COMP_JUNCTION: "J", COMP_LABEL: "LBL",
}

# Description keywords -> component type. First match wins, so order matters
# (more specific phrases first).
_DESCRIPTION_RULES = [
    ("throttling",       COMP_THROTTLE_VALVE),
    ("solenoid",         COMP_SOLENOID),
    ("check valve",      COMP_CHECK_VALVE),
    ("needle valve",     COMP_NEEDLE_VALVE),
    ("globe valve",      COMP_GLOBE_VALVE),
    ("ball valve",       COMP_BALL_VALVE),
    ("relief",           COMP_PRV),
    ("burst",            COMP_BURST_DISK),
    ("regulator",        COMP_REGULATOR),
    ("pressure gauge",   COMP_PRESSURE_GAUGE),
    ("pressure transducer", COMP_PRESSURE),
    ("thermocouple",     COMP_TEMPERATURE),
    ("load cell",        COMP_LOAD_CELL),
    ("flow meter",       COMP_FLOW_METER),
    ("orifice",          COMP_ORIFICE),
    ("filter",           COMP_FILTER),
    ("heat exchanger",   COMP_HEAT_EXCHANGER),
    ("igniter",          COMP_IGNITER),
    ("quick disconnect", COMP_QUICK_DISCONNECT),
    ("hose",             COMP_FLEX_HOSE),
    ("coil",             COMP_FLEX_HOSE),
    ("compressor",       COMP_PUMP),
    ("pump",             COMP_PUMP),
    ("bottle",           COMP_TANK),
    ("tank",             COMP_TANK),
]

_VALVE_TYPE = {
    "gate": COMP_VALVE, "ball": COMP_BALL_VALVE, "check": COMP_CHECK_VALVE,
    "globe": COMP_GLOBE_VALVE, "needle": COMP_NEEDLE_VALVE, "angle": COMP_VALVE,
    "butterfly": COMP_VALVE, "plug": COMP_VALVE, "threeWay": COMP_THREE_WAY_VALVE,
    "relief": COMP_PRV,
}

_LETTER_TYPE = {
    "P": COMP_PRESSURE, "T": COMP_TEMPERATURE, "L": COMP_LOAD_CELL, "LC": COMP_LOAD_CELL,
    "F": COMP_FLOW_METER, "FM": COMP_FLOW_METER, "DP": COMP_DIFF_PRESSURE,
}

_COLOR_FLUID = {
    "FF0000": FLUID_FUEL, "0000FF": FLUID_OXIDIZER, "00FF00": FLUID_PURGE,
    "FFFF00": FLUID_PRESSURANT, "FFD600": FLUID_PRESSURANT, "FFC000": FLUID_PRESSURANT,
}


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@dataclass
class ImportReport:
    page: str = ""
    components: dict = field(default_factory=dict)      # type -> count
    lines_imported: int = 0
    lines_connected: int = 0                            # both ends snapped to a component
    lines_skipped: list = field(default_factory=list)
    unrecognized: list = field(default_factory=list)    # shapes kept as "? ..." labels
    unassigned_tags: list = field(default_factory=list)
    labels_created: int = 0
    notes: list = field(default_factory=list)

    def summary(self) -> str:
        out = [f"Imported page: {self.page}", ""]
        total = sum(self.components.values())
        out.append(f"Components: {total}")
        for t, n in sorted(self.components.items()):
            out.append(f"    {t}: {n}")
        out.append("")
        out.append(f"Pipes: {self.lines_imported} imported, "
                   f"{self.lines_connected} with both ends attached to a component, "
                   f"{len(self.lines_skipped)} skipped")
        for s in self.lines_skipped:
            out.append(f"    skipped: {s}")
        if self.unrecognized:
            out.append("")
            out.append(f"Needs attention - {len(self.unrecognized)} shape(s) not recognised "
                       "(kept as '?' labels so you can replace them):")
            for s in self.unrecognized:
                out.append(f"    {s}")
        if self.unassigned_tags:
            out.append("")
            out.append(f"{len(self.unassigned_tags)} tag(s) had no symbol nearby (kept as labels): "
                       + ", ".join(self.unassigned_tags))
        if self.labels_created:
            out.append("")
            out.append(f"{self.labels_created} free-text annotation(s) kept as label components.")
        for n in self.notes:
            out.append("")
            out.append(n)
        out.append("")
        out.append("Hardware bindings (relay / ADC channel) are not imported - set them in the editor. "
                   "Pipe connections were inferred from geometry; check them.")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# draw.io parsing helpers
# ---------------------------------------------------------------------------
@dataclass
class _Cell:
    id: str
    el: ET.Element            # the <mxCell>
    meta: dict                # attributes of the wrapping <object>/<UserObject>, if any
    value: str                # label text (HTML)
    style: str
    parent: str
    vertex: bool
    edge: bool
    source: str
    target: str
    geom: Optional[ET.Element]

    def style_get(self, key: str, default: str = "") -> str:
        m = re.search(rf"(?:^|;){re.escape(key)}=([^;]*)", self.style)
        return m.group(1) if m else default

    def has_shape(self, fragment: str) -> bool:
        return fragment in self.style

    @property
    def description(self) -> str:
        """Joined description attributes of the wrapping object (e.g. _01_Description,
        _02_Valve_Description, ...), lower-cased for keyword matching."""
        parts = [v for k, v in self.meta.items() if "escription" in k and v]
        return " | ".join(parts)


def _strip_html(text: str) -> str:
    text = re.sub(r"<\s*/?\s*(?:br|div|p|li)\b[^>]*>", " ", text or "", flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"\s+", " ", text).strip()


def _decode_diagram(diagram: ET.Element) -> ET.Element:
    """Return the <mxGraphModel> of a <diagram>, decoding the compressed form if needed."""
    model = diagram.find("mxGraphModel")
    if model is not None:
        return model
    data = (diagram.text or "").strip()
    if not data:
        raise ValueError(f"Page '{diagram.get('name')}' is empty")
    raw = base64.b64decode(data)
    xml = zlib.decompress(raw, -15).decode("utf-8")
    return ET.fromstring(urllib.parse.unquote(xml))


def _load_cells(model: ET.Element) -> dict:
    cells: dict = {}
    for el in model.iter():
        if el.tag in ("object", "UserObject"):
            inner = el.find("mxCell")
            if inner is None:
                continue
            ident, meta, value = el.get("id"), dict(el.attrib), el.get("label", "")
        elif el.tag == "mxCell":
            ident, meta, value, inner = el.get("id"), {}, el.get("value", ""), el
        else:
            continue
        if not ident or ident in cells:
            continue
        cells[ident] = _Cell(
            id=ident, el=inner, meta=meta, value=value, style=inner.get("style") or "",
            parent=inner.get("parent") or "", vertex=inner.get("vertex") == "1",
            edge=inner.get("edge") == "1", source=inner.get("source") or "",
            target=inner.get("target") or "", geom=inner.find("mxGeometry"),
        )
    return cells


class _Geo:
    """Absolute geometry (resolving nested group offsets)."""

    def __init__(self, cells: dict):
        self.cells = cells
        self._cache: dict = {}

    def origin(self, cid: str) -> tuple:
        """Absolute top-left of a cell's parent frame."""
        c = self.cells.get(cid)
        if c is None or c.geom is None or cid in ("0", "1"):
            return 0.0, 0.0
        if cid in self._cache:
            return self._cache[cid]
        px, py = self.origin(c.parent) if c.parent in self.cells else (0.0, 0.0)
        res = (px + float(c.geom.get("x", 0)), py + float(c.geom.get("y", 0)))
        self._cache[cid] = res
        return res

    def rect(self, cid: str) -> Optional[tuple]:
        c = self.cells.get(cid)
        if c is None or c.geom is None:
            return None
        x, y = self.origin(cid)
        return x, y, float(c.geom.get("width", 0)), float(c.geom.get("height", 0))

    def center(self, cid: str) -> Optional[tuple]:
        r = self.rect(cid)
        return None if r is None else (r[0] + r[2] / 2, r[1] + r[3] / 2)

    def frame_origin(self, parent_id: str) -> tuple:
        return self.origin(parent_id) if parent_id in self.cells else (0.0, 0.0)


def _orthogonalize(pts: list) -> list:
    """Turn every diagonal segment into a horizontal+vertical elbow so pipes stay
    straight. The elbow is placed so the segment that follows an existing straight
    run keeps that run's direction."""
    out = [pts[0]]
    for i in range(1, len(pts)):
        a, b = out[-1], pts[i]
        if a[0] != b[0] and a[1] != b[1]:
            prev = out[-2] if len(out) > 1 else None
            nxt = pts[i + 1] if i + 1 < len(pts) else None
            if prev is not None and prev[1] == a[1]:        # arrived horizontally: continue horizontally
                out.append((b[0], a[1]))
            elif prev is not None and prev[0] == a[0]:      # arrived vertically: continue vertically
                out.append((a[0], b[1]))
            elif nxt is not None and nxt[1] == b[1]:        # leaves horizontally: arrive vertically
                out.append((a[0], b[1]))
            elif nxt is not None and nxt[0] == b[0]:        # leaves vertically: arrive horizontally
                out.append((b[0], a[1]))
            elif abs(b[0] - a[0]) >= abs(b[1] - a[1]):
                out.append((b[0], a[1]))
            else:
                out.append((a[0], b[1]))
        out.append(b)
    return out


def _declutter(project: PIDProject, comp_rects: dict):
    """Nudge free-text labels so they don't sit on top of component tags or symbols.
    Text geometry mirrors PID_RENDERER (label baseline = centre + (VLV_HH+20)*scale)."""
    def scale(c):
        return (float(c.extras.get("scale_x", 1.0) or 1.0), float(c.extras.get("scale_y", 1.0) or 1.0))

    def text_rect(c, x, y):
        sx, sy = scale(c)
        fs = max(sx, sy) if c.type == COMP_LABEL else 1.0
        off = 34.0 * max(sy, 0.8)
        w = 5.8 * len(c.label or "") * fs + 4
        return (x - w / 2, y + off - 11 * fs, w, 14 * fs)

    def overlap(a, b, pad=2.0):
        return not (a[0] + a[2] + pad <= b[0] or b[0] + b[2] + pad <= a[0] or
                    a[1] + a[3] + pad <= b[1] or b[1] + b[3] + pad <= a[1])

    fixed = []
    for cid, c in project.components.items():
        if c.type in (COMP_LABEL, COMP_JUNCTION) or cid not in comp_rects:
            continue
        pt = project.layout[cid]
        _, _, w, h = comp_rects[cid]
        fixed.append((pt.x - w / 2, pt.y - h / 2, w, h))
        if c.label and not c.hide_lbl:
            fixed.append(text_rect(c, pt.x, pt.y))

    labels = sorted((cid for cid, c in project.components.items() if c.type == COMP_LABEL),
                    key=lambda i: (project.layout[i].y, project.layout[i].x))
    placed = []
    for cid in labels:
        c, pt = project.components[cid], project.layout[cid]
        options = [(0, 0)]
        for r in range(10, 161, 10):
            options += [(0, r), (0, -r), (r, 0), (-r, 0), (r, r), (-r, r), (r, -r), (-r, -r)]
        for dx, dy in options:
            rect = text_rect(c, pt.x + dx, pt.y + dy)
            if not any(overlap(rect, o) for o in fixed + placed):
                pt.x, pt.y = _snap(pt.x + dx), _snap(pt.y + dy)
                placed.append(text_rect(c, pt.x, pt.y))
                break
        else:
            placed.append(text_rect(c, pt.x, pt.y))


def _snap(v: float) -> float:
    return round(v / GRID) * GRID


def _rotation(style: str) -> int:
    m = re.search(r"(?:^|;)rotation=(-?[\d.]+)", style)
    if not m:
        return 0
    return int(round(float(m.group(1)) / 90.0)) * 90 % 360


def _fluid(style: str) -> str:
    m = re.search(r"(?:^|;)strokeColor=([^;]+)", style)
    if not m:
        return FLUID_GENERIC
    hexes = re.findall(r"#([0-9A-Fa-f]{6})", m.group(1))
    return _COLOR_FLUID.get(hexes[0].upper(), FLUID_GENERIC) if hexes else FLUID_GENERIC


def _pick_page(root: ET.Element, page: Optional[str]) -> ET.Element:
    diagrams = list(root.iter("diagram"))
    if not diagrams:
        raise ValueError("No <diagram> pages found - is this a draw.io file?")
    if page:
        for d in diagrams:
            if (d.get("name") or "").strip() == page.strip():
                return d
        raise ValueError(f"No page named '{page}'. Pages: {[d.get('name') for d in diagrams]}")
    # Default: the page with the most edges (the actual drawing, not a legend)
    best, best_n = diagrams[0], -1
    for d in diagrams:
        try:
            n = sum(1 for c in _decode_diagram(d).iter("mxCell") if c.get("edge") == "1")
        except Exception:
            n = -1
        if n > best_n:
            best, best_n = d, n
    return best


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
def _classify(cell: _Cell) -> Optional[str]:
    """Component type for a vertex, or None if it is not a recognisable symbol."""
    desc = cell.description.lower()
    if desc:
        for kw, ctype in _DESCRIPTION_RULES:
            if kw in desc:
                return ctype
    st = cell.style
    if "mxgraph.pid2valves.valve" in st:
        vt = cell.style_get("valveType", "gate")
        actuator = cell.style_get("actuator", "none")
        ctype = _VALVE_TYPE.get(vt, COMP_VALVE)
        if ctype == COMP_VALVE and actuator == "powered":
            ctype = COMP_ACTUATED_VALVE
        return ctype
    if "vessels.tank" in st:
        return COMP_TANK
    if "pumps." in st:
        return COMP_PUMP
    if "concentric_reducer" in st or "eccentric_reducer" in st:
        return COMP_REDUCER
    if "shape=sumEllipse" in st:
        return COMP_PRESSURE_GAUGE
    if st.startswith("ellipse") and cell.vertex:
        text = _strip_html(cell.value).upper()
        if text in _LETTER_TYPE:
            return _LETTER_TYPE[text]
    return None


def _is_text(cell: _Cell) -> bool:
    return cell.style.startswith("text") or "shape=text" in cell.style


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def import_drawio(path: str, page: Optional[str] = None, spacing: float = 1.5) -> tuple:
    """Read a draw.io file and return (PIDProject, ImportReport).

    spacing scales every position (not symbol sizes) so the editor's larger symbols
    and labels don't crowd; 1.0 keeps draw.io's own spacing.

    Raises on unreadable input; never modifies anything on disk or in the app.
    """
    root = ET.parse(path).getroot()
    diagram = _pick_page(root, page)
    model = _decode_diagram(diagram)
    cells = _load_cells(model)
    geo = _Geo(cells)

    report = ImportReport(page=(diagram.get("name") or "").strip())
    project = PIDProject.new_empty(
        re.sub(r"\.drawio(\.xml)?$|\.xml$", "", path.replace("\\", "/").split("/")[-1], flags=re.I))

    counters: dict = {}
    comp_of_cell: dict = {}     # draw.io cell id (incl. consumed children) -> component id
    comp_rects: dict = {}       # component id -> (x, y, w, h)

    def new_id(ctype: str) -> str:
        prefix = _PREFIX.get(ctype, ctype[:3].upper())
        counters[ctype] = counters.get(ctype, 0) + 1
        return f"{prefix}_{counters[ctype]}"

    def children_of(cid: str) -> list:
        return [c for c in cells.values() if c.parent == cid]

    def claim_subtree(cid: str, comp_id: str):
        comp_of_cell[cid] = comp_id
        for ch in children_of(cid):
            claim_subtree(ch.id, comp_id)

    def add_component(cell: _Cell, ctype: str, label_text: str = ""):
        rect = geo.rect(cell.id)
        if rect is None:
            return None
        x, y, w, h = rect
        cx, cy = x + w / 2, y + h / 2
        comp_id = new_id(ctype)
        comp = Component(id=comp_id, type=ctype, label=label_text or comp_id,
                         rotation=_rotation(cell.style))
        notes = cell.description
        if notes:
            comp.extras["notes"] = notes
        link = " ".join(v for k, v in cell.meta.items() if "Link" in k and v)
        if link:
            comp.extras["link"] = link
        if ctype == COMP_TANK:
            sx, sy = w / _TANK_BASE[0], h / _TANK_BASE[1]
            if abs(sx - 1) > 0.05:
                comp.extras["scale_x"] = round(sx, 3)
            if abs(sy - 1) > 0.05:
                comp.extras["scale_y"] = round(sy, 3)
        project.add_component(comp, _snap(cx), _snap(cy))
        comp_rects[comp_id] = (cx - w / 2, cy - h / 2, w, h)
        claim_subtree(cell.id, comp_id)
        report.components[ctype] = report.components.get(ctype, 0) + 1
        return comp

    # -- 1. Walk the vertex tree: classified shapes become components -------------
    texts: list = []
    junction_like: list = []

    def walk(cid: str):
        for cell in children_of(cid):
            if cell.id in comp_of_cell or cell.edge:
                continue
            if not cell.vertex:
                continue
            ctype = _classify(cell)
            if ctype:
                add_component(cell, ctype)
                continue
            if _is_text(cell):
                if _strip_html(cell.value):
                    texts.append(cell)
                continue
            if cell.style.startswith("ellipse"):
                rect = geo.rect(cell.id)
                if rect and max(rect[2], rect[3]) <= 12 and not _strip_html(cell.value):
                    junction_like.append(cell)
                    continue
            # a container: look inside it
            if children_of(cell.id):
                walk(cell.id)
                continue
            # a leaf that is not text and not a known symbol
            desc = cell.description or _strip_html(cell.value)
            if cell.style_get("shape") in ("zigzag",) or "part=1" in cell.style:
                continue            # decoration inside a symbol we didn't classify
            if cell.style_get("shape") == "image" and not desc:
                report.notes.append("Ignored an image with no description (logo/background?).")
                continue
            if desc:
                rect = geo.rect(cell.id)
                where = f"({rect[0]:.0f}, {rect[1]:.0f})" if rect else "?"
                text = desc or cell.style_get("shape") or "shape"
                lbl = add_component(cell, COMP_LABEL, label_text=f"? {text[:40]}")
                report.components[COMP_LABEL] = report.components.get(COMP_LABEL, 0)
                report.unrecognized.append(f"{lbl.id} at {where}: {text[:60]}")

    walk("1")

    for cell in junction_like:
        add_component(cell, COMP_JUNCTION)

    # -- 2. Match tag text to the nearest unlabelled symbol ----------------------
    tag_cells = [t for t in texts if TAG_RE.match(_strip_html(t.value).replace(" ", ""))]
    other_texts = [t for t in texts if t not in tag_cells]
    pairs = []
    for t in tag_cells:
        tc = geo.center(t.id)
        if tc is None:
            continue
        for comp_id, (x, y, w, h) in comp_rects.items():
            if project.components[comp_id].type in (COMP_LABEL, COMP_JUNCTION):
                continue
            d = math.hypot(tc[0] - (x + w / 2), tc[1] - (y + h / 2))
            if d <= TAG_MAX_DIST:
                pairs.append((d, t.id, comp_id))
    pairs.sort()
    used_tags, labelled = set(), set()
    for d, tid, comp_id in pairs:
        if tid in used_tags or comp_id in labelled:
            continue
        project.components[comp_id].label = _strip_html(cells[tid].value).replace(" ", "")
        used_tags.add(tid)
        labelled.add(comp_id)

    # -- 3. Remaining text becomes label components ------------------------------
    for t in tag_cells:
        if t.id not in used_tags:
            report.unassigned_tags.append(_strip_html(t.value))
            other_texts.append(t)
    def nearest_tank(cx: float, cy: float):
        best, best_d = None, 250.0
        for cid_, (x, y, w, h) in comp_rects.items():
            if project.components[cid_].type != COMP_TANK:
                continue
            d = math.hypot(cx - (x + w / 2), cy - (y + h / 2))
            if d < best_d:
                best, best_d = cid_, d
        return best

    attached_notes = 0
    for t in other_texts:
        c = geo.center(t.id)
        if c is None:
            continue
        txt = _strip_html(t.value)
        if re.match(r"(?i)^vol\b", txt):          # "Vol: 1.54 CF  EOP: ...  MAWP: ..." belongs to a tank
            tank = nearest_tank(*c)
            if tank:
                ex = project.components[tank].extras
                ex["notes"] = (ex["notes"] + " | " if ex.get("notes") else "") + txt
                attached_notes += 1
                continue
        comp_id = new_id(COMP_LABEL)
        # the renderer draws a label ~34px below its anchor, so anchor above the text
        project.add_component(Component(id=comp_id, type=COMP_LABEL, label=txt),
                              _snap(c[0]), _snap(c[1] - 30))
        comp_rects[comp_id] = (c[0] - 1, c[1] - 1, 2, 2)
        report.labels_created += 1
        report.components[COMP_LABEL] = report.components.get(COMP_LABEL, 0) + 1
    if attached_notes:
        report.notes.append(f"{attached_notes} volume/EOP/MAWP note(s) were attached to their tanks "
                            "(see each tank's notes) instead of being drawn as labels.")

    # -- 4. Pipes -------------------------------------------------------------------
    def nearest_component(px: float, py: float):
        best, best_d = None, SNAP_DIST
        for comp_id, (x, y, w, h) in comp_rects.items():
            if project.components[comp_id].type == COMP_LABEL:
                continue
            dx = max(x - px, 0.0, px - (x + w))
            dy = max(y - py, 0.0, py - (y + h))
            d = math.hypot(dx, dy)
            if d <= best_d:
                best, best_d = comp_id, d
        return best

    n_lines = 0
    for cell in cells.values():
        if not cell.edge or cell.geom is None or cell.id in comp_of_cell:
            continue        # (edges inside a symbol group are part of its drawing)
        ox, oy = geo.frame_origin(cell.parent)

        def end_point(role: str, attr: str):
            ref = cells.get(attr) if attr else None
            if ref is not None:
                c = geo.center(ref.id)
                if c is not None:
                    return c, comp_of_cell.get(ref.id)
            for pt in cell.geom.findall("mxPoint"):
                if pt.get("as") == role:
                    return (ox + float(pt.get("x", 0)), oy + float(pt.get("y", 0))), None
            return None, None

        p0, c0 = end_point("sourcePoint", cell.source)
        p1, c1 = end_point("targetPoint", cell.target)
        if p0 is None or p1 is None:
            report.lines_skipped.append(f"edge {cell.id}: missing an endpoint")
            continue

        mids = []
        arr = cell.geom.find("Array")
        if arr is not None:
            for pt in arr.findall("mxPoint"):
                mids.append((ox + float(pt.get("x", 0)), oy + float(pt.get("y", 0))))
        elif "orthogonalEdgeStyle" in cell.style and p0[0] != p1[0] and p0[1] != p1[1]:
            mids.append((p1[0], p0[1]))     # one elbow so it stays orthogonal

        c0 = c0 or nearest_component(*p0)
        c1 = c1 or nearest_component(*p1)
        pts = [p0] + mids + [p1]
        # Attach each end to a small component (valve/sensor) by sliding it along
        # the pipe's own axis to the component's centre, so a straight pipe stays
        # straight. Big components (tanks) keep the drawn end so the pipe still
        # meets their outline.
        for idx, comp_id, nb in ((0, c0, 1), (len(pts) - 1, c1, len(pts) - 2)):
            if not comp_id:
                continue
            x, y, w, h = comp_rects[comp_id]
            if max(w, h) > BIG_COMPONENT:
                continue
            cx, cy = x + w / 2, y + h / 2
            ex, ey = pts[idx]
            nx, ny = pts[nb]
            if abs(ex - nx) < 1.0:          # vertical pipe: slide along y
                pts[idx] = (ex, cy)
            elif abs(ey - ny) < 1.0:        # horizontal pipe: slide along x
                pts[idx] = (cx, ey)
            else:
                pts[idx] = (cx, cy)
        pts = [(_snap(x), _snap(y)) for x, y in pts]
        # Fluid pipes (and anything attached at both ends) become straight runs;
        # unattached grey linework (e.g. the engine outline) keeps its drawn shape.
        if _fluid(cell.style) != FLUID_GENERIC or (c0 and c1):
            pts = _orthogonalize(pts)
        dedup = [pts[0]]
        for p in pts[1:]:
            if p != dedup[-1]:
                dedup.append(p)
        if len(dedup) < 2:
            report.lines_skipped.append(f"edge {cell.id}: zero length after snapping")
            continue

        line = PipeLine(
            id="", points=[LayoutPoint(x, y) for x, y in dedup],
            fluid=_fluid(cell.style), dotted="dashed=1" in cell.style,
            connects=[c0, c1] if (c0 and c1 and c0 != c1) else [],
        )
        project.add_line(line)
        n_lines += 1
        if line.connects:
            report.lines_connected += 1
    report.lines_imported = n_lines

    if spacing != 1.0:
        for pt in project.layout.values():
            pt.x, pt.y = _snap(pt.x * spacing), _snap(pt.y * spacing)
        for line in project.lines:
            for pt in line.points:
                pt.x, pt.y = _snap(pt.x * spacing), _snap(pt.y * spacing)

    _declutter(project, comp_rects)

    if not project.components:
        report.notes.append("No components were recognised on this page. Is it the right page? "
                            "Pages in the file: " + ", ".join(
                                (d.get("name") or "").strip() for d in root.iter("diagram")))
    return project, report
