from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

from gcode_viewer.gcode.errors import GCodeValidationError, GCodeValidationIssue
from gcode_viewer.gcode.line import GCodeSource, normalize_gcode_lines
from gcode_viewer.gcode.words import (
    extract_feedrate,
    extract_motion_command,
    extract_spindle,
    extract_tool_diameter_mm,
    extract_tool_name_from_comment,
    extract_xyz,
    tokenize,
)
from gcode_viewer.utils.geometry import (
    Bounds3D,
    distance_3d,
    expand_bounds3d,
    format_stock_size,
)
from gcode_viewer.utils.step_depth import format_step_z_info
from gcode_viewer.utils.time_estimate import format_duration, travel_time_seconds

DEFAULT_CUT_FEEDRATE_MM_MIN = 1000.0
DEFAULT_RAPID_FEEDRATE_MM_MIN = 600.0
DEFAULT_TOOL_DIAMETER_MM = 3.0
# Z at/above last rapid height minus this margin counts as clearance, not stock.
CLEARANCE_Z_MARGIN_MM = 3.0


@dataclass(frozen=True)
class MachiningStats:
    tool_name: str
    max_spindle_rpm: int
    max_feedrate_mm_min: int
    cutting_time_seconds: float
    rapid_time_seconds: float
    unique_z_levels: frozenset[float]
    stock_bounds: Optional[Bounds3D] = None
    tool_diameter_mm: float = DEFAULT_TOOL_DIAMETER_MM
    warnings: Tuple[GCodeValidationIssue, ...] = ()
    used_default_cut_feedrate: bool = False

    @property
    def total_time_seconds(self) -> float:
        return self.cutting_time_seconds + self.rapid_time_seconds

    @property
    def time_estimation(self) -> str:
        return format_duration(self.total_time_seconds)

    @property
    def tool_info(self) -> str:
        lines: List[str] = [f"Tool: {self.tool_name}"]
        lines.append(f"Tool diameter: {self.tool_diameter_mm:.2f} mm")
        if self.max_spindle_rpm > 0:
            lines.append(f"Spindle speed: {self.max_spindle_rpm} RPM")
        if self.max_feedrate_mm_min > 0:
            feedrate_mms = self.max_feedrate_mm_min / 60.0
            lines.append(
                f"Feedrate: {self.max_feedrate_mm_min} mm/min ({feedrate_mms:.1f} mm/s)"
            )
        elif self.used_default_cut_feedrate:
            feedrate_mms = DEFAULT_CUT_FEEDRATE_MM_MIN / 60.0
            lines.append(
                f"Feedrate: default {DEFAULT_CUT_FEEDRATE_MM_MIN:.0f} mm/min "
                f"({feedrate_mms:.1f} mm/s) - file has F0/invalid F"
            )
        return "\n".join(lines)

    @property
    def step_z_info(self) -> str:
        return format_step_z_info(self.unique_z_levels)

    @property
    def material_size_info(self) -> str:
        return format_stock_size(self.stock_bounds)


def _engaged_stock_z_range(samples: Sequence[float]) -> Optional[Tuple[float, float]]:
    if not samples:
        return None
    counts = Counter(round(value, 1) for value in samples)
    min_count = max(20, int(0.001 * len(samples)))
    common = [value for value, count in counts.items() if count >= min_count]
    # Deepest cut must always be included so lower step-downs stay in the stock box.
    stock_z_min = min(samples)
    if common:
        stock_z_max = max(common)
    else:
        stock_z_max = max(samples)
    # When all engaged Z are ≤ 0, treat Z0 as stock top (common CNC convention).
    if stock_z_max <= 1e-9:
        stock_z_max = 0.0
    return stock_z_min, stock_z_max


