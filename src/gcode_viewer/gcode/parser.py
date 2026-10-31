from __future__ import annotations

from typing import List, Optional, Sequence

from gcode_viewer.gcode.analysis import MachiningStats, analyze_machining
from gcode_viewer.gcode.errors import GCodeValidationIssue
from gcode_viewer.gcode.layer import ColorRGBA, Layer
from gcode_viewer.gcode.line import GCodeLine, GCodeSource, normalize_gcode_lines
from gcode_viewer.gcode.words import (
    extract_ij,
    extract_motion_command,
    extract_xyz,
    is_comment_line,
    parse_float_word,
    tokenize,
)
from gcode_viewer.utils.arc import tessellate_arc
from gcode_viewer.utils.geometry import bounds_from_segment

DEFAULT_BOUNDS = 1e24
RAPID_COLOR: ColorRGBA = (1.0, 0.3, 0.3, 0.8)
CUT_COLOR: ColorRGBA = (0.0, 1.0, 0.5, 1.0)
OTHER_COLOR: ColorRGBA = (0.5, 0.5, 0.5, 0.5)
MOVEMENT_COMMANDS = {"G0", "G1", "G2", "G3", "G5"}


class LayerParser:
    def __init__(self) -> None:
        self.from_x = 0.0
        self.from_y = 0.0
        self.from_z = 0.0
        self.to_x = 0.0
        self.to_y = 0.0
        self.to_z = 0.0
        self.min_x = DEFAULT_BOUNDS
        self.max_x = 0.0
        self.min_y = DEFAULT_BOUNDS
        self.max_y = 0.0
        self.tool_name = "Default Tool"
        self.max_spindle = 0
        self.max_feedrate = 0
        self.tool_info = ""
        self.time_estimation_str = ""
        self.step_z_info_str = ""
        self.material_size_info_str = ""
        self.warnings: List[GCodeValidationIssue] = []

    def parse_layer_list(
        self,
        string_list: Sequence[GCodeSource],
        override_feedrate: Optional[float] = None,
    ) -> List[Layer]:
        lines = normalize_gcode_lines(string_list)
        stats = analyze_machining(lines, override_feedrate=override_feedrate)
        self._apply_stats(stats)

        self.from_x = self.from_y = self.from_z = 0.0
        self.to_x = self.to_y = self.to_z = 0.0
        self._reset_bounds()

        layers: List[Layer] = []
        for index, layer_lines in enumerate(self.split_into_layers(lines)):
            layer = self.parse_single_layer(layer_lines)
            layer.number = index
            layer.tool_info = self.tool_info
            layer.time_estimation = self.time_estimation_str
            layer.step_z_info = self.step_z_info_str
            layer.material_size_info = self.material_size_info_str
            layers.append(layer)
        return layers

    def _apply_stats(self, stats: MachiningStats) -> None:
        self.tool_name = stats.tool_name
        self.max_spindle = stats.max_spindle_rpm
        self.max_feedrate = stats.max_feedrate_mm_min
        self.tool_info = stats.tool_info
        self.time_estimation_str = stats.time_estimation
        self.step_z_info_str = stats.step_z_info
        self.material_size_info_str = stats.material_size_info
        self.warnings = list(stats.warnings)

    def split_into_layers(self, lines: Sequence[GCodeSource]) -> List[List[GCodeLine]]:
        result: List[List[GCodeLine]] = []
        current_layer: List[GCodeLine] = []
        last_seen_z: Optional[float] = None

        for line in normalize_gcode_lines(lines):
            if is_comment_line(line.text):
                current_layer.append(line)
                continue

            words = tokenize(line.text)
            if extract_motion_command(words) is not None:
                for word in words:
                    current_z = parse_float_word(word, "Z")
                    if current_z is None:
                        continue
                    if last_seen_z is not None and current_z != last_seen_z:
                        if current_layer:
                            result.append(current_layer)
                        current_layer = []
                    last_seen_z = current_z

            current_layer.append(line)

        if current_layer:
            result.append(current_layer)
        return result

    def parse_single_layer(
        self,
        lines: Sequence[GCodeSource],
        layer_color: ColorRGBA = OTHER_COLOR,
        layer_min_max_offset: float = 2.5,
        rapid_color: ColorRGBA = RAPID_COLOR,
        cut_color: ColorRGBA = CUT_COLOR,
        g2_angle_ratio: float = 2.0,
    ) -> Layer:
        normalized = normalize_gcode_lines(lines)
        layer = Layer(layer_as_string=[line.text for line in normalized])

        for line in normalized:
            if is_comment_line(line.text):
                continue

            words = tokenize(line.text)
            if not words:
                continue

            command = extract_motion_command(words)
            if command is not None and command in MOVEMENT_COMMANDS:
                self._append_movement(
                    layer=layer,
                    line=line.text,
                    words=words,
                    command=command,
                    rapid_color=rapid_color,
                    cut_color=cut_color,
                    g2_angle_ratio=g2_angle_ratio,
                )
            else:
                layer.x_data.append((self.to_x, self.to_x))
                layer.y_data.append((self.to_y, self.to_y))
                layer.z_data.append((self.to_z, self.to_z))
                layer.pyqtgraph_color.append(layer_color)
                layer.matplot_color.append("k")
                layer.move_data.append(line.text)

        layer.min_x = self.min_x - layer_min_max_offset
        layer.max_x = self.max_x + layer_min_max_offset
        layer.min_y = self.min_y - layer_min_max_offset
        layer.max_y = self.max_y + layer_min_max_offset
        self._reset_bounds()
        return layer

    def _append_movement(
        self,
        layer: Layer,
        line: str,
        words: List[str],
        command: str,
        rapid_color: ColorRGBA,
        cut_color: ColorRGBA,
        g2_angle_ratio: float,
    ) -> None:
        if command == "G0":
            pg_color = rapid_color
            mp_color = "r"
        else:
            pg_color = cut_color
            mp_color = "g"

        target_x, target_y, target_z = extract_xyz(words, self.to_x, self.to_y, self.to_z)
        i_val, j_val = extract_ij(words)

        self.from_x, self.from_y, self.from_z = self.to_x, self.to_y, self.to_z

        if command in {"G2", "G3"}:
            points = tessellate_arc(
                start=(self.from_x, self.from_y, self.from_z),
                end=(target_x, target_y, target_z),
                i_offset=i_val,
                j_offset=j_val,
                clockwise=command == "G2",
                g2_angle_ratio=g2_angle_ratio,
            )
            last = (self.from_x, self.from_y, self.from_z)
            for point in points:
                layer.x_data.append((last[0], point[0]))
                layer.y_data.append((last[1], point[1]))
                layer.z_data.append((last[2], point[2]))
                layer.pyqtgraph_color.append(pg_color)
                layer.matplot_color.append(mp_color)
                layer.move_data.append(line)
                last = point
            self.to_x, self.to_y, self.to_z = target_x, target_y, target_z
        else:
            self.to_x, self.to_y, self.to_z = target_x, target_y, target_z
            layer.x_data.append((self.from_x, self.to_x))
            layer.y_data.append((self.from_y, self.to_y))
            layer.z_data.append((self.from_z, self.to_z))
            layer.pyqtgraph_color.append(pg_color)
            layer.matplot_color.append(mp_color)
            layer.move_data.append(line)

        self._update_min_max()

    def _update_min_max(self) -> None:
        self.min_x, self.max_x, self.min_y, self.max_y = bounds_from_segment(
            self.from_x,
            self.from_y,
            self.to_x,
            self.to_y,
            self.min_x,
            self.max_x,
            self.min_y,
            self.max_y,
        )

    def _reset_bounds(self) -> None:
        self.min_x = DEFAULT_BOUNDS
        self.max_x = 0.0
        self.min_y = DEFAULT_BOUNDS
        self.max_y = 0.0
