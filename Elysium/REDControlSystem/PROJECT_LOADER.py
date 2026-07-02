import os
from pathlib import Path
from typing import Optional
from PID_SCHEMA import PIDProject

PROJECTS_DIR = Path(__file__).resolve().parent / "PIDs"

def discover_projects() -> list[tuple[str, str]]:
    if not PROJECTS_DIR.is_dir():
        return []

    entries: list[tuple[str, str]] = []
    for path in sorted(PROJECTS_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() == ".red":
            entries.append((path.stem, str(path.resolve())))

    return entries

def load_project(path: str) -> Optional[PIDProject]:
    import json as _json

    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return None

    try:
        raw = open(path, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("cp1252")
        d = _json.loads(text)
    except Exception as exc:
        print(f"Failed to load '{path}': {exc}")
        return None

    try:
        return _project_from_dict(d, path)
    except Exception as exc:
        print(f"Failed to parse '{path}': {exc}")
        return None

def _project_from_dict(d: dict, path: str) -> "PIDProject":
    import os as _os
    from PID_SCHEMA import (
        Component, Connection, LayoutPoint,
        PipeLine, SystemParameters, AbortRule,
    )
    from PROJECT_SEQUENCE_EDITOR import SequenceStep
    proj = PIDProject(name=d.get("name", _os.path.basename(path)))
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
    proj.parameters = SystemParameters.from_dict(d.get("parameters", {}))
    for rd in d.get("rules", []):
        proj.rules.append(AbortRule.from_dict(rd))
    for sd in d.get("sequence", []):
        proj.sequence.append(SequenceStep.from_dict(sd))
    return proj

def project_summary(project: PIDProject) -> str:
    n_comp  = len(project.components)
    n_lines = len(project.lines)
    n_rules = len(project.rules)
    n_steps = len(project.sequence)

    parts = [f"{n_comp} component{'s' if n_comp != 1 else ''}",
             f"{n_lines} pipe{'s' if n_lines != 1 else ''}"]
    if n_rules:
        parts.append(f"{n_rules} abort rule{'s' if n_rules != 1 else ''}")
    if n_steps:
        parts.append(f"{n_steps} sequence step{'s' if n_steps != 1 else ''}")

    return f"{project.name}  v{project.version}  –  {', '.join(parts)}"