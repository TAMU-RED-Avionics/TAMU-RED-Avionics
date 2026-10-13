# GUI_VIEWER.py
# Read-only telemetry viewer. Connects to a host GUI started with --serve.
#   python GUI_VIEWER.py HOST[:PORT] [--token SECRET] [--name NAME]
# There is no command path in this program: it can watch, not actuate.
import argparse
import sys
import time

from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QHeaderView, QLabel, QListWidget, QMainWindow,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from GUI_REMOTE import DEFAULT_PORT, ViewerLink, ViewerState

LINK_COLORS = {
    "LIVE": "#2e7d32", "CONNECTING": "#f9a825", "STALE": "#ef6c00",
    "DISCONNECTED": "#c62828", "REJECTED": "#c62828",
}
MODE_COLORS = {
    "SAFE": "#1565c0", "MANUAL": "#2e7d32", "LOCKED": "#6a1b9a", "ABORT": "#c62828",
}
SENSOR_STALE_S = 2.0


class _Bridge(QObject):
    message = pyqtSignal(dict)


class ViewerWindow(QMainWindow):
    def __init__(self, host: str, port: int, token: str, name: str):
        super().__init__()
        self.setWindowTitle(f"RED Control System - VIEWER (read-only) - {host}:{port}")
        self.resize(900, 700)
        self.state = ViewerState()
        self.host_label = f"{host}:{port}"

        self.link_lbl = QLabel()
        self.mode_lbl = QLabel()
        self.teensy_lbl = QLabel()
        self.project_lbl = QLabel("Project: -")
        for lbl in (self.link_lbl, self.mode_lbl, self.teensy_lbl):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMargin(6)
        self.abort_lbl = QLabel()
        self.abort_lbl.setAlignment(Qt.AlignCenter)
        self.abort_lbl.setMargin(8)
        self.abort_lbl.setStyleSheet("background:#c62828;color:white;font-weight:bold;")
        self.abort_lbl.hide()

        top = QHBoxLayout()
        top.addWidget(self.link_lbl, 1)
        top.addWidget(self.mode_lbl, 1)
        top.addWidget(self.teensy_lbl, 1)

        self.sensor_tbl = self._table(["Sensor", "Value"])
        self.valve_tbl = self._table(["Valve / actuator", "State"])
        tables = QHBoxLayout()
        tables.addWidget(self.sensor_tbl, 1)
        tables.addWidget(self.valve_tbl, 1)

        self.warn_list = QListWidget()
        self.warn_list.setMaximumHeight(110)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(self.abort_lbl)
        root.addWidget(self.project_lbl)
        root.addLayout(tables, 1)
        root.addWidget(QLabel("Warnings"))
        root.addWidget(self.warn_list)
        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._bridge = _Bridge()
        self._bridge.message.connect(self._on_message)
        self.link = ViewerLink(host, port, token, name,
                               on_message=self._bridge.message.emit)
        self.link.start()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(100)
        self._refresh()

    @staticmethod
    def _table(headers):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionMode(QTableWidget.NoSelection)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        return t

    def _on_message(self, msg: dict):
        self.state.apply(msg)

    @staticmethod
    def _badge(lbl: QLabel, text: str, color: str):
        lbl.setText(text)
        lbl.setStyleSheet(f"background:{color};color:white;font-weight:bold;border-radius:4px;")

    def _refresh(self):
        s = self.state
        self._badge(self.link_lbl, f"HOST LINK: {s.link}", LINK_COLORS.get(s.link, "#555"))
        live = s.link in ("LIVE", "STALE")
        self._badge(self.mode_lbl, f"MODE: {s.mode or '-'}" if live else "MODE: -",
                    MODE_COLORS.get(s.mode, "#555") if live else "#555")
        self._badge(self.teensy_lbl, "TEENSY: CONNECTED" if (live and s.host_link) else "TEENSY: NOT CONNECTED",
                    "#2e7d32" if (live and s.host_link) else "#555")
        if s.abort:
            self.abort_lbl.setText(f"ABORT: {s.abort.get('abort_type', '')} - {s.abort.get('reason', '')}")
            self.abort_lbl.show()
        else:
            self.abort_lbl.hide()
        name = (s.project or {}).get("name")
        self.project_lbl.setText(f"Project: {name}" if name else "Project: -")

        now = time.monotonic()
        stale_all = s.link != "LIVE"
        self._fill(self.sensor_tbl,
                   [(k, f"{v:.2f}", stale_all or now - s.sensor_rx.get(k, 0) > SENSOR_STALE_S)
                    for k, v in sorted(s.sensors.items(), key=lambda kv: (len(kv[0]), kv[0]))])
        rows = [(k, v, stale_all) for k, v in sorted(s.valves.items())]
        for k, pct in sorted(s.actuators.items()):
            rows.append((f"{k} (position)", f"{pct:.0f}%", stale_all))
        self._fill(self.valve_tbl, [(k, ("OPEN" if v is True else "CLOSED" if v is False else str(v)), st)
                                    for k, v, st in rows])

        if [self.warn_list.item(i).text() for i in range(self.warn_list.count())] != s.warnings:
            self.warn_list.clear()
            self.warn_list.addItems(s.warnings)

    @staticmethod
    def _fill(table: QTableWidget, rows):
        table.setRowCount(len(rows))
        for r, (k, v, stale) in enumerate(rows):
            for c, text in enumerate((k, v)):
                item = table.item(r, c)
                if item is None:
                    item = QTableWidgetItem()
                    table.setItem(r, c, item)
                if item.text() != text:
                    item.setText(text)
                item.setForeground(QColor("#888888" if stale else
                                          "#2e7d32" if text == "OPEN" else "#000000"))

    def closeEvent(self, event):
        self.link.stop()
        super().closeEvent(event)


def parse_host(arg: str):
    host, _, port = arg.partition(":")
    return host, int(port) if port else DEFAULT_PORT


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="RED Control System read-only viewer")
    ap.add_argument("host", help="host GUI address, HOST or HOST:PORT")
    ap.add_argument("--token", default="")
    ap.add_argument("--name", default="viewer")
    args, qt_args = ap.parse_known_args()
    h, p = parse_host(args.host)
    app = QApplication([sys.argv[0]] + qt_args)
    win = ViewerWindow(h, p, args.token, args.name)
    win.show()
    sys.exit(app.exec_())
