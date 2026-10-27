# Virtual Teensy 3  (this is entirely vibe coded)

This project simulates the Teensy 4.1 hardware for the Elysium Ground Support Equipment (GSE). It allows you to test the Python GUI without needing the physical avionics hardware.

## Features
-   **UDP Communication**: Simulates the Ethernet protocol used by the flight hardware.
-   **Sensor Simulation**: Individual sliders for Pressure Transducers (P1-P12), Thermocouples (TC1-TC3), and Load Cells (LC1-LC6). Each sends under the ADC channel that `PIDs/Elysium.red` (and `E2_RED_Spec.red`) binds it to, so the GUI shows it under the right name. If you change a sensor's ADC channel in the project, change it in `SENSOR_MAP` in `vt_comms.py` too.
-   **Valve Feedback**: Visual indicators for valve states request by the GUI.
-   **Actuators (SV-1, SV-2, MFV Bray)**: Position-commanded valves. The GUI's position commands (`PKT_POS`) are ACKed immediately, then the bar travels to the target at the *Travel speed* setting. Drag an actuator's slider to actuate it by hand and the GUI follows. The FAIL box withholds the ACK like it does for on/off valves.
-   **Noise Simulation**: tick *Enable noise* to layer realistic noise on top of the slider values as each reading is sent (sliders stay the "true" value). Adjustable white noise for PTs / TCs / LCs, a slow PT drift (the part that averaging can't remove), and occasional spikes. Off by default.
-   **Leak Check Simulation**: check the PTs to include, give each a leak rate (psi/min; 0 = a perfect seal), and press *Pressurize & start leak*: those PTs jump to the start pressure and then fall at their rate. An optional *Settling drop* adds the exponential fall of gas cooling after pressurizing, for trying the Tests tab's settle time. *Stop (hold)* freezes the PTs at their current values. Pressurize first, then press Start in the GUI's Tests tab. Combine with noise for a realistic leak check.
-   **Localhost Compatible**: Automatically handles port binding to allow running on the same machine as the GUI.

## Setup
No additional installation is required if you already have the `REDControlSystem` dependencies installed (`pip install -r Elysium/REDControlSystem/requirements.txt`; the Virtual Teensy itself only needs `PyQt5`).

## Usage

1.  **Start Virtual Teensy**
    ```bash
    cd Elysium/Virtual_Teensy_3
    python3 virtual_teensy_gui.py
    ```
    The window will open and begin listening on Port 8889 (default).

2.  **Start Main GUI**
    ```bash
    cd Elysium/REDControlSystem
    python3 GUI_MAIN.py
    ```

3.  **Connect**
    -   In the Main GUI connection panel:
        -   **IP**: `127.0.0.1`
        -   **Port**: `8889`
    -   Click **Connect**.
    -   If successful, the Virtual Teensy log will show "New client connected" and the GUI will show "Connected Successfully".

4.  **Simulate**
    -   Move sliders in Virtual Teensy to see graphs move in the Main GUI.
    -   Click valve buttons in Main GUI to see indicators change in Virtual Teensy.
    -   Command SV-1 / SV-2 in the Main GUI to watch the simulated actuator travel; move their sliders in Virtual Teensy to change the position shown in the Main GUI.
    -   On/off valves are one-way: the GUI commands them and Virtual Teensy shows the result. The GUI has no handler for a valve opening or closing on its own, so there is no by-hand control for them here.

## Troubleshooting
-   **Connection Failed**: Ensure you use `127.0.0.1` and Port `8889`. The GUI's connection panel defaults to the real hardware (IP `192.168.1.174`, Port `8888`), so change both fields.
-   **Virtual Teensy says "Address already in use"**: another Virtual Teensy is still running on Port 8889. Close it and restart.
-   **Address already in use**: If you restart the GUI, wait a few seconds for the socket to release, or rely on the GUI falling back to a free local port (`GUI_COMMS.py`).
