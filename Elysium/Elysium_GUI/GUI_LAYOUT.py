# GUI_LAYOUT.py
# This is the master file that determines the overall layout of the various UI elements
from re import S
from PyQt5.QtWidgets import QMainWindow, QSizePolicy, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFrame, QLabel
from PyQt5.QtCore import QSize, Qt

from GUI_LOGO import LogoWindow
from GUI_ABORT import AbortWindow
from GUI_LOGO import LogoWindow
from GUI_DAQ import DAQWindow
from GUI_CONNECT import ConnectionWindow
from GUI_VALVE_DIAGRAM import ValveDiagramWindow
from GUI_GRAPHS import SensorGridWindow, SensorGraph
from GUI_VALVE_CONTROL import ValveControlWindow

from GUI_CONTROLLER import GUIController

""" 
Main Window

This window is organizing the main layout of the whole GUI, particually the location and
orientation of the different windows with respect to each other.

It owns both the controller and the different sub windows, feeding the controller into their initializers
Note that each window will deal with all their connections internally. If they require an update from external changes,
they can bind themselves to the controller's signals. If they have buttons which need to do things, they bind those
buttons to functions in the controller.

"""
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rocket Engine Control Panel")
        self.setGeometry(10, 10, 1280, 720)

        # Dark mode is the only setting where it makes sense to have contained to this window
        self.dark_mode = False

        self.controller = GUIController(self)

        # Here we declare most of the UI elements that will be used. They are owned by the Controller to make it easy to manage interconnections
        self.diagram = ValveDiagramWindow(self.controller)
        self.conn_widget = ConnectionWindow(self.controller)
        self.valve_control = ValveControlWindow(self.controller)
        self.status_label = QLabel("Current State: None")
        self.sensor_grid = SensorGridWindow(self.controller)
        self.daq_window = DAQWindow(self.controller)
        self.abort_menu = AbortWindow(self.controller)

        self.controller.signals.system_status.connect(self.update_status_label)

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        
        # Main layout def (top most layout)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Logo layout
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(20)
        self.logo = LogoWindow()

        # Mode and text configuration
        self.dark_mode_btn = QPushButton("Dark Mode")
        self.dark_mode_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)

        self.text_size = 12
        self.text_size_btn = QPushButton("Large Text")
        self.text_size_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.text_size_btn.clicked.connect(self.change_text_size)

        # Building out the logo widget
        logo_layout.addWidget(self.logo)
        logo_layout.addWidget(self.text_size_btn)
        logo_layout.addWidget(self.dark_mode_btn)
        main_layout.addLayout(logo_layout)

        # Setting up the main 2 pane horizontal layout
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)

        lhs_layout = QVBoxLayout()
        lhs_layout.setContentsMargins(0, 0, 0, 0)
        lhs_layout.setSpacing(10)

        rhs_layout = QVBoxLayout()
        rhs_layout.setContentsMargins(0, 0, 0, 0)
        rhs_layout.setSpacing(10)

        body_layout.addLayout(lhs_layout, stretch=3)
        body_layout.addLayout(rhs_layout, stretch=2)

        # Setup of connection widget
        lhs_layout.addWidget(self.conn_widget, stretch=2)

        # Setup of the daq widget
        lhs_layout.addWidget(self.daq_window, stretch=3)

        # Setup of abort menu
        lhs_layout.addWidget(self.abort_menu, stretch=1)

        # Setup of the valve control grid
        lhs_layout.addWidget(self.valve_control, stretch=7)
        rhs_layout.addWidget(self.diagram)
        
        # Current states and sensor grid
        self.status_label.setAlignment(Qt.AlignCenter)
        lhs_layout.addWidget(self.status_label, stretch=1)
        lhs_layout.addWidget(self.sensor_grid, stretch=5)

        # The main graph which will always be there
        self.sensor_grid.main_graph.setMinimumHeight(20)
        rhs_layout.addWidget(self.sensor_grid.main_graph)

        # Add the 2 pane layout to the main vertical payout
        main_layout.addLayout(body_layout)

        # Configure the look of all buttons, text, etc
        self.apply_stylesheet()

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)


    def update_status_label(self, status: str):
        self.status_label.setText("Current State: " + status)

    def make_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line
    
    def change_text_size(self):
        if self.text_size == 10:
            self.text_size = 12
            self.apply_stylesheet()
            self.text_size_btn.setText("Small Text")

        elif self.text_size == 12:
            self.text_size = 8
            self.apply_stylesheet()
            self.text_size_btn.setText("Medium Text")

        elif self.text_size == 8:
            self.text_size = 10
            self.apply_stylesheet()
            self.text_size_btn.setText("Large Text")
        else:
            self.text_size = 10
            self.apply_stylesheet()
            self.text_size_btn.setText("Large Text")


    def toggle_dark_mode(self):
        """Toggle between dark and light mode"""
        self.dark_mode = not self.dark_mode
        self.apply_stylesheet()
        if self.dark_mode:
            self.logo.set_dark_image()
            self.diagram.set_dark_image()
        else:
            self.logo.set_light_image()
            self.diagram.set_light_image()
        
        self.dark_mode_btn.setText("Light Mode" if self.dark_mode else "Dark Mode")
    
    
    def apply_stylesheet(self):
        """Apply appropriate stylesheet based on current mode"""
        if self.dark_mode:
            dark_stylesheet = f"""
                QMainWindow {{
                    background-color: #222222;
                }}
                QWidget {{
                    background-color: #222222;
                    color: #FFFFFF;
                }}
                QPushButton {{
                    background-color: #333333;
                    color: #FFFFFF;
                    border-style: inset;
                    border-width: 2px;
                    border-radius: 8px;
                    border-color: #999999;
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    padding: 2px 10px 2px 10px;
                }}
                QPushButton:pressed {{
                    background-color: #222222;
                    border-style: inset;
                }}
                QPushButton:hover {{
                    background-color: #222222;
                }}
                QPushButton:disabled {{
                    background-color: #222222;
                }}
                QLineEdit {{
                    background-color: #333333;
                    color: #FFFFFF;
                    font-size: {self.text_size}pt;
                    font-weight: normal;
                    border-style: inset;
                    border-width: 2px;
                    border-radius: 8px;
                    border-color: #666666;
                    padding: 2px 10px 2px 10px;
                }}
                QLabel {{
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    color: #FFFFFF;
                }}
                ValveDiagram {{
                    background-color: #222222;
                }}
                SensorFrame {{
                    border: 2px solid #CCCCCC;
                    border-radius: 5px;
                    background-color: #444444;
                }}
                QLabel {{
                    background-color: transparent;
                }}
            """
            self.setStyleSheet(dark_stylesheet)
        else:
            # Light mode - reset to default
            light_stylesheet = f"""
                QMainWindow {{
                    background-color: #FFFFFF;
                }}
                QPushButton {{
                    background-color: #FFFFFF;
                    color: #000000;
                    border-style: inset;
                    border-width: 2px;
                    border-radius: 8px;
                    border-color: #666666;
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    padding: 2px 10px 2px 10px;
                }}
                QPushButton:hover {{
                    background-color: #CCCCCC;
                    border-style: inset;
                }}
                QPushButton:disabled {{
                    background-color: #CCCCCC;
                }}
                QPushButton:pressed {{
                    background-color: #CCCCCC;
                    border-style: inset;
                }}
                QLineEdit {{
                    background-color: #FFFFFF;
                    color: #000000;
                    font-size: {self.text_size}pt;
                    font-weight: normal;
                    border-style: inset;
                    border-width: 2px;
                    border-radius: 8px;
                    border-color: #666666;
                    padding: 2px 10px 2px 10px;
                }}
                QLabel {{
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    color: #000000;
                }}
                QHBoxLayout {{
                    background-color: #FFFFFF;
                }}
                QVBoxLayout {{
                    background-color: #FFFFFF;
                }}
                ValveDiagram {{
                    background-color: #FFFFFF;
                }}
                SensorFrame {{
                    border: 2px solid #AAAAAA;
                    border-radius: 5px;
                    background-color: #F0F0F0;
                }}
                QLabel {{
                    background-color: transparent;
                }}
            """
            self.setStyleSheet(light_stylesheet)

        self.sensor_grid.set_dark_mode(self.dark_mode)
