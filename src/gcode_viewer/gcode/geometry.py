"""Compatibility re-exports; prefer ``gcode_viewer.utils`` for new code."""

from gcode_viewer.utils.arc import tessellate_arc
from gcode_viewer.utils.geometry import Point3D, bounds_from_segment, distance_3d

__all__ = ["Point3D", "distance_3d", "tessellate_arc", "bounds_from_segment"]
