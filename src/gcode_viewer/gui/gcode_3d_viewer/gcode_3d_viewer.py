from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np
import pyqtgraph.opengl as gl
from PyQt5.QtGui import QVector3D
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.utils.endmill_mesh import build_endmill_mesh, mesh_as_arrays
from gcode_viewer.utils.geometry import (
    Bounds2D,
    Point3D,
    camera_distance_for_bounds,
    grid_spacing_for_bed,
    origin_alignment_offset,
    xy_bounds_from_segments,
)

DEFAULT_BED_SIZE = 200.0


def collect_path_bounds(
    layer_list: Sequence[Layer],
) -> Optional[Tuple[float, float, float, float]]:
    x_segments = [segment for layer in layer_list for segment in layer.x_data]
    y_segments = [segment for layer in layer_list for segment in layer.y_data]
    bounds = xy_bounds_from_segments(x_segments, y_segments)
    if bounds is None:
        return None
    return bounds.min_x, bounds.max_x, bounds.min_y, bounds.max_y


def first_toolpath_point(
    layer_list: Sequence[Layer],
    offset_x: float,
    offset_y: float,
) -> Optional[Point3D]:
    for layer in layer_list:
        if not layer.x_data:
            continue
        x_seg = layer.x_data[0]
        y_seg = layer.y_data[0]
        z_seg = layer.z_data[0]
        return (
            float(x_seg[0]) + offset_x,
            float(y_seg[0]) + offset_y,
            float(z_seg[0]),
        )
    return None


class GCode3DViewer(QWidget):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__()
        self.settings = settings
        self.viewer = gl.GLViewWidget()
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.viewer, 1)
        self.viewer.setWindowTitle("Viewer")
        self.viewer.setCameraPosition(distance=250)
        grid = gl.GLGridItem()
        grid.setSize(DEFAULT_BED_SIZE, DEFAULT_BED_SIZE)
        grid.setSpacing(5, 5)
        self.viewer.addItem(grid)

    def _clear_scene(self) -> None:
        for item in list(self.viewer.items):
            self.viewer.removeItem(item)

    def _bed_size(self) -> Tuple[float, float]:
        if self.settings is None:
            return DEFAULT_BED_SIZE, DEFAULT_BED_SIZE
        bed = self.settings.workspace.machine_bed
        return float(bed.width_x), float(bed.depth_y)

    def load_gcode(self, layer_list: Sequence[Layer]) -> None:
        self._clear_scene()
        bed_x, bed_y = self._bed_size()

        grid = gl.GLGridItem()
        grid.setSize(bed_x, bed_y, 1.0)
        spacing = grid_spacing_for_bed(bed_x)
        grid.setSpacing(spacing, spacing, 1.0)
        grid.resetTransform()
        grid.translate(bed_x / 2.0, bed_y / 2.0, 0.0)
        grid.setColor((200, 200, 200, 60))
        self.viewer.addItem(grid)

        bounds_tuple = collect_path_bounds(layer_list)
        if bounds_tuple is None:
            return

        min_x, max_x, min_y, max_y = bounds_tuple
        bounds = Bounds2D(min_x, max_x, min_y, max_y)
        offset_x, offset_y = origin_alignment_offset(bounds)

        for layer in layer_list:
            if not layer.x_data:
                continue
            points: List[List[float]] = []
            colors: List[Tuple[float, float, float, float]] = []
            for index in range(len(layer.x_data)):
                x_start, x_end = layer.x_data[index]
                y_start, y_end = layer.y_data[index]
                z_start, z_end = layer.z_data[index]
                points.append(
                    [float(x_start) + offset_x, float(y_start) + offset_y, float(z_start)]
                )
                points.append(
                    [float(x_end) + offset_x, float(y_end) + offset_y, float(z_end)]
                )
                color = (
                    layer.pyqtgraph_color[index]
                    if index < len(layer.pyqtgraph_color)
                    else (0.0, 1.0, 0.5, 1.0)
                )
                colors.append(color)
                colors.append(color)

            if points:
                line_item = gl.GLLinePlotItem(
                    pos=np.array(points),
                    color=np.array(colors),
                    width=2.0,
                    mode="lines",
                )
                self.viewer.addItem(line_item)

        shifted_width = bounds.width
        shifted_depth = bounds.depth
        center_x = shifted_width / 2.0
        center_y = shifted_depth / 2.0
        self.viewer.setCameraPosition(
            pos=QVector3D(center_x, center_y, 0.0),
            distance=camera_distance_for_bounds(shifted_width, shifted_depth),
            elevation=45,
            azimuth=-45,
        )

        start_point = first_toolpath_point(layer_list, offset_x, offset_y)
        if start_point is None:
            return

        vertices, faces = mesh_as_arrays(build_endmill_mesh())
        mesh_data = gl.MeshData(vertexes=np.array(vertices), faces=np.array(faces, dtype=int))
        tool_mesh = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=True,
            color=(1.0, 0.65, 0.1, 1.0),
            shader="shaded",
        )
        tool_mesh.translate(start_point[0], start_point[1], start_point[2])
        self.viewer.addItem(tool_mesh)
