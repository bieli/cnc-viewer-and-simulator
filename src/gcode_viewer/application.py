from __future__ import annotations

import sys
from typing import Optional

from PyQt5.QtWidgets import QApplication

from gcode_viewer.gui.main_screen import MainScreen


class Application(QApplication):
    def __init__(self, file_path: Optional[str] = None) -> None:
        super().__init__(sys.argv)
        main_screen = MainScreen()
        if file_path:
            main_screen.central_widget.load_gcode_file(file_path)
            main_screen.showMaximized()
        else:
            main_screen.start()
        sys.exit(self.exec_())
