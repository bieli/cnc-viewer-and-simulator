from __future__ import annotations

from PyQt5 import QtGui
from PyQt5.QtWidgets import QFileDialog, QWidget

from gcode_viewer.config.file_handler import FileHandler


class StartupWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        file_handler = FileHandler()
        self.setWindowIcon(QtGui.QIcon(str(file_handler.icon_png_path)))

    def get_initial_file_path(self) -> str:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a G-code file to load",
            filter="G-code (*.gcode *.nc *.ngc)",
            initialFilter="G-code (*.gcode *.nc *.ngc)",
        )
        return file_path
