from __future__ import annotations

import math
from typing import List, Tuple

Point3D = Tuple[float, float, float]


def distance_3d(a: Point3D, b: Point3D) -> float:
    return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2)


def tessellate_arc(
    start: Point3D,
    end: Point3D,
    i_offset: float,
    j_offset: float,
    clockwise: bool,
    g2_angle_ratio: float = 2.0,
) -> List[Point3D]:
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
    segments = max(4, min(32, int(arc_length * 2.0)))

    points: List[Point3D] = []
    for step in range(1, segments + 1):
        t = step / float(segments)
        current_angle = angle_start + angle_diff * t
        inter_x = center_x + radius * math.cos(current_angle)
        inter_y = center_y + radius * math.sin(current_angle)
        inter_z = start[2] + (end[2] - start[2]) * t
        points.append((inter_x, inter_y, inter_z))
    return points


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
    larger_x = max(to_x, from_x)
    smaller_x = min(to_x, from_x)
    larger_y = max(to_y, from_y)
    smaller_y = min(to_y, from_y)
    return (
        min(min_x, smaller_x),
        max(max_x, larger_x),
        min(min_y, smaller_y),
        max(max_y, larger_y),
    )
