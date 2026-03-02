# Virtual Teensy 3  (this is entirely vibe coded)

This project simulates the Teensy 4.1 hardware for the Elysium Ground Support Equipment (GSE). It allows you to test the Python GUI without needing the physical avionics hardware.

## Features
-   **UDP Communication**: Simulates the Ethernet protocol used by the flight hardware.
-   **Sensor Simulation**: Individual sliders for Pressure Transducers (P1-P6), Thermocouples (TC1-TC2), and Load Cells (LC1-LC2).
-   **Valve Feedback**: Visual indicators for valve states request by the GUI.
-   **Localhost Compatible**: Automatically handles port binding to allow running on the same machine as the GUI.

## Setup
No additional installation is required if you already have the `Elysium_GUI` dependencies installed (specifically `PyQt5`).

## Usage

1.  **Start Virtual Teensy**
    ```bash
    cd Elysium/Virtual_Teensy_3
    python3 virtual_teensy_gui.py
    ```
    The window will open and begin listening on Port 8889 (default).

2.  **Start Main GUI**
    ```bash
    cd Elysium/Elysium_GUI
    python3 GUI_MAIN.py
    ```

3.  **Connect**
    -   In the Main GUI connection panel:
        -   **IP**: `127.0.0.1`
        -   **Port**: `8888`
    -   Click **Connect**.
    -   If successful, the Virtual Teensy log will show "New client connected" and the GUI will show "Connected Successfully".

4.  **Simulate**
    -   Move sliders in Virtual Teensy to see graphs move in the Main GUI.
    -   Click valve buttons in Main GUI to see indicators change in Virtual Teensy.

## Troubleshooting
-   **Connection Failed**: Ensure you use `127.0.0.1` and Port `8889`. The real hardware uses Port `8888`, so the default in the GUI might need to be changed.
-   **Address already in use**: If you restart the GUI, wait a few seconds for the socket to release, or rely on the auto-fallback mechanism implemented in `GUI_COMMS.py`.
