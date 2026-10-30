# Configurations
Each subdirectory represents a configuration of valves and sensors, with the corresponding P&ID. The name of the subdirectory indicates the configuration name, the file names within are required to be fixed so that the GUI can access them. I.e., there must files titled `sensors.cfg`, `valves.cfg`, `control_states.cfg` and `P&ID.png`.

## Format of configuration files

Each row (or possibly pair of rows) represents one element that should be added to the GUI. Every row is a set of comma seperated values (no additional spaces) representing a set of arguments.

The first arguments identify the object and provide the parameters required for its initialization. The final arguments, which may go on the second row&mdash;this has not been implemented yet&mdash;will indicate additional placement info to the GUI. For example, should the sensor be independent or grouped with the Pressure Sensors or where on the P&ID should it be located.

The order matters, as the elements are added to the GUI from the top down, starting at the beginning of the file.

### For `sensors.cfg` the arguments are given in the following order:
`ID,name,unit`$\newline$
`group,type`

The first line is self explanatory; `group` indicates that the sensor should be placed in the GUI in a seperated area for all sensors in that group, titled with `group`. The ordering is still first is top, and the same applies to the groups (first group top left, then top right, the second row left, second row right, etc.). If it is left blank (i.e., the line line starts with a `,`), then it is grouped but without a title. The `type` indicates if the sensor is a directly measured quanitity (`measured`), or derived from the others (`derived`). Additional `derived` quantities will require modifying GUI_DAQ_Window(.h/.cpp) to handle their calculations.

### For `valves.cfg` the arguments are given in the following order:
`class,ID,name,[args]*`

The `class` has three values: `Valve`, `Solenoid`, and `LA_Ball`, indicating the `Valve`, `Solenoid_Valve`, and `LA_Ball_Valve` classes respectively.

The `[args]*` depends on the class. For `Valve` it indicates the `state` parameter, for `Solenoid` it indicates the `normally_open` parameter, and for `LA_Ball` it will be two values indicating `state` then `is_open`.

### For `control_states.cfg` the arguments are given in the following order:
`name1/name2/name3,row1/row2/row3,col1/col2/col3`$\newline$
`valve1:state1,valve2:state2,valve3:state3`

Note that while this example lists three (3) of all values, the lists can be shortened or lengthed at will for arbitrary control.

The first line indicates all names of the control state in a `/` separated list, followed by the rows and then columns that each name should be displayed on, similarly presented in a `/` separated list. This allows for multiple named states to have the same valve configurations and be listed in the correct places in the operations page.

The second line indicates the states of all valves in a comma separated list of key:value pairs, denoting the valves (by ID) and the state (0=closed, 1=open). The ignition system is also treated as a valve with ID=IGNITE and 0=unpowered, 1=powered. Additionally, the requirement that there are no personnel near the engine is listed as a valve with ID=SAFE and 0=personnel can be nearby, 1=operator must confirm that no personnel are nearby.
