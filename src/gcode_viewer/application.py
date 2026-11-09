from __future__ import annotations

import sys
from typing import Optional

import gcode_viewer.numpy_compat  # noqa: F401  # before pyqtgraph / NumPy 2
from PyQt5.QtWidgets import QApplication

from gcode_viewer.gui.main_screen import MainScreen


class Application(QApplication):
    def __init__(self, file_path: Optional[str] = None) -> None:
        super().__init__(sys.argv)
        main_screen = MainScreen()
        if file_path:
            main_screen.central_widget.load_gcode_file(file_path)
            if main_screen.central_widget.right_side.gcode_loaded:
                main_screen.showMaximized()
            else:
                main_screen.close()
                sys.exit(1)
        else:
            main_screen.start()
            if not main_screen.central_widget.right_side.gcode_loaded:
                sys.exit(0)
        sys.exit(self.exec_())
