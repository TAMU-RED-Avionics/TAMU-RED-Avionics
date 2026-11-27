# Changelog


---

## 11/27/2026

### Load cells are sent as raw counts; calibration lives in the P&ID
*Flash the new firmware and update the GUI + P&ID together.*
- **Teensy** sends each load cell as a raw count (`PKT_RAW`, 10 Hz). `LC_SLOPE` / `LC_INTERCEPT` are gone from the firmware
  (the last values are kept in a comment and were copied into the P&ID).
- **P&ID**: each load cell has `cal_gain` (slope) and `cal_offset` (intercept); the GUI turns `raw` into pounds
  (`pounds = slope * raw + intercept`). A load cell with no calibration shows a warning and its raw count.
  A GUI still talking to an older firmware (which sends pounds) passes those values through untouched.
- **Health tab > Load Cell Calibration** (replaces the old sensor-calibration wizard, which is still in `GUI_HEALTH.py` but
  unreachable): pick a cell, capture a zero, add known weights; every cell stays live on screen; the slope / intercept fit is
  the same least-squares fit as the `loadcell_cal` sketch; **Save to P&ID** writes it into the file and uses it immediately.
  Points are kept in `gui_settings.ini`.
- **P&ID editor**: load cell properties have Slope / Intercept fields.
- The GUI now keeps sensor values to 4 decimals (was 2) so raw counts derived from them are exact.

### Flight recorder (SD "black box") and Teensy diagnostics
- While the GUI runs an automatic (sequence) recording, the Teensy keeps its own copy of the last ~36 s (one sample per 10 ms)
  **in RAM only**. GUI "stop" discards it; if the Teensy **shuts down** first (comms loss, abort) it writes the buffer to the SD
  card as `RECnnnn.BIN`, after everything is closed. The SD card is never written during a run (a card can stall for
  10-100+ ms, which would delay the control loop and the 200 ms watchdog).
- Each sample has the pressure loop currents (raw mA), thermocouples, load cell counts, which outputs are energized
  (igniters, MOV, ...), the Bray position, and the **Ethernet chip's link status**.
- On every shutdown it also writes a **diagnostics report** (`RECnnnn.TXT`, or `DIAGnnnn.TXT` when nothing was recording):
  why the chip last reset (reset cause + crash report), whether the Ethernet chip answers, its registers with a verdict
  (settings different from what the firmware wrote at boot = the chip reset itself), packet counters, chip temperature, and the
  Teensy's own timestamped event log. `BOOTLOG.TXT` gets a line at every boot.
- **No SD card**: detected at boot; no recording is started, nothing is written, the card is never probed during a run, and
  the Teensy tells the GUI, which shows a warning. A failed write (card full / pulled) is detected and logged.
- `teensy_rec_to_xlsx.py` (in `REDControlSystem/`) converts a `.BIN` to a spreadsheet the Telemetry tab opens (sensor names
  and load cell calibration from the P&ID, output on/off events, link column, the report as a second sheet).
- New firmware pieces: packet types `PKT_REC` (recorder start/stop and card status) and `PKT_RAW` (load cell counts) in `EGCP.h`.
  See `Real_Teensy/E2_Teensy/README.md`.

### Virtual Teensy
- Simulates the 200 ms watchdog, the abort/shutdown state (sends nothing, waits for START), output on/off tracking, the
  flight recorder (same file format; saved in `Virtual_Teensy_3/sd_card/`), the diagnostics report, raw load cell counts,
  and the card-present flag.
- New controls: **Link down** (simulated comms loss), **Bad Ethernet chip** (chip reset itself / stopped answering),
  **SD card inserted**, watchdog on/off.

### Repo
- This changelog.
- `GUI_MAIN.py`: the "needs Python 3.10 or newer" error now says to upgrade Python or activate an environment that has it, then
  `pip install -r requirements.txt` (it used to point at `setup_conda.bat`).

---

## 2026-11-25 - `bf9ef9e` "teensy 50ms igniter cutoff, 200ms watchdog, ethernet recovery, better aborts"
**Teensy firmware**
- **Igniters shut off after 50 ms** by a hardware timer (`IGN_AUTO_OFF 1`), whatever the GUI or a sequence is doing; if the
  timer can't be armed the igniter is not energized.
