# How to start the GUI

First navigate so that your active directory is `Elysium_GUI`.

If you have made no changes/it is already compiled, simply run `sudo ./Elysium_GUI`.

If you have just changed a couple files, but not added significant includes or new files:
1. `make` to compile.
2. `sudo ./Elysium_GUI` to run.


If you have made signficant changes (new files or substantive includes):
1. `qmake -project` to (re)create the project file.
2. Update the project file:

    A. Set `INCLUDEPATH = ./Headers` so it can locate the header files.

    To let the makefile/compiler know where to find core includes:

    B. Add a line reading `QT += widgets` for QApplication and QMainWindow, among others.

    C. Add a line reading `QT += gui` for QPixmap.

    D. Add a line reading `QT += core` for the namespace (alignment flags, among others).

    E. Add a line reading `QT += serialport` for the serial connections.

    [comment]: # (Update Here if new lines become necessary)

3. `qmake Elysium_GUI.pro` to generate a makefile from the project file.
4. `make` to compile (this is where errors will show up with improper code).
5. `sudo ./Elysium_GUI` to run.

## Setup
Use a unix-like enviornment and install the proper libraries.

In my case, the command is `sudo apt install make` to install `make`.

You will need the `g++` compiler and the access to the commands `make` and `qmake` (via `qtchooser` library), and `qtdeclarative5-dev`.

Additionally, for the serial comunication, I installed `libqt5serialport5-dev`, and for the live graphs, I installed `libqt5charts5-dev`.

## To connect to the Teensy via WSL
1. Install `usbipd-win` via the .msi file for the latest release https://github.com/dorssel/usbipd-win/releases.
2. Open Windows Powershell as administrator and execute `usbipd list`.
3. Identify which device corresponds to the Teensy (the description may not list it, so confirm the COM number via the Arduino IDE or any other method) and remember the bus ID.
4. Execute `usbipd bind --busid ID` (with the previously found `ID`). Verify that it is shared with `usbipd list`, if desired.
5. Execute `usbipd attach --wsl --busid ID` (with the previously found `ID`). Verify that it is attached with `usbipd list`, if desired.
6. A more precise way to verify is to open WSL terminal and execute `lsusb`, which should list the attached port.

To detach, either remove the device physically or execute `usbipd detach --busid ID` (with the previously found `ID`).

Every time the device is disconnected or the PC restarts, you will have to repeat step 5 (although, it would be wise to recheck the list to confirm the `ID`).

## Additional Note
The `sudo` keyword is needed for running the executable in order to access the serial ports. You will recieve a `PermissionError` without it. I am not certain why this is, but I think the `/dev/` directory (which is how ports are treated in WSL) is considered protected.
