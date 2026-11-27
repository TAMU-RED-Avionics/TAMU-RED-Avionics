# How to connect

## Windows:
In an elevated command prompt
Look for an interface that appears when you plug in the teensy
`netsh interface show interface` 

Use the interface name (ex: Ethernet 5) in the command below
`netsh interface ip set address name="{INTERFACE NAME}" static 192.168.1.175 255.255.255.0`

## Mac/Linux:
In terminal
Find the network interface name by running
`ifconfig` (Look for an interface like en0, eth0, or enp0s3 that activates only when the cable is connected)

Use the interface name (ex: eth0) in the command below
`sudo ifconfig {INTERFACE_NAME} inet 192.168.1.175 netmask 255.255.255.0 up`

-----
Upload code to Teensy from Arduino IDE if not already done

Open GUI and connect to IP: `192.168.1.174` PORT: `8888`

-----
Note: As noted in the teensy code, there is a HUMAN_CONNECTION_TIMEOUT variable. This means that if there is no human action (valve actuation) in that amount of time, the teensy will shut down and it will not reconnect unless you reopen the GUI. In E1 it was set as 5 minutes and it was a pain. With that being said, it could be an important safety feature. I have it set to 1 hour (3600000000 microsec). In theory, this should NEVER trigger (which makes it kinda useless).

-----
## Flight recorder (SD card "black box")
While the GUI runs an automatic (sequence) recording it tells the Teensy to start/stop (`PKT_REC`, 0xC).
The Teensy keeps its own copy of the last ~36 s (one sample per 10 ms) in RAM only:
* GUI sends **stop** -> the Teensy throws its copy away (the GUI has the same data).
* The Teensy **shuts down** while recording (comms loss, abort, ...) -> after every valve is closed it writes the
  buffer to the SD card as `RECnnnn.BIN`.

The SD card is never written during a run (a card can stall 10-100+ ms, which would delay the control loop and
the 200 ms comms watchdog); the only other SD access is `SD.begin()` once at boot. Put a FAT32 card in the Teensy
before a test; the boot log says `SD card ready` or `no SD card`.

On **every** shutdown (recording or not) the Teensy also writes a **diagnostics report** to the card:
`RECnnnn.TXT` next to the recording, or `DIAGnnnn.TXT` when nothing was recording. It says why the chip last reset
(`SRC_SRSR`: power-on / watchdog / software / lockup - a brownout or crash reboot shows here, a "stayed up, link died"
event does not), whether the Ethernet chip answers and its registers with a verdict (RCSR/LEDCR different from what the
firmware wrote at boot = the chip reset itself), packet counters, chip temperature, and the Teensy's own timestamped
event log (commands, link up/down, shutdown, recovery attempts). `BOOTLOG.TXT` gets a line at every boot with the reset
cause and any CrashReport. The recording itself also has the Ethernet link status on every 10 ms sample.

**No SD card:** the Teensy checks once at boot (`NO SD CARD` in the boot log). Without a card it refuses to start a
recording, writes nothing at shutdown, never probes the socket during a run (a missing card can be slow to probe), and
tells the GUI after every connect, which then shows a warning. At a shutdown it re-probes at most once per 5 s, so a card
inserted later is picked up. A write that fails (card full or pulled out) is detected, logged, and the card is re-probed
next time. The safety shutdown itself never depends on the card.

Convert a file on the PC (names the sensors from the P&ID, opens in the Telemetry tab):
`python teensy_rec_to_xlsx.py REC0001.BIN` (in the REDControlSystem folder). It also lists every output switching
on/off (e.g. IGN-1) with the Teensy's own timestamps, plus raw loop currents (`mA <sensor>` columns).

-----
## Load cells (raw counts)
The Teensy sends each load cell as a **raw count** (`PKT_RAW`, 10 Hz), not pounds - there are no slopes or intercepts in
the firmware. The GUI turns a count into pounds with `slope * raw + intercept`, saved per load cell in the P&ID
(`cal_gain` = slope, `cal_offset` = intercept, in `E2_RED_Spec.red`). Find them in the GUI under
**Health > Load Cell Calibration** (capture a zero, add known weights, *Save to P&ID*), or type them in the P&ID editor's
Load Cell properties. A load cell with no calibration in the P&ID shows a warning and its raw count.
The flight recorder's load cell columns are raw counts too (file version 2); `teensy_rec_to_xlsx.py` applies the
P&ID calibration when it converts the file.
