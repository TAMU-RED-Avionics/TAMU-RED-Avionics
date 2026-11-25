"""Expression engine for abort / warning / action rules.

Rules are written with the OFFICIAL sensor names from the P&ID (MCC_P, OPT-1501, OTH-1501, LC1 ...),
the way an operator reads them. The internal hardware ids (P8, P3, TC1 ...) still work too, so older
rules keep firing. Calculated channels can be used by their label as well (Thrust, Tank Weight).

An expression is a plain Python-style expression, checked before it is ever run:

    numbers, + - * / // % **, comparisons (< <= > >= == !=), and / or / not, ( ), x if c else y
    functions:  abs  min  max  round  sqrt  pow  floor  ceil
    constants:  G0
    sequence timing (so a rule can be armed only during a run):
        SEQ_T        seconds relative to T-0 while a sequence runs: negative during the terminal count,
                     0 at T-0, positive after. Has no value (every comparison is False) when none runs.
        SEQ_END      time (relative to T-0) of the sequence's last step
        SEQ_RUNNING  True while a sequence is running

Nothing else is allowed (no attribute access, indexing, imports, strings), so a rule can't do anything
but arithmetic on sensor values. A rule that can't be understood is reported when the project loads
instead of silently never firing.

    e = ExprEngine(project)
    e.validate("abs(LC1) + abs(LC2) < 200")                  -> None (ok) or an error message
    e.evaluate("MCC_P > OMI_P", sensors, calcs, seq)          -> value; raises MissingValue / ExprError
"""
import ast
import math
import re

FUNCS = {
    "abs": abs, "min": min, "max": max, "round": round, "sqrt": math.sqrt,
    "pow": pow, "floor": math.floor, "ceil": math.ceil,
}
CONSTS = {"G0": 32.174}
SEQ_VARS = ("SEQ_T", "SEQ_END", "SEQ_RUNNING")
_KEYWORD_NAMES = {"True": True, "False": False}

_ALLOWED_NODES = (
    ast.Expression, ast.BoolOp, ast.BinOp, ast.UnaryOp, ast.Compare, ast.IfExp, ast.Call,
    ast.Name, ast.Constant, ast.Load,
    ast.And, ast.Or, ast.Not, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
)
_LEADING_UNDERSCORE = re.compile(r"(?<![A-Za-z0-9_])_[A-Za-z0-9_]*")


class ExprError(Exception):
    """The expression can't be understood (bad syntax, unknown name, forbidden construct)."""


class MissingValue(Exception):
    """The expression is fine but a sensor it uses has no reading yet."""
    def __init__(self, name):
        super().__init__(f"no reading for {name}")
        self.name = name


class _Compiled:
    __slots__ = ("code", "refs")

    def __init__(self, code, refs):
        self.code = code
        self.refs = refs            # [(key, kind, official_label)]  index i  <->  identifier _v{i}


