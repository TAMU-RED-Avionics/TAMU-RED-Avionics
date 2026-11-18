"""Display unit for temperatures.

Everything inside the GUI is in degrees Celsius: what the firmware sends, the saved data files, abort
thresholds, actuation conditions and every calculation formula (e.g. TC1 in an expression is degC).
This switch ONLY changes what the live displays show (the sensor sidebar, the P&ID callouts and the
live graphs); it never changes a stored or computed value. The choice is remembered between runs.
"""
import os
from PyQt5.QtCore import QObject, QSettings, pyqtSignal

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gui_settings.ini")
_KEY = "display/temperature_fahrenheit"


class _Units(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.fahrenheit = False
        try:
            v = QSettings(_SETTINGS_PATH, QSettings.IniFormat).value(_KEY, False)
            self.fahrenheit = str(v).lower() in ("true", "1")
        except Exception:
            pass

    def set_fahrenheit(self, on: bool):
        on = bool(on)
        if on == self.fahrenheit:
            return
        self.fahrenheit = on
        try:
            st = QSettings(_SETTINGS_PATH, QSettings.IniFormat)
            st.setValue(_KEY, on)
            st.sync()
        except Exception:
            pass
        self.changed.emit()

    def temp(self, celsius: float) -> float:
        """A Celsius reading as it should be displayed (NaN stays NaN)."""
        return celsius * 9.0 / 5.0 + 32.0 if self.fahrenheit and celsius == celsius else celsius

    def temp_unit(self) -> str:
        return "°F" if self.fahrenheit else "°C"


units = _Units()
