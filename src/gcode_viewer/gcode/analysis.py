from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set

from gcode_viewer.gcode.words import (
    extract_feedrate,
    extract_spindle,
    extract_tool_name_from_comment,
    extract_xyz,
    tokenize,
)


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

    @property
    def total_time_seconds(self) -> float:
        return self.cutting_time_seconds + self.rapid_time_seconds

    @property
    def time_estimation(self) -> str:
        total = self.total_time_seconds
        hours = int(total // 3600)
        minutes = int((total % 3600) // 60)
        seconds = int(total % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

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
        return "\n".join(lines)

    @property
    def step_z_info(self) -> str:
        return format_step_z_info(self.unique_z_levels)


def format_step_z_info(unique_z_levels: Iterable[float]) -> str:
    levels = sorted(set(unique_z_levels), reverse=True)
    if len(levels) <= 1:
        return "Step Z: A single working layer"

    step_counts: Counter[float] = Counter()
    for index in range(len(levels) - 1):
        step = round(abs(levels[index] - levels[index + 1]), 3)
        if step > 0.001:
            step_counts[step] += 1

    total_steps = sum(step_counts.values())
    if total_steps == 0:
        return "Step Z: A single working layer"

    lines: List[str] = []
    for step in sorted(step_counts.keys(), reverse=True):
        count = step_counts[step]
        percentage = (count / total_steps) * 100.0
        lines.append(f"Step {step:.3f}mm: {percentage:.1f}%")
    return "\n".join(lines)


def analyze_machining(
    lines: Sequence[str],
    override_feedrate: Optional[float] = None,
    rapid_feedrate: float = DEFAULT_RAPID_FEEDRATE_MM_MIN,
) -> MachiningStats:
    tool_name = "Default Tool"
    max_spindle = 0
    max_feedrate = 0
    cutting_time = 0.0
    rapid_time = 0.0
    unique_z_levels: Set[float] = set()

    current_feedrate = (
        float(override_feedrate)
        if override_feedrate is not None
        else DEFAULT_CUT_FEEDRATE_MM_MIN
    )
    position_x = 0.0
    position_y = 0.0
    position_z = 0.0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        tool_from_comment = extract_tool_name_from_comment(stripped)
        if tool_from_comment:
            tool_name = tool_from_comment

        words = tokenize(stripped)
        if not words:
            continue

        spindle = extract_spindle(words)
        if spindle is not None and spindle > max_spindle:
            max_spindle = spindle

        feedrate = extract_feedrate(words)
        if feedrate is not None:
            feedrate_int = int(feedrate)
            if feedrate_int > max_feedrate:
                max_feedrate = feedrate_int
            if override_feedrate is None:
                current_feedrate = float(feedrate_int)

        command = words[0].upper()
        if command not in {"G0", "G1", "G2", "G3"}:
            continue

        next_x, next_y, next_z = extract_xyz(words, position_x, position_y, position_z)
        if command in {"G1", "G2", "G3"} and next_z <= 0.0:
            unique_z_levels.add(next_z)

        distance = math.sqrt(
            (next_x - position_x) ** 2
            + (next_y - position_y) ** 2
            + (next_z - position_z) ** 2
        )
        if distance > 0:
            if command == "G0":
                rapid_time += (distance / rapid_feedrate) * 60.0
            else:
                rapid_time_or_cut = (distance / current_feedrate) * 60.0
                cutting_time += rapid_time_or_cut

        position_x, position_y, position_z = next_x, next_y, next_z

    return MachiningStats(
        tool_name=tool_name,
        max_spindle_rpm=max_spindle,
        max_feedrate_mm_min=max_feedrate,
        cutting_time_seconds=cutting_time,
        rapid_time_seconds=rapid_time,
        unique_z_levels=frozenset(unique_z_levels),
    )
