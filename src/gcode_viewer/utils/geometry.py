from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple

Point3D = Tuple[float, float, float]
Segment = Tuple[float, float]


@dataclass(frozen=True)
class Bounds2D:
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def depth(self) -> float:
        return self.max_y - self.min_y

    @property
    def center(self) -> Tuple[float, float]:
        return (self.min_x + self.max_x) / 2.0, (self.min_y + self.max_y) / 2.0


def distance_3d(a: Point3D, b: Point3D) -> float:
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)


def bounds_from_segment(
    from_x: float,
    from_y: float,
    to_x: float,
    to_y: float,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
) -> Tuple[float, float, float, float]:
    return (
        min(min_x, from_x, to_x),
        max(max_x, from_x, to_x),
        min(min_y, from_y, to_y),
        max(max_y, from_y, to_y),
    )


def xy_bounds_from_segments(
    x_segments: Iterable[Segment],
    y_segments: Iterable[Segment],
) -> Optional[Bounds2D]:
    xs = [value for segment in x_segments for value in segment]
    ys = [value for segment in y_segments for value in segment]
    if not xs or not ys:
        return None
    return Bounds2D(min(xs), max(xs), min(ys), max(ys))


def origin_alignment_offset(bounds: Bounds2D) -> Tuple[float, float]:
    """Shift so the toolpath's min corner lands on machine origin (0, 0)."""
    return -bounds.min_x, -bounds.min_y


def camera_distance_for_bounds(
    width: float,
    depth: float,
    margin: float = 1.5,
    minimum_distance: float = 40.0,
) -> float:
    distance = max(width, depth) * margin
    return max(distance, minimum_distance)


def grid_spacing_for_bed(bed_width: float, large_threshold: float = 400.0) -> float:
    return 50.0 if bed_width > large_threshold else 10.0


def padded_limits(
    minimum: float,
    maximum: float,
    relative_padding: float,
    absolute_padding: float,
) -> Tuple[float, float]:
    span = maximum - minimum
    pad = max(absolute_padding, span * relative_padding)
    return minimum - pad, maximum + pad
