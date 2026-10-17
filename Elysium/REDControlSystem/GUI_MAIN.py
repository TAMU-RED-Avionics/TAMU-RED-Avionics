# GUI_MAIN.py
# This file is the starting point for the Elysium2 GUI
import sys
import importlib
import importlib.util
import subprocess

# import name -> pip package name
REQUIRED = {
    "openpyxl": "openpyxl",
    "pyqtspinner": "pyqtspinner",
    "matplotlib": "matplotlib",
    "CoolProp": "CoolProp",
}
OPTIONAL_PACKAGES = {"CoolProp"}   # the app falls back gracefully without these


def pip_install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])


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
    splash.start([(label, lambda m=mod: load(m)) for label, mod in LOAD_STEPS], build)
    sys.exit(app.exec_())
