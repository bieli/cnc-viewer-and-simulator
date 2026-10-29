from __future__ import annotations

from typing import List, Optional, Sequence

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gcode.parser import LayerParser
from gcode_viewer.gui.gcode_layer_viewer.gcode_layer_viewer_static import GCodeLayerViewerStatic


class RightSide(QWidget):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.gcode_loaded = False
        self.layer_list: Optional[List[Layer]] = None
        self.raw_lines: Optional[List[str]] = None
        self.tool_title_label = QLabel("Active tool and CNC properties:")
        self.tool_info_label = QLabel("No tool loaded!")
        self.input_title_label = QLabel("Check new working feed rate [mm/min]:")
        self.feedrate_input = QLineEdit("2000")
        self.recalc_button = QPushButton("Recalculate")
        self.time_title_label = QLabel("Estimated machining/cutting time:")
        self.time_info_label = QLabel("--:--:--")
        self.step_z_title_label = QLabel("Depth steps in material:")
        self.step_z_info_label = QLabel("Step Z: --")
        self.gcode_layer_viewer_static = GCodeLayerViewerStatic(self.settings)
        self._init_ui()

    def _init_ui(self) -> None:
        grid = QGridLayout()
        row = 0

        self.tool_title_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #444;"
        )
        grid.addWidget(self.tool_title_label, row, 0)
        row += 1

        self.tool_info_label.setStyleSheet(
            "font-size: 15px; color: #0066cc; font-weight: bold; padding: 6px; "
            "background-color: #e6f2ff; border-radius: 4px;"
        )
        grid.addWidget(self.tool_info_label, row, 0)
        row += 1

        self.input_title_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #444; margin-top: 5px;"
        )
        grid.addWidget(self.input_title_label, row, 0)
        row += 1

        input_layout = QHBoxLayout()
        self.feedrate_input.setFixedWidth(200)
        self.feedrate_input.setStyleSheet(
            "font-size: 15px; padding: 4px; border: 1px solid #ccc; border-radius: 4px;"
        )
        input_layout.addWidget(self.feedrate_input)

        self.recalc_button.setStyleSheet(
            "font-weight: bold; padding: 5px 10px; background-color: #0066cc; "
            "color: white; border: none; border-radius: 4px;"
        )
        self.recalc_button.clicked.connect(self.recalculate_time)
        input_layout.addWidget(self.recalc_button)
        grid.addLayout(input_layout, row, 0)
        row += 1

        self.time_title_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #444; margin-top: 5px;"
        )
        grid.addWidget(self.time_title_label, row, 0)
        row += 1

        self.time_info_label.setStyleSheet(
            "font-size: 22px; color: #2e7d32; font-weight: bold; padding: 6px; "
            "background-color: #e8f5e9; border-radius: 4px;"
        )
        grid.addWidget(self.time_info_label, row, 0)
        row += 1

        self.step_z_title_label.setStyleSheet(
            "font-weight: bold; font-size: 16px; color: #444; margin-top: 5px;"
        )
        grid.addWidget(self.step_z_title_label, row, 0)
        row += 1

        self.step_z_info_label.setStyleSheet(
            "font-size: 15px; color: #b78103; font-weight: bold; padding: 6px; "
            "background-color: #fffde7; border-radius: 4px;"
        )
        grid.addWidget(self.step_z_info_label, row, 0)
        row += 1

        grid.setRowMinimumHeight(row, 10)
        row += 1

        title_label = QLabel("Depth cross-section (2D view)")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; font-size: 18px;")
        grid.addWidget(title_label, row, 0)
        row += 1

        grid.addWidget(self.gcode_layer_viewer_static, row, 0)
        self.setLayout(grid)

    def load_new_gcode(self, layer_list: Sequence[Layer]) -> None:
        self.layer_list = list(layer_list)
        self.gcode_layer_viewer_static.set_layer_list(self.layer_list)

        if layer_list:
            first_layer = layer_list[0]
            self.tool_info_label.setText(first_layer.tool_info)
            self.time_info_label.setText(first_layer.time_estimation)
            self.step_z_info_label.setText(first_layer.step_z_info)
        else:
            self.tool_info_label.setText("Cutter parameters not detected")
            self.time_info_label.setText("--:--:--")
            self.step_z_info_label.setText("Step Z: --")

        self.refresh_gcode_viewer()

    def set_raw_lines(self, line_list: Sequence[str]) -> None:
        self.raw_lines = list(line_list)

    def recalculate_time(self) -> None:
        if not self.raw_lines:
            return

        try:
            user_feedrate = float(self.feedrate_input.text().strip())
        except ValueError:
            self.time_info_label.setText("Incorrect feed!")
            return

        parser = LayerParser()
        new_layers = parser.parse_layer_list(
            self.raw_lines, override_feedrate=user_feedrate
        )
        if not new_layers:
            return

        self.time_info_label.setText(new_layers[0].time_estimation)
        feedrate_mms = user_feedrate / 60.0
        current_text = self.tool_info_label.text().split("\n")
        tool_line = current_text[0] if current_text else f"Tool: {parser.tool_name}"
        spindle_line = current_text[1] if len(current_text) > 1 else ""

        updated_info = tool_line
        if spindle_line and "Spindle" in spindle_line:
            updated_info += f"\n{spindle_line}"
        updated_info += (
            f"\nFeedrate (manual): {user_feedrate:.0f} mm/min ({feedrate_mms:.1f} mm/s)"
        )
        self.tool_info_label.setText(updated_info)
        self.step_z_info_label.setText(new_layers[0].step_z_info)

    def refresh_gcode_viewer(self) -> None:
        self.gcode_layer_viewer_static.load_layer(0)
