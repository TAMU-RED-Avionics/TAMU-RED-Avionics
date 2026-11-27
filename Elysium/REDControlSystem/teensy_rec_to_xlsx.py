"""Convert a Teensy flight-recorder file (RECnnnn.BIN from the SD card) to an .xlsx the Telemetry tab opens.

    python teensy_rec_to_xlsx.py REC0001.BIN                   -> REC0001.xlsx next to it
    python teensy_rec_to_xlsx.py REC0001.BIN -o out.xlsx --spec PIDs/E2_RED_Spec.red

The Teensy writes this file only when it shuts down (comms loss, abort) while the GUI was running an
automatic (sequence) recording: it is what the BOARD saw, at full rate (one sample per 10 ms) with its
own clock, up to the last ~36 s before the shutdown. See "Flight recorder" in E2_Teensy.ino.

Columns follow the GUI's recordings (sensor names from the P&ID, the Teensy timestamp in microseconds
from boot) so the file plots the same way. Differences from a GUI recording:
  * load cells in a version 2 file are RAW counts: they are converted to pounds with the slope / intercept
    (cal_gain / cal_offset) saved in the P&ID. A cell with no calibration there is left in raw counts and its
    column is named "<name> (raw)". Version 1 files already have pounds;
  * pressures are computed straight from the raw loop current, WITHOUT the firmware's smoothing, and
    are left blank when the loop current is under 3.85 mA (the GUI shows that as NO SIGNAL);
  * extra "mA <name>" columns hold the raw loop currents - a supply or wiring problem shows up there
    (a collapsed loop reads ~0 mA);
  * extra "FMV (Bray) %" column; and Event Type / Event Details list every output switching
    on or off (OUTPUT_ON / OUTPUT_OFF, e.g. IGN-1) plus the shutdown reason on the last row, so the
    igniter pulse lengths can be read straight off the timestamps;
  * version 3 files also record the Ethernet chip's link status every sample: a link column (1 up / 0 down /
    -1 chip not answering) and ETHERNET_LINK_DOWN / _UP / ETHERNET_CHIP_SILENT events, so you can see exactly
    when the link dropped relative to the sensor data;
  * if RECnnnn.TXT (the Teensy's diagnostics report: reset cause, Ethernet chip registers with a verdict,
    counters, event log) is next to the .BIN, it becomes a second sheet "Teensy diagnostics".
"""
import argparse
import json
import math
import os
import struct
import sys

HEADER_SIZE = 512
MAGIC = b"ELYREC1\x00"
# struct layouts: keep in step with RecSample / RecHeader in E2_Teensy.ino (the firmware static_asserts the sizes)
SAMPLE_FMT_V2 = "<Q12H12h6fHH"                          # versions 1 and 2: 84 bytes
SAMPLE_FMT_V3 = "<Q12H12h6fHHHH"                        # version 3: + Ethernet chip BMSR and PHYSTS: 88 bytes
SAMPLE_SIZE = struct.calcsize(SAMPLE_FMT_V2)
HEADER_FMT = "<8sHHIQQ24s12B12fff16B"
PT_NO_SIGNAL_MA = 3.85

OUT_NAMES = {
    0x0A: "NCS1", 0x0B: "NCS2", 0x0C: "NCS3", 0x04: "NCS5", 0x06: "PA-BV3", 0x0D: "PNEUMA",
    0x0E: "BRAY-AUX", 0x10: "PA-BV1", 0x11: "PA-BV2", 0x12: "FP-1201", 0x13: "AP-1601",
    0x14: "FV-1202", 0x20: "GV-1", 0x21: "GV-2", 0x30: "IGN-1", 0x31: "IGN-2", 0x40: "GIMBAL",
}


def load_calibrations(spec_path):
    """{sensor adc id: (slope, intercept)} from cal_gain / cal_offset in the P&ID, or {}."""
    cals = {}
    try:
        with open(spec_path, encoding="utf-8") as fh:
            d = json.load(fh)
        comps = d.get("components", [])
        comps = comps.values() if isinstance(comps, dict) else comps
        for c in comps:
            adc = (c.get("hardware") or {}).get("adc")
            ex = c.get("extras") or {}
            if adc is not None and "cal_gain" in ex:
                cals[int(adc)] = (float(ex["cal_gain"]), float(ex.get("cal_offset", 0.0)))
    except (OSError, ValueError):
        pass
    return cals


