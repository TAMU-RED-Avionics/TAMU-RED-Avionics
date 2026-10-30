# Elysium
## Elysium GUI
The Elysium Graphical User Interface is the primary way that the system is controlled. It handels the inputs of the operator, automated control sequences, as well as the live display, graphing, and storage of data. It is programmed in C++ with Qt. For information on how to run and recompile (as needed), see the README.md in that directory.

## Real_Teensy
This directory contains the sketch(es) used by the Teensy to interpret the signals from the GUI, directly send the signals to actuate the valves, and read/transmit data from the sensors. Additionally, the system will handle an abort if there is a communications failure.

## Virtual_Teensy
This directory contains the code for a simulated version of the Teensy which is used to test the GUI. It recognizes and prints out any commands it recieves, and allows a user to control the data that it outputs to the GUI. For information on how to run and recompile (as needed), see the README.md in that directory.

Additionally, it will be configured to connect to another real Teensy to allow for Hardware In-the-Loop (HIL) testing.

## Data Formatting
For Elysium, all data will be transferred in `key:value` pairs. These pairs can be chained together in a comma separated string `"key1:val1,key2:val2,key3:val3\r\n"`, which terminates the carriage return (`'\r'`) and newline (`'\n'`) characters (the standard ending protocol for serial communication).The three goals are standardization, ease of maintainence/extension, and redundancy.

Standardization is both across programs and across subteams. We shall use the IDs of Sensors and Valves from the cross-team P&ID as the `key` terms, and the relevant data as the `value` terms. This will eliminate confusion between groups that were experienced in the WTS campaign, when one team was using `P1` and `P2`, and the other was using `PA` and `PB`.

This makes maintainence easier because it allows sensors and valves to be universally configured with a single, critical value. Similarly, if more valves or sensors are added, they can be added to the system with the same, single value.

This allows for some redundancy in the data transmission. If one value or part of a value fails to send correctly, the rest of the data in that batch (because of the keys), can still be readily and accurately identified by the receiver.

### Comparison to Older Design
Compare to the simpler system used during the WTS campaign: Comma separated values where the position dictates which property it corresponds to. First, the order of the properties had to be explicitly coordinated between the Teensy group and the GUI group and was not in reference to an existing, agreed upon document (such as the P&ID). Second, if a new sensor was added, both sides had to again determine where in the sequence to put the new value and manually hard-code it. Finally, if one value fails to send, all the following values (in that batch) are shifted and thus misread by the system.

### Example
Suppose the P&ID has three Pressure Transduces (P1-P3), two Thermocouples (T1 and T2) and one accelerometer (A1), which reads accelerations in three directions. The Teensy also outputs the local time with key `t`. Thus, it should output something like:

`"t:6545450000,P1:685.5422001,P2:14.78512405,P3:500.12124541,T1:7.2301502,T2:312.128575954,A1x:0.784213850,A1y:0.34517850652,A1z:2.0006781249\r\n"`

The order of the pairs does not matter, so something like the following is also acceptable, though less readable for debugging:

`"P3:500.12124541,A1x:0.784213850,P1:685.5422001,T2:312.128575954,A1z:2.0006781249,P2:14.78512405,T1:7.2301502,t:6545450000,A1y:0.34517850652\r\n"`

### Valve Example
For the valves, the solution is nearly identical, except that each command is always sent on its own line (no comma separated strings). Additionally, the value `0` always denotes a closed valve or close operation, and the value `1` always denotes an open valve or operation. For any extra electrical components (such as the ignition system), `0` will correspond to no power and `1` will correspond to providing power.

Consider a system with four normally closed solenoid valves (NCS1-NCS4) and two linearly-actuated ball valves (LA-BV 1 and LA-BV 2), and an igniter (IG1).

The signals to close all solenoids, open all ball valves and power igniter #1 would be given by:

`"NCS1:0\r\n"`
`"NCS2:0\r\n"`
`"NCS3:0\r\n"`
`"NCS4:0\r\n"`
`"LA-BV 1:1\r\n"`
`"LA-BV 2:1\r\n"`
`"IG1:1\r\n"`

Spaces in the IDs do not affect anything in either system. Again, these could be given in any order.

## Known Issues
There are a couple issues which have evaded all attempts to remove, but have simple methods to circumvent.

### GUI Freezes when connecting to Teensy
Identify: This typically results in the GUI freezing for several seconds, then expanding to full size, but not detecting any data inbound. It also will freeze upon shutdown or disconnect.

Cause: The connection to the Teensy is really sensitive with repeated connections and disconnections, especially with the WSL forwarding.

Solution: Unplug/replug the Teensy, and immediately attach it to WSL and attempt the connection again.<br>
A similar fix is to detach from WSL, and open the serial monitor in the Arduino IDE. Try opening and closing the serial monitor menu, and it should alternate between correct functionality, and a blank screen. When it is on a blank screen, close it, attach to WSL and attempt the connection again.

### GUI Connects, but the Teensy stays in the aborted state
Identify: GUI immediately "connects", but all data fields remain blank and the terminal is filled with `Not enough data: Aborted` and `Not enough data: New Input= nop`.

Cause: The connection to the Teensy is really sensitive and the first data sent over the connection often is lost/corrupted (buffer overriden?). This only occurs the first time after the Teensy is restarted.

Solution: Close the GUI and relaunch it. Not totally sure why, but it only ever happens the first time.
