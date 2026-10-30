# GUI ARCHITECTURE; CONTAINTS CLASSES OF ALL VARIABLES AND FUNCTIONS FOR THE GUI

from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import serial.tools.list_ports
import time
import sys
import os

# Included here to simplify imports in the Master File
class GUI_APP(QtWidgets.QApplication):
    def __init__(self):
        """
        Generates main instance of application.
        Accepts Command Line arguments.
        """
        super().__init__(sys.argv)

class GUI_Main_Window(QtWidgets.QMainWindow):
    def __init__(self):
        """
        Initializes the Main Window for the GUI
        """
        super().__init__()

        # Locks the size of the GUI
        self.manual_resize(320, 150)

        # Enables shutdown confirmation
        self.enable_shutdown_confirmation = True

        # TODO: Add a dark theme as well.
        # Sets the background to white
        self.set_color(self, "white")

        # Attaches the Layout to a widget and attaches to the window
        self.layout = QtWidgets.QGridLayout()
        w = QtWidgets.QWidget()
        w.setLayout(self.layout)
        self.setCentralWidget(w)

        # Margins to the border of the GUI and spacing between content components
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.layout.setSpacing(10)

        # TODO: Two versions of the logo for light/dark
        # RED LOGO
        directory_path = os.path.dirname(__file__)
        logo_path = os.path.join(directory_path, "RED_logo.png")
        self.logo = QtWidgets.QLabel()
        self.logo.setPixmap(QtGui.QPixmap(logo_path))
        self.logo.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.logo.setMaximumHeight(30)
        self.set_color(self.logo, "red")
        self.layout.addWidget(self.logo, 0, 0)

        # Contructs menu for connecting to the Teensy
        self.com_menu = GUI_COM_Window(self)

    def closeEvent(self, event):
        """
        Method to intercept closing the window and ensure that all components are shut down.
        """
        # If you are not connected to the Teensy, no confirmation needed
        if not self.com_menu.is_connected:
            print("No connection shutdown")
            self.com_menu.delete()
            event.accept()
            return
        
        # Otherwise ask for confimation to shutdown the GUI
        confirmation = QtWidgets.QMessageBox.StandardButton.Apply
        if self.enable_shutdown_confirmation:
            confirmation = QtWidgets.QMessageBox.warning(self, "Confirmation", "Are you sure you want to exit the GUI?",
                                                         QtWidgets.QMessageBox.StandardButton.Cancel |
                                                         QtWidgets.QMessageBox.StandardButton.Apply)
        
        if confirmation == QtWidgets.QMessageBox.StandardButton.Apply:
            self.com_menu.delete()
            event.accept()
        else:
            # Must ignore the event or it falls up and improperly closes the program
            event.ignore()

    def manual_resize(self, width, height):
        """
        Method to force the Window the resize, but then allow it to be changed by the user.
        """
        self.setFixedSize(QtCore.QSize(width, height))
        self.setMaximumSize(QtWidgets.QWIDGETSIZE_MAX, QtWidgets.QWIDGETSIZE_MAX)
        self.setMinimumSize(0, 0)

    def set_color(self, widget, color):
        """
        Method to change the background color of any widget.
        """
        widget.setAutoFillBackground(True)
        palette = widget.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(color))
        widget.setPalette(palette)