def load_labels(spec_path):
    """{sensor adc id: P&ID label} from the project file, or {} if it can't be read."""
    labels = {}
    try:
        with open(spec_path, encoding="utf-8") as fh:
            d = json.load(fh)
        comps = d.get("components", [])
        comps = comps.values() if isinstance(comps, dict) else comps
        for c in comps:
            adc = (c.get("hardware") or {}).get("adc")
            if adc is not None and c.get("label"):
                labels[int(adc)] = c["label"]
    except (OSError, ValueError):
        pass
    return labels


def read_recording(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < HEADER_SIZE or data[:8] != MAGIC:
        raise ValueError("not a Teensy flight-recorder file (bad header)")
    hsize = struct.calcsize(HEADER_FMT)
    f = struct.unpack(HEADER_FMT, data[:hsize])
    hdr = {
        "version": f[1], "sample_size": f[2], "count": f[3], "rec_start_us": f[4], "dump_us": f[5],
        "reason": f[6].split(b"\0", 1)[0].decode("ascii", "replace"),
        "pt_num_for_ch": list(f[7:19]), "pt_fs_psi": list(f[19:31]),
        "pt_psi_at_4ma": f[31], "pt_atm_psi": f[32], "out_ids": list(f[33:49]),
    }
    fmt = SAMPLE_FMT_V3 if hdr["version"] >= 3 else SAMPLE_FMT_V2
    if hdr["version"] not in (1, 2, 3) or hdr["sample_size"] != struct.calcsize(fmt):
        raise ValueError(f"unsupported file version {hdr['version']} / record size {hdr['sample_size']}")
    size = struct.calcsize(fmt)
    body = data[HEADER_SIZE:]
    n = min(hdr["count"], len(body) // size)                # a truncated file (power lost mid-write) keeps what is whole
    samples = [struct.unpack_from(fmt, body, i * size) for i in range(n)]
    return hdr, samples


def convert(path, out_path, spec_path):
    hdr, samples = read_recording(path)
    labels = load_labels(spec_path)
    cals = load_calibrations(spec_path)
    lc_raw_counts = hdr["version"] >= 2                     # version 2: load cells are raw counts

    def name(adc_id, fallback):
        return labels.get(adc_id, fallback)

    # --- columns -------------------------------------------------------------------------
    # PTs: ADS channel i carries PT number pt_num_for_ch[i] (sensor id = PT number + 1)
    pt_cols = sorted(range(12), key=lambda i: hdr["pt_num_for_ch"][i])
    pt_names = {i: name(hdr["pt_num_for_ch"][i] + 1, f"P{hdr['pt_num_for_ch'][i] + 1}") for i in pt_cols}
    tc_idx = [i for i in range(12) if any(s[1 + 12 + i] != 0x7FFF for s in samples)]
    tc_names = {i: name(0x64 + i, f"TC{i + 1}") for i in tc_idx}
    lc_idx = [i for i in range(6) if any(not math.isnan(s[1 + 24 + i]) for s in samples)]
    lc_names = {i: name(0x19 + i, f"LC{i + 1}") for i in lc_idx}
    lc_cal = {i: (cals.get(0x19 + i) if lc_raw_counts else (1.0, 0.0)) for i in lc_idx}      # None = leave raw
    for i in lc_idx:
        if lc_cal[i] is None:
            lc_names[i] += " (raw)"

    header = ["Local Time (YYYY-MM-DD HH:mm:ss)", "Teensy Timestamp (µs from boot)", ""]
    header += [pt_names[i] for i in pt_cols] + [""]
    header += [tc_names[i] for i in tc_idx] + [""]
    header += [lc_names[i] for i in lc_idx] + [""]
    header += ["Control State", "Event Type", "Event Details"]
    header += [""] + [f"mA {pt_names[i]}" for i in pt_cols] + ["FMV (Bray) %"]
    has_link = hdr["version"] >= 3
    if has_link:
        header += ["Ethernet link (1=up 0=down -1=chip silent)", "PHY BMSR (hex)", "PHY PHYSTS (hex)"]

    def psi(mA, ch):
        fs = hdr["pt_fs_psi"][ch]
        return hdr["pt_psi_at_4ma"] + (mA - 4.0) / 16.0 * (fs - hdr["pt_psi_at_4ma"]) + hdr["pt_atm_psi"]

    out_ids = hdr["out_ids"]
    rows = []
    prev_mask = None
    prev_link = None
    for k, s in enumerate(samples):
        us = s[0]
        mA = [v / 1000.0 for v in s[1:13]]
        tc = s[13:25]
        lc = s[25:31]
        mask, bray = s[31], s[32]
        events = []
        for bit, oid in enumerate(out_ids):
            on = bool(mask & (1 << bit))
            was = None if prev_mask is None else bool(prev_mask & (1 << bit))
            nm = OUT_NAMES.get(oid, f"0x{oid:02X}")
            if was is None and on:
                events.append(("OUTPUT_ON", f"{nm} (already on when the recording began)"))
            elif was is not None and on != was:
                events.append(("OUTPUT_ON" if on else "OUTPUT_OFF", nm))
        prev_mask = mask
        link_cols = []
        if has_link:
            bmsr, phy_sts = s[33], s[34]
            state = -1 if bmsr == 0 else (1 if bmsr & 4 else 0)
            if prev_link is not None and state != prev_link:
                events.append(("ETHERNET_LINK_UP" if state == 1 else
                               "ETHERNET_CHIP_SILENT" if state == -1 else "ETHERNET_LINK_DOWN",
                               f"BMSR=0x{bmsr:04X} PHYSTS=0x{phy_sts:04X}"))
            prev_link = state
            link_cols = [state, f"0x{bmsr:04X}", f"0x{phy_sts:04X}"]
        base = [""] * 3
        base[1] = us
        row = list(base)
        row += [(round(psi(mA[i], i), 4) if mA[i] >= PT_NO_SIGNAL_MA else None) for i in pt_cols] + [None]
        row += [(tc[i] / 16.0 if tc[i] != 0x7FFF else None) for i in tc_idx] + [None]
        row += [(None if math.isnan(lc[i]) else
                 round(lc[i] * (lc_cal[i][0] if lc_cal[i] else 1.0) + (lc_cal[i][1] if lc_cal[i] else 0.0), 4))
                for i in lc_idx] + [None]
        extra = [None] + [mA[i] for i in pt_cols] + [bray / 100.0] + link_cols
        ev = events or [("", "")]
        for j, (et, ed) in enumerate(ev):                       # one row per event, the sample repeated
            rows.append(row + ["", et, ed] + extra)
    if samples:
        last = rows[-1]
        rows.append(last[:-len(extra) - 3] + ["", "TEENSY_SHUTDOWN", f"reason: {hdr['reason']}"] + extra)

    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("DAQ")
    ws.freeze_panes = "A2"
    from openpyxl.cell import WriteOnlyCell
    head = []
    for t in header:
        c = WriteOnlyCell(ws, value=t if t != "" else None)
        c.font = Font(bold=True)
        head.append(c)
    ws.append(head)
    for r in rows:
        ws.append([None if v == "" else v for v in r])
    # The Teensy's own diagnostics report (RECnnnn.TXT beside the .BIN): reset cause, Ethernet chip registers, event log
    txt = os.path.splitext(path)[0] + ".TXT"
    if not os.path.isfile(txt):
        txt = os.path.splitext(path)[0] + ".txt"
    if os.path.isfile(txt):
        ds = wb.create_sheet("Teensy diagnostics")
        with open(txt, encoding="utf-8", errors="replace") as fh:
            for line in fh.read().splitlines():
                ds.append([line])
    wb.save(out_path)
    span = (samples[-1][0] - samples[0][0]) / 1e6 if len(samples) > 1 else 0.0
    return len(samples), span, hdr["reason"]


def fix_path(path):
    """Accept Windows-style paths when this runs under Linux/WSL: backslashes, \\wsl.localhost\\<distro>\\...
    and C:\\... (-> /mnt/c/...). Anything that already exists is left alone."""
    if os.path.exists(path) or "\\" not in path:
        return path
    p = path.replace("\\", "/")
    low = p.lower()
    for prefix in ("//wsl.localhost/", "//wsl$/"):
        if low.startswith(prefix):                      # //wsl.localhost/Ubuntu/home/... -> /home/...
            rest = p[len(prefix):]
            return "/" + rest.split("/", 1)[1] if "/" in rest else p
    if len(p) > 2 and p[1] == ":" and p[0].isalpha():   # C:/Users/... -> /mnt/c/Users/...
        return f"/mnt/{p[0].lower()}/{p[3:].lstrip('/')}"
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("bin", help="RECnnnn.BIN from the Teensy's SD card")
    ap.add_argument("-o", "--out", help="output .xlsx (default: next to the input)")
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--spec", default=os.path.join(here, "PIDs", "E2_RED_Spec.red"),
                    help="P&ID file used to name the sensors")
    a = ap.parse_args(argv)
    a.bin = fix_path(a.bin)
    out = fix_path(a.out) if a.out else os.path.splitext(a.bin)[0] + ".xlsx"
    n, span, reason = convert(a.bin, out, a.spec)
    print(f"{n} samples, {span:.1f} s, shutdown reason: {reason} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
