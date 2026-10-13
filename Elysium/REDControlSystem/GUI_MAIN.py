# GUI_MAIN.py
# This file is the starting point for the Elysium2 GUI
#
# Optional read-only viewer sharing (see GUI_REMOTE.py):
#   python GUI_MAIN.py --serve [PORT] [--token SECRET] [--bind ADDR]
# Viewers then run:  python GUI_VIEWER.py HOST[:PORT] --token SECRET
import argparse
import sys
from PyQt5.QtWidgets import QApplication
from GUI_LAYOUT import MainWindow

def _parse_args(argv):
    p = argparse.ArgumentParser(description="RED Control System (operator GUI)")
    p.add_argument("--serve", nargs="?", const=8900, type=int, metavar="PORT",
                   help="share read-only telemetry with viewers on PORT (default 8900)")
    p.add_argument("--token", default="", help="shared secret viewers must present")
    p.add_argument("--bind", default="0.0.0.0",
                   help="address to listen on; use the router-side address to keep "
                        "viewer traffic off the Teensy Ethernet interface")
    return p.parse_known_args(argv)   # leave unknown (Qt) args alone

if __name__ == "__main__":
    args, qt_args = _parse_args(sys.argv[1:])
    app = QApplication([sys.argv[0]] + qt_args)
    window = MainWindow()
    window.show()

    if args.serve is not None:
        from GUI_REMOTE import TelemetryServer
        server = TelemetryServer(window.controller, host=args.bind, port=args.serve,
                                 token=args.token, parent=window)
        server.log.connect(lambda msg: print(f"[TelemetryServer] {msg}"))
        server.start()
        window.telemetry_server = server   # keep a reference alive
        if not args.token:
            print("[TelemetryServer] WARNING: no --token set; any device on the "
                  "network can watch telemetry.")

    sys.exit(app.exec_())
