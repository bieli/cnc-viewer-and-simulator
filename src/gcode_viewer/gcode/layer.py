from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from gcode_viewer.utils.geometry import Bounds3D

ColorRGBA = Tuple[float, float, float, float]
Segment = Tuple[float, float]
DEFAULT_LAYER_TOOL_DIAMETER_MM = 3.0


@dataclass
class Layer:
    number: Optional[int] = None
    layer_as_string: List[str] = field(default_factory=list)
    move_data: List[str] = field(default_factory=list)
    x_data: List[Segment] = field(default_factory=list)
    y_data: List[Segment] = field(default_factory=list)
    z_data: List[Segment] = field(default_factory=list)
    min_x: float = 0.0
    max_x: float = 0.0
    min_y: float = 0.0
    max_y: float = 0.0
    pyqtgraph_color: List[ColorRGBA] = field(default_factory=list)
    matplot_color: List[str] = field(default_factory=list)
    largest_extrusion_value: float = 0.0
    tool_info: str = ""
    time_estimation: str = ""
    step_z_info: str = ""
    material_size_info: str = ""
    tool_diameter_mm: float = DEFAULT_LAYER_TOOL_DIAMETER_MM
    stock_bounds: Optional[Bounds3D] = None