- **Comms watchdog 5 s -> 200 ms.**
- **Ethernet chip recovery** from the shutdown loop: soft reset, hard reset, re-apply the two boot registers, and reboot as a
  last resort. Outputs are forced off at the very start of `setup()` so a reboot can't leave them floating.
- Sensor packets carry a 64-bit Teensy timestamp (microseconds since boot); the DAQ "Teensy Timestamp" column is filled and the
  Telemetry tab uses it as the time axis. A backwards clock is logged as `TEENSY_REBOOT`.

**GUI**
- **Abort / warning rules** use the official P&ID names (MCC_P, OPT-1501, ...) with auto-fill and live validation; `abs()`,
  `min`, `max`, `round`, `sqrt`, `pow`, `floor`, `ceil`, `and/or/not` now work (before, any rule using a function silently never
  fired); a rule that can't be understood raises a "RULE NOT ACTIVE" warning. Calculated channels (Thrust, Tank Weight) can be
  used by name. A (disabled) low-thrust abort rule was added. New `GUI_EXPR.py`.
- **Sequencing is relative to T-0**: a single *Terminal Count* length box replaces the terminal-count step; step times are
  `T-0.5`, `T+0.4`, ...; older files convert automatically. `SEQ_T` / `SEQ_END` / `SEQ_RUNNING` are available in rules.
- **Auto-reconnect** after a comms loss during live operation (retries for up to 60 s, always lands in SAFE).
- The abort pressure messages use official names.

## 2026-11-20 - `2a4a37c` P&ID update
## 2026-11-19 - `61b03b0` "LC filtering, telemetry"
- Firmware: load cells on a shared chip reject outlier samples before averaging. Telemetry tab improvements.

## 2026-11-18 - `fc5745b` "Updated p&id and others"; merge `910fd79`
- **Temperature display switch**: thermocouples stay in degC everywhere (data, formulas, thresholds); a C/F button in the sensor
  sidebar changes only what live displays show (`GUI_UNITS.py`).
- Merged mihir's thermocouple bench fixes (`0e160cc`, Nov 17: only TCs 10-12 enabled in firmware) and the load cell calibration
  sketch `Load_Cell_Calibration_Ethernet`.

## 2026-11-15 - `bca3acc` "Fixes to data, sequence, etc", `97444a5` "control bray % in sequence"
- **Data saving rewritten**: recording streams to disk on a background thread and converts to `.xlsx` on Stop (no more "Not
  Responding"); unfinished recordings are recovered at start-up; saving on close; automatic recording at terminal count that
  stops 10 s after the sequence; Control State and event rows (valve commands, aborts, step actions) in the data.
- Telemetry tab opens large recordings off the GUI thread.
- **Per-step servo / Bray valve position** in the sequence editor (same popup as the home screen).
- MOV added to the 5 Second Fire sequence.

## 2026-11-13 - `0609276` "Sequencing"
- Sequence editor can command every actuated valve, servo and igniter.

## 2026-11-05 / 11-06 - `69a943a`, `ab4e9c7`, `d0cac51`
- Relay pin map reworked from the daughtercard schematic (GUI/P&ID reverted to `2de38b0`, firmware kept); load cell
  calibrations (5 of 6).

## 2026-11-02 to 11-04 - `4367636`, `b706086`, `8145df9`, `2de38b0`
- **Bray valve** (AD5420 4-20 mA positioner) support and power relay handling; load cell calibration (mihir); GUI keeps the screen
  awake; valve re-ordering and renaming.

## October 2026 (summary from commit messages)
- GUI modes SAFE / MANUAL / LOCKED / ABORT, abort configuration, live data page, multi-device (viewer) connection (mihir, Oct 12-16).
- draw.io P&ID importer, E2 RED spec P&ID, Virtual Teensy updates (mihir, Oct 16-17).
- GUI relay and servo controls, P&ID spec and EGCP header updates (Ben, Oct 17-19); PT calibration, loading screen, Pneuma (csmeby).
- PT oversampling / auto actuation (mihir, Oct 20-27; the firmware oversampling was later reverted to the known-good version).
