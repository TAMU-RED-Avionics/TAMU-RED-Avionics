import sys
import csv
import os
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QPushButton, QLineEdit, QMessageBox, QWidget, QGridLayout, QToolButton, QSizePolicy, QScrollArea
from PyQt5.QtCore import Qt


class WarningValueConfigWindow(QDialog):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Warning Value Configuration")
        self.resize(600, 600)

        self.csv_file = "warning_ranges.csv"
        self.blocks = {}

        main_layout = QVBoxLayout(self)

        title = QLabel("Warning Range Configuration")
        title.setAlignment(Qt.AlignCenter)
        font = title.font()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        parameters = [
            "P1","P2","P3","P4","P5","P6","P7","P8",
            "TC1","TC2","TC3",
            "LC1","LC2","LC3",
            "B1","B2"
        ]

        for name in parameters:
            self.create_collapsible_block(name)

        self.save_btn = QPushButton("Save All")
        self.save_btn.clicked.connect(self.save_values)
        main_layout.addWidget(self.save_btn)

        self.load_values()

    def create_collapsible_block(self, name):
        block = {}

        toggle_button = QToolButton()
        toggle_button.setText(name)
        toggle_button.setCheckable(True)
        toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toggle_button.setArrowType(Qt.RightArrow)

        toggle_button.setStyleSheet("""
            QToolButton {
                font-weight: bold;
                font-size: 14px;
                padding: 8px;
                text-align: left;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
        """)

        self.scroll_layout.addWidget(toggle_button)

        content_widget = QWidget()
        content_widget.setVisible(False)
        layout = QGridLayout(content_widget)

        # Warning
        warning_label = QLabel("Warning Range")
        warning_label.setStyleSheet("color: #b58900; font-weight: bold;")
        layout.addWidget(warning_label, 0, 0, 1, 2)

        warn_low = QLineEdit()
        warn_low.setPlaceholderText("Low")

        warn_high = QLineEdit()
        warn_high.setPlaceholderText("High")

        layout.addWidget(warn_low, 1, 0)
        layout.addWidget(warn_high, 1, 1)

        # Hot/Cold
        hotcold_label = QLabel("Cold/Hot Range")
        hotcold_label.setStyleSheet("color: #b00020; font-weight: bold;")
        layout.addWidget(hotcold_label, 2, 0, 1, 2)

        cold = QLineEdit()
        cold.setPlaceholderText("Cold")

        hot = QLineEdit()
        hot.setPlaceholderText("Hot")

        layout.addWidget(cold, 3, 0)
        layout.addWidget(hot, 3, 1)

        self.scroll_layout.addWidget(content_widget)

        toggle_button.clicked.connect(
            lambda checked, cw=content_widget, btn=toggle_button:
            self.toggle_section(cw, btn)
        )

        block["warn_low"] = warn_low
        block["warn_high"] = warn_high
        block["cold"] = cold
        block["hot"] = hot

        self.blocks[name] = block

    def toggle_section(self, content_widget, button):
        content_widget.setVisible(button.isChecked())
        button.setArrowType(
            Qt.DownArrow if button.isChecked() else Qt.RightArrow
        )

    def validate_ranges(self):
        for name, block in self.blocks.items():
            try:
                w_low = float(block["warn_low"].text())
                w_high = float(block["warn_high"].text())
                c_val = float(block["cold"].text())
                h_val = float(block["hot"].text())
            except ValueError:
                QMessageBox.warning(self, "Error", f"{name}: All fields must be numeric.")
                return False

            if w_low >= w_high:
                QMessageBox.warning(self, "Error", f"{name}: Warning low must be < warning high.")
                return False

            if c_val >= h_val:
                QMessageBox.warning(self, "Error", f"{name}: Cold value must be < hot value.")
                return False


        return True

    def save_values(self):
        if not self.validate_ranges():
            return

        with open(self.csv_file, "w", newline="") as file:
            writer = csv.writer(file)

            writer.writerow(["Name", "WarnLow", "WarnHigh", "Cold", "Hot"])

            for name, block in self.blocks.items():
                writer.writerow([
                    name,
                    block["warn_low"].text(),
                    block["warn_high"].text(),
                    block["cold"].text(),
                    block["hot"].text()
                ])

        # Reload ranges in the controller immediately
        if self.controller:
            self.controller.load_warning_ranges()

        QMessageBox.information(self, "Saved", "All ranges saved successfully!")

    def load_values(self):
        if not os.path.exists(self.csv_file):
            return

        with open(self.csv_file, newline="") as file:
            reader = csv.reader(file)
            next(reader, None)

            for row in reader:
                name, w_low, w_high, a_low, a_high = row

                if name in self.blocks:
                    block = self.blocks[name]
                    block["warn_low"].setText(w_low)
                    block["warn_high"].setText(w_high)
                    block["cold"].setText(a_low)
                    block["hot"].setText(a_high)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = WarningValueConfigWindow()
    window.show()
    sys.exit(app.exec_())