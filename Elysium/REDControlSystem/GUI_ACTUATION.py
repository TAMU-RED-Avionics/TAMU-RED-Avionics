"""
GUI_ACTUATION

Automated actuation: an operator-run, ordered list of valve actions for things too fast
or too precise to do by hand - e.g. a controlled vent: open NV-1105, then close it when
NPT-1101 drops below a value or 0.5 s has passed, whichever comes first.

    ActuationRunner  - runs one ActuationPlan (see PID_SCHEMA). No UI.
    ActuationPanel   - the collapsible editor / run panel floated over the bottom-right
                       of the Home page P&ID canvas.

Steps run in order. Each step waits for its conditions ("any" = whichever happens
first, or "all"), then sends all of its actions back-to-back. A step without
conditions fires as soon as the previous one has, so consecutive unconditional steps
(or several actions in one step) actuate together. Time conditions count from the
moment the previous step fired (step 1: from Start). A sensor condition already true
when its step is reached fires straight away.

Safety: a plan only starts in MANUAL with the Teensy connected, and every command is
re-checked against the lockout as it is sent. Any abort, mode change, disconnect,
viewer switch or project reload stops the run (an abort then drives the valves to its
abort state as usual). STOP halts the run and leaves the valves where they are.
Igniters are never offered. Everything runs on the GUI thread: sensor conditions are
checked on every sample as it arrives and time conditions on a precise timer, so timing
is good to roughly 10-20 ms plus the link - millisecond work belongs in the firmware.
"""
import math
import time
import uuid
from typing import Optional

from PyQt5.QtCore import Qt, QObject, QTimer, QEvent, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QToolButton,
    QComboBox, QDoubleSpinBox, QScrollArea, QMessageBox, QInputDialog, QListView,
)

from PID_SCHEMA import (
    ActuationPlan, ActuationStep, ActuationCondition, ActuationAction,
    ACT_COND_TIME, ACT_COND_SENSOR, COMMANDABLE_VALVE_TYPES, COMP_IGNITER,
    COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL, get_actuator_spec,
)
from GUI_CONTROLLER import GuiMode
from GUI_GRAPHS import sensor_unit

_SENSOR_TYPES = (COMP_PRESSURE, COMP_TEMPERATURE, COMP_LOAD_CELL)


def valve_choices(project) -> dict:
    """{component id: (display label, hw_id)} for every valve a plan may command."""
    out = {}
    if project is None:
        return out
    for cid, comp in project.components.items():
        if comp.type == COMP_IGNITER:
            continue        # never automated (same rule as the health-check valve cycling)
        if comp.type not in COMMANDABLE_VALVE_TYPES and get_actuator_spec(comp) is None:
            continue
        hw_id = comp.extras.get("hw_id") or comp.label
        if hw_id:
            out[cid] = (comp.label or hw_id, hw_id)
    return dict(sorted(out.items(), key=lambda kv: kv[1][0]))


def sensor_choices(project) -> dict:
    """{component id: (display label, hw_id)} for every sensor a condition may watch."""
    out = {}
    if project is None:
        return out
    for cid, comp in project.components.items():
        if comp.type not in _SENSOR_TYPES:
            continue
        hw_id = comp.extras.get("hw_id", comp.label) or comp.label
        if hw_id:
            out[cid] = (comp.label or hw_id, hw_id)
    return dict(sorted(out.items(), key=lambda kv: kv[1][0]))


def describe_step(step: ActuationStep, valves: dict, sensors: dict) -> str:
    """One-line summary, e.g. 'when NPT-1101 < 100 psi or 0.5 s -> close NV-1105'."""
    parts = []
    for cond in step.conditions:
        if cond.kind == ACT_COND_TIME:
            parts.append(f"{cond.seconds:g} s")
        else:
            label, hw_id = sensors.get(cond.sensor, (cond.sensor or "?", ""))
            parts.append(f"{label} {cond.op} {cond.value:g} {sensor_unit(hw_id)}".rstrip())
    when = ("when " + f" {'or' if step.match == 'any' else 'and'} ".join(parts)) if parts else "immediately"
    acts = ", ".join(f"{'open' if a.open else 'close'} {valves.get(a.valve, (a.valve or '?',))[0]}"
                     for a in step.actions) or "(no actions)"
    return f"{when} → {acts}"


