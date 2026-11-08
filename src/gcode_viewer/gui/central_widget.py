from __future__ import annotations

from typing import Any, List, Optional

from PyQt5.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QWidget,
)

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.errors import (
    GCodeValidationError,
    GCodeValidationIssue,
    format_validation_issues,
)
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gcode.parser import LayerParser
from gcode_viewer.gcode.safe_start import rewrite_gcode_safe_start
from gcode_viewer.gui.left_side.left_side import LeftSide
from gcode_viewer.gui.menu_bar.menu_bar import MenuBar
from gcode_viewer.gui.right_side.right_side import RightSide

BUTTON_STYLE = (
    "font-weight: bold; padding: 8px 14px; background-color: #0066cc; "
    "color: white; border: none; border-radius: 4px;"
)


class CentralWidget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.file_handler = FileHandler()
        self.settings = self.file_handler.read_settings()
        self.menu_bar = MenuBar(self.settings)
        self.left_side = LeftSide(self.settings)
        self.right_side = RightSide(self.settings)
        self.right_side.on_feedrate_changed = (
            self.left_side.gcode_3d_viewer.set_simulation_feedrate
        )
        self.current_gcode_path: Optional[str] = None
        self.load_file_button = QPushButton("Load G-Code File")
        self.safe_start_button = QPushButton(
            "Set CNC start: corner + clearance travel"
        )
        self._init_ui()
        self._update_safe_start_button()

    def _init_ui(self) -> None:
        grid = QGridLayout()
        grid.addWidget(self.menu_bar, 0, 0, 1, 2)
        self.menu_bar.observer = self

        grid.addWidget(self.left_side, 1, 0)
        grid.addWidget(self.right_side, 1, 1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        self.load_file_button.setStyleSheet(BUTTON_STYLE)
        self.load_file_button.clicked.connect(self.get_path_to_file)
        bottom_row.addWidget(self.load_file_button)

        self.safe_start_button.setStyleSheet(BUTTON_STYLE)
        self.safe_start_button.setToolTip(
            "Shift WCS to left-near corner (0,0), lift above stock, then rapid "
            "to the first process point before cutting. Saves file.bak once."
        )
        self.safe_start_button.clicked.connect(self.apply_safe_cnc_start)
        bottom_row.addWidget(self.safe_start_button)
        bottom_row.addStretch(1)
        grid.addLayout(bottom_row, 2, 0, 1, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 1)
        self.setLayout(grid)

    def _update_safe_start_button(self) -> None:
        enabled = bool(self.current_gcode_path and self.right_side.gcode_loaded)
        self.safe_start_button.setEnabled(enabled)

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
        try:
            layer_list = parser.parse_layer_list(line_list)
        except GCodeValidationError as exc:
            if exc.file_path is None:
                exc.file_path = file_path
            self._show_validation_error(exc)
            self.current_gcode_path = None
            self._update_safe_start_button()
            return
        self.current_gcode_path = file_path
        self.right_side.set_raw_lines(line_list)
        self.load_new_file_on_screen(layer_list)
        self._update_safe_start_button()
        if parser.warnings:
            self._show_validation_warnings(parser.warnings, file_path)

    def apply_safe_cnc_start(self) -> None:
        if not self.current_gcode_path:
            QMessageBox.information(
                self,
                "No file loaded",
                "Load a G-code file before setting the CNC start position.",
            )
            return

        try:
            original_text = self.file_handler.read_gcode_text(self.current_gcode_path)
            rewritten_text, pose = rewrite_gcode_safe_start(original_text)
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot set CNC start", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "File read error", str(exc))
            return

        try:
            created_bak, bak_path = self.file_handler.ensure_bak_copy(
                self.current_gcode_path
            )
            self.file_handler.write_gcode_text(self.current_gcode_path, rewritten_text)
        except OSError as exc:
            QMessageBox.critical(self, "File write error", str(exc))
            return

        self.load_gcode_file(self.current_gcode_path)
        bak_note = (
            f"Backup created: {bak_path}"
            if created_bak
            else f"Backup already existed (left unchanged): {bak_path}"
        )
        QMessageBox.information(
            self,
            "CNC start updated",
            (
                "WCS shifted: left-near corner is now machine origin.\n"
                "Idle on stock top, then raise and rapid above material:\n"
                f"X={pose.x:.3f}  Y={pose.y:.3f}  Z(stock top)={pose.z:.3f}\n\n"
                f"{bak_note}"
            ),
        )

    def _show_validation_error(self, error: GCodeValidationError) -> None:
        message = str(error)
        print(message, flush=True)
        QMessageBox.critical(self, "G-code validation error", message)

    def _show_validation_warnings(
        self,
        warnings: List[GCodeValidationIssue],
        file_path: str,
    ) -> None:
        message = format_validation_issues(warnings, file_path=file_path)
        print(message, flush=True)
        QMessageBox.warning(self, "G-code validation warning", message)

    def load_new_file_on_screen(self, layer_list: List[Layer]) -> None:
        self.right_side.load_new_gcode(layer_list)
        self.right_side.gcode_loaded = True
        self.left_side.gcode_3d_viewer.load_gcode(layer_list)
        feedrate = self.right_side.current_feedrate()
        if feedrate is not None:
            self.left_side.gcode_3d_viewer.set_simulation_feedrate(feedrate)
        self._update_safe_start_button()

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
