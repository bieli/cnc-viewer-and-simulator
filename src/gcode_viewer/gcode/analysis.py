from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

from gcode_viewer.gcode.errors import GCodeValidationError, GCodeValidationIssue
from gcode_viewer.gcode.line import GCodeSource, normalize_gcode_lines
from gcode_viewer.gcode.words import (
    extract_feedrate,
    extract_spindle,
    extract_tool_name_from_comment,
    extract_xyz,
    tokenize,
)
from gcode_viewer.utils.geometry import distance_3d
from gcode_viewer.utils.step_depth import format_step_z_info
from gcode_viewer.utils.time_estimate import format_duration, travel_time_seconds

DEFAULT_CUT_FEEDRATE_MM_MIN = 1000.0
DEFAULT_RAPID_FEEDRATE_MM_MIN = 600.0


@dataclass(frozen=True)
class MachiningStats:
    tool_name: str
    max_spindle_rpm: int
    max_feedrate_mm_min: int
    cutting_time_seconds: float
    rapid_time_seconds: float
    unique_z_levels: frozenset[float]
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
                f"({feedrate_mms:.1f} mm/s) — file has F0/invalid F"
            )
        return "\n".join(lines)

    @property
    def step_z_info(self) -> str:
        return format_step_z_info(self.unique_z_levels)


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
    max_spindle = 0
    max_feedrate = 0
    cutting_time = 0.0
    rapid_time = 0.0
    unique_z_levels: Set[float] = set()
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

    for line in normalize_gcode_lines(lines):
        tool_from_comment = extract_tool_name_from_comment(line.text)
        if tool_from_comment:
            tool_name = tool_from_comment

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

        command = words[0].upper()
        if command not in {"G0", "G1", "G2", "G3"}:
            continue

        next_x, next_y, next_z = extract_xyz(words, position_x, position_y, position_z)
        if command in {"G1", "G2", "G3"} and next_z <= 0.0:
            unique_z_levels.add(next_z)

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

    return MachiningStats(
        tool_name=tool_name,
        max_spindle_rpm=max_spindle,
        max_feedrate_mm_min=max_feedrate,
        cutting_time_seconds=cutting_time,
        rapid_time_seconds=rapid_time,
        unique_z_levels=frozenset(unique_z_levels),
        warnings=tuple(warnings),
        used_default_cut_feedrate=override_feedrate is None and not saw_positive_cut_feedrate,
    )