class ExprEngine:
    def __init__(self, project=None):
        self._alias = {}            # lower-case name -> (key, kind, official label)
        self._sensors = []          # [(label, key)]          for the UI
        self._calcs = []            # [(label, channel id)]
        self._cache = {}
        self._pattern = None
        if project is not None:
            self._build(project)

    # ------------------------------------------------------------------ names
    def _add(self, name, key, kind, label):
        name = (name or "").strip()
        if name and name.lower() not in self._alias:
            self._alias[name.lower()] = (key, kind, label)

    def _build(self, project):
        sensors = []
        for comp in project.components.values():
            if comp.hardware is None or getattr(comp.hardware, "adc", None) is None:
                continue
            key = (comp.extras.get("hw_id") or comp.label or "").strip()
            if not key:
                continue
            sensors.append((comp.label.strip() or key, key))
        for label, key in sensors:                       # official names first: they win any clash
            self._add(label, key, "sensor", label)
        for label, key in sensors:
            self._add(key, key, "sensor", label)         # old hardware ids keep working
        self._sensors = sorted(set(sensors), key=lambda lk: _natural(lk[0]))

        for ch in getattr(project, "calc_channels", []) or []:
            label = (ch.label or ch.id).strip()
            self._add(label, ch.id, "calc", label)
            self._add(ch.id, ch.id, "calc", label)
            self._calcs.append((label, ch.id))

        names = sorted(self._alias, key=len, reverse=True)   # longest first: OPT-1501 before OPT
        if names:
            self._pattern = re.compile(
                r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(n) for n in names) + r")(?![A-Za-z0-9_])",
                re.IGNORECASE)

    def official_names(self) -> list:
        """Every name an operator can type: sensors, calculated channels, functions, sequence vars."""
        return ([l for l, _k in self._sensors] + [l for l, _k in self._calcs]
                + [f + "(" for f in FUNCS] + list(SEQ_VARS))

    def sensor_names(self) -> list:
        return [l for l, _k in self._sensors]

    def calc_names(self) -> list:
        return [l for l, _k in self._calcs]

    def official_for(self, name: str) -> str:
        """The official name for a sensor key / alias (P8 -> MCC_P); the text itself if unknown."""
        hit = self._alias.get((name or "").strip().lower())
        return hit[2] if hit else name

    # --------------------------------------------------------------- rewriting
    def to_official(self, text: str) -> str:
        """Rewrite every hardware id / alias in an expression to its official name (P8 -> MCC_P)."""
        if not text or self._pattern is None:
            return text
        return self._pattern.sub(lambda m: self._alias[m.group(0).lower()][2], text)

    def template_to_official(self, template: str) -> str:
        """Same for message templates: {P8} -> {MCC_P}. Other {tokens} are left alone."""
        if not template:
            return template

        def repl(m):
            hit = self._alias.get(m.group(1).strip().lower())
            return "{" + hit[2] + "}" if hit else m.group(0)
        return re.sub(r"\{([^{}]+)\}", repl, template)

    def annotate(self, expression: str) -> str:
        """'MCC_P > OMI_P' -> 'MCC_P ({MCC_P}) > OMI_P ({OMI_P})' (default alert text)."""
        if self._pattern is None:
            return expression

        def repl(m):
            label = self._alias[m.group(0).lower()][2]
            return f"{label} ({{{label}}})"
        return self._pattern.sub(repl, expression)

    # -------------------------------------------------------------- compiling
    def compile(self, expression: str) -> _Compiled:
        hit = self._cache.get(expression)
        if hit is not None:
            return hit
        text = (expression or "").strip()
        if not text:
            raise ExprError("the expression is empty")
        bad = _LEADING_UNDERSCORE.search(text)
        if bad:
            raise ExprError(f"'{bad.group(0)}' is not allowed")

        refs = []

        def repl(m):
            key, kind, label = self._alias[m.group(0).lower()]
            for i, r in enumerate(refs):
                if r[0] == key and r[1] == kind:
                    return f"_v{i}"
            refs.append((key, kind, label))
            return f"_v{len(refs) - 1}"

        src = self._pattern.sub(repl, text) if self._pattern is not None else text
        try:
            tree = ast.parse(src, mode="eval")
        except SyntaxError:
            raise ExprError("can't read this expression - check brackets and operators "
                            "(sensor names with spaces or dashes must match the P&ID exactly)") from None

        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ExprError(f"'{type(node).__name__}' is not allowed in a rule")
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float, bool)):
                raise ExprError("only numbers are allowed")
            if isinstance(node, ast.Name):
                n = node.id
                if re.fullmatch(r"_v\d+", n) or n in FUNCS or n in CONSTS or n in SEQ_VARS or n in _KEYWORD_NAMES:
                    continue
                raise ExprError(f"unknown name '{n}' - use a sensor name from the P&ID "
                                f"(e.g. {self._example()})")
            if isinstance(node, ast.Call):
                if not (isinstance(node.func, ast.Name) and node.func.id in FUNCS) or node.keywords:
                    raise ExprError("only abs, min, max, round, sqrt, pow, floor and ceil can be called")
        calls = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}    # "abs > 3" is a mistake
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in FUNCS and id(node) not in calls:
                raise ExprError(f"'{node.id}' is a function: write {node.id}( ... )")

        comp = _Compiled(compile(tree, "<rule>", "eval"), refs)
        self._cache[expression] = comp
        return comp

    def _example(self) -> str:
        return ", ".join(l for l, _k in self._sensors[:3]) or "P1"

    def validate(self, expression: str):
        """None when the expression is fine, otherwise a short message for the operator."""
        try:
            self.compile(expression)
            return None
        except ExprError as e:
            return str(e)

    # ------------------------------------------------------------- evaluating
    def evaluate(self, expression: str, sensors: dict, calcs: dict = None, seq: dict = None):
        """Value of the expression. MissingValue if a sensor/channel it needs has no reading yet,
        ExprError if it can't be compiled, ArithmeticError/ValueError on bad math (e.g. divide by 0)."""
        comp = self.compile(expression)
        env = dict(CONSTS)
        env.update(_KEYWORD_NAMES)
        seq = seq or {}
        env["SEQ_T"] = float(seq.get("SEQ_T", math.nan))
        env["SEQ_END"] = float(seq.get("SEQ_END", math.nan))
        env["SEQ_RUNNING"] = bool(seq.get("SEQ_RUNNING", False))
        for i, (key, kind, label) in enumerate(comp.refs):
            if kind == "calc":
                v = (calcs or {}).get(key)
            else:
                v = sensors.get(key.upper())
                if v is None:
                    v = sensors.get(key)
            if v is None:
                raise MissingValue(label)
            env[f"_v{i}"] = v
        return eval(comp.code, {"__builtins__": {}, **FUNCS}, env)

    def message_context(self, sensors: dict, calcs: dict = None) -> dict:
        """{official name: live value} so a template can say {MCC_P} or {Thrust}. Hardware ids stay
        available through the sensors dict itself."""
        ctx = {}
        for label, key in self._sensors:
            v = sensors.get(key.upper(), sensors.get(key))
            if v is not None:
                ctx[label] = v
                ctx[label.upper()] = v
        for label, cid in self._calcs:
            v = (calcs or {}).get(cid)
            if v is not None:
                ctx[label] = v
                ctx[label.upper()] = v
        return ctx


def _natural(text: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]
