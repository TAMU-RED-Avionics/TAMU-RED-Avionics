# GUI_LAYOUT.py
# This is the master file that determines the overall layout of the various UI elements
from re import S
from PyQt5.QtWidgets import QMainWindow, QSizePolicy, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFrame
from PyQt5.QtCore import QSize, Qt
from GUI_LOGO import LogoWindow
from GUI_CONTROLLER import GUIController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rocket Engine Control Panel")
        self.setGeometry(10, 10, 1280, 720)

        # Dark mode is the only setting where it makes sense to have contained to this window
        self.dark_mode = False

        self.controller = GUIController()

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Logo layout
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(20)

        self.logo = LogoWindow()

        self.dark_mode_btn = QPushButton("Dark Mode")
        self.dark_mode_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)

        self.text_size = 12
        self.text_size_btn = QPushButton("Large Text")
        self.text_size_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.text_size_btn.clicked.connect(self.change_text_size)

        logo_layout.addWidget(self.logo)
        logo_layout.addWidget(self.text_size_btn)
        logo_layout.addWidget(self.dark_mode_btn)
        main_layout.addLayout(logo_layout)

        # Initialization of all the controls and valve diagram
        control_layout = QHBoxLayout()
        control_lhs_layout = QVBoxLayout()
        control_rhs_layout = QVBoxLayout()
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_lhs_layout.setContentsMargins(0, 0, 0, 0)
        control_rhs_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(20)
        control_lhs_layout.setSpacing(10)
        control_rhs_layout.setSpacing(0)
        control_rhs_layout.setAlignment(Qt.AlignTop)

        # Setup of connection widget
        control_lhs_layout.addWidget(self.controller.conn_widget)

        # Setup of the daq widget
        control_lhs_layout.addWidget(self.controller.daq_window)

        # Setup of abort menu
        control_lhs_layout.addWidget(self.controller.abort_menu)

        # Setup of the valve control grid
        control_lhs_layout.addWidget(self.controller.valve_control)
        control_rhs_layout.addWidget(self.controller.diagram)

        control_layout.addLayout(control_lhs_layout, stretch=3)
        control_layout.addLayout(control_rhs_layout, stretch=2)

        main_layout.addLayout(control_layout)

        sensor_layout = QHBoxLayout()
        sensor_lhs_layout = QVBoxLayout()
        sensor_rhs_layout = QVBoxLayout()
        sensor_layout.setContentsMargins(0, 0, 0, 0)
        sensor_lhs_layout.setContentsMargins(0, 0, 0, 0)
        sensor_rhs_layout.setContentsMargins(0, 0, 0, 0)
        sensor_layout.setSpacing(20)
        sensor_lhs_layout.setSpacing(10)
        sensor_rhs_layout.setSpacing(0)
        sensor_rhs_layout.setAlignment(Qt.AlignTop)

        # Current states and sensor grid
        self.controller.status_label.setAlignment(Qt.AlignCenter)
        sensor_lhs_layout.addWidget(self.controller.status_label)
        sensor_lhs_layout.addWidget(self.controller.sensor_grid)

        # The main graph which will always be there
        sensor_rhs_layout.addWidget(self.controller.sensor_grid.main_graph)

        # Final configuration of main window
        sensor_layout.addLayout(sensor_lhs_layout, stretch=3)
        sensor_layout.addLayout(sensor_rhs_layout, stretch=2)

        main_layout.addLayout(sensor_layout)

        self.apply_stylesheet()

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def make_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line
    
    def change_text_size(self):
        if self.text_size == 12:
            self.text_size = 14
            self.apply_stylesheet()
            self.text_size_btn.setText("Small Text")

        elif self.text_size == 14:
            self.text_size = 6
            self.apply_stylesheet()
            self.text_size_btn.setText("Medium Text")

        elif self.text_size == 6:
            self.text_size = 12
            self.apply_stylesheet()
            self.text_size_btn.setText("Large Text")
        else:
            self.text_size = 12
            self.apply_stylesheet()
            self.text_size_btn.setText("Large Text")


    def toggle_dark_mode(self):
        """Toggle between dark and light mode"""
        self.dark_mode = not self.dark_mode
        self.apply_stylesheet()
        if self.dark_mode:
            self.logo.set_dark_image()
            self.controller.diagram.set_dark_image()
        else:
            self.logo.set_light_image()
            self.controller.diagram.set_light_image()
        
        self.dark_mode_btn.setText("Light Mode" if self.dark_mode else "Dark Mode")
        
        # Update sensor grid
        self.controller.sensor_grid.set_dark_mode(self.dark_mode)

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
                    border-radius: 10px;
                    border-color: #999999;
                    font-family: "Arail";
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    padding: 2px 6px 2px 6px;
                }}
                QPushButton:pressed {{
                    background-color: #222222;
                    border-style: inset;
                }}
                QPushButton:hover {{
                    background-color: #666666;
                }}
                QLineEdit {{
                    background-color: #333333;
                    color: #FFFFFF;
                    font-family: "Arail";
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    border-style: inset;
                    border-width: 2px;
                    border-radius: 10px;
                    border-color: #666666;
                    padding: 2px 6px 2px 6px;
                }}
                QLabel {{
                    font-family: "Arail";
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    color: #FFFFFF;
                }}
                ValveDiagram {{
                    background-color: #222222;
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
                    border-radius: 10px;
                    border-color: #666666;
                    font-family: "Arail";
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    padding: 2px 6px 2px 6px;
                }}
                QPushButton:hover {{
                    background-color: #CCCCCC;
                    border-style: inset;
                }}
                QPushButton:pressed {{
                    background-color: #666666;
                    border-style: inset;
                }}
                QLineEdit {{
                    background-color: #FFFFFF;
                    color: #000000;
                    font-family: "Arail";
                    font-size: {self.text_size}pt;
                    font-weight: bold;
                    border-style: inset;
                    border-width: 2px;
                    border-radius: 10px;
                    border-color: #666666;
                    padding: 2px 6px 2px 6px;
                }}
                QLabel {{
                    font-family: "Arail";
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
            """
            self.setStyleSheet(light_stylesheet)
