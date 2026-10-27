# GUI_MAIN.py
# This file is the starting point for the Elysium2 GUI
import sys
import importlib
import importlib.util
import subprocess

# The GUI code uses Python 3.10 syntax (e.g. "Component | None" type hints), so an
# older interpreter fails deep inside an import. Stop here with a clear message instead.
if sys.version_info < (3, 10):
    sys.exit(f"RED Control System needs Python 3.10 or newer, but this is Python "
             f"{sys.version.split()[0]} ({sys.executable}).\n"
             "Run setup_conda.bat in this folder (double-click it, or ./setup_conda.bat in "
             "Git Bash) to create the red-gui environment and launch the GUI from it.")


# PyQt5 aborts the whole process (SIGABRT) when a Python exception escapes a slot and
# sys.excepthook is still the default one - that is how the GUI used to die at random.
# Log it (stderr + gui_errors.log) and carry on instead. Installed before anything else
# so the loading stage is covered too.
import faulthandler
import os
import threading
import time
import traceback

_ERROR_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_errors.log")
try:
    _fault_file = open(_ERROR_LOG, "a")             # kept open: faulthandler writes to it on a native crash
    faulthandler.enable(_fault_file, all_threads=True)
except OSError:
    faulthandler.enable(all_threads=True)


def _log_unhandled(exc_type, exc, tb, where="unhandled exception"):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    sys.stderr.write(text)
    try:
        with open(_ERROR_LOG, "a") as f:
            f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} {where} ---\n{text}")
    except OSError:
        pass


def _log_thread_unhandled(args):
    if args.exc_type is SystemExit:
        return
    name = args.thread.name if args.thread else "?"
    _log_unhandled(args.exc_type, args.exc_value, args.exc_traceback,
                   f"unhandled exception in thread '{name}'")


sys.excepthook = _log_unhandled
threading.excepthook = _log_thread_unhandled    # plain Python threads don't go through sys.excepthook


# import name -> pip package name
REQUIRED = {
    "openpyxl": "openpyxl",
    "pyqtspinner": "pyqtspinner",
    "matplotlib": "matplotlib",
    "CoolProp": "CoolProp",
}
OPTIONAL_PACKAGES = {"CoolProp"}   # the app falls back gracefully without these


def pip_install(pkg):
    cmd = [sys.executable, "-m", "pip", "install", pkg]
    if pkg in OPTIONAL_PACKAGES:
        # Never compile optional packages from source (CoolProp's sdist needs Python 3.9+ and a
        # C++ toolchain, and can take minutes before failing). Use a prebuilt wheel or skip it.
        cmd.insert(4, "--only-binary=:all:")
    subprocess.check_call(cmd)


# PyQt5 draws the splash itself, so it is the one dependency that must be installed before it appears.
try:
    import PyQt5.QtWidgets  # a leftover empty PyQt5 folder passes find_spec("PyQt5"), so import the real thing
except ImportError:
    print("Installing PyQt5...")
    pip_install("PyQt5")
    importlib.invalidate_caches()
    for name in [m for m in sys.modules if m == "PyQt5" or m.startswith("PyQt5.")]:
        del sys.modules[name]

from PyQt5.QtWidgets import QApplication, QMainWindow
from GUI_SPLASH import SplashScreen


def check_dependencies():
    """Install any missing package (shown on the splash as the first load step)."""
    importlib.invalidate_caches()
    for mod, pkg in REQUIRED.items():
        if importlib.util.find_spec(mod) is not None:
            continue
        try:
            pip_install(pkg)
        except subprocess.CalledProcessError:
            if mod not in OPTIONAL_PACKAGES:
                raise RuntimeError(f"Could not install required package '{pkg}'")
    importlib.invalidate_caches()


LOAD_STEPS = [
    ("Checking dependencies", None),
    ("Loading plotting engine", "matplotlib.backends.backend_qt5agg"),
    ("Loading thermodynamics", "CoolProp.CoolProp"),
    ("Loading data export", "openpyxl"),
    ("Loading communications", "GUI_COMMS"),
    ("Loading controller", "GUI_CONTROLLER"),
    ("Loading P&ID tools", "PID_EDITOR"),
    ("Loading P&ID viewer", "PID_VIEW"),
    ("Loading sequence editor", "PROJECT_SEQUENCE_EDITOR"),
    ("Loading telemetry & graphs", "GUI_GRAPHS"),
    ("Loading main layout", "GUI_LAYOUT"),
]

OPTIONAL = {"CoolProp.CoolProp"}   # the app falls back gracefully without these


def load(mod):
    if mod is None:
        return check_dependencies()
    try:
        importlib.import_module(mod)
    except ImportError:
        if mod not in OPTIONAL:
            raise


if __name__ == "__main__":
    app = QApplication(sys.argv)
    state = {}

    # The loading screen is the content of the app window itself. It has the same title and
    # geometry as the real MainWindow, which replaces it in place the moment loading finishes.
    shell = QMainWindow()
    shell.setWindowTitle("RED Control System")
    shell.setGeometry(10, 10, 1400, 820)
    splash = SplashScreen(shell)
    shell.setCentralWidget(splash)

    def build():
        state["window"] = importlib.import_module("GUI_LAYOUT").MainWindow()

    def swap():
        window = state["window"]
        window.setGeometry(shell.geometry())
        if shell.isMaximized():
            window.showMaximized()
        else:
            window.show()
        shell.close()

    splash.finished_loading.connect(swap)
    shell.show()
    # Imports run on the GUI thread (importing PyQt modules off it races the splash's painting
    # and can segfault). Only the dependency check - pip, no Qt - runs in the background.
    splash.start([(label, lambda m=mod: load(m), mod is None) for label, mod in LOAD_STEPS], build)
    sys.exit(app.exec_())
