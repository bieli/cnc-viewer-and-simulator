from __future__ import annotations

import math
from typing import List

from gcode_viewer.utils.geometry import Point3D


def tessellate_arc(
    start: Point3D,
    end: Point3D,
    i_offset: float,
    j_offset: float,
    clockwise: bool,
    g2_angle_ratio: float = 2.0,
    min_segments: int = 4,
    max_segments: int = 32,
    density: float = 2.0,
) -> List[Point3D]:
    """Approximate a G2/G3 circular arc as a polyline in XY with linear Z.

    Center is defined by I/J offsets from the start point (CNC convention).
    Segment count scales with arc length so short arcs stay cheap and long
    arcs keep a readable curve.
    """
    center_x = start[0] + i_offset
    center_y = start[1] + j_offset

    radius_start = math.hypot(start[0] - center_x, start[1] - center_y)
    radius_end = math.hypot(end[0] - center_x, end[1] - center_y)
    radius = (radius_start + radius_end) / 2.0

    angle_start = math.atan2(start[1] - center_y, start[0] - center_x)
    angle_end = math.atan2(end[1] - center_y, end[0] - center_x)

    if clockwise:
        if angle_end >= angle_start:
            angle_end -= g2_angle_ratio * math.pi
    else:
        if angle_end <= angle_start:
            angle_end += g2_angle_ratio * math.pi

    angle_diff = angle_end - angle_start
    arc_length = abs(angle_diff) * radius
    segments = max(min_segments, min(max_segments, int(arc_length * density)))

    points: List[Point3D] = []
    for step in range(1, segments + 1):
        t = step / float(segments)
        current_angle = angle_start + angle_diff * t
        inter_x = center_x + radius * math.cos(current_angle)
        inter_y = center_y + radius * math.sin(current_angle)
        inter_z = start[2] + (end[2] - start[2]) * t
        points.append((inter_x, inter_y, inter_z))
    return points
