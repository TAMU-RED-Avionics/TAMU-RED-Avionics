# GUI_LAYOUT.py
# This is the master file that determines the overall layout of the various UI elements
from re import S
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFrame
from PyQt5.QtCore import Qt
from GUI_LOGO import LogoWindow
from GUI_CONTROLLER import GUIController

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rocket Engine Control Panel")
        self.setGeometry(100, 100, 1280, 720)

        # Dark mode is the only setting where it makes sense to have contained to this window
        self.dark_mode = False

        self.controller = GUIController()

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(0)

        # Logo layout
        logo_layout = QHBoxLayout()
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(20)

        self.logo = LogoWindow()

        self.dark_mode_btn = QPushButton("Dark Mode")
        self.dark_mode_btn.setFixedWidth(200)
        self.dark_mode_btn.clicked.connect(self.toggle_dark_mode)

        self.text_size = 12
        self.text_size_btn = QPushButton("Large Text")
        self.text_size_btn.setFixedWidth(200)
        self.text_size_btn.clicked.connect(self.change_text_size)

        logo_layout.addWidget(self.logo)
        # logo_layout.addWidget(self.text_size_btn)
        logo_layout.addWidget(self.dark_mode_btn)
        main_layout.addLayout(logo_layout)

        # Initialization of the main body
        body_horizontal_layout = QHBoxLayout()
        body_lhs_layout = QVBoxLayout()
        body_rhs_layout = QVBoxLayout()
        body_horizontal_layout.setContentsMargins(0, 0, 0, 0)
        body_lhs_layout.setContentsMargins(0, 0, 0, 0)
        body_rhs_layout.setContentsMargins(0, 0, 0, 0)
        body_horizontal_layout.setSpacing(20)
        body_lhs_layout.setSpacing(10)
        body_rhs_layout.setSpacing(0)
        body_rhs_layout.setAlignment(Qt.AlignTop)

        # Setup of connection widget
        body_lhs_layout.addWidget(self.controller.conn_widget)

        # Setup of the daq widget
        body_lhs_layout.addWidget(self.controller.daq_window)

        # Setup of abort menu
        body_lhs_layout.addWidget(self.controller.abort_menu)

        # Setup of the valve control panel
        valve_control_layout = QHBoxLayout()

        # self.valve_control.setStyleSheet("border: 2px solid red;")
        valve_control_layout.addWidget(self.controller.valve_control)
        valve_control_layout.addWidget(self.controller.diagram)
        body_lhs_layout.addWidget(self.controller.valve_control)

        # Current states and sensor grid
        self.controller.status_label.setAlignment(Qt.AlignCenter)
        body_lhs_layout.addWidget(self.controller.status_label)
        body_lhs_layout.addWidget(self.controller.sensor_grid)

        body_rhs_layout.addWidget(self.controller.diagram)        

        # Final configuration of main window
        body_horizontal_layout.addLayout(body_lhs_layout)
        body_horizontal_layout.addLayout(body_rhs_layout)
        main_layout.addLayout(body_horizontal_layout)

        self.apply_stylesheet()

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def make_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        return line
    
    def change_text_size(self):
        if self.text_size == 16:
            print("Setting to large size")
            self.text_size = 24
            self.apply_stylesheet()
            self.text_size_btn.setText("Small Text")

        elif self.text_size == 24:
            print("Setting to small size")
            self.text_size = 12
            self.apply_stylesheet()
            self.text_size_btn.setText("Medium Text")

        elif self.text_size == 12:
            print("Setting to medium size")
            self.text_size = 16
            self.apply_stylesheet()
            self.text_size_btn.setText("Large Text")
        else:
            print("No matching text size")
            self.text_size = 16
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
            # dark_stylesheet = """
            #     QWidget {
            #         background-color: #333333;
            #         color: #EEEEEE;
            #     }
            #     QLabel {
            #         color: #EEEEEE;
            #     }
            #     QPushButton {
            #         background-color: #555555;
            #         color: #EEEEEE;
            #         border: 1px solid #888888;
            #     }
            #     QPushButton:hover {
            #         background-color: #666666;
            #     }
            #     QPushButton:pressed {
            #         background-color: #444444;
            #     }
            #     QLineEdit {
            #         background-color: #444444;
            #         color: #EEEEEE;
            #         border: 1px solid #555555;
            #     }
            #     QCheckBox {
            #         color: #EEEEEE;
            #     }
            #     QScrollArea {
            #         background-color: #333333;
            #     }
            #     QFrame {
            #         background-color: #555555;
            #     }
            #     QDialog {
            #         background-color: #333333;
            #     }
            #     /* Valve diagram background */
            #     ValveDiagram {
            #         background-color: #222222;
            #     }
            # """
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
                    padding: 6px;
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
                    padding: 2px;
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
                    padding: 6px;
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
                    padding: 2px;
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
