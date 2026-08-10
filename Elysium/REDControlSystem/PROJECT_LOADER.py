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
    """Load a .red project, returning None (with a console message) on any
    failure instead of raising - callers show their own error dialog."""
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        return None

    try:
        return PIDProject.load(path)
    except Exception as exc:
        print(f"Failed to load '{path}': {exc}")
        return None

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

    return f"{project.name}  v{project.version}  -  {', '.join(parts)}"
