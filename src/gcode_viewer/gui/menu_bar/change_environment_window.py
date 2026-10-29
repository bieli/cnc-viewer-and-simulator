from __future__ import annotations

from typing import List, Optional

from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
)

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.config.mapper import SettingsMapper
from gcode_viewer.config.settings import Settings


class ChangeEnvironmentWindow(QDialog):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__()
        self.settings = settings
        self.entries_to_check: List[QLineEdit] = []
        self.printer_width_x_entry = QLineEdit()
        self.printer_depth_y_entry = QLineEdit()
        self.printer_height_z_entry = QLineEdit()
        self._init_ui()

    def _init_ui(self) -> None:
        file_handler = FileHandler()
        self.setWindowTitle("Machine workspace")
        self.setWindowIcon(QtGui.QIcon(str(file_handler.icon_png_path)))
        self.setWindowFlags(Qt.WindowFlags())

        grid = QGridLayout()

        top_label = QLabel("Set the CNC machine work envelope dimensions")
        top_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(top_label, 0, 0, 1, 6)

        environment_label = QLabel("Machine bed")
        environment_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(environment_label, 1, 0, 1, 3)

        grid.addWidget(QLabel("Bed width (X)"), 2, 0)
        grid.addWidget(self.printer_width_x_entry, 2, 1)
        self.entries_to_check.append(self.printer_width_x_entry)

        grid.addWidget(QLabel("Bed depth (Y)"), 3, 0)
        grid.addWidget(self.printer_depth_y_entry, 3, 1)
        self.entries_to_check.append(self.printer_depth_y_entry)

        grid.addWidget(QLabel("Travel height (Z)"), 4, 0)
        grid.addWidget(self.printer_height_z_entry, 4, 1)
        self.entries_to_check.append(self.printer_height_z_entry)

        for row in range(2, 5):
            grid.addWidget(QLabel("mm"), row, 2)

        for entry in self.entries_to_check:
            entry.setFixedWidth(60)
            entry.setMaximumWidth(60)
            entry.setAlignment(Qt.AlignmentFlag.AlignCenter)

        accept_button = QPushButton("Accept")
        cancel_button = QPushButton("Cancel")
        grid.addWidget(accept_button, 5, 1, 1, 3)
        grid.addWidget(cancel_button, 6, 1, 1, 3)
        accept_button.clicked.connect(self.accept_pressed)
        cancel_button.clicked.connect(self.reject)
        self.setLayout(grid)

        if self.settings is not None:
            bed = self.settings.workspace.machine_bed
            self.printer_width_x_entry.setText(str(bed.width_x))
            self.printer_depth_y_entry.setText(str(bed.depth_y))
            self.printer_height_z_entry.setText(str(bed.height_z))

    def accept_pressed(self) -> None:
        if not self.sanity_check():
            return
        values = [float(entry.text()) for entry in self.entries_to_check]
        self.settings = SettingsMapper.float_to_settings(values)
        self.close()

    def sanity_check(self) -> bool:
        has_error = False
        for entry in self.entries_to_check:
            try:
                value = float(entry.text())
                if value < 0.0 or value > 1000.0:
                    raise ValueError
            except ValueError:
                has_error = True
                entry.setText("")

        if has_error:
            box = QMessageBox(self)
            box.setText("All inputs must be numbers between 0 and 1000")
            box.setWindowTitle("Input Error")
            box.setIcon(QMessageBox.Warning)
            box.exec_()
            return False
        return True

    @staticmethod
    def change_environment(settings: Settings) -> Settings:
        window = ChangeEnvironmentWindow(settings)
        window.exec_()
        return window.settings if window.settings is not None else settings
