# GUI_GRAPHS.py
# This file hosts the UI elements for plotting data from various sensors aboard the flight hardware
from collections import deque
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QDialog, QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
from typing import Dict, Tuple

from GUI_CONTROLLER import GUIController


"""
Sensor Graph

This widget uses matplotlib in order to plot data. It is inteded to be heavily manually
controlled by its parent, as such it is a very passive widget, only containing functions
that change its state which are meant to be called by the parent

"""
class SensorGraph(QWidget):
    def __init__(self, sensor_name: str, parent=None):
        super().__init__(parent)
        self.sensor_name = sensor_name
        
        self.render_seconds: int = 10           # render the last 10 seconds
        
        self.backend_maxlen: int = 1000         # enough to store 10s of 100Hz data
        self.render_maxlen: int = 300           # cheaper to render

        self.backend_data: deque[float, float] = deque(maxlen=self.backend_maxlen)  # value, timestamp
        self.render_data: deque[float, float] = deque(maxlen=self.render_maxlen)    # value, timestamp

        
        
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)

        self.figure.set_constrained_layout(True)
        
        unit = self.get_unit(self.sensor_name)
        self.ax.set_title(f"{self.sensor_name} ({unit})")
        self.ax.set_xlabel("Time (seconds ago)")
        self.ax.set_ylabel(f"Value ({unit})")
        self.line = self.ax.plot([], [], 'g-', linewidth=2)[0]
        self.ax.grid(True)

        self.last_render_time: int = 0          # ms since Jan 1 1970 (UNIX time)
        self.max_render_interval: int = 100     # ms
        
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self.set_graph_styling()
        
        self.line.set_data([], [])
        self.ax.set_xlim(-10, 0)
        self.canvas.draw()

    def get_unit(self, sensor_name: str):
        if sensor_name.startswith('P'):
            return 'psi'
        elif sensor_name.startswith('TC'):
            return '°C'
        elif sensor_name.startswith('LC') or sensor_name.startswith('B'):
            return 'lb'
        return ''

    def list_all_fonts(self):
        # List all available fonts with their properties
        fonts = fm.fontManager.ttflist
        print("All available fonts:")
        for font in fonts:
            print(f"Name: {font.name}, File: {font.fname}")

    def update_graph(self):
        if not self.backend_data:
            return

        # Determine the step size needed to produce an evenly spaced array to render
        step = self.render_seconds / self.render_maxlen

        # Grab the current time in a float
        now = QDateTime.currentMSecsSinceEpoch() / 1000.0
        
        # Reload the render data
        # self.render_data = []
        for val, ts in self.backend_data:
            relative_ts = ts - now

            # If this val is within the time range
            if -self.render_seconds <= relative_ts <= 0:
                # If ts is an appropiate step size away from the previous item
                if not self.render_data or abs(relative_ts - self.render_data[-1][1]) > step:
                    self.render_data.append([val, relative_ts])

        # Quit if no data matched the profile
        if not self.render_data:
            return

        # Set the line data
        render_timestamps = [item[1] for item in self.render_data]
        render_values = [item[0] for item in self.render_data]
        self.line.set_data(render_timestamps, render_values)
        
        # Determine x and y constraints
        y_min = min(render_values)
        y_max = max(render_values)
        padding = max(0.1 * (y_max - y_min), 0.1)
        self.ax.set_ylim(y_min - padding, y_max + padding)
        self.ax.set_xlim(-self.render_seconds, 0)
        
        # Render
        self.canvas.draw()
    
    def update_single(self, value: float, timestamp: float):
        # Add the data to the backend
        self.backend_data.append([value, timestamp])
        
        # Re-render ONLY at regular time intervals
        now = QDateTime.currentMSecsSinceEpoch()
        if (now - self.last_render_time) > self.max_render_interval:
            self.last_render_time = now
            self.update_graph()

    def set_graph_styling(self):
        # Get the actual screen DPI
        screen = QApplication.primaryScreen()
        dpi = screen.logicalDotsPerInch()

        def points_to_pixels(points: int):
            return 0.75 * points * dpi / 72   # tuned by iteration but allegedly it is supposed to be dpi/72

        font_pts = points_to_pixels(10)

        self.ax.xaxis.label.set_fontsize(font_pts)
        self.ax.yaxis.label.set_fontsize(font_pts)
        self.ax.title.set_fontsize(font_pts)

        self.ax.xaxis.label.set_fontweight('bold')
        self.ax.yaxis.label.set_fontweight('bold')
        self.ax.title.set_fontweight('bold')

        for label in self.ax.get_xticklabels():
            label.set_fontsize(font_pts)
            label.set_fontweight('normal')
        
        for label in self.ax.get_yticklabels():
            label.set_fontsize(font_pts)
            label.set_fontweight('normal')
        

    def set_dark_mode(self, dark: bool):
        if dark:
            self.figure.set_facecolor('#222222')
            self.ax.set_facecolor('#222222')

            self.ax.xaxis.label.set_color('white')
            self.ax.yaxis.label.set_color('white')
            self.ax.title.set_color('white')

            self.ax.tick_params(axis='x', colors='white')
            self.ax.tick_params(axis='y', colors='white')

            for spine in self.ax.spines.values():
                spine.set_color('white')

            self.line.set_color('cyan')
        else:
            self.figure.set_facecolor('white')
            self.ax.set_facecolor('white')

            self.ax.xaxis.label.set_color('black')
            self.ax.yaxis.label.set_color('black')
            self.ax.title.set_color('black')

            self.ax.tick_params(axis='x', colors='black')
            self.ax.tick_params(axis='y', colors='black')

            for spine in self.ax.spines.values():
                spine.set_color('black')
            self.line.set_color('green')

        self.canvas.draw()