class ActuationRunner(QObject):
    """Runs one ActuationPlan against the controller. See the module docstring."""

    progress = pyqtSignal()         # a step was armed or fired
    finished = pyqtSignal(str)      # "" = completed, else why it stopped

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.c = controller
        self.plan: Optional[ActuationPlan] = None   # set while running
        self.last_plan_id = ""                      # plan the step states below belong to
        self.fired_at: list = []                    # per step: seconds after Start it fired, or None
        self.index = 0                              # step currently armed
        self._steps: list = []                      # resolved copy of the plan's steps
        self._started_at = 0.0
        self._armed_at = 0.0                        # when the current step was armed (= previous step fired)
        self._evaluating = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.timeout.connect(self._evaluate)

        s = controller.signals
        s.sensor_updated.connect(self._on_sensor)
        s.abort_triggered.connect(self._on_abort)
        s.mode_changed.connect(self._on_mode)
        s.disconnected.connect(self._on_disconnected)
        s.view_only_changed.connect(self._on_view_only)
        s.project_changed.connect(self._on_project_changed)

    @property
    def running(self) -> bool:
        return self.plan is not None

    # -- start / stop -----------------------------------------------------------------
    def check_start(self, plan: Optional[ActuationPlan]) -> Optional[str]:
        """Why this plan can't start right now, or None if it can."""
        c = self.c
        if self.running:
            return "A plan is already running."
        if c.view_only:
            return "This GUI is in view-only mode."
        if not c.ethernet_client.connected:
            return "Connect to the Teensy first."
        if c.mode != GuiMode.MANUAL:
            return f"Automated actuation requires MANUAL mode (currently {c.mode})."
        if c.sequence_running:
            return "An auto-fire sequence is running."
        if plan is None or not plan.steps:
            return "This plan has no steps."
        steps, problems = self._resolve(plan)
        if problems:
            return "Fix these first:\n• " + "\n• ".join(problems)
        if not any(st["actions"] for st in steps):
            return "This plan doesn't actuate anything."
        return None

    def start(self, plan: ActuationPlan) -> Optional[str]:
        err = self.check_start(plan)
        if err:
            return err
        self._steps, _ = self._resolve(plan)
        self.plan = plan
        self.last_plan_id = plan.id
        self.fired_at = [None] * len(self._steps)
        self.index = 0
        self._started_at = time.monotonic()
        self.c.log_event("AUTO_ACTUATION", f"START '{plan.name}' ({len(self._steps)} steps)")
        self._arm(self._started_at)
        return None

    def stop(self, reason: str):
        if not self.running:
            return
        self._timer.stop()
        name = self.plan.name
        self.plan = None
        self.c.log_event("AUTO_ACTUATION", f"STOPPED '{name}': {reason}")
        self.progress.emit()
        self.finished.emit(reason)

    def _finish(self):
        self._timer.stop()
        name = self.plan.name
        self.plan = None
        self.c.log_event("AUTO_ACTUATION", f"COMPLETE '{name}'")
        self.progress.emit()
        self.finished.emit("")

    def _resolve(self, plan: ActuationPlan):
        """Turn component ids into hardware ids. Returns (steps, problems)."""
        valves = valve_choices(self.c.project)
        sensors = sensor_choices(self.c.project)
        steps, problems = [], []
        for n, step in enumerate(plan.steps, start=1):
            conds, actions = [], []
            for cond in step.conditions:
                if cond.kind == ACT_COND_TIME:
                    conds.append({"kind": ACT_COND_TIME, "seconds": max(0.0, cond.seconds)})
                elif not cond.sensor:
                    problems.append(f"Step {n}: a sensor condition has no sensor selected.")
                elif cond.sensor not in sensors:
                    problems.append(f"Step {n}: a condition's sensor is no longer in the P&ID.")
                else:
                    label, hw_id = sensors[cond.sensor]
                    conds.append({"kind": ACT_COND_SENSOR, "key": hw_id.upper(), "label": label,
                                  "unit": sensor_unit(hw_id), "op": cond.op, "value": cond.value})
            for act in step.actions:
                if not act.valve:
                    problems.append(f"Step {n}: an action has no valve selected.")
                elif act.valve not in valves or valves[act.valve][1] not in self.c.valve_states:
                    problems.append(f"Step {n}: an action's valve is no longer in the P&ID.")
                else:
                    label, hw_id = valves[act.valve]
                    actions.append((hw_id, act.open, label))
            steps.append({"conds": conds, "actions": actions, "match": step.match})
        return steps, problems

    # -- interlocks -------------------------------------------------------------------
    def _on_abort(self, *_):
        self.stop("an abort was triggered")

    def _on_mode(self, mode: str):
        if mode != GuiMode.MANUAL:
            self.stop(f"the mode changed to {mode}")

    def _on_disconnected(self, *_):
        self.stop("the link to the Teensy was lost")

    def _on_view_only(self, *_):
        self.stop("this GUI switched to viewer mode")

    def _on_project_changed(self):
        self.stop("the project was reloaded")

    # -- evaluation -------------------------------------------------------------------
    def _arm(self, t: float):
        self._armed_at = t
        self.progress.emit()
        self._evaluate()

    def _on_sensor(self, name: str, _value: float, _ts: float):
        if not self.running or self.index >= len(self._steps):
            return
        key = name.upper()
        if any(cd["kind"] == ACT_COND_SENSOR and cd["key"] == key
               for cd in self._steps[self.index]["conds"]):
            self._evaluate()

    def _evaluate(self):
        if self._evaluating:        # a command's side effects re-entering us
            return
        self._evaluating = True
        try:
            while self.running:
                if self.index >= len(self._steps):
                    self._finish()
                    return
                step = self._steps[self.index]
                now = time.monotonic()
                fired = self._true_conditions(step, now)
                if fired is None:
                    self._schedule(step, now)
                    return
                if not self._fire(step, now, fired):
                    return
                self.index += 1
                self._armed_at = now        # the next step's times count from here
                self.progress.emit()
        finally:
            self._evaluating = False

    def _cond_true(self, cd: dict, now: float) -> bool:
        if cd["kind"] == ACT_COND_TIME:
            return now - self._armed_at >= cd["seconds"] - 1e-4
        value = self.c.current_sensor_values.get(cd["key"])
        if value is None or value != value:         # no reading yet / NaN (no signal)
            return False
        return value > cd["value"] if cd["op"] == ">" else value < cd["value"]

    def _true_conditions(self, step: dict, now: float) -> Optional[list]:
        """The conditions that make this step fire now, or None if it can't fire yet."""
        conds = step["conds"]
        if not conds:
            return []
        true = [cd for cd in conds if self._cond_true(cd, now)]
        if step["match"] == "all":
            return true if len(true) == len(conds) else None
        return true or None

    def _schedule(self, step: dict, now: float):
        waits = [self._armed_at + cd["seconds"] - now for cd in step["conds"]
                 if cd["kind"] == ACT_COND_TIME and not self._cond_true(cd, now)]
        if waits:
            self._timer.start(max(0, math.ceil(min(waits) * 1000)))
        else:
            self._timer.stop()      # waiting on sensors only: re-evaluated as samples arrive

    def _fire(self, step: dict, now: float, fired: list) -> bool:
        c = self.c
        n = self.index + 1
        if c.lockout or not c.ethernet_client.connected:
            self.stop(f"MANUAL mode or the link was lost before step {n} could fire")
            return False
        for hw_id, is_open, _label in step["actions"]:
            # force: always send. The normal "already in that state" skip compares against
            # the last *confirmed* state, so a quick close right after an open whose ACK
            # hasn't landed yet would otherwise be silently dropped.
            c._drive_valve(hw_id, is_open, force=True)
        elapsed = now - self._started_at
        self.fired_at[self.index] = elapsed
        acts = ", ".join(f"{'open' if o else 'close'} {label}" for _, o, label in step["actions"]) or "no actions"
        c.log_event("AUTO_ACTUATION",
                    f"'{self.plan.name}' step {n} at +{elapsed:.3f} s: {acts} ({self._why(fired)})")
        return True

    def _why(self, fired: list) -> str:
        if not fired:
            return "immediate"
        out = []
        for cd in fired:
            if cd["kind"] == ACT_COND_TIME:
                out.append(f"{cd['seconds']:g} s elapsed")
            else:
                v = self.c.current_sensor_values.get(cd["key"])
                out.append(f"{cd['label']} {cd['op']} {cd['value']:g} (read {v:.2f})")
        return "; ".join(out)

    # -- for the UI -------------------------------------------------------------------
    def step_state(self, plan_id: str, i: int) -> str:
        """'armed' | 'done' | '' for step i of the given plan (last run's results)."""
        if plan_id != self.last_plan_id or i >= len(self.fired_at):
            return ""
        if self.fired_at[i] is not None:
            return "done"
        return "armed" if self.running and i == self.index else ""

    def status_text(self) -> str:
        if not self.running or self.index >= len(self._steps):
            return ""
        step = self._steps[self.index]
        now = time.monotonic()
        parts = []
        for cd in step["conds"]:
            if cd["kind"] == ACT_COND_TIME:
                left = max(0.0, self._armed_at + cd["seconds"] - now)
                parts.append(f"{left:.2f} s left")
            else:
                v = self.c.current_sensor_values.get(cd["key"])
                now_txt = "no data" if v is None or v != v else f"now {v:.2f}"
                parts.append(f"{cd['label']} {cd['op']} {cd['value']:g} {cd['unit']} ({now_txt})".replace("  ", " "))
        joiner = " or " if step["match"] == "any" else " and "
        return f"Step {self.index + 1}/{len(self._steps)} waiting: " + joiner.join(parts)