def analyze_machining(
    lines: Sequence[GCodeSource],
    override_feedrate: Optional[float] = None,
    rapid_feedrate: float = DEFAULT_RAPID_FEEDRATE_MM_MIN,
) -> MachiningStats:
    if override_feedrate is not None and override_feedrate <= 0:
        raise GCodeValidationError(
            reason="override feedrate must be positive",
            line_number=None,
            line_text=None,
        )
    if rapid_feedrate <= 0:
        raise GCodeValidationError(
            reason="rapid feedrate must be positive",
            line_number=None,
            line_text=None,
        )

    tool_name = "Default Tool"
    tool_diameter_mm = DEFAULT_TOOL_DIAMETER_MM
    max_spindle = 0
    max_feedrate = 0
    cutting_time = 0.0
    rapid_time = 0.0
    unique_z_levels: Set[float] = set()
    cutting_xy: Optional[Bounds3D] = None
    cutting_z_samples: List[float] = []
    all_bounds: Optional[Bounds3D] = None
    warnings: List[GCodeValidationIssue] = []
    invalid_feed_examples: List[GCodeValidationIssue] = []
    invalid_feed_count = 0
    saw_positive_cut_feedrate = override_feedrate is not None
    max_feed_examples = 5

    current_feedrate = (
        float(override_feedrate)
        if override_feedrate is not None
        else DEFAULT_CUT_FEEDRATE_MM_MIN
    )
    position_x = 0.0
    position_y = 0.0
    position_z = 0.0
    last_clearance_z: Optional[float] = None

    for line in normalize_gcode_lines(lines):
        tool_from_comment = extract_tool_name_from_comment(line.text)
        if tool_from_comment:
            tool_name = tool_from_comment
        diameter = extract_tool_diameter_mm(line.text)
        if diameter is not None:
            tool_diameter_mm = diameter
            if tool_from_comment is None and "Endmill" in line.text:
                tool_name = line.text.strip("() ")

        words = tokenize(line.text)
        if not words:
            continue

        spindle = extract_spindle(words)
        if spindle is not None and spindle > max_spindle:
            max_spindle = spindle

        feedrate = extract_feedrate(words)
        if feedrate is not None:
            if feedrate <= 0:
                invalid_feed_count += 1
                if len(invalid_feed_examples) < max_feed_examples:
                    invalid_feed_examples.append(
                        GCodeValidationIssue(
                            reason=(
                                "non-positive feedrate F ignored "
                                "(not valid for cutting; common FreeCAD Adaptive "
                                "export when tool feeds are unset)"
                            ),
                            line_number=line.number,
                            line_text=line.text,
                            severity="warning",
                        )
                    )
            else:
                feedrate_int = int(feedrate)
                if feedrate_int > max_feedrate:
                    max_feedrate = feedrate_int
                if override_feedrate is None:
                    current_feedrate = float(feedrate_int)
                    saw_positive_cut_feedrate = True

        command = extract_motion_command(words)
        if command not in {"G0", "G1", "G2", "G3"}:
            continue

        next_x, next_y, next_z = extract_xyz(words, position_x, position_y, position_z)
        if command in {"G1", "G2", "G3"} and next_z <= 0.0:
            unique_z_levels.add(next_z)

        all_bounds = expand_bounds3d(all_bounds, position_x, position_y, position_z)
        all_bounds = expand_bounds3d(all_bounds, next_x, next_y, next_z)
        if command == "G0":
            last_clearance_z = next_z
        if command in {"G1", "G2", "G3"}:
            # XY: full cutting path footprint.
            cutting_xy = expand_bounds3d(
                cutting_xy, position_x, position_y, position_z
            )
            cutting_xy = expand_bounds3d(cutting_xy, next_x, next_y, next_z)
            # Z: engaged depths only - skip retracts and clearance-band moves.
            xy_moved = (
                abs(next_x - position_x) > 1e-9 or abs(next_y - position_y) > 1e-9
            )
            z_samples: Tuple[float, ...]
            if xy_moved and next_z > position_z + 1e-9:
                z_samples = (position_z,)
            elif xy_moved:
                z_samples = (position_z, next_z)
            elif next_z <= position_z + 1e-9:
                z_samples = (next_z,)
            else:
                z_samples = ()
            for z_value in z_samples:
                if last_clearance_z is not None:
                    clearance_band = max(
                        CLEARANCE_Z_MARGIN_MM, 0.2 * abs(last_clearance_z)
                    )
                    if z_value >= last_clearance_z - clearance_band:
                        continue
                cutting_z_samples.append(z_value)

        distance = distance_3d(
            (position_x, position_y, position_z),
            (next_x, next_y, next_z),
        )
        if distance > 0:
            if command == "G0":
                rapid_time += travel_time_seconds(distance, rapid_feedrate)
            else:
                cutting_time += travel_time_seconds(distance, current_feedrate)

        position_x, position_y, position_z = next_x, next_y, next_z

    if invalid_feed_count:
        warnings.extend(invalid_feed_examples)
        if invalid_feed_count > len(invalid_feed_examples):
            warnings.append(
                GCodeValidationIssue(
                    reason=(
                        f"also found {invalid_feed_count - len(invalid_feed_examples)} "
                        "more non-positive F values in this file"
                    ),
                    severity="warning",
                )
            )

    # Cutting envelope = required stock; fall back to full path if file is rapids-only.
    # Frequency filter drops sparse helical/clearance Z samples from stock height.
    stock_bounds: Optional[Bounds3D]
    engaged_z = _engaged_stock_z_range(cutting_z_samples)
    if cutting_xy is not None and engaged_z is not None:
        stock_z_min, stock_z_max = engaged_z
        stock_bounds = Bounds3D(
            cutting_xy.min_x,
            cutting_xy.max_x,
            cutting_xy.min_y,
            cutting_xy.max_y,
            stock_z_min,
            stock_z_max,
        )
    else:
        stock_bounds = all_bounds

    return MachiningStats(
        tool_name=tool_name,
        max_spindle_rpm=max_spindle,
        max_feedrate_mm_min=max_feedrate,
        cutting_time_seconds=cutting_time,
        rapid_time_seconds=rapid_time,
        unique_z_levels=frozenset(unique_z_levels),
        stock_bounds=stock_bounds,
        tool_diameter_mm=tool_diameter_mm,
        warnings=tuple(warnings),
        used_default_cut_feedrate=override_feedrate is None and not saw_positive_cut_feedrate,
    )