class GUI_COM_Window(QtWidgets.QWidget):
    def __init__(self, parent):
        """
        Constructs the menu for connecting to the Teensy.
        """
        super().__init__(parent)
        self.root = parent

        # Communication Data
        self.current_port_name = ""
        self.current_baud_rate = ""

        # Enable Disconnection confirmation
        self.enable_disconnect_confirmation = True

        # Grid Layout for buttons and labels
        bottom_layout = QtWidgets.QGridLayout()
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(10)

        # Labels for COM Port and Baud Rate selection
        Standard_Label("COM Port:", bottom_layout, 0)
        Standard_Label("Baud Rate:", bottom_layout, 1)

        # Selection box for COM Port
        self.COM_selection = QtWidgets.QComboBox()
        self.COM_selection.currentTextChanged.connect(self.update_port)
        bottom_layout.addWidget(self.COM_selection, 0, 1)

        # Selection box for Baud Rates
        self.baud_selection = QtWidgets.QComboBox()
        self.baud_selection.currentTextChanged.connect(self.update_baud)
        self.baud_selection.setMaxVisibleItems(16)
        bottom_layout.addWidget(self.baud_selection, 1, 1)

        # Refresh Button checks and updates both lists (may reset selection to default)
        self.is_connected = False
        self.refresh = QtWidgets.QPushButton()
        self.refresh.setText("Refresh")
        self.refresh.clicked.connect(self.update_COM_options)
        self.refresh.clicked.connect(self.update_baud_options)
        bottom_layout.addWidget(self.refresh, 0, 2)

        # Refresh Button checks and updates both lists (may reset selection to default)
        self.connect = QtWidgets.QPushButton()
        self.connect.setText("Connect")
        self.connect.clicked.connect(self.connect_to_serial)
        bottom_layout.addWidget(self.connect, 1, 2)


        # Initialize options for the selection menus
        # Must be done after the buttons are initialized, to set their states
        self.update_COM_options()
        self.update_baud_options()

        # Dummy widget to hold the layout and be placed inside the frame
        layout_widget = QtWidgets.QFrame()
        layout_widget.setLayout(bottom_layout)

        # Generate new layout with frame and title, set as the layout
        layout = Frame_with_Title("Teensy Connection", layout_widget)
        self.setLayout(layout)
        self.root.layout.addWidget(self, 1, 0)

        # Fix the size
        self.setFixedHeight(106)

    def delete(self):
        """
        Method to delete subwindows and end serial connection
        """
        if self.is_connected:
            # CTRL.delete() will actuate valves to power-off, so it requires still having the connection open
            self.CTRL.delete()

            # The DAQ requires the serial communication to be interrupted to shutdown
            self.serial_close()
            self.DAQ.delete()

    def update_COM_options(self):
        """
        Method to search for the teensy and update the list of available COM Ports.
        """
        # search computer for serial ports
        self.teensy_ports = []
        print("\nsearching for serial ports...")
        ports = serial.tools.list_ports.comports()
        if len(ports) > 0:
            for port, desc, hwid in sorted(ports):
                print("COM PORT FOUND:", f"[{port}][{desc}][{hwid}]")
                if "13960230" or "14200900" in hwid:
                    self.teensy_ports.append(port)
                # Virtual port used for testing
                elif "CNCB0" in hwid or "CNCA0" in hwid or "CNCA1" in hwid or "CNCB1" in hwid:
                    self.teensy_ports.append(port)
            print("searching for teensy ports...")
            if len(self.teensy_ports) > 0:
                for port in self.teensy_ports:
                    print("TEENSY PORT FOUND:", port)
            else:
                print("NO TEENSY PORT FOUND: make sure a teensy is plugged in and refresh.")
        else:
            print("NO COM PORT FOUND: make sure a serial port is plugged in and refresh.")
        
        self.COM_selection.clear()
        self.COM_selection.addItem('-')
        self.COM_selection.addItems(self.teensy_ports)
    
    def update_port(self, name):
        """
        Updates the currently selected COM port by name.
        """
        self.current_port_name = name
        print("Current port name", self.current_port_name)
        self.check_connection_button()

    def update_baud_options(self):
        """
        Method to update the list of available Baud rates.
        """
        baud_rates = ["-", "300", "600", "1200", "2400", "4800",
                "9600", "14400", "19200", "28800", "38400",
                "56000", "57600", "115200", "128000", "256000"]
        self.baud_selection.clear()
        self.baud_selection.addItems(baud_rates)
    
    def update_baud(self, name):
        """
        Updates the currently selected baud rate.
        """
        self.current_baud_rate = name
        print("Current baud rate", self.current_baud_rate)
        self.check_connection_button()

    def check_connection_button(self):
        """
        Enables or disables the connect button based on if the currently selected settings are valid.
        """
        if '-' == self.current_port_name or '-' == self.current_baud_rate:
            self.connect.setDisabled(True)
        else:
            self.connect.setEnabled(True)

    def connect_to_serial(self):
        """
        Attempts to connect or disconnect from the current serial communcation,
        using the currently stored COM Port and Baud Rate.
        """
        if not self.is_connected:
            # Connect to serial
            self.serial_open()
            if self.ser.is_open:
                self.is_connected = True
            else:
                print("ERROR: Cannot open serial connection")
                return
            
            # Disable connection configuration buttons
            self.COM_selection.setDisabled(True)
            self.baud_selection.setDisabled(True)
            self.refresh.setDisabled(True)
            self.connect.setText("Disconnect")

            # Create CTRL and DAQ blocks, resize
            self.CTRL = GUI_CTRL_Window(self.root, self.ser)
            self.DAQ = GUI_DAQ_Window(self.root, self.ser)
            self.root.manual_resize(320, 450)

            self.DAQ.start()
            return

        # Ask for confimation to disconnect from the Teensy
        confirmation = QtWidgets.QMessageBox.StandardButton.Apply
        if self.enable_disconnect_confirmation:
            confirmation = QtWidgets.QMessageBox.warning(self, "Confirmation",
                                                         "Are you sure you want to disconnect from the Teensy?",
                                                         QtWidgets.QMessageBox.StandardButton.Cancel |
                                                         QtWidgets.QMessageBox.StandardButton.Apply)
        
        # Do nothing if the user selects no
        if confirmation == QtWidgets.QMessageBox.StandardButton.Apply:
            # Remove the CTRL and DAQ blocks, CTRL requires active serial connection
            self.CTRL.delete()
            
            # DAQ requires no serial connection
            self.serial_close()
            self.is_connected = False
            self.DAQ.delete()

            # Re-enable connection configuration buttons
            self.root.manual_resize(320, 150)
            self.COM_selection.setEnabled(True)
            self.baud_selection.setEnabled(True)
            self.refresh.setEnabled(True)
            self.connect.setText("Connect")
    
    def serial_open(self):
        '''
        Method to setup the serial connection and make sure to go for the next only 
        if the connection is done properly
        '''
        try:
            self.ser.is_open
        except:
            PORT = self.current_port_name
            BAUD = self.current_baud_rate
            self.ser = serial.Serial()
            self.ser.baudrate = BAUD
            self.ser.port = PORT
            # TESTING (WAS 0.1)
            self.ser.timeout = 0.1
        try:
            if self.ser.is_open:
                print("Already Open")
                self.ser.status = True
            else:
                PORT = self.current_port_name
                BAUD = self.current_baud_rate
                self.ser = serial.Serial()
                self.ser.baudrate = BAUD
                self.ser.port = PORT
                # TESTING (WAS 0.01)
                self.ser.timeout = 0.01

                self.ser.open()
                self.ser.status = True
        except:
            self.ser.status = False

    def serial_close(self):
        '''
        Method used to close the serial communication connection
        '''
        try:
            self.ser.is_open
            self.ser.close()
            self.ser.status = False
        except:
            self.ser.status = False

