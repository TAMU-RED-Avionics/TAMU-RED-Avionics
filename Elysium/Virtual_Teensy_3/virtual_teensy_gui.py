import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QDoubleSpinBox, QTextEdit, QCheckBox, QProgressBar
from PyQt5.QtCore import Qt, QTimer
try:
    from vt_comms import VTComms
except ImportError:
    from .vt_comms import VTComms

class VirtualTeensy(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Virtual Teensy 3")
        self.setGeometry(100, 100, 1000, 800)

        self.comms = VTComms()      # before init_ui: the actuator controls read its settings
        self.init_ui()

        self.comms.log_signal.connect(self.log)
        self.comms.valve_update_signal.connect(self.update_valve)
        self.comms.actuator_position_signal.connect(self.update_actuator_position)
        self.comms.actuator_target_signal.connect(self.update_actuator_target)
        self.comms.start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Column: Sensors
        sensors_layout = QVBoxLayout()
        main_layout.addLayout(sensors_layout)

        # Heartbeat Control
        hb_layout = QHBoxLayout()
        self.hb_checkbox = QCheckBox("Send Heartbeat")
        self.hb_checkbox.setChecked(True)
        self.hb_checkbox.stateChanged.connect(self.toggle_heartbeat)
        hb_layout.addWidget(self.hb_checkbox)
        sensors_layout.addLayout(hb_layout)


        self.sensor_inputs = {}
        sensor_names = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8",
                       "P9", "P10", "P11", "P12",
                       "TC1", "TC2", "TC3", 
                       "LC1", "LC2", "LC3", "LC4", "LC5", "LC6",
                       "B1", "B2"]
        
        for name in sensor_names:
            row = QHBoxLayout()
            label = QLabel(name)
            label.setFixedWidth(40)
            
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 2000)
            
            spinbox = QDoubleSpinBox()
            spinbox.setRange(-2000, 2000)
            spinbox.setFixedWidth(80)

            null_check = QCheckBox("NULL")
            null_check.setFixedWidth(60)
            
            row.addWidget(label)
            row.addWidget(slider)
            row.addWidget(spinbox)
            row.addWidget(null_check)
            sensors_layout.addLayout(row)
            
            self.sensor_inputs[name] = (slider, spinbox, null_check)
            
            # Connect
            # Slider -> Spinbox
            slider.valueChanged.connect(lambda val, s=spinbox: s.setValue(val))
            
            # Spinbox -> Slider (Clamped) + Update Backend
            spinbox.valueChanged.connect(lambda val, n=name, s=slider, nc=null_check: self.update_sensor(n, val, s, nc))

            # NULL Check -> Update Backend
            null_check.stateChanged.connect(lambda state, n=name, s=slider, sp=spinbox: self.update_sensor(n, sp.value(), s, self.sensor_inputs[n][2]))

        # Right Column: Valves and Logs
        right_layout = QVBoxLayout()
        main_layout.addLayout(right_layout)

        # Valves (with failure checkboxes)
        valves_label = QLabel("Valve Status & Failure Simulation")
        valves_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(valves_label)
        
        valves_layout = QHBoxLayout()
        right_layout.addLayout(valves_layout)
        
        self.valve_indicators = {}
        self.valve_failure_checkboxes = {}
        valve_ids = list(self.comms.RELAY_NAMES)
        valve_names = [self.comms.RELAY_NAMES[v] for v in valve_ids]
        
        for name, valve_id in zip(valve_names, valve_ids):
            v_layout = QVBoxLayout()
            lbl = QLabel(name)
            lbl.setStyleSheet("font-weight: bold;")
            
            indicator = QLabel()
            indicator.setFixedSize(20, 20)
            indicator.setStyleSheet("background-color: red; border-radius: 10px;")
            
            fail_check = QCheckBox("FAIL")
            fail_check.setStyleSheet("color: red; font-size: 10px;")
            fail_check.stateChanged.connect(lambda state, vid=valve_id: self.toggle_valve_failure(vid, state))
            
            v_layout.addWidget(lbl)
            v_layout.addWidget(indicator)
            v_layout.addWidget(fail_check)

            valves_layout.addLayout(v_layout)
            
            self.valve_indicators[name] = indicator
            self.valve_failure_checkboxes[name] = fail_check

        # Actuators (position-commanded valves): simulated travel, GUI-commanded or moved by hand here
        act_label = QLabel("Actuators (SV-1 / SV-2 / MFV Bray)")
        act_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(act_label)
        act_hint = QLabel("Bar = simulated position (moves at the travel speed after the GUI commands it). "
                          "Move the slider here to actuate by hand - the GUI follows.")
        act_hint.setWordWrap(True)
        right_layout.addWidget(act_hint)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Travel speed (% per second):"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(1, 1000)
        self.speed_spin.setValue(self.comms.actuator_speed)
        self.speed_spin.valueChanged.connect(lambda v: setattr(self.comms, "actuator_speed", v))
        speed_row.addWidget(self.speed_spin)
        speed_row.addStretch()
        right_layout.addLayout(speed_row)

        self.actuator_bars = {}
        self.actuator_sliders = {}
        self.actuator_targets = {}
        for act_id, name in self.comms.ACTUATOR_IDS.items():
            row = QHBoxLayout()
            lbl = QLabel(name)
            lbl.setFixedWidth(50)
            lbl.setStyleSheet("font-weight: bold;")
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setFormat("0.0 %")
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 1000)
            slider.setToolTip("Actuate by hand (0-100 %): reports the new position to the GUI")
            slider.valueChanged.connect(lambda v, n=name: self.manual_actuate(n, v / 10.0))
            target = QLabel("→ 0.0 %")
            target.setFixedWidth(70)
            fail_check = QCheckBox("FAIL")
            fail_check.setStyleSheet("color: red; font-size: 10px;")
            fail_check.stateChanged.connect(lambda state, vid=act_id: self.toggle_valve_failure(vid, state))
            row.addWidget(lbl)
            row.addWidget(bar, 2)
            row.addWidget(target)
            row.addWidget(slider, 2)
            row.addWidget(fail_check)
            right_layout.addLayout(row)
            self.actuator_bars[name] = bar
            self.actuator_sliders[name] = slider
            self.actuator_targets[name] = target

        # Log
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        right_layout.addWidget(self.log_area)

    def toggle_heartbeat(self, state):
        self.comms.set_heartbeat_enabled(state == Qt.Checked)
    
    def toggle_valve_failure(self, valve_id, state):
        self.comms.set_valve_failure(valve_id, state == Qt.Checked)

    def update_sensor(self, name, value, slider, null_check):
        # Update slider but clamp to 0 (don't let it go negative)
        slider.blockSignals(True)
        slider.setValue(max(0, int(value)))
        slider.blockSignals(False)
        
        # Determine value to send
        if null_check.isChecked():
            final_val = "NULL"
            slider.setEnabled(False)
            # spinbox is part of sensor_inputs, but we don't have direct ref here easily unless passed.
            # actually we can access via self.sensor_inputs if needed, or rely on UI
        else:
            final_val = value
            slider.setEnabled(True)

        # Update spinbox enabled state via lookup
        spinbox = self.sensor_inputs[name][1]
        spinbox.setEnabled(not null_check.isChecked())

        self.comms.update_sensor(name, final_val)



    def update_valve(self, name, state):
        if name in self.valve_indicators:
            color = "green" if state else "red"
            self.valve_indicators[name].setStyleSheet(f"background-color: {color}; border-radius: 10px;")

    def manual_actuate(self, name, pct):
        self.comms.actuate(name, pct)

    def update_actuator_position(self, name, pct):
        bar = self.actuator_bars.get(name)
        if bar is None:
            return
        bar.setValue(int(round(pct * 10)))
        bar.setFormat(f"{pct:.1f} %")
        slider = self.actuator_sliders[name]
        if not slider.isSliderDown():           # don't fight the user's drag
            slider.blockSignals(True)
            slider.setValue(int(round(pct * 10)))
            slider.blockSignals(False)

    def update_actuator_target(self, name, pct):
        if name in self.actuator_targets:
            self.actuator_targets[name].setText(f"→ {pct:.1f} %")

    def log(self, message):
        self.log_area.append(message)

    def closeEvent(self, event):
        self.comms.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = VirtualTeensy()
    window.show()
    sys.exit(app.exec_())
