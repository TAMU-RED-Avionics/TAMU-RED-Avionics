"""Keep the screen (and the machine) awake while the GUI is open, like a video player does.

start() asks the OS not to dim/turn off the display or go to sleep; stop() (also run when the app
quits, and by the OS if the process dies) gives that back. Nothing here touches a setting
permanently. A corporate/lock-screen policy that forces a lock after N minutes can still win.
"""
import ctypes
import os
import shutil
import subprocess
import sys

# SetThreadExecutionState flags (Windows)
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002

_helper = None      # macOS / Linux helper process that holds the inhibit


def start() -> str:
    """Returns a short description of what was done (for logging); never raises."""
    global _helper
    try:
        if sys.platform.startswith("win"):
            # Applies to the calling thread until it exits or stop() clears it: call from the GUI thread.
            ctypes.windll.kernel32.SetThreadExecutionState(
                _ES_CONTINUOUS | _ES_DISPLAY_REQUIRED | _ES_SYSTEM_REQUIRED)
            return "Windows: display + system kept awake"
        if sys.platform == "darwin":
            # caffeinate exits by itself when the GUI process (-w) does.
            _helper = subprocess.Popen(["caffeinate", "-d", "-i", "-w", str(os.getpid())])
            return "macOS: caffeinate running"
        if shutil.which("systemd-inhibit"):
            _helper = subprocess.Popen(
                ["systemd-inhibit", "--what=idle:sleep", "--who=RED Control System",
                 "--why=Live test in progress", "--mode=block",
                 "sh", "-c", f"while kill -0 {os.getpid()} 2>/dev/null; do sleep 5; done"])
            return "Linux: systemd-inhibit running"
        return "no keep-awake method available on this system"
    except Exception as e:      # the GUI must still start if this fails
        return f"keep-awake failed: {e}"


def stop():
    global _helper
    try:
        if sys.platform.startswith("win"):
            ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
        elif _helper is not None:
            _helper.terminate()
    except Exception:
        pass
    _helper = None
