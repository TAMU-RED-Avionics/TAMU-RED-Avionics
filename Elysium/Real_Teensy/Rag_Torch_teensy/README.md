# Ragnarok Torch Igniter - Teensy Firmware (Made by Claude (My Goat! 🐐)))

Ethernet-based ignition controller for the Ragnarok torch igniter test. Runs on a Teensy with NativeEthernet, exposes a UDP command interface, reads 6 pressure transducers, and drives solenoid valves + an ignition coil spark driver.

---

## Network Config

| Field    | Value             |
|----------|-------------------|
| Local IP | `192.168.1.174`   |
| Remote IP| `192.168.1.175`   |
| Port     | `8888` (UDP both directions) |

---

## How the Loops Work

### `setup()`
1. Opens Serial at 115200 baud.
2. Calls `init_comms()` — configures Ethernet with static IP/gateway/subnet, starts UDP listener on port 8888.
3. Sets all output pins to `OUTPUT` mode and drives them `LOW` (all valves closed, IGBT off, coil resting).
4. Sends `"RT: pins initialised\n"` over UDP to the remote host.

---

### `loop()` — main execution path

The loop runs as fast as possible (no blocking `delay()` except the 10 ms data-flush after sensor reads). Three things happen every iteration:

#### 1. UDP Command Parsing

```
udp.parsePacket()  →  input_until('\n')
```

Expected packet format: `IDENTIFIER:STATE\r\n`

| Message        | Meaning                                      |
|----------------|----------------------------------------------|
| `nop\r`        | Heartbeat only — resets `LAST_COMMUNICATION_TIME`, nothing else |
| `h_nop:0\r` / `h_nop:1\r` | Human no-op button — resets both timers, no action |
| `SPARK:1\r`    | Start spark state machine                    |
| `SPARK:0\r`    | Stop sparking, force IGBT LOW                |
| `NCS1:1\r`     | Open solenoid 1 (HIGH)                       |
| `NCS1:0\r`     | Close solenoid 1 (LOW)                       |
| *(same for NCS2–5, EABV, PABV)* | |

Any packet that doesn't match `IDENTIFIER:STATE` format (no `:` delimiter, or unknown identifier) is silently dropped.

#### 2. Spark State Machine

Runs every loop iteration when `is_sparking == true`. Drives a 4-phase non-blocking sequence:

```
SPARK_IDLE
  │  digitalWrite(SPARK_PIN, HIGH)   ← energise coil (IGBT on)
  ▼
SPARK_DWELL   (DWELL_TIME µs, default 3000 µs)
  │  digitalWrite(SPARK_PIN, LOW)    ← collapse field → spark fires
  ▼
SPARK_DISCHARGE  (SPARK_TIME µs, default 2000 µs)
  │  coil resting, energy dissipating
  ▼
SPARK_WAIT    (BETWEEN_SPARKS ms, default 50 ms)
  │  full inter-spark gap
  ▼
SPARK_IDLE    (loops back)
```

All timing is done with `micros()` deltas — no `delay()`, so the rest of the loop keeps running between phases.

> **Safety note:** Keep `DWELL_TIME` under ~5000 µs to prevent coil overheating.

#### 3. Sensor Broadcast

Every `SENSOR_UPDATE_INTERVAL` µs (default 1000 µs = 1 kHz), the firmware:

1. Reads all 6 PT analog pins.
2. Converts each raw ADC count to PSI via a linear calibration:
   ```
   pressure = slope[i] * analog + intercept[i]
   ```
   (All slopes currently `1.22983871`; intercepts differ per transducer.)
3. Streams a comma-separated telemetry packet over UDP:
   ```
   t:<micros>,P1:<psi>,P2:<psi>,...,P6:<psi>,t_loc:<seconds_until_human_timeout>\n
   ```
   Each field is sent as a separate UDP packet (not one big packet — the remote host assembles the CSV line).

---

### Abort / Watchdog

Two independent timeouts are checked every loop iteration:

| Timeout | Constant | Default | Triggered by |
|---------|----------|---------|--------------|
| Comms loss | `CONNECTION_TIMEOUT` | 200 ms | No UDP packet of any kind received |
| Human loss | `HUMAN_CONNECTION_TIMEOUT` | 300 s | No non-nop command received |

If **either** fires:

1. `emergency_close_all()` is called — all solenoids go LOW, IGBT goes LOW, spark state machine resets.
2. Firmware enters a **blocking abort loop**:
   - Broadcasts `"Aborted\n"` every `ABORTED_TIME_INTERVAL` µs (500 ms).
   - Keeps parsing UDP packets.
   - Only exits when it receives `"start\r"` or `"Start\r"`, at which point both timers reset and normal `loop()` resumes.

```
comms_lost || human_lost
  │
  ▼  emergency_close_all()
  │
  └─► blocking while(aborted):
        broadcast "Aborted" every 500 ms
        wait for "start\r" / "Start\r"
          │
          └─► reset timers, return to loop()
```

> The `t_loc` field in the telemetry stream gives the ground station a live countdown (in seconds) to the human timeout — useful for UI warnings before an unintended abort.

---

## Timing Summary

| Parameter | Value | Notes |
|-----------|-------|-------|
| Sensor rate | 1000 µs | 1 kHz ADC reads + UDP broadcast |
| Comms watchdog | 200 ms | Any UDP packet resets it |
| Human watchdog | 300 s | Non-nop command resets it |
| Abort broadcast | 500 ms | Rate of `"Aborted\n"` spam |
| Dwell time | 3000 µs | IGBT on / coil charge |
| Discharge time | 2000 µs | Post-collapse rest |
| Inter-spark gap | 50 ms | Full cycle period |