"""
Sensor Popup Graph

This is a container for a graph that has it inside a dedicated window, it is extremely
passive and is manually controlled in its entirety by SensorGridWindow

"""
class SensorPopupGraph(QDialog):
    def __init__(self, sensor_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{sensor_name} - Live Graph")
        self.resize(800, 500)
        self.sensor_name = sensor_name
        self.setModal(False)

        self.sensor_graph = SensorGraph(sensor_name=self.sensor_name, parent=parent)

        layout = QVBoxLayout()
        layout.addWidget(self.sensor_graph)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)


"""
Sensor Frame

This is simply a wrapper for the QFrame type, which is helpful for making global style
configuration easier. Frames used in SensorGridWindow need to have different style settings
from the rest of the QFrames in the GUI, so it just calls this wrapper type instead. 

Globally they are treated as different types
"""
class SensorFrame(QFrame):
    def __init__(self):
        super().__init__()

"""
SensorGridWindow

This window displayes a big grid of the current sensor readings.
A single click to each sensor reading will update the main graph in the layout to that sensor
A double click to each sensor reading opens up a separate window containing its data

INPUT DEPENDENCIES:
    GUIController.signals.sensor_updated(str, float)
        When data comes in directly from the comms system and is post processed by the GUIController, it updates
        this view in order to see new sensor readings and updated graphs

OUTPUT DEPENDENCIES:
    self.open_graph(str)
        Opens a new window with a corresponding graph (albeit that window is still owned and managed by this window)

"""
class SensorGridWindow(QWidget):
    def __init__(self, controller: GUIController):
        super().__init__()

        self.controller = controller
        self.controller.signals.sensor_updated.connect(self.update_sensor_value)
        
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.setLayout(self.grid)

        self.sensors = [f"P{i}" for i in range(1, 9)] + \
                       [f"TC{i}" for i in range(1, 4)] + \
                       [f"LC{i}" for i in range(1, 4)] + \
                       [f"B{i}" for i in range(1, 3)]
        
        self.sensor_frames: Dict[str, SensorFrame] = {}  # Container frames for each sensor
        self.sensor_labels: Dict[str, str] = {}  # Sensor name labels
        self.value_labels: Dict[str, QLabel] = {}   # Value display labels
        self.unit_labels: Dict[str, str] = {}   # Unit labels
        self.graphs: Dict[str, SensorPopupGraph] = {}
        self.main_graph: SensorGraph = None
        self.sensor_history: Dict[str, deque[Tuple[float, float]]] = {}
        # self.sensor_history: Dict[ str, [Tuple[float, float]] ] = {}
        self.dark_mode = False

        self.update_main_graph(self.sensors[0])

        for idx, name in enumerate(self.sensors):
            self.create_sensor_box(name, idx)
            self.sensor_history[name] = deque(maxlen=10000)     # length will be much larger than the one used in rendering

    def create_sensor_box(self, name: str, idx: int):
        """Create a bordered box for each sensor with labels inside"""
        # Create frame with border
        frame = SensorFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(2)
        
        # Layout for the frame
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)
        frame_layout.setSpacing(5)
        
        # Sensor name label (left-aligned, borderless) - larger font (14pt)
        name_label = QLabel(f"{name}:")
        name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        # name_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # name_label.setFont(QFont("Arial", 14))  # Increased identifier font
        frame_layout.addWidget(name_label)
        
        # Value display (centered) - slightly smaller font (18pt instead of 20pt)
        value_label = QLabel("---")
        value_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        frame_layout.addWidget(value_label)
        
        # Unit label (right-aligned, borderless) - larger font (14pt)
        unit = self.get_unit(name)
        unit_label = QLabel(unit)
        unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        frame_layout.addWidget(unit_label)
        
        # Add to grid
        row, col = divmod(idx, 4)
        self.grid.addWidget(frame, row, col)
        
        # Store references
        self.sensor_frames[name] = frame
        self.sensor_labels[name] = name_label
        self.value_labels[name] = value_label
        self.unit_labels[name] = unit_label
        
        # Make entire frame clickable to open graph
        frame.mousePressEvent = lambda event, sn=name: self.update_main_graph(sn)
        frame.mouseDoubleClickEvent = lambda event, sn=name: self.open_graph(sn)
        
        # Apply initial styling
        # self.update_sensor_style(name)

    def get_unit(self, sensor_name: str):
        if sensor_name.startswith('P'):
            return 'psi'
        elif sensor_name.startswith('TC'):
            return '°C'
        elif sensor_name.startswith('LC') or sensor_name.startswith('B'):
            return 'lb'
        return ''

    def set_dark_mode(self, dark: bool):
        self.dark_mode = dark
        if self.main_graph:
            self.main_graph.set_dark_mode(self.dark_mode)
        # for sensor in self.sensors:
        #     self.update_sensor_style(sensor)
        for graph in self.graphs.values():
            graph.sensor_graph.set_dark_mode(dark)

    def update_sensor_value(self, sensor: str, value: float, timestamp: float):
        if sensor not in self.value_labels:
            return
            
        self.value_labels[sensor].setText(f"{value:.2f}")
        self.sensor_history[sensor].append((timestamp, value))
        
        if sensor in self.graphs:
            self.graphs[sensor].sensor_graph.update_single(value, timestamp)
        
        if sensor == self.main_graph.sensor_name:
            self.main_graph.update_single(value, timestamp)

    def update_main_graph(self, sensor: str):
        # If we already have a main_graph update its data to maintain the link to the UI
        if self.main_graph:
            # Update the sensor name and title
            self.main_graph.sensor_name = sensor
            unit = self.main_graph.get_unit(sensor)
            
            # Clear existing data
            self.main_graph.timestamps.clear()
            self.main_graph.values.clear()
            self.main_graph.ax.clear()

            self.main_graph.ax.set_title(f"{sensor} ({unit})")
            self.main_graph.ax.set_xlabel("Time (seconds ago)")
            self.main_graph.ax.set_ylabel(f"Value ({unit})")
            self.main_graph.line = self.main_graph.ax.plot([], [], 'g-', linewidth=2)[0]
            self.main_graph.ax.grid(True)

            self.main_graph.set_graph_styling()

            self.main_graph.line.set_data([], [])
            self.main_graph.ax.set_xlim(-10, 0)
            self.main_graph.ax.set_ylim(0, 1)
            self.main_graph.canvas.draw()
            
            # Load historical data for this sensor
            history = self.sensor_history.get(sensor, [])
            for ts, val in history:
                self.main_graph.timestamps.append(ts)
                self.main_graph.values.append(val)

            self.main_graph.update_graph()

        else:
            # Create new graph only if we don't have one yet
            self.main_graph = SensorGraph(sensor)
            # self.main_graph.set_dark_mode(self.dark_mode)
            self.main_graph.canvas.draw()
            
            history = self.sensor_history.get(sensor, [])
            for ts, val in history:
                self.main_graph.timestamps.append(ts)
                self.main_graph.values.append(val)

            self.main_graph.update_graph()
        
    def open_graph(self, sensor: str):
        if sensor not in self.graphs:
            self.graphs[sensor] = SensorPopupGraph(sensor)
            # self.graphs[sensor].sensor_graph.set_dark_mode(self.dark_mode)
            
            history = self.sensor_history.get(sensor, [])
            for ts, val in history:
                self.graphs[sensor].sensor_graph.timestamps.append(ts)
                self.graphs[sensor].sensor_graph.values.append(val)
            
            self.graphs[sensor].sensor_graph.update_graph()
            # for ts, val in history:
            #     self.graphs[sensor].sensor_graph.update_graph(val, ts)
        
        self.graphs[sensor].show()
        self.graphs[sensor].raise_()
        self.graphs[sensor].activateWindow()
