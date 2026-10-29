from __future__ import annotations

import ctypes
import sys

from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import QMainWindow

from gcode_viewer import __version__
from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.gui.central_widget import CentralWidget
from gcode_viewer.gui.startup_window.startup_window import StartupWindow


class MainScreen(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.file_handler = FileHandler()
        self.central_widget = CentralWidget()
        self._init_ui()

    def _init_ui(self) -> None:
        title = f"CNC G-Code Viewer {__version__}"
        self.setWindowTitle(title)
        self.setWindowIcon(QIcon(str(self.file_handler.icon_png_path)))
        self.setFont(QFont("Sans Serif", 12))
        self.setGeometry(180, 180, 1480, 720)
        self.setCentralWidget(self.central_widget)

        if sys.platform == "win32" and hasattr(ctypes, "windll"):
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(title)

    def start(self) -> None:
        startup_window = StartupWindow()
        file_path = startup_window.get_initial_file_path()
        if not file_path:
            self.close()
            return
        self.central_widget.load_gcode_file(file_path)
        if self.central_widget.right_side.gcode_loaded:
            self.showMaximized()
        else:
            self.close()
