from __future__ import annotations

from typing import Optional

from PyQt5.QtWidgets import QGridLayout, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gui.gcode_3d_viewer.gcode_3d_viewer import GCode3DViewer


class LeftSide(QWidget):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__()
        self.gcode_loaded = False
        self.gcode_3d_viewer = GCode3DViewer(settings=settings)
        self._init_ui()

    def _init_ui(self) -> None:
        grid = QGridLayout()
        grid.addWidget(self.gcode_3d_viewer, 1, 0)
        self.setLayout(grid)
