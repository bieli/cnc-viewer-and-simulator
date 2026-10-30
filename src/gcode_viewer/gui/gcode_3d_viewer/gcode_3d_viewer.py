from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np
import pyqtgraph.opengl as gl
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QVector3D
from PyQt5.QtWidgets import QVBoxLayout, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gui.simulation_controls import SimulationControls
from gcode_viewer.utils.endmill_mesh import build_endmill_mesh, mesh_as_arrays
from gcode_viewer.utils.geometry import (
    Bounds2D,
    Point3D,
    camera_distance_for_bounds,
    grid_spacing_for_bed,
    origin_alignment_offset,
    xy_bounds_from_segments,
)
from gcode_viewer.utils.simulation import (
    DEFAULT_CUT_FEED_MM_MIN,
    ToolpathSimulator,
    build_simulation_segments,
)

DEFAULT_BED_SIZE = 200.0
TIMER_INTERVAL_MS = 33


def collect_path_bounds(
    layer_list: Sequence[Layer],
) -> Optional[Tuple[float, float, float, float]]:
    x_segments = [segment for layer in layer_list for segment in layer.x_data]
    y_segments = [segment for layer in layer_list for segment in layer.y_data]
    bounds = xy_bounds_from_segments(x_segments, y_segments)
    if bounds is None:
        return None
    return bounds.min_x, bounds.max_x, bounds.min_y, bounds.max_y


class GCode3DViewer(QWidget):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__()
        self.settings = settings
        self.viewer = gl.GLViewWidget()
        self.controls = SimulationControls()
        self.simulator = ToolpathSimulator()
        self.tool_mesh: Optional[gl.GLMeshItem] = None
        self._playing = False
        self._timer = QTimer(self)
        self._timer.setInterval(TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer_tick)
        self._wire_controls()
        self._init_ui()

    def _wire_controls(self) -> None:
        self.controls.on_play = self.play
        self.controls.on_pause = self.pause
        self.controls.on_stop = self.stop
        self.controls.on_next = self.next_step
        self.controls.on_prev = self.prev_step
        self.controls.on_to_end = self.jump_to_end
        self.controls.on_seek = self.seek_segment
        self.controls.on_speed_changed = self.set_speed_multiplier
        self.controls.set_playing(False)

    def _init_ui(self) -> None:
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.viewer, 1)
        layout.addWidget(self.controls, 0)
        self.viewer.setWindowTitle("Viewer")
        self.viewer.setCameraPosition(distance=250)
        grid = gl.GLGridItem()
        grid.setSize(DEFAULT_BED_SIZE, DEFAULT_BED_SIZE)
        grid.setSpacing(5, 5)
        self.viewer.addItem(grid)

    def _clear_scene(self) -> None:
        self.pause()
        self.tool_mesh = None
        for item in list(self.viewer.items):
            self.viewer.removeItem(item)

    def _bed_size(self) -> Tuple[float, float]:
        if self.settings is None:
            return DEFAULT_BED_SIZE, DEFAULT_BED_SIZE
        bed = self.settings.workspace.machine_bed
        return float(bed.width_x), float(bed.depth_y)

    def set_simulation_feedrate(self, feedrate_mm_min: float) -> None:
        if feedrate_mm_min <= 0:
            return
        self.simulator.override_cut_feedrate_mm_min = feedrate_mm_min
        self._refresh_status()

    def set_speed_multiplier(self, multiplier: float) -> None:
        self.simulator.speed_multiplier = max(0.01, multiplier)

    def play(self) -> None:
        if not self.simulator.segments:
            return
        if self.simulator.is_finished:
            self.simulator.reset()
            self._update_tool_pose()
        self._playing = True
        self.controls.set_playing(True)
        self._timer.start()
        self._refresh_status()

    def pause(self) -> None:
        self._playing = False
        self._timer.stop()
        self.controls.set_playing(False)
        self._refresh_status()

    def stop(self) -> None:
        self.pause()
        self.simulator.reset()
        self._update_tool_pose()
        self.controls.set_progress_value(0)
        self._refresh_status()

    def next_step(self) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        self.simulator.step_forward()
        self._update_tool_pose()
        self._sync_slider()
        self._refresh_status()

    def prev_step(self) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        self.simulator.step_backward()
        self._update_tool_pose()
        self._sync_slider()
        self._refresh_status()

    def jump_to_end(self) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        self.simulator.jump_to_end()
        self._update_tool_pose()
        self._sync_slider()
        self._refresh_status()

    def seek_segment(self, index: int) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        self.simulator.set_segment_index(index)
        self._update_tool_pose()
        self._refresh_status()

    def _on_timer_tick(self) -> None:
        still_running = self.simulator.advance(TIMER_INTERVAL_MS / 1000.0)
        self._update_tool_pose()
        self._sync_slider()
        self._refresh_status()
        if not still_running:
            self.pause()

    def _sync_slider(self) -> None:
        self.controls.set_progress_value(self.simulator.segment_index)

    def _refresh_status(self) -> None:
        feed = self.simulator.override_cut_feedrate_mm_min
        feed_text = (
            f" | cut feed {feed:.0f} mm/min"
            if feed is not None
            else f" | cut feed default {DEFAULT_CUT_FEED_MM_MIN:.0f} mm/min"
        )
        state = "playing" if self._playing else "paused"
        self.controls.set_status(
            f"Simulation ({state}): {self.simulator.status_text()}{feed_text}"
        )

    def _update_tool_pose(self) -> None:
        if self.tool_mesh is None:
            return
        position = self.simulator.current_position()
        if position is None:
            return
        self.tool_mesh.resetTransform()
        self.tool_mesh.translate(position[0], position[1], position[2])

    def _create_tool_mesh(self, position: Point3D) -> gl.GLMeshItem:
        vertices, faces = mesh_as_arrays(build_endmill_mesh())
        mesh_data = gl.MeshData(
            vertexes=np.array(vertices),
            faces=np.array(faces, dtype=int),
        )
        tool_mesh = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=True,
            color=(1.0, 0.65, 0.1, 1.0),
            shader="shaded",
        )
        tool_mesh.translate(position[0], position[1], position[2])
        return tool_mesh

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
            self.simulator = ToolpathSimulator()
            self.controls.set_progress_range(0)
            self._refresh_status()
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
        self.viewer.setCameraPosition(
            pos=QVector3D(shifted_width / 2.0, shifted_depth / 2.0, 0.0),
            distance=camera_distance_for_bounds(shifted_width, shifted_depth),
            elevation=45,
            azimuth=-45,
        )

        previous_feed = self.simulator.override_cut_feedrate_mm_min
        segments = build_simulation_segments(layer_list, offset_x, offset_y)
        self.simulator = ToolpathSimulator(
            segments=segments,
            override_cut_feedrate_mm_min=previous_feed,
            speed_multiplier=self.controls.current_speed(),
        )
        self.controls.set_progress_range(max(0, len(segments) - 1))
        self.controls.set_progress_value(0)

        if segments:
            self.tool_mesh = self._create_tool_mesh(segments[0].start)
            self.viewer.addItem(self.tool_mesh)
        self._refresh_status()
