"""Background data recorder.

The old recorder appended every row to an in-memory openpyxl worksheet on the GUI thread and
saved the whole workbook (hundreds of thousands of cells) on the GUI thread when you pressed Stop,
which froze the window ("Not Responding") and lost everything if the GUI died. This one:

  * streams rows to a plain CSV file on a worker thread while recording (cheap for the GUI thread,
    flushed about once a second, so a crash loses at most a second of data), and
  * converts the CSV to the .xlsx the Telemetry tab reads on the same worker thread after Stop,
    then deletes the CSV. If the GUI dies mid-recording, the next start-up finishes the conversion
    (recover_orphans).

Everything the GUI thread does here (write / stop) returns immediately.
"""
import csv
import os
import queue
import threading
import time

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt5.QtCore import QObject, pyqtSignal

CSV_SUFFIX = ".recording.csv"       # a recording in progress (or one that never got converted)
_STOP = object()
_SENSOR_FIRST_COL = 3               # columns 0-2: local time, Teensy time, spacer; sensors follow
_TRAILING_TEXT_COLS = 3             # Control State, Event Type, Event Details


def csv_path_for(xlsx_path: str) -> str:
    return xlsx_path[:-5] + CSV_SUFFIX if xlsx_path.lower().endswith(".xlsx") else xlsx_path + CSV_SUFFIX


def convert_csv_to_xlsx(csv_path: str, xlsx_path: str) -> int:
    """Stream a recording CSV into an .xlsx (write-only workbook: constant memory, fast).
    The file appears under its final name only once it is complete. Returns the data row count."""
    tmp_path = xlsx_path + ".tmp"
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("DAQ")
    rows = 0
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            raise ValueError("recording file is empty")
        ws.freeze_panes = "A2"
        head_cells = []
        for text in header:
            cell = WriteOnlyCell(ws, value=text if text != "" else None)
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="D9D9D9")
            cell.alignment = Alignment(horizontal="center")
            head_cells.append(cell)
        ws.append(head_cells)

        text_start = len(header) - _TRAILING_TEXT_COLS
        for row in reader:
            out = []
            for i, v in enumerate(row):
                if v == "":
                    out.append(None)
                elif _SENSOR_FIRST_COL <= i < text_start:
                    try:
                        out.append(float(v))
                    except ValueError:
                        out.append(v)
                else:
                    out.append(v)
            ws.append(out)
            rows += 1
            if rows % 2000 == 0:
                time.sleep(0.001)       # let the GUI thread breathe during a long conversion
    wb.save(tmp_path)
    os.replace(tmp_path, xlsx_path)
    return rows


class DaqRecorder(QObject):
    """One recording. write() and stop() never block."""
    finished = pyqtSignal(str, bool, str)       # xlsx path, ok, message

    def __init__(self, xlsx_path: str, header: list, parent=None):
        super().__init__(parent)
        self.xlsx_path = xlsx_path
        self.csv_path = csv_path_for(xlsx_path)
        self._header = list(header)
        self._q: "queue.Queue" = queue.Queue()
        self._active = True
        self._error = ""
        os.makedirs(os.path.dirname(os.path.abspath(self.csv_path)), exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="daq-writer", daemon=True)
        self._thread.start()

    @property
    def active(self) -> bool:
        return self._active

    def write(self, row: list):
        if self._active:
            self._q.put(row)

    def stop(self):
        """Ask the worker to finish: it writes the remaining rows, converts to .xlsx and emits finished."""
        if self._active:
            self._active = False
            self._q.put(_STOP)

    def _run(self):
        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(self._header)
                fh.flush()
                last_flush = time.monotonic()
                while True:
                    try:
                        item = self._q.get(timeout=0.25)
                    except queue.Empty:
                        fh.flush()
                        last_flush = time.monotonic()
                        continue
                    if item is _STOP:
                        break
                    writer.writerow(item)
                    if time.monotonic() - last_flush >= 1.0:
                        fh.flush()
                        last_flush = time.monotonic()
        except Exception as e:                  # disk full, file locked, ...
            self._error = f"could not write {self.csv_path}: {e}"
            self.finished.emit(self.xlsx_path, False, self._error)
            return
        try:
            rows = convert_csv_to_xlsx(self.csv_path, self.xlsx_path)
        except Exception as e:
            self.finished.emit(self.xlsx_path, False,
                               f"saved the raw data to {self.csv_path} but could not build the .xlsx: {e}")
            return
        try:
            os.remove(self.csv_path)
        except OSError:
            pass
        self.finished.emit(self.xlsx_path, True, f"{rows} rows")

    def wait(self, timeout_s: float = 120.0) -> bool:
        """Block (used only when the app is closing) until the worker is done."""
        self._thread.join(timeout_s)
        return not self._thread.is_alive()


def recover_orphans(data_dir: str, on_done=None):
    """Finish recordings that never got converted (the GUI died mid-recording). Runs in the background."""
    def work():
        recovered = []
        try:
            names = [n for n in os.listdir(data_dir) if n.endswith(CSV_SUFFIX)]
        except OSError:
            return
        for n in names:
            csv_path = os.path.join(data_dir, n)
            xlsx_path = csv_path[: -len(CSV_SUFFIX)] + ".xlsx"
            if os.path.exists(xlsx_path):
                continue
            try:
                convert_csv_to_xlsx(csv_path, xlsx_path)
                os.remove(csv_path)
                recovered.append(os.path.basename(xlsx_path))
            except Exception:
                pass
        if recovered and on_done:
            on_done(recovered)
    threading.Thread(target=work, name="daq-recover", daemon=True).start()
