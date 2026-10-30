# How to use the Virtual Teensy
## Setup

Install the socat module with `sudo apt-get install socat`.

## Usage

Open two WSL terminals. In first, it does not matter what directory is open.

Execute `sudo socat -d -d pty,raw,echo=0,b115200,link="/dev/Test_GUI" pty,raw,echo=0,b115200,link="/dev/Virtual_Teensy"`. This will generate a pair of `/dev/pts/X` serial ports with arbitrary values `X` (typically, 0, 1, or 2, but can vary based on system activity), which are linked to the fixed names `/dev/Test_GUI` and `/dev/Virtual_Teensy`. This command needs to remain active as long as you need to test the GUI/Virtual Teensy.

In the second terminal, navigate so that your active directory is `Virtual_Teensy`.

First navigate so that your active directory is `Virtual Teensy`. Execute `make` any time you update a source file. To run the Virtual Teensy, execute `sudo ./Virtual_Teensy`.

## Additional Testing
If the Virtual Teensy is not working (or for some other reason you want to check that the virtual ports are working), you can manually send information to and recieve from the pair of ports via the following commands.

`sudo bash -c 'echo "hello" > /dev/Test_GUI'` to write a signal. This command uses strange formatting because both the `echo` part and accessing the port (which is treated as a file) require the root privileges, but a typical `sudo echo "hello" > /dev/Test_GUI` would only give root privileges to the `echo` portion.

`sudo cat /dev/Virtual_Teensy` to recieve a signal. This command will "listen in" to the port until you exit the command.

You can swap the names as desired. Remember that only one application can be attached to each port at the same time, so if the Virtual Teensy is running, you can only connect to `/dev/Test_GUI` and vice versa if the GUI is connected.
