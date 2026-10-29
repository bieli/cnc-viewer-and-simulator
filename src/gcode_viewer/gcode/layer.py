from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

ColorRGBA = Tuple[float, float, float, float]
Segment = Tuple[float, float]


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
