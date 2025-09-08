from collections import deque
from PyQt5.QtWidgets import (
    QWidget, QLabel, QGridLayout, QDialog, 
    QVBoxLayout, QHBoxLayout, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal, QObject
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

class SensorSignals(QObject):
    update_signal = pyqtSignal(str, float)

class SensorPopupGraph(QDialog):
    def __init__(self, sensor_name, parent=None):
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


class SensorGraph(QWidget):
    def __init__(self, sensor_name, parent=None):
        super().__init__(parent)
        
        self.timestamps = deque(maxlen=100)
        self.values = deque(maxlen=100)
        
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        
        unit = self.get_unit(sensor_name)
        self.ax.set_title(f"{sensor_name} ({unit})")
        self.ax.set_xlabel("Time (seconds ago)")
        self.ax.set_ylabel(f"Value ({unit})")
        self.line, = self.ax.plot([], [], 'g-', linewidth=2)
        self.ax.grid(True)
        
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        self.line.set_data([], [])
        self.ax.set_xlim(-10, 0)
        self.canvas.draw()

    def get_unit(self, sensor_name):
        if sensor_name.startswith('P'):
            return 'psi'
        elif sensor_name.startswith('TC'):
            return '°C'
        elif sensor_name.startswith('LC') or sensor_name.startswith('B'):
            return 'lb'
        return ''

    def update_graph(self, value, current_time):
        self.timestamps.append(current_time)
        self.values.append(value)
        
        if not self.timestamps:
            return
            
        relative_times = [(ts - current_time) for ts in self.timestamps]
        self.line.set_data(relative_times, self.values)
        self.ax.set_xlim(-10, 0)
        
        if self.values:
            visible_indices = [i for i, rt in enumerate(relative_times) if rt >= -10]
            if visible_indices:
                visible_values = [self.values[i] for i in visible_indices]
                y_min = min(visible_values)
                y_max = max(visible_values)
                padding = max(0.1 * (y_max - y_min), 0.1)
                self.ax.set_ylim(y_min - padding, y_max + padding)
        
        self.canvas.draw()

    def set_dark_mode(self, dark):
        if dark:
            self.figure.set_facecolor('#333333')
            self.ax.set_facecolor('#333333')
            self.ax.tick_params(axis='x', colors='white')
            self.ax.tick_params(axis='y', colors='white')
            self.ax.xaxis.label.set_color('white')
            self.ax.yaxis.label.set_color('white')
            self.ax.title.set_color('white')
            for spine in self.ax.spines.values():
                spine.set_color('white')
            self.line.set_color('cyan')
        else:
            self.figure.set_facecolor('white')
            self.ax.set_facecolor('white')
            self.ax.tick_params(axis='x', colors='black')
            self.ax.tick_params(axis='y', colors='black')
            self.ax.xaxis.label.set_color('black')
            self.ax.yaxis.label.set_color('black')
            self.ax.title.set_color('black')
            for spine in self.ax.spines.values():
                spine.set_color('black')
            self.line.set_color('green')
        self.canvas.draw()

class SensorGridWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.signals = SensorSignals()
        self.signals.update_signal.connect(self._update_sensor_value)
        
        self.grid = QGridLayout()
        self.grid.setSpacing(10)
        self.setLayout(self.grid)
        
        self.sensor_frames = {}  # Container frames for each sensor
        self.sensor_labels = {}  # Sensor name labels
        self.value_labels = {}   # Value display labels
        self.unit_labels = {}   # Unit labels
        self.graphs = {}
        self.sensor_history = {}
        self.dark_mode = False
        
        self.sensors = [f"P{i}" for i in range(1, 9)] + \
                      [f"TC{i}" for i in range(1, 4)] + \
                      [f"LC{i}" for i in range(1, 4)] + \
                      [f"B{i}" for i in range(1, 3)]
        
        for idx, name in enumerate(self.sensors):
            self._create_sensor_box(name, idx)
            self.sensor_history[name] = deque(maxlen=100)

    def _create_sensor_box(self, name, idx):
        """Create a bordered box for each sensor with labels inside"""
        # Create frame with border
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(2)
        frame.setStyleSheet("border-radius: 5px;")
        
        # Layout for the frame
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(10, 5, 10, 5)
        frame_layout.setSpacing(5)
        
        # Sensor name label (left-aligned, borderless) - larger font (14pt)
        name_label = QLabel(f"{name}:")
        name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        name_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        name_label.setFont(QFont("Arial", 14))  # Increased identifier font
        frame_layout.addWidget(name_label)
        
        # Value display (centered) - slightly smaller font (18pt instead of 20pt)
        value_label = QLabel("---")
        value_label.setAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        value_label.setFont(QFont("Arial", 18))  # Slightly smaller value font
        value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame_layout.addWidget(value_label)
        
        # Unit label (right-aligned, borderless) - larger font (14pt)
        unit = self.get_unit(name)
        unit_label = QLabel(unit)
        unit_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        unit_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        unit_label.setFont(QFont("Arial", 14))  # Increased unit font
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
        frame.mousePressEvent = lambda event, sn=name: self.open_graph(sn)
        
        # Apply initial styling
        self.update_sensor_style(name)

    def get_unit(self, sensor_name):
        if sensor_name.startswith('P'):
            return 'psi'
        elif sensor_name.startswith('TC'):
            return '°C'
        elif sensor_name.startswith('LC') or sensor_name.startswith('B'):
            return 'lb'
        return ''

    def update_sensor_style(self, sensor_name):
        """Apply appropriate styling based on dark mode setting"""
        frame = self.sensor_frames[sensor_name]
        name_label = self.sensor_labels[sensor_name]
        value_label = self.value_labels[sensor_name]
        unit_label = self.unit_labels[sensor_name]
        
        if self.dark_mode:
            frame.setStyleSheet("""
                QFrame {
                    border: 2px solid #CCCCCC;
                    border-radius: 5px;
                    background-color: #444444;
                }
            """)
            name_label.setStyleSheet("color: #EEEEEE; font-weight: bold; border: none;")
            value_label.setStyleSheet("color: #FFFFFF; font-weight: bold; border: none;")
            unit_label.setStyleSheet("color: #EEEEEE; font-weight: bold; border: none;")
        else:
            frame.setStyleSheet("""
                QFrame {
                    border: 2px solid #AAAAAA;
                    border-radius: 5px;
                    background-color: #F0F0F0;
                }
            """)
            name_label.setStyleSheet("color: #333333; font-weight: bold; border: none;")
            value_label.setStyleSheet("color: #000000; font-weight: bold; border: none;")
            unit_label.setStyleSheet("color: #333333; font-weight: bold; border: none;")

    def set_dark_mode(self, dark):
        self.dark_mode = dark
        for sensor in self.sensors:
            self.update_sensor_style(sensor)
        for graph in self.graphs.values():
            graph.set_dark_mode(dark)

    def _update_sensor_value(self, sensor, value):
        if sensor not in self.value_labels:
            return
            
        self.value_labels[sensor].setText(f"{value:.2f}")
        current_time = QDateTime.currentDateTime().toMSecsSinceEpoch() / 1000.0
        self.sensor_history[sensor].append((current_time, value))
        
        if sensor in self.graphs:
            self.graphs[sensor].update_graph(value, current_time)

    def open_graph(self, sensor):
        if sensor not in self.graphs:
            self.graphs[sensor] = SensorPopupGraph(sensor)
            self.graphs[sensor].sensor_graph.set_dark_mode(self.dark_mode)
            
            history = self.sensor_history.get(sensor, [])
            for ts, val in history:
                self.graphs[sensor].update_graph(val, ts)
        
        self.graphs[sensor].show()
        self.graphs[sensor].raise_()
        self.graphs[sensor].activateWindow()

    def handle_data_line(self, line):
        readings = line.strip().split()
        for reading in readings:
            if ':' in reading:
                try:
                    parts = reading.split(':', 1)
                    sensor_name = parts[0].strip().upper()
                    value = float(parts[1].strip())
                    self.signals.update_signal.emit(sensor_name, value)
                except ValueError:
                    pass