class GUI_CTRL_Window(QtWidgets.QWidget):
    def __init__(self, root, ser):
        """
        Constructs the menu for controlling the valves.
        """
        super().__init__(root)
        self.root = root
        self.ser = ser

        # Valve No Power data (0 = closed, 1 = open)
        self.no_power_valve_states = {}
        self.no_power_valve_states["A"] = 0     # No power closed
        self.no_power_valve_states["B"] = 1     # No power open

        # Initialize states to no power
        self.valve_states = {key:val for key, val in self.no_power_valve_states.items()}

        # Define control state names:
        self.control_state_names = {}
        self.control_state_names["A=0,B=0"] = "Fully Closed"
        self.control_state_names["A=0,B=1"] = "Power off/Operation"
        self.control_state_names["A=1,B=0"] = "Pressurization"
        self.control_state_names["A=1,B=1"] = "Fully Open"

        # Valve Buttons
        self.open_buttons = {}
        self.close_buttons = {}

        # Determines whether control data is saved upon launch or manually
        self.saving_data = False    # Must be manually user enabled.

        # Grid layout for buttons and labels
        bottom_layout = QtWidgets.QGridLayout()
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(10)

        # Create labels
        Standard_Label("VALVE A Control:", bottom_layout, 0)
        Standard_Label("VALVE B Control:", bottom_layout, 1)
        Standard_Label("Control State:", bottom_layout, 2)

        # Open/close buttons for valves A/B
        self.create_open_close_buttons(bottom_layout, "A", 0, 1)
        self.create_open_close_buttons(bottom_layout, "B", 1, 1)

        # Create label for current control state
        self.control_state = QtWidgets.QLabel()
        self.control_state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.update_control_state()
        bottom_layout.addWidget(self.control_state, 2, 1, 1, 2)

        # Create button to begin saving control data
        self.start_button = QtWidgets.QPushButton("Start Save")
        self.start_button.clicked.connect(self.start_save)
        self.start_button.setEnabled(True)
        bottom_layout.addWidget(self.start_button, 0, 3)
        
        # Create button to end saving control data
        self.end_button = QtWidgets.QPushButton("End Save")
        self.end_button.clicked.connect(self.end_save)
        self.end_button.setEnabled(False)
        bottom_layout.addWidget(self.end_button, 1, 3)

        # Dummy widget to hold the layout and be placed inside the frame
        layout_widget = QtWidgets.QFrame()
        layout_widget.setLayout(bottom_layout)
        layout = Frame_with_Title("Control Information", layout_widget)
        self.setLayout(layout)
        self.root.layout.addWidget(self, 2, 0)

    def delete(self):
        """
        Method to remove CTRL Window from the display and delete elements.
        Additionally, forces all valves to return to power-off states and end the current data collection.
        """
        # Cycles through all valves and disables them, regardless of current state
        for key, val in self.no_power_valve_states.items():
            if val:
                self.open_valve(key)
            else:
                self.close_valve(key)

        # Attempts to close the current control data collection, if it is active
        if self.saving_data:
            self.end_save()
        
        # Deletes all widgets in this class
        self.root.layout.removeWidget(self)
        self.deleteLater()
        self = None

    def create_label(self, bottom_layout, text, row):
        """
        Method to create a label with the given text and add it to the layout in a given row.
        """
        label = QtWidgets.QLabel()
        label.setText(text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        bottom_layout.addWidget(label, row, 0)

    def create_open_close_buttons(self, bottom_layout, ID, row, col):
        """
        Method to create a pair of open/close buttons given a button ID and location to put the buttons.
        Automatically initializes the buttons to the current valve states and adds them to the list of buttons.
        """
        open = QtWidgets.QPushButton()
        open.setText("OPEN")
        open.clicked.connect(lambda x: self.open_valve(ID))
        open.setEnabled(not self.valve_states[ID])
        bottom_layout.addWidget(open, row, col)
        self.open_buttons[ID] = open

        close = QtWidgets.QPushButton()
        close.setText("CLOSE")
        close.clicked.connect(lambda x: self.close_valve(ID))
        close.setEnabled(self.valve_states[ID])
        bottom_layout.addWidget(close, row, col+1)
        self.close_buttons[ID] = close

    def open_valve(self, ID):
        """
        Method to open valve with a given ID.
        """
        # Actuate valve + log in console
        self.actuate(ID, "OPEN")
        print(f"Open valve: {ID}")

        # Toggle relevant buttons
        self.valve_states[ID] = 1
        self.open_buttons[ID].setEnabled(False)
        self.close_buttons[ID].setEnabled(True)

        # Update text of control state and log info, if active
        self.update_control_state()
        if self.saving_data:
            self.record_valve_states(f"Open valve {ID}")

    def close_valve(self, ID):
        """
        Method to close valve with a given ID.
        """
        # Actuate valve + log in console
        self.actuate(ID, "CLOSE")
        print(f"Close valve: {ID}")

        # Toggle relevant buttons
        self.valve_states[ID] = 0
        self.open_buttons[ID].setEnabled(True)
        self.close_buttons[ID].setEnabled(False)

        # Update text of control state and log info, if active
        self.update_control_state()
        if self.saving_data:
            self.record_valve_states(f"Close valve {ID}")

    def actuate(self, valve, command):
        """
        Method to give Teensy a signal to actuate MOSFETs for valves.
        """
        # TODO: Create dictionary to directly lookup and send the signal.
        # NOTE: I think the comments are incorrect, as the B valve is open in the power off state.
        if valve == "A":
            if command == "OPEN":
                case = "0"              # pin 2, high
            else:
                case = "1"              # pin 2, low
        else:
            if command == "OPEN":
                case = "2"              # pin 9, high
            else:
                case = "3"              # pin 9, low
        self.ser.write(case.encode())
        print("ACTUATED:", valve, command, case.encode())

    def start_save(self):
        """
        Method to begin saving the control data.
        """
        try:
            directory_path = os.path.dirname(__file__)
            file_path = os.path.join(directory_path, "Data/" + str(time.time_ns()) + "_control_data.csv")
            self.control_data = open(file_path, 'w')

            # Header and initial state
            self.control_data.write("Global Time (ns from Epoch),Valve A State (1=Open),Valve B State(1=Open),Control State,Last Command\n")
            self.record_valve_states("Begin Saving Data")

            # Update buttons, state and print confirmation
            self.saving_data = True
            self.start_button.setEnabled(False)
            self.end_button.setEnabled(True)
            print("Begin saving CONTROL data")
        except:
            print("Cannot open CONTROL data file")
    
    def end_save(self):
        """
        Method to end saving the control data.
        """
        try:
            self.control_data.close()
            self.saving_data = False
            self.start_button.setEnabled(True)
            self.end_button.setEnabled(False)
            print("End saving CONTROL data")
        except:
            print("Cannot close control data file")

    def update_control_state(self):
        """
        Method to update the label indicating the current control state.
        """
        key = f"A={self.valve_states['A']},B={self.valve_states['B']}"
        self.control_state.setText(self.control_state_names[key])

    def record_valve_states(self, command):
        """
        Method to store the state of all valves into the .csv file.
        """
        self.control_data.write(f"{time.time_ns()},{self.valve_states['A']},{self.valve_states['B']},")
        self.control_data.write(f"{self.control_state.text()},{command}\n")

class GUI_DAQ_Window(QtWidgets.QWidget):
    def __init__(self, root, ser):
        """
        Constructs the menu for Viewing and Recording data.
        """
        super().__init__(root)
        self.root = root
        self.ser = ser

        # Constants
        self.Cd = 0.815                           # coeff
        self.A = 3.14159/4.0*(0.125*0.0254)**2    # m^2 using A = pi*1/4(d**2), d is converted from inches to meters
        self.RHO = 998.0                          # kg/m^3

        # Tank volume
        self.vol_gallons = 5.0                   # Initial volume in gallons
        self.vol_start = self.vol_gallons*0.0037854118        # m^3, (initial volume in gal)*( 1 m^3/ 1 gal)
        self.vol = self.vol_start                # m^3, remaining volume
        self.vol_perc = 100.0                    # percentage, remaining volume

        # Variables to track data
        self.p_up = 0.0
        self.p_down = 0.0
        self.mfr = 0.0
        self.saving_data = False

        # Data for plotting
        self.plt_time = []
        self.plt_p_up = []
        self.plt_p_down = []
        self.plt_mfr = []
        self.plt_p_up_mvg_avg = []
        self.plt_p_down_mvg_avg = []
        self.plt_mfr_mvg_avg = []


        # Grid Layout for labels, text, buttons
        bottom_layout = QtWidgets.QGridLayout()
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(10)

        # Create labels for rows
        Standard_Label("Upstream Pressure (PU) [psia]:", bottom_layout, 0)
        Standard_Label("Downstream Pressure (PD) [psia]:", bottom_layout, 1)
        Standard_Label("Mass Flow Rate [kg/s]:", bottom_layout, 2)
        Standard_Label("Tank Volume [%]:", bottom_layout, 3)

        # Create labels for live data
        self.create_data_labels(bottom_layout)

        # Create button to begin saving control data
        self.start_button = QtWidgets.QPushButton("Start Save")
        self.start_button.clicked.connect(self.start_save)
        self.start_button.setEnabled(True)
        bottom_layout.addWidget(self.start_button, 0, 3)
        
        # Create button to end saving control data
        self.end_button = QtWidgets.QPushButton("End Save")
        self.end_button.clicked.connect(self.end_save)
        self.end_button.setEnabled(False)
        bottom_layout.addWidget(self.end_button, 1, 3)

        # Button to refill tank
        self.tank_button = QtWidgets.QPushButton("Refill")
        self.tank_button.clicked.connect(self.refill_tank)
        self.end_button.setEnabled(True)
        bottom_layout.addWidget(self.tank_button, 3, 3)

        # Dummy widget to hold the layout and be placed inside the frame
        layout_widget = QtWidgets.QFrame()
        layout_widget.setLayout(bottom_layout)
        layout = Frame_with_Title("Sensor Information", layout_widget)
        self.setLayout(layout)
        self.root.layout.addWidget(self, 3, 0)

        # Create Graph window
        self.graph = GUI_Graph_Window(root, self)

    def delete(self):
        """
        Method to remove DAQ Window from the display and delete elements.
        Ends data collection, if it is active.
        """
        if self.saving_data:
            self.end_save()

        # Delete the graphs
        self.graph.delete()
        
        self.root.layout.removeWidget(self)
        self.deleteLater()
        self = None

    def start(self):
        """
        Method to read and update sensor data in real time.
        """
        while self.ser.status:
            self.read_data()
            self.update_text()
            self.root.update()
    
    def read_data(self):
        """
        Method to read data from the teensy and update local variables.
        """
        # Read data from teensy
        try:
            local_time, p_up, p_down = self.read_sensors()
            local_time = int(local_time) / 1000000.0        # Convert microseconds (int) to seconds (float)
            self.p_up = float(p_up)
            self.p_down = float(p_down)
            self.calculate_mfr()
        except:
            print("Incorrect number of values read (or conversion error)")
            return
        
        # Writes data to file if currently recording sensor data
        if self.saving_data:
            self.sensor_data.write(f"{time.time_ns()},{local_time},{self.p_up},{self.p_down},{self.mfr},{self.vol_perc}\n")
    
        # Update the 20-point moving average
        self.plt_p_up_mvg_avg = self.plt_p_up_mvg_avg[-19:] + [self.p_up]
        self.plt_p_down_mvg_avg = self.plt_p_down_mvg_avg[-19:] + [self.p_down]
        self.plt_mfr_mvg_avg = self.plt_mfr_mvg_avg[-19:] + [self.mfr]

        # Update the plotting points (last 15 seconds at >25ms samples)
        if 20 <= len(self.plt_p_up_mvg_avg) and ((0 == len(self.plt_time)) or (local_time - self.plt_time[-1] > .025)):
            self.plt_time = self.plt_time[-500:] + [local_time]
            self.plt_p_up = self.plt_p_up[-500:] + [sum(self.plt_p_up_mvg_avg) / 20.0]
            self.plt_p_down = self.plt_p_down[-500:] + [sum(self.plt_p_down_mvg_avg) / 20.0]
            self.plt_mfr = self.plt_mfr[-500:] + [sum(self.plt_mfr_mvg_avg) / 20.0] 

            if len(self.plt_time) < 2:
                return
            
            # update remaining volume using the average mfr over the last time sample
            vol_lost = self.plt_mfr[-1] * (self.plt_time[-1] - self.plt_time[-2]) / self.RHO
            self.vol = max(self.vol - vol_lost, 0)
            self.vol_perc = float(self.vol/self.vol_start*100.0)

    def update_text(self):
        """
        Method to update the live sensor readings.
        """
        if self.p_up:
            self.data_labels["PU"].setText(f"{self.p_up:.6g}")
            self.data_labels["PD"].setText(f"{self.p_down:.6g}")
            self.data_labels["MFR"].setText(f"{self.mfr:.6g}")
            self.data_labels["Volume"].setText(f"{self.vol_perc:.3g}")
        QtWidgets.QApplication.processEvents()

    def calculate_mfr(self):
        """
        Method to calculate mass flow rate.
        """
        # If valve B is closed, there cannot be a mass flow rate, so set it to 0
        if not self.root.com_menu.CTRL.valve_states["B"]:
            self.mfr = 0
            return
        
        # Convert from psi to pascal
        p1 = self.p_up * 6894.75789
        p2 = self.p_down * 6894.75789

        # Calculate mass flow rate, store as string
        self.mfr = self.Cd* self.A* (2*self.RHO*abs(p2 - p1)) ** 0.5

    def read_sensors(self):
        """
        Method to read analog data from teensy over COM connection.
        """
        self.teensy_data = self.ser.readline()
        self.teensy_data = self.teensy_data.decode("ascii").rstrip()
        return self.teensy_data.split(',')

    def start_save(self):
        """
        Method to begin saving the sensor data.
        """
        try:
            directory_path = os.path.dirname(__file__)
            file_path = os.path.join(directory_path, "Data/" + str(time.time_ns()) + "_sensor_data.csv")
            self.sensor_data = open(file_path, 'w')

            # Header
            self.sensor_data.write("Global Time (ns from Epoch),Local Time (ms from test),Upstream Pressure (psia),")
            self.sensor_data.write("Downstream Pressure (psia), Mass Flow Rate (kg/s), Tank Volume (%)\n")

            # Update buttons and print confirmation
            self.saving_data = True
            self.start_button.setEnabled(False)
            self.end_button.setEnabled(True)
            print("Begin saving SENSOR data")
        except:
            print("Cannot open SENSOR data file")
    
    def end_save(self):
        """
        Method to end saving the sensor data.
        """
        try:
            self.sensor_data.close()
            self.saving_data = False
            self.start_button.setEnabled(True)
            self.end_button.setEnabled(False)
            print("End saving SENSOR data")
        except:
            print("Cannot close SENSOR data file")

    def create_data_labels(self, layout):
        """
        Method to create the labels for live data readings.
        """
        self.data_labels = {}

        for i, key in enumerate(["PU", "PD", "MFR", "Volume"]):
            label = QtWidgets.QLabel("-")
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.data_labels[key] = label
            layout.addWidget(label, i, 1)

    def refill_tank(self):
        """
        Method to allow the user to input the initial volume of tank.
        """
        self.dlg = QtWidgets.QDialog()

        # Setup the instructions
        layout = QtWidgets.QVBoxLayout()
        message = QtWidgets.QLabel("How much water is in the tank?\nProvide value in gallons.")
        layout.addWidget(message)

        # Setup the user input
        self.dlg_input = QtWidgets.QLineEdit()
        self.dlg_input.setPlaceholderText("Type here")
        layout.addWidget(self.dlg_input)

        # Add standard buttons and connect to relevant functions
        QBtn = QtWidgets.QDialogButtonBox.StandardButton.Cancel | QtWidgets.QDialogButtonBox.StandardButton.Apply
        buttonBox = QtWidgets.QDialogButtonBox(QBtn)
        buttonBox.clicked.connect(self.refill_tank_activated)
        layout.addWidget(buttonBox)
        self.dlg.setLayout(layout)

        self.dlg.exec()

    def refill_tank_activated(self, button):
        """
        Method to handle input checking and updating the tank display.
        """
        # If the user does not wish to apply the input, ignore everything and close the box
        if "Apply" != button.text():
            self.dlg.close()
            return
        
        # Try to convert user input to floating point value
        try:
            self.vol_gallons = float(self.dlg_input.text())
            self.vol_start = self.vol_gallons*0.0037854118        # m^3, (initial volume in gal)*( 1 m^3/ 1 gal)
            self.vol = self.vol_start                # m^3, remaining volume
            self.vol_perc = 100.0                    # percentage, remaining volume
            self.data_labels["Volume"].setText(f"{self.vol_perc:.3g}")

            # Close the window
            self.dlg.close()
        except:
            print("Cannot convert value to float")
            QtWidgets.QMessageBox.critical(self.dlg, "Improper value",
                                                   "Improper input volume.\nExpected floating point value (e.g., 4.7 or 3).",
                                                   QtWidgets.QMessageBox.StandardButton.Ok)

class GUI_Graph_Window(QtWidgets.QWidget):
    def __init__(self, root, daq):
        """
        Constructs the menu for displaying the data in a live updating graph.
        """
        super().__init__(root)
        self.root = root
        self.daq = daq

        # Constants
        self.interval = 500             # Time between visual graph updates in ms
        self.max_psi = 164.7 + 14.754   # Max Guage pressure + atmosphereic in psi

        # Grid Layout for each plot
        bottom_layout = QtWidgets.QGridLayout()
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.setSpacing(10)

        # Create the pressure plot object
        self.pressure_plot = pg.PlotWidget()
        self.pressure_plot.setBackground("w")
        self.pressure_plot.setTitle("Pressure Readings (last 15 seconds)")
        self.pressure_plot.setLabel("left", "Pressure [psia]")
        self.pressure_plot.setLabel("bottom", "Time [s]")
        self.pressure_plot.addLegend(offset=(-275, 225))
        self.pressure_plot.showGrid(x=True, y=True)
        self.pressure_plot.setMinimumWidth(400)
        bottom_layout.addWidget(self.pressure_plot, 0, 0)

        # TODO: Consider initiallizing the plots with empty lists then only input data in the graph update function to reduce repeated code.
        # Create the local graph data
        self.x_vals = [t - self.daq.plt_time[0] for t in self.daq.plt_time]
        self.plt_max_psi = [self.max_psi] * len(self.x_vals)

        # Create the line objects which will be updated
        self.p_up_pen = pg.mkPen(color='b', width=2)
        self.p_up_line = self.pressure_plot.plot(self.x_vals, self.daq.plt_p_up, name="PU", pen=self.p_up_pen)
        self.p_down_pen = pg.mkPen(color='g', width=2)
        self.p_down_line = self.pressure_plot.plot(self.x_vals, self.daq.plt_p_down, name="PD", pen=self.p_down_pen)
        self.danger_pen = pg.mkPen(color='r', width=2, style=QtCore.Qt.PenStyle.DashLine)
        self.danger_line = self.pressure_plot.plot(self.x_vals, self.plt_max_psi, name="Danger", pen=self.danger_pen)

        # Create the mass flow rate plot object
        self.mfr_plot = pg.PlotWidget()
        self.mfr_plot.setBackground("w")
        self.mfr_plot.setTitle("Mass Flow Rate (last 15 seconds)")
        self.mfr_plot.setLabel("left", "Mass Flow Rate [kg/s]")
        self.mfr_plot.setLabel("bottom", "Time [s]")
        self.mfr_plot.showGrid(x=True, y=True)
        self.mfr_plot.setMinimumWidth(400)
        bottom_layout.addWidget(self.mfr_plot, 0, 1)

        # Create the line object which will be updated
        self.mfr_pen = pg.mkPen(color='k', width=2)
        self.mfr_line = self.mfr_plot.plot(self.x_vals, self.daq.plt_mfr, pen=self.mfr_pen)

        # Creates a timer to update the graphs on a regular interval
        self.timer = QtCore.QTimer()
        self.timer.setInterval(self.interval)
        self.timer.timeout.connect(self.update_plots)
        self.timer.start()

        # Dummy widget to hold the layout and be placed inside the frame
        layout_widget = QtWidgets.QFrame()
        layout_widget.setLayout(bottom_layout)
        layout = Frame_with_Title("Live Graphs", layout_widget)
        self.setLayout(layout)
        self.root.layout.addWidget(self, 1, 1, 3, 1)

    def delete(self):
        """
        Method to remove Graph Window from the display and delete elements.
        """
        self.root.layout.removeWidget(self)
        self.deleteLater()
        self = None

    def update_plots(self):
        """
        Method to visually update the plots.
        """
        # Create the local graph data
        self.x_vals = [t - self.daq.plt_time[0] for t in self.daq.plt_time]
        self.plt_max_psi = [self.max_psi] * len(self.x_vals)

        # Update the data for each of the line objects
        self.p_up_line.setData(self.x_vals, self.daq.plt_p_up)
        self.p_down_line.setData(self.x_vals, self.daq.plt_p_down)
        self.danger_line.setData(self.x_vals, self.plt_max_psi)
        self.mfr_line.setData(self.x_vals, self.daq.plt_mfr)

        # Update the bounds for the pressure plot
        lower_bound = 0.5 * min(min(self.daq.plt_p_up), min(self.daq.plt_p_down))
        upper_bound = 1.1 * max(max(self.daq.plt_p_up), max(self.daq.plt_p_down))
        self.pressure_plot.setYRange(lower_bound, upper_bound)

        # Update the bounds for the mfr plot
        lower_bound = 0
        upper_bound = 1.1 * max(max(self.daq.plt_mfr), 0.02)
        self.mfr_plot.setYRange(lower_bound, upper_bound)
        

class Frame_with_Title(QtWidgets.QVBoxLayout):
    def __init__(self, title, bottom_widget):
        """
        Packages together a layout section with a label and title.
        """
        super().__init__()

        # Formatting
        self.setContentsMargins(0, 10, 0, 0)
        self.setSpacing(0)

        # Adds the title to a widget aligned to the left side of the top box
        title_w = QtWidgets.QLabel()
        title_w.setText(f"  {title}")
        title_w.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        title_w.setMaximumHeight(15)
        self.addWidget(title_w)

        # Adds a frame around the bottom widget and inserts into the bottom box
        bottom_widget.setFrameShape(QtWidgets.QFrame.Shape.Box)
        self.addWidget(bottom_widget)

        # TESTING ONLY (COLOR FOR BOUNDARIES)
        self.set_color(title_w, "purple")
        self.set_color(bottom_widget, "green")
        #self.set_color(frame, "blue")

    def set_color(self, widget, color):
        """
        Method to change the background color of any widget.
        """
        widget.setAutoFillBackground(True)
        palette = widget.palette()
        palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(color))
        widget.setPalette(palette)

class Standard_Label(QtWidgets.QLabel):
    def __init__(self, text, layout, row):
        """
        Generates a label with left aligned text and attaches it to the leftmost column on the specified row.
        """
        super().__init__()
        self.setText(text)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self, row, 0)
