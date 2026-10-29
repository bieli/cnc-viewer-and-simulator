from __future__ import annotations

from typing import Any, List, Optional

from PyQt5.QtWidgets import QFileDialog, QGridLayout, QPushButton, QWidget

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gcode.parser import LayerParser
from gcode_viewer.gui.left_side.left_side import LeftSide
from gcode_viewer.gui.menu_bar.menu_bar import MenuBar
from gcode_viewer.gui.right_side.right_side import RightSide


class CentralWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.file_handler = FileHandler()
        self.settings = self.file_handler.read_settings()
        self.menu_bar = MenuBar(self.settings)
        self.left_side = LeftSide(self.settings)
        self.right_side = RightSide(self.settings)
        self.load_file_button = QPushButton("Load G-Code File")
        self._init_ui()

    def _init_ui(self) -> None:
        grid = QGridLayout()
        grid.addWidget(self.menu_bar, 0, 0, 1, 2)
        self.menu_bar.observer = self

        grid.addWidget(self.left_side, 1, 0)
        grid.addWidget(self.right_side, 1, 1)

        bottom_grid = QGridLayout()
        bottom_grid.addWidget(self.load_file_button, 0, 1)
        bottom_grid.setColumnStretch(0, 1)
        bottom_grid.setColumnStretch(2, 1)
        self.load_file_button.clicked.connect(self.get_path_to_file)
        grid.addLayout(bottom_grid, 2, 0, 1, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 1)
        self.setLayout(grid)

    def get_path_to_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select a G-code file to load",
            filter="G-code (*.gcode *.nc *.ngc)",
            initialFilter="G-code (*.gcode *.nc *.ngc)",
        )
        if file_path:
            self.load_gcode_file(file_path)

    def load_gcode_file(self, file_path: str) -> None:
        line_list = self.file_handler.read_gcode_file(file_path)
        parser = LayerParser()
        layer_list = parser.parse_layer_list(line_list)
        self.right_side.set_raw_lines(line_list)
        self.load_new_file_on_screen(layer_list)

    def load_new_file_on_screen(self, layer_list: List[Layer]) -> None:
        self.right_side.load_new_gcode(layer_list)
        self.right_side.gcode_loaded = True
        self.left_side.gcode_3d_viewer.load_gcode(layer_list)

    def on_menu_event(
        self,
        event_type: str,
        payload: Any,
        _unused: Optional[Any] = None,
    ) -> None:
        if event_type == "new_settings":
            new_settings: Settings = payload
            self.settings = new_settings
            self.menu_bar.settings = new_settings
            self.right_side.settings = new_settings
            self.right_side.gcode_layer_viewer_static.settings = new_settings
            self.left_side.gcode_3d_viewer.settings = new_settings
            self.file_handler.settings_to_file(self.settings)
