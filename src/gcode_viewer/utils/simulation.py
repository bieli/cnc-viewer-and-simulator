from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gcode.words import extract_feedrate, tokenize
from gcode_viewer.utils.geometry import Point3D, distance_3d
from gcode_viewer.utils.time_estimate import travel_time_seconds

DEFAULT_CUT_FEED_MM_MIN = 1000.0
DEFAULT_RAPID_FEED_MM_MIN = 3000.0


@dataclass(frozen=True)
class SimSegment:
    start: Point3D
    end: Point3D
    is_rapid: bool
    file_feedrate_mm_min: Optional[float] = None

    @property
    def length_mm(self) -> float:
        return distance_3d(self.start, self.end)


@dataclass
class ToolpathSimulator:
    segments: List[SimSegment] = field(default_factory=list)
    segment_index: int = 0
    progress: float = 0.0
    override_cut_feedrate_mm_min: Optional[float] = None
    rapid_feedrate_mm_min: float = DEFAULT_RAPID_FEED_MM_MIN
    default_cut_feedrate_mm_min: float = DEFAULT_CUT_FEED_MM_MIN
    speed_multiplier: float = 1.0

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def is_finished(self) -> bool:
        if not self.segments:
            return True
        return self.segment_index >= len(self.segments) - 1 and self.progress >= 1.0

    @property
    def is_at_start(self) -> bool:
        if not self.segments:
            return True
        return self.segment_index <= 0 and self.progress >= 1.0

    @property
    def is_before_first_move(self) -> bool:
        return self.segment_index <= 0 and self.progress <= 0.0

    def reset(self) -> None:
        self.segment_index = 0
        self.progress = 0.0

    def go_to_safe_start(self) -> None:
        """Place the tool at the end of the first approach move (not at work origin)."""
        if not self.segments:
            self.reset()
            return
        self.segment_index = 0
        self.progress = 1.0

    def jump_to_end(self) -> None:
        if not self.segments:
            return
        self.segment_index = len(self.segments) - 1
        self.progress = 1.0

    def set_segment_index(self, index: int) -> None:
        if not self.segments:
            self.segment_index = 0
            self.progress = 0.0
            return
        self.segment_index = max(0, min(index, len(self.segments) - 1))
        self.progress = 0.0

    def effective_feedrate(self, segment: SimSegment) -> float:
        if segment.is_rapid:
            return max(self.rapid_feedrate_mm_min, 1.0)
        if self.override_cut_feedrate_mm_min is not None:
            return max(self.override_cut_feedrate_mm_min, 1.0)
        if segment.file_feedrate_mm_min is not None and segment.file_feedrate_mm_min > 0:
            return segment.file_feedrate_mm_min
        return max(self.default_cut_feedrate_mm_min, 1.0)

    def current_position(self) -> Optional[Point3D]:
        if not self.segments:
            return None
        index = min(self.segment_index, len(self.segments) - 1)
        segment = self.segments[index]
        t = self.progress
        return (
            segment.start[0] + (segment.end[0] - segment.start[0]) * t,
            segment.start[1] + (segment.end[1] - segment.start[1]) * t,
            segment.start[2] + (segment.end[2] - segment.start[2]) * t,
        )

    def step_forward(self) -> bool:
        if not self.segments:
            return False
        if self.is_finished:
            return False
        if self.progress < 1.0:
            self.progress = 1.0
            return True
        if self.segment_index < len(self.segments) - 1:
            self.segment_index += 1
            self.progress = 1.0
            return True
        return False

    def step_backward(self) -> bool:
        if not self.segments:
            return False
        if self.progress > 0.0 and self.segment_index < len(self.segments):
            self.progress = 0.0
            return True
        if self.segment_index > 0:
            self.segment_index -= 1
            self.progress = 0.0
            return True
        return False

    def advance(self, dt_seconds: float) -> bool:
        """Advance simulation by wall-clock dt, scaled by speed_multiplier.

        Returns False when the toolpath is finished.
        """
        if not self.segments or self.is_finished or dt_seconds <= 0:
            return not self.is_finished

        remaining = dt_seconds * max(self.speed_multiplier, 0.01)
        while remaining > 0 and not self.is_finished:
            segment = self.segments[self.segment_index]
            length = segment.length_mm
            if length <= 1e-9:
                if self.segment_index >= len(self.segments) - 1:
                    self.progress = 1.0
                    break
                self.segment_index += 1
                self.progress = 0.0
                continue

            feed = self.effective_feedrate(segment)
            segment_duration = travel_time_seconds(length, feed)
            time_left_in_segment = segment_duration * (1.0 - self.progress)
            if remaining >= time_left_in_segment:
                remaining -= time_left_in_segment
                self.progress = 1.0
                if self.segment_index >= len(self.segments) - 1:
                    break
                self.segment_index += 1
                self.progress = 0.0
            else:
                self.progress += remaining / segment_duration
                remaining = 0.0
        return not self.is_finished

    def status_text(self) -> str:
        if not self.segments:
            return "No toolpath"
        step = min(self.segment_index + 1, len(self.segments))
        kind = "rapid" if self.segments[self.segment_index].is_rapid else "cut"
        return f"Step {step} / {len(self.segments)} ({kind})"


def build_simulation_segments(
    layer_list: Sequence[Layer],
    offset_x: float = 0.0,
    offset_y: float = 0.0,
) -> List[SimSegment]:
    segments: List[SimSegment] = []
    for layer in layer_list:
        for index in range(len(layer.x_data)):
            x0, x1 = layer.x_data[index]
            y0, y1 = layer.y_data[index]
            z0, z1 = layer.z_data[index]
            start = (float(x0) + offset_x, float(y0) + offset_y, float(z0))
            end = (float(x1) + offset_x, float(y1) + offset_y, float(z1))
            if distance_3d(start, end) <= 1e-9:
                continue

            color = (
                layer.matplot_color[index]
                if index < len(layer.matplot_color)
                else "g"
            )
            is_rapid = color == "r"
            file_feed: Optional[float] = None
            if index < len(layer.move_data):
                words = tokenize(layer.move_data[index])
                extracted = extract_feedrate(words)
                if extracted is not None and extracted > 0:
                    file_feed = extracted
            segments.append(
                SimSegment(
                    start=start,
                    end=end,
                    is_rapid=is_rapid,
                    file_feedrate_mm_min=file_feed,
                )
            )
    return segments