# ── UI ──────────────────────────────────────────────────────────────────────────────────

class _Combo(QComboBox):
    """Ignores the mouse wheel unless focused, so scrolling the step list can't
    silently change a valve, sensor or action.

    Also uses a plain list popup at least as wide as its longest item: the macOS-native
    popup is drawn over the box at the box's own width (plus a checkmark column), which
    clipped short combos like Open / Close to "Ope" / "Clos"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.setView(QListView())
        self.setStyleSheet("QComboBox { combobox-popup: 0; }"
                           "QComboBox QAbstractItemView::item { padding: 3px 10px; min-height: 18px; }")

    def showPopup(self):
        view = self.view()
        view.setMinimumWidth(max(self.width(), view.sizeHintForColumn(0) + 2 * view.frameWidth() + 24))
        super().showPopup()

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class _Spin(QDoubleSpinBox):
    def __init__(self, lo, hi, decimals, step, suffix="", parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setRange(lo, hi)
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setSuffix(suffix)
        self.setKeyboardTracking(False)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


_PANEL_QSS = """
QFrame#actuation_step { border: 1px solid rgba(128, 128, 128, 110); border-radius: 6px; }
QFrame#actuation_step[state="armed"] { border: 2px solid #ff9800; }
QFrame#actuation_step[state="done"]  { border: 1px solid #2e7d32; }
QLabel#actuation_step_title { font-weight: bold; }
QLabel#actuation_hint { color: #8a8a8a; }
"""
_START_QSS = ("QPushButton { background:#1a4a1a; color:#00dd55; border:1px solid #00aa44; border-radius:6px;"
              " font-weight:bold; padding:5px 14px; } QPushButton:disabled { color:#5a6a5a; border-color:#3a4a3a; }")
_STOP_QSS = ("QPushButton { background:#4a1a1a; color:#ff5544; border:1px solid #aa2222; border-radius:6px;"
             " font-weight:bold; padding:5px 14px; } QPushButton:disabled { color:#6a5a5a; border-color:#4a3a3a; }")
_RUNNING_BTN_QSS = "QPushButton { background:#4a3200; color:#ffb74d; border:1px solid #ff9800; font-weight:bold; }"


class ActuationPanel(QFrame):
    """Collapsible automated-actuation panel over the bottom-right of a P&ID canvas.

    Collapsed it is a single button in the corner; expanded it is the plan editor plus
    START / STOP. Edits are saved into the project file (actuation_plans) as you go."""

    PANEL_W = 540
    PANEL_H = 620
    MARGIN = 12

    def __init__(self, controller, canvas: QWidget):
        super().__init__(canvas)
        self.c = controller
        self.canvas = canvas
        self.project = None
        self._cards: list = []
        self._last_result = ""          # outcome of the last run (or a save error), shown while idle

        self.runner = ActuationRunner(controller, self)
        self.runner.progress.connect(self._refresh_states)
        self.runner.finished.connect(self._on_finished)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._save)

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(100)
        self._live_timer.timeout.connect(self._refresh_live)

        self.setObjectName("config_card")
        self.setStyleSheet(_PANEL_QSS)

        self.toggle_btn = QPushButton("Automated Actuation  ▴", canvas)
        self.toggle_btn.setObjectName("action_bar_btn")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setToolTip("Automatically open / close valves on timers or sensor values")
        self.toggle_btn.clicked.connect(lambda: self.set_expanded(True))

        self._build_ui()

        s = controller.signals
        s.project_changed.connect(self._on_project_changed)
        s.view_only_changed.connect(lambda *_: self._sync_visibility())
        for sig in (s.mode_changed, s.connected, s.disconnected):
            sig.connect(lambda *_: self._sync_controls())

        canvas.installEventFilter(self)
        self.set_project(controller.project)
        self.set_expanded(False)

    # -- layout -----------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("AUTOMATED ACTUATION")
        title.setObjectName("panel_section_title")
        header.addWidget(title)
        header.addStretch()
        collapse = QToolButton()
        collapse.setText("Hide ▾")
        collapse.setToolTip("Collapse to the corner button (a running plan keeps running)")
        collapse.clicked.connect(lambda: self.set_expanded(False))
        header.addWidget(collapse)
        root.addLayout(header)

        plan_row = QHBoxLayout()
        plan_row.addWidget(QLabel("Plan:"))
        self.plan_combo = _Combo()
        self.plan_combo.currentIndexChanged.connect(lambda *_: self._rebuild_steps())
        plan_row.addWidget(self.plan_combo, stretch=1)
        self.new_btn = self._small_btn("New", self._new_plan, plan_row)
        self.rename_btn = self._small_btn("Rename", self._rename_plan, plan_row)
        self.delete_btn = self._small_btn("Delete", self._delete_plan, plan_row)
        root.addLayout(plan_row)

        hint = QLabel("Steps run top to bottom. Each waits for its conditions, then sends all of its "
                      "actions at once. Times count from the previous step.")
        hint.setObjectName("actuation_hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._steps_host = QWidget()
        self._steps_lay = QVBoxLayout(self._steps_host)
        self._steps_lay.setContentsMargins(0, 0, 4, 0)
        self._steps_lay.setSpacing(6)
        self.scroll.setWidget(self._steps_host)
        root.addWidget(self.scroll, stretch=1)

        self.status_lbl = QLabel("")
        self.status_lbl.setWordWrap(True)
        root.addWidget(self.status_lbl)

        run_row = QHBoxLayout()
        run_row.addStretch()
        self.start_btn = QPushButton("▶  START")
        self.start_btn.setStyleSheet(_START_QSS)
        self.start_btn.clicked.connect(self._start)
        run_row.addWidget(self.start_btn)
        self.stop_btn = QPushButton("■  STOP")
        self.stop_btn.setStyleSheet(_STOP_QSS)
        self.stop_btn.setToolTip("Stop the run. Valves stay where they are.")
        self.stop_btn.clicked.connect(lambda: self.runner.stop("stopped by the operator"))
        run_row.addWidget(self.stop_btn)
        root.addLayout(run_row)

    @staticmethod
    def _small_btn(text, slot, layout) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("small_btn")
        b.clicked.connect(slot)
        layout.addWidget(b)
        return b

    def set_expanded(self, expanded: bool):
        allowed = not self.c.view_only
        self.setVisible(allowed and expanded)
        self.toggle_btn.setVisible(allowed and not expanded)
        self._reposition()
        if self.isVisible():
            self.raise_()
        else:
            self.toggle_btn.raise_()

    def _sync_visibility(self):
        if self.c.view_only:
            self.setVisible(False)
            self.toggle_btn.setVisible(False)
        else:
            self.set_expanded(self.isVisible())

    def _reposition(self):
        cw, ch, m = self.canvas.width(), self.canvas.height(), self.MARGIN
        self.toggle_btn.adjustSize()
        bw, bh = self.toggle_btn.width(), self.toggle_btn.height()
        self.toggle_btn.move(max(0, cw - bw - m), max(0, ch - bh - m))
        w = max(260, min(self.PANEL_W, cw - 2 * m))
        h = max(200, min(self.PANEL_H, ch - 2 * m))
        self.setGeometry(max(0, cw - w - m), max(0, ch - h - m), w, h)

    def eventFilter(self, obj, event):
        if obj is self.canvas and event.type() == QEvent.Resize:
            self._reposition()
        return False

    # The panel floats over the canvas: keep clicks, drags and wheel turns on it from
    # falling through and panning / zooming / selecting on the P&ID underneath.
    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()

    # -- project / plans --------------------------------------------------------------
    def _on_project_changed(self):
        self.set_project(self.c.project)

    def set_project(self, project):
        self.project = project
        self._valves = valve_choices(project)
        self._sensors = sensor_choices(project)
        self._reload_plans()

    def _plans(self) -> list:
        return self.project.actuation_plans if self.project is not None else []

    def _current_plan(self) -> Optional[ActuationPlan]:
        pid = self.plan_combo.currentData()
        return next((p for p in self._plans() if p.id == pid), None)

    def _reload_plans(self, select_id: str = ""):
        current = select_id or self.plan_combo.currentData() or ""
        self.plan_combo.blockSignals(True)
        self.plan_combo.clear()
        for plan in self._plans():
            self.plan_combo.addItem(plan.name, plan.id)
        idx = self.plan_combo.findData(current)
        self.plan_combo.setCurrentIndex(idx if idx >= 0 else (0 if self.plan_combo.count() else -1))
        self.plan_combo.blockSignals(False)
        self._rebuild_steps()

    def _new_plan(self):
        if self.project is None:
            return
        name, ok = QInputDialog.getText(self, "New Plan", "Plan name:",
                                        text=f"Plan {len(self._plans()) + 1}")
        if not ok or not name.strip():
            return
        plan = ActuationPlan(id=f"act_{uuid.uuid4().hex[:8]}", name=name.strip(),
                             steps=[ActuationStep(actions=[ActuationAction()])])
        self.project.actuation_plans.append(plan)
        self._reload_plans(select_id=plan.id)
        self._changed()

    def _rename_plan(self):
        plan = self._current_plan()
        if plan is None:
            return
        name, ok = QInputDialog.getText(self, "Rename Plan", "Plan name:", text=plan.name)
        if ok and name.strip():
            plan.name = name.strip()
            self._reload_plans(select_id=plan.id)
            self._changed()

    def _delete_plan(self):
        plan = self._current_plan()
        if plan is None:
            return
        if QMessageBox.question(self, "Delete Plan", f"Delete '{plan.name}'?") != QMessageBox.Yes:
            return
        self.project.actuation_plans.remove(plan)
        self._reload_plans()
        self._changed()

    def _changed(self):
        """A plan was edited: save it into the project file (debounced). Only the project
        the controller loaded from disk is saved - a streamed (viewer) copy has no file."""
        if self.project is not None and self.project is self.c.project and self.c.project_path:
            self._save_timer.start()
        self._sync_controls()

    def _save(self):
        try:
            self.c.project.save(self.c.project_path)
        except OSError as e:
            self._last_result = f"Could not save the plan to the project file: {e}"
            self._sync_controls()

    # -- step editor ------------------------------------------------------------------
    def _rebuild_steps(self):
        """Rebuild the step cards from the current plan (any structural edit)."""
        bar = self.scroll.verticalScrollBar()
        scroll_pos = bar.value()
        while self._steps_lay.count():
            item = self._steps_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()                # deleteLater alone leaves a ghost until the event loop runs
                w.deleteLater()
        self._cards = []

        plan = self._current_plan()
        if self.project is None:
            self._steps_lay.addWidget(self._note("Load a project to set up automated actuation."))
        elif plan is None:
            self._steps_lay.addWidget(self._note("No plans yet - click New to create one."))
        else:
            for i, step in enumerate(plan.steps):
                card = self._make_card(plan, i, step)
                self._cards.append(card)
                self._steps_lay.addWidget(card)
            add = QPushButton("+ Add step")
            add.setObjectName("small_btn")
            add.clicked.connect(lambda: self._edit(lambda: plan.steps.append(
                ActuationStep(conditions=[ActuationCondition()], actions=[ActuationAction()]))))
            self._steps_lay.addWidget(add)
        self._steps_lay.addStretch()
        QTimer.singleShot(0, lambda: bar.setValue(scroll_pos))
        self._refresh_states()
        self._sync_controls()

    @staticmethod
    def _note(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("actuation_hint")
        lbl.setWordWrap(True)
        return lbl

    def _edit(self, fn):
        """Apply a structural edit, then rebuild and save."""
        fn()
        self._rebuild_steps()
        self._changed()

    @staticmethod
    def _tool(text: str, tip: str, slot, enabled: bool = True) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setEnabled(enabled)
        b.clicked.connect(slot)
        return b

    def _make_card(self, plan: ActuationPlan, i: int, step: ActuationStep) -> QFrame:
        card = QFrame()
        card.setObjectName("actuation_step")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 6, 8, 8)
        lay.setSpacing(4)
        steps = plan.steps

        top = QHBoxLayout()
        title = QLabel(f"STEP {i + 1}")
        title.setObjectName("actuation_step_title")
        top.addWidget(title)
        card.state_lbl = QLabel("")
        top.addWidget(card.state_lbl)
        top.addStretch()

        def move(delta):
            steps.insert(i + delta, steps.pop(i))
        top.addWidget(self._tool("▲", "Move up", lambda: self._edit(lambda: move(-1)), i > 0))
        top.addWidget(self._tool("▼", "Move down", lambda: self._edit(lambda: move(1)), i < len(steps) - 1))
        top.addWidget(self._tool("✕", "Delete step", lambda: self._edit(lambda: steps.pop(i))))
        lay.addLayout(top)

        # WHEN
        when = QHBoxLayout()
        since = "Start" if i == 0 else "the previous step"
        if not step.conditions:
            when.addWidget(QLabel(f"Immediately (as soon as {'started' if i == 0 else 'step ' + str(i) + ' fires'})"))
        else:
            when.addWidget(QLabel("When"))
            if len(step.conditions) > 1:
                match = _Combo()
                match.addItem("any of these (first wins)", "any")
                match.addItem("all of these", "all")
                match.setCurrentIndex(0 if step.match == "any" else 1)
                match.currentIndexChanged.connect(
                    lambda _i, m=match: (setattr(step, "match", m.currentData()), self._changed()))
                when.addWidget(match)
        when.addStretch()
        when.addWidget(self._tool("+ Condition", "Add a time or sensor condition",
                                  lambda: self._edit(lambda: step.conditions.append(ActuationCondition()))))
        lay.addLayout(when)
        for j, cond in enumerate(step.conditions):
            lay.addLayout(self._cond_row(step, j, cond, since))

        # THEN
        then = QHBoxLayout()
        then.addWidget(QLabel("Then"))
        then.addStretch()
        then.addWidget(self._tool("+ Action", "Add a valve to actuate in this step",
                                  lambda: self._edit(lambda: step.actions.append(ActuationAction()))))
        lay.addLayout(then)
        for k, act in enumerate(step.actions):
            lay.addLayout(self._action_row(step, k, act))
        if not step.actions:
            lay.addWidget(self._note("    (no actions - this step only waits)"))
        return card

    def _cond_row(self, step: ActuationStep, j: int, cond: ActuationCondition, since: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(14, 0, 0, 0)
        kind = _Combo()
        kind.addItem("Time elapsed", ACT_COND_TIME)
        kind.addItem("Sensor", ACT_COND_SENSOR)
        kind.setCurrentIndex(0 if cond.kind == ACT_COND_TIME else 1)
        kind.currentIndexChanged.connect(
            lambda _i: self._edit(lambda: setattr(cond, "kind", kind.currentData())))
        row.addWidget(kind)

        if cond.kind == ACT_COND_TIME:
            secs = _Spin(0.0, 3600.0, 3, 0.1, " s")
            secs.setValue(cond.seconds)
            secs.valueChanged.connect(lambda v: (setattr(cond, "seconds", v), self._changed()))
            row.addWidget(secs)
            row.addWidget(QLabel(f"after {since}"))
            row.addStretch()
        else:
            sensor = self._choice_combo(self._sensors, cond.sensor, "Select sensor…")
            row.addWidget(sensor, stretch=1)
            op = _Combo()
            op.addItems([">", "<"])
            op.setCurrentText(cond.op)
            op.currentTextChanged.connect(lambda t: (setattr(cond, "op", t), self._changed()))
            row.addWidget(op)
            value = _Spin(-1e6, 1e6, 2, 1.0)
            value.setValue(cond.value)
            value.valueChanged.connect(lambda v: (setattr(cond, "value", v), self._changed()))
            row.addWidget(value)
            unit = QLabel(sensor_unit(self._sensors.get(cond.sensor, ("", ""))[1]))
            unit.setMinimumWidth(28)
            row.addWidget(unit)

            def on_sensor(_i):
                cond.sensor = sensor.currentData() or ""
                unit.setText(sensor_unit(self._sensors.get(cond.sensor, ("", ""))[1]))
                self._changed()
            sensor.currentIndexChanged.connect(on_sensor)

        row.addWidget(self._tool("✕", "Remove condition",
                                 lambda: self._edit(lambda: step.conditions.pop(j))))
        return row

    def _action_row(self, step: ActuationStep, k: int, act: ActuationAction) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(14, 0, 0, 0)
        verb = _Combo()
        verb.addItem("Open", True)
        verb.addItem("Close", False)
        verb.setCurrentIndex(0 if act.open else 1)
        verb.currentIndexChanged.connect(lambda _i: (setattr(act, "open", verb.currentData()), self._changed()))
        row.addWidget(verb)
        valve = self._choice_combo(self._valves, act.valve, "Select valve…")
        valve.currentIndexChanged.connect(lambda _i: (setattr(act, "valve", valve.currentData() or ""), self._changed()))
        row.addWidget(valve, stretch=1)
        row.addWidget(self._tool("✕", "Remove action",
                                 lambda: self._edit(lambda: step.actions.pop(k))))
        return row

    @staticmethod
    def _choice_combo(choices: dict, current: str, placeholder: str) -> _Combo:
        combo = _Combo()
        combo.addItem(placeholder, "")
        for cid, (label, hw_id) in choices.items():
            combo.addItem(label, cid)
            combo.setItemData(combo.count() - 1, f"hardware id: {hw_id}", Qt.ToolTipRole)
        if current and current not in choices:
            combo.addItem(f"(missing: {current})", current)     # keep a stale reference visible
        combo.setCurrentIndex(max(0, combo.findData(current)))
        return combo

    # -- running ----------------------------------------------------------------------
    def _start(self):
        plan = self._current_plan()
        err = self.runner.check_start(plan)
        if err:
            QMessageBox.warning(self, "Can't Start", err)
            return
        summary = "\n".join(f"{n}. {describe_step(s, self._valves, self._sensors)}"
                            for n, s in enumerate(plan.steps, start=1))
        reply = QMessageBox.question(
            self, "Start Automated Actuation",
            f"Run '{plan.name}'?\n\n{summary}\n\nValves will be commanded automatically.\n"
            "STOP halts the run and leaves the valves where they are; any abort stops it too.",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if reply != QMessageBox.Yes:
            return
        self._last_result = ""
        err = self.runner.start(plan)       # re-checked: the state may have changed meanwhile
        if err:
            QMessageBox.warning(self, "Can't Start", err)
            return
        self._sync_controls()
        if self.runner.running:             # (a plan of only immediate steps is already done)
            self._live_timer.start()
            self._refresh_live()

    def _on_finished(self, reason: str):
        self._live_timer.stop()
        self._last_result = "Last run completed." if not reason else f"Last run stopped: {reason}."
        self._sync_controls()

    def _refresh_states(self):
        plan = self._current_plan()
        armed_card = None
        for i, card in enumerate(self._cards):
            state = self.runner.step_state(plan.id, i) if plan else ""
            if card.property("state") != state:
                card.setProperty("state", state)
                card.style().unpolish(card)
                card.style().polish(card)
            if state == "done":
                card.state_lbl.setText(f"✓ fired at +{self.runner.fired_at[i]:.3f} s")
            elif state == "armed":
                card.state_lbl.setText("● waiting")
                armed_card = card
            else:
                card.state_lbl.setText("")
        if armed_card is not None:
            self.scroll.ensureWidgetVisible(armed_card)

    def _refresh_live(self):
        if self.runner.running:
            self.status_lbl.setText(self.runner.status_text())

    def _sync_controls(self):
        running = self.runner.running
        has_plan = self._current_plan() is not None
        for w in (self.plan_combo, self.new_btn, self._steps_host):
            w.setEnabled(not running and self.project is not None)
        self.rename_btn.setEnabled(not running and has_plan)
        self.delete_btn.setEnabled(not running and has_plan)
        self.stop_btn.setEnabled(running)
        if running:
            self.start_btn.setEnabled(False)
            self.toggle_btn.setText("●  Automated Actuation RUNNING  ▴")
            self.toggle_btn.setStyleSheet(_RUNNING_BTN_QSS)
        else:
            blocked = self._blocked_reason() if has_plan else "Create or select a plan."
            self.start_btn.setEnabled(blocked is None)
            self.start_btn.setToolTip(blocked or "")
            self.status_lbl.setText("  ".join(t for t in (self._last_result, blocked or "Ready to start.") if t))
            self.toggle_btn.setText("Automated Actuation  ▴")
            self.toggle_btn.setStyleSheet("")
        self._reposition()

    def _blocked_reason(self) -> Optional[str]:
        """Why START is unavailable right now (the mode / link part only - the plan's
        contents are checked when START is pressed, with a full list of problems)."""
        c = self.c
        if not c.ethernet_client.connected:
            return "START needs a live link to the Teensy."
        if c.mode != GuiMode.MANUAL:
            return f"START needs MANUAL mode (currently {c.mode})."
        return None
