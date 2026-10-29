from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pyqtgraph.opengl as gl
from PyQt5.QtGui import QVector3D
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.layer import Layer

Point3D = Tuple[float, float, float]
DEFAULT_BED_SIZE = 200.0


def build_tool_mesh(
    radius: float = 1.5,
    cylinder_height: float = 12.0,
    cone_height: float = 4.0,
    sides: int = 16,
) -> Tuple[np.ndarray, np.ndarray]:
    vertices: List[List[float]] = [[0.0, 0.0, 0.0]]

    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append([radius * math.cos(angle), radius * math.sin(angle), cone_height])

    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append(
            [
                radius * math.cos(angle),
                radius * math.sin(angle),
                cone_height + cylinder_height,
            ]
        )

    vertices.append([0.0, 0.0, cone_height + cylinder_height])

    faces: List[List[int]] = []
    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append([0, index + 1, next_index + 1])

    for index in range(sides):
        next_index = (index + 1) % sides
        p1 = index + 1
        p2 = next_index + 1
        p3 = index + 1 + sides
        p4 = next_index + 1 + sides
        faces.append([p1, p2, p3])
        faces.append([p2, p4, p3])

    top_center_index = len(vertices) - 1
    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append([top_center_index, index + 1 + sides, next_index + 1 + sides])

    return np.array(vertices), np.array(faces, dtype=int)


def collect_path_bounds(
    layer_list: Sequence[Layer],
) -> Optional[Tuple[float, float, float, float]]:
    all_x: List[float] = []
    all_y: List[float] = []
    for layer in layer_list:
        for segment in layer.x_data:
            all_x.extend([segment[0], segment[1]])
        for segment in layer.y_data:
            all_y.extend([segment[0], segment[1]])
    if not all_x or not all_y:
        return None
    return min(all_x), max(all_x), min(all_y), max(all_y)


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
        grid_spacing = 50.0 if bed_x > 400.0 else 10.0
        grid.setSpacing(grid_spacing, grid_spacing, 1.0)
        grid.resetTransform()
        grid.translate(bed_x / 2.0, bed_y / 2.0, 0.0)
        grid.setColor((200, 200, 200, 60))
        self.viewer.addItem(grid)

        bounds = collect_path_bounds(layer_list)
        if bounds is None:
            return

        min_x, max_x, min_y, max_y = bounds
        offset_x = -min_x
        offset_y = -min_y

        for layer in layer_list:
            if not layer.x_data:
                continue
            points: List[List[float]] = []
            colors: List[Tuple[float, float, float, float]] = []
            for index in range(len(layer.x_data)):
                x_start, x_end = layer.x_data[index]
                y_start, y_end = layer.y_data[index]
                z_start, z_end = layer.z_data[index]
                points.append([float(x_start) + offset_x, float(y_start) + offset_y, float(z_start)])
                points.append([float(x_end) + offset_x, float(y_end) + offset_y, float(z_end)])
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

        final_max_x = max_x + offset_x
        final_max_y = max_y + offset_y
        center_x = final_max_x / 2.0
        center_y = final_max_y / 2.0
        max_dimension = max(final_max_x, final_max_y)
        self.viewer.setCameraPosition(
            pos=QVector3D(center_x, center_y, 0.0),
            distance=max_dimension * 1.5,
            elevation=45,
            azimuth=-45,
        )

        start_point = first_toolpath_point(layer_list, offset_x, offset_y)
        if start_point is None:
            return

        vertices, faces = build_tool_mesh()
        mesh_data = gl.MeshData(vertexes=vertices, faces=faces)
        tool_mesh = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=True,
            color=(1.0, 0.65, 0.1, 1.0),
            shader="shaded",
        )
        tool_mesh.translate(start_point[0], start_point[1], start_point[2])
        self.viewer.addItem(tool_mesh)
