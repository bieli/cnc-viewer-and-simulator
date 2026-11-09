from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import numpy as np
import pyqtgraph.opengl as gl
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QVector3D
from PyQt5.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.analysis import DEFAULT_TOOL_DIAMETER_MM
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gui.simulation_controls import SimulationControls
from gcode_viewer.utils.endmill_mesh import build_endmill_mesh, mesh_as_arrays
from gcode_viewer.utils.geometry import (
    Bounds2D,
    Bounds3D,
    Point3D,
    camera_distance_for_bounds,
    grid_spacing_for_bed,
    origin_alignment_offset,
    xy_bounds_from_segments,
)
from gcode_viewer.utils.recording import (
    DEFAULT_RECORD_FPS,
    SimulationRecorder,
    default_recording_path,
    grab_widget_rgb_frame,
)
from gcode_viewer.utils.simulation import (
    DEFAULT_CUT_FEED_MM_MIN,
    SimSegment,
    ToolpathSimulator,
    build_simulation_segments,
)
from gcode_viewer.utils.stock_heightmap import StockHeightMap
from gcode_viewer.utils.stock_octree import offset_bounds

# Keep ~8 GiB for the height field inside the user's ~10 GiB material budget.
STOCK_HEIGHTMAP_MAX_BYTES = 8 * 1024**3


DEFAULT_BED_SIZE = 200.0
TIMER_INTERVAL_MS = 33
RECORD_INTERVAL_MS = 33
STOCK_MESH_REBUILD_S = 0.45
# Light orange — shaded GL lighting darkens base color, so keep it bright.
STOCK_COLOR = (1.0, 0.82, 0.48, 1.0)
PENDING_PATH_COLOR = (0.70, 0.72, 0.76, 0.95)
RAPID_PATH_COLOR = (1.0, 0.3, 0.3, 0.8)
CUT_PATH_COLOR = (0.0, 1.0, 0.5, 1.0)


def collect_path_bounds(
    layer_list: Sequence[Layer],
) -> Optional[Tuple[float, float, float, float]]:
    x_segments = [segment for layer in layer_list for segment in layer.x_data]
    y_segments = [segment for layer in layer_list for segment in layer.y_data]
    bounds = xy_bounds_from_segments(x_segments, y_segments)
    if bounds is None:
        return None
    return bounds.min_x, bounds.max_x, bounds.min_y, bounds.max_y


def segment_base_color(segment: SimSegment) -> Tuple[float, float, float, float]:
    return RAPID_PATH_COLOR if segment.is_rapid else CUT_PATH_COLOR


def _lerp_point(start: Point3D, end: Point3D, t: float) -> Point3D:
    return (
        start[0] + (end[0] - start[0]) * t,
        start[1] + (end[1] - start[1]) * t,
        start[2] + (end[2] - start[2]) * t,
    )


class GCode3DViewer(QWidget):
    def __init__(self, settings: Optional[Settings] = None) -> None:
        super().__init__()
        self.settings = settings
        self.viewer = gl.GLViewWidget()
        self.controls = SimulationControls()
        self.simulator = ToolpathSimulator()
        self.tool_mesh: Optional[gl.GLMeshItem] = None
        self.path_item: Optional[gl.GLLinePlotItem] = None
        self.stock_mesh_item: Optional[gl.GLMeshItem] = None
        self._path_positions: Optional[np.ndarray] = None
        self._path_base_colors: Optional[np.ndarray] = None
        self._trail_mode = False
        self._playing = False
        self._recording = False
        self._recorder: Optional[SimulationRecorder] = None
        self._last_recording_path: Optional[Path] = None
        self._stock: Optional[StockHeightMap] = None
        self._stock_source_bounds: Optional[Bounds3D] = None
        self._tool_diameter_mm = DEFAULT_TOOL_DIAMETER_MM
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._carved_segment_index = 0
        self._carved_progress = 0.0
        self._stock_dirty = False
        self._last_stock_mesh_time = 0.0
        self._material_enabled = False
        self._precise_enabled = False
        self._toolpaths_visible = True
        self._finalizing_recording = False
        self._timer = QTimer(self)
        self._timer.setInterval(TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._on_timer_tick)
        self._record_timer = QTimer(self)
        self._record_timer.setInterval(RECORD_INTERVAL_MS)
        self._record_timer.timeout.connect(self._on_record_tick)
        self._wire_controls()
        self._init_ui()

    def _wire_controls(self) -> None:
        self.controls.on_play = self.play
        self.controls.on_pause = self.pause
        self.controls.on_stop = self.stop
        self.controls.on_record = self.start_recording
        self.controls.on_next = self.next_step
        self.controls.on_prev = self.prev_step
        self.controls.on_to_end = self.jump_to_end
        self.controls.on_seek = self.seek_segment
        self.controls.on_speed_changed = self.set_speed_multiplier
        self.controls.on_material_toggled = self.set_material_enabled
        self.controls.on_precise_toggled = self.set_precise_enabled
        self.controls.on_toolpaths_toggled = self.set_toolpaths_visible
        self.controls.set_playing(False)
        self.controls.set_recording(False)
        self.controls.set_material_enabled(False)
        self.controls.set_precise_enabled(False)
        self.controls.set_toolpaths_visible(True)

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
        self._finalize_recording(notify=False)
        self.pause()
        self.tool_mesh = None
        self.path_item = None
        self.stock_mesh_item = None
        self._path_positions = None
        self._path_base_colors = None
        self._trail_mode = False
        self._stock = None
        self._stock_source_bounds = None
        self._carved_segment_index = 0
        self._carved_progress = 0.0
        self._stock_dirty = False
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

    def set_material_enabled(self, enabled: bool) -> None:
        self._material_enabled = enabled
        if not enabled:
            self._hide_stock_mesh()
            return
        self._refresh_material_display(force_rebuild=True)

    def set_precise_enabled(self, enabled: bool) -> None:
        self._precise_enabled = enabled
        if self._material_enabled:
            self._refresh_material_display(force_rebuild=True)
        self._refresh_status()

    def set_toolpaths_visible(self, visible: bool) -> None:
        self._toolpaths_visible = visible
        if self.path_item is not None:
            self.path_item.setVisible(visible)

    def play(self) -> None:
        if not self.simulator.segments:
            return
        if self.simulator.is_finished or self.simulator.is_at_start:
            # Restart at stock-top corner; first motion is raise, then clearance travel.
            self.simulator.reset()
            self._update_tool_pose()
            if self._material_enabled:
                self._reset_stock_carving()
                self._sync_stock_to_simulator(force_mesh=True)
        self._trail_mode = True
        self._refresh_path_colors()
        self._playing = True
        self.controls.set_playing(True)
        self._timer.start()
        self._refresh_status()

    def pause(self) -> None:
        self._playing = False
        self._timer.stop()
        self.controls.set_playing(False)
        if self._material_enabled and self._stock_dirty:
            self._rebuild_stock_mesh()
        self._refresh_status()

    def start_recording(self) -> None:
        if self._recording:
            return
        if not self.simulator.segments:
            QMessageBox.information(
                self,
                "Nothing to record",
                "Load a G-code file before recording the simulation.",
            )
            return
        output_path = default_recording_path()
        try:
            recorder = SimulationRecorder(output_path, fps=DEFAULT_RECORD_FPS)
            recorder.start()
        except Exception as exc:  # noqa: BLE001 - surface ffmpeg/imageio setup issues
            QMessageBox.critical(
                self,
                "Recording failed",
                f"Could not start MP4 recorder:\n{exc}",
            )
            return

        self._recorder = recorder
        self._recording = True
        self._last_recording_path = output_path
        self.controls.set_recording(True)
        self._record_timer.start()
        self._capture_recording_frame()
        self.play()
        self._refresh_status()

    def stop(self) -> None:
        self._record_timer.stop()
        self.pause()
        # Idle pose: corner on stock top (before raise), ready for clearance travel.
        self.simulator.go_to_safe_start()
        self._trail_mode = False
        self._update_tool_pose()
        self._refresh_path_colors()
        if self._material_enabled:
            self._reset_stock_carving()
            self._sync_stock_to_simulator(force_mesh=True)
        self.controls.set_progress_value(self.simulator.segment_index)
        self._finalize_recording(notify=True)
        self._refresh_status()

    def next_step(self) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        if not self._trail_mode:
            self._trail_mode = True
        self.simulator.step_forward()
        self._update_tool_pose()
        self._refresh_path_colors()
        self._sync_stock_to_simulator(force_mesh=True)
        self._sync_slider()
        self._refresh_status()

    def prev_step(self) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        if not self._trail_mode:
            self._trail_mode = True
        self.simulator.step_backward()
        self._update_tool_pose()
        self._refresh_path_colors()
        self._sync_stock_to_simulator(force_mesh=True)
        self._sync_slider()
        self._refresh_status()

    def jump_to_end(self) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        self._trail_mode = True
        self.simulator.jump_to_end()
        self._update_tool_pose()
        self._refresh_path_colors()
        self._sync_stock_to_simulator(force_mesh=True)
        self._sync_slider()
        self._refresh_status()

    def seek_segment(self, index: int) -> None:
        if not self.simulator.segments:
            return
        self.pause()
        self._trail_mode = True
        self.simulator.set_segment_index(index)
        self._update_tool_pose()
        self._refresh_path_colors()
        self._sync_stock_to_simulator(force_mesh=True)
        self._refresh_status()

    def _on_timer_tick(self) -> None:
        still_running = self.simulator.advance(TIMER_INTERVAL_MS / 1000.0)
        self._update_tool_pose()
        self._refresh_path_colors()
        self._sync_stock_to_simulator(force_mesh=False)
        self._sync_slider()
        self._refresh_status()
        if not still_running:
            self.pause()
            # Stop frame grabs before finalize; grabFramebuffer runs processEvents.
            self._record_timer.stop()
            self._finalize_recording(notify=True)

    def _on_record_tick(self) -> None:
        if not self._recording or self._finalizing_recording:
            return
        self._capture_recording_frame()

    def _capture_recording_frame(self) -> None:
        if self._finalizing_recording:
            return
        recorder = self._recorder
        if not self._recording or recorder is None or not recorder.is_open:
            return
        frame = grab_widget_rgb_frame(self.viewer)
        # grabFramebuffer / processEvents may have finalized recording already.
        if (
            frame is None
            or self._finalizing_recording
            or not self._recording
            or self._recorder is not recorder
            or not recorder.is_open
        ):
            return
        try:
            recorder.add_frame(frame)
        except Exception as exc:  # noqa: BLE001
            message = f"Could not write video frame:\n{exc}"
            self._recording = False
            self._record_timer.stop()
            self.controls.set_recording(False)
            if self._recorder is recorder:
                try:
                    recorder.close()
                except Exception:  # noqa: BLE001
                    pass
                self._recorder = None
            QMessageBox.critical(self, "Recording failed", message)

    def _finalize_recording(self, notify: bool) -> None:
        if self._finalizing_recording:
            return
        if not self._recording and self._recorder is None:
            self.controls.set_recording(False)
            return
        self._finalizing_recording = True
        self._record_timer.stop()
        self._recording = False
        self.controls.set_recording(False)
        recorder = self._recorder
        self._recorder = None
        saved_path: Optional[Path] = None
        frame_count = 0
        try:
            if recorder is not None:
                frame_count = recorder.frame_count
                try:
                    # Capture one last frame with final pose/colors.
                    self._update_tool_pose()
                    self._refresh_path_colors()
                    if self._material_enabled and self._stock_dirty:
                        self._rebuild_stock_mesh()
                    if recorder.is_open:
                        frame = grab_widget_rgb_frame(self.viewer)
                        if frame is not None and recorder.is_open:
                            recorder.add_frame(frame)
                            frame_count = recorder.frame_count
                    saved_path = recorder.close()
                except Exception as exc:  # noqa: BLE001
                    try:
                        if recorder.is_open:
                            recorder.close()
                    except Exception:  # noqa: BLE001
                        pass
                    if notify:
                        QMessageBox.critical(
                            self,
                            "Recording failed",
                            f"Could not finalize MP4:\n{exc}",
                        )
                    return
            self._last_recording_path = saved_path
            if notify and saved_path is not None:
                QMessageBox.information(
                    self,
                    "Recording saved",
                    (
                        f"Simulation recording saved:\n{saved_path.resolve()}\n\n"
                        f"Frames: {frame_count}"
                    ),
                )
        finally:
            self._finalizing_recording = False

    def _sync_slider(self) -> None:
        self.controls.set_progress_value(self.simulator.segment_index)

    def _refresh_status(self) -> None:
        feed = self.simulator.override_cut_feedrate_mm_min
        feed_text = (
            f" | cut feed {feed:.0f} mm/min"
            if feed is not None
            else f" | cut feed default {DEFAULT_CUT_FEED_MM_MIN:.0f} mm/min"
        )
        if self._recording:
            state = "recording"
        elif self._playing:
            state = "playing"
        else:
            state = "paused"
        recording_text = ""
        if self._recording and self._last_recording_path is not None:
            recording_text = f" | MP4 {self._last_recording_path.name}"
        material_text = ""
        if self._material_enabled and self._stock is not None:
            mode = "Precise" if self._precise_enabled else "Fast"
            material_text = (
                f" | material {mode} {self._stock.cell_mm:.2f}mm "
                f"({self._stock.nx}x{self._stock.ny})"
            )
        elif self._material_enabled:
            material_text = " | material ON"
        self.controls.set_status(
            f"Simulation ({state}): {self.simulator.status_text()}"
            f"{feed_text}{material_text}{recording_text}"
        )

    def _segment_is_done(self, index: int) -> bool:
        if index < self.simulator.segment_index:
            return True
        if index > self.simulator.segment_index:
            return False
        return self.simulator.progress > 0.0

    def _refresh_path_colors(self) -> None:
        if self.path_item is None or self._path_base_colors is None:
            return
        if not self._trail_mode:
            self.path_item.setData(color=self._path_base_colors)
            return

        colors = np.array(self._path_base_colors, copy=True)
        pending = np.array(PENDING_PATH_COLOR, dtype=float)
        segment_count = len(self.simulator.segments)
        for index in range(segment_count):
            if self._segment_is_done(index):
                continue
            colors[index * 2] = pending
            colors[index * 2 + 1] = pending
        self.path_item.setData(color=colors)

    def _update_tool_pose(self) -> None:
        if self.tool_mesh is None:
            return
        position = self.simulator.current_position()
        if position is None:
            return
        self.tool_mesh.resetTransform()
        self.tool_mesh.translate(position[0], position[1], position[2])

    def _create_tool_mesh(self, position: Point3D) -> gl.GLMeshItem:
        radius = max(self._tool_diameter_mm / 2.0, 0.2)
        vertices, faces = mesh_as_arrays(build_endmill_mesh(radius=radius))
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

    def _build_path_arrays(
        self,
        segments: Sequence[SimSegment],
    ) -> Tuple[np.ndarray, np.ndarray]:
        points: List[List[float]] = []
        colors: List[Tuple[float, float, float, float]] = []
        for segment in segments:
            points.append([segment.start[0], segment.start[1], segment.start[2]])
            points.append([segment.end[0], segment.end[1], segment.end[2]])
            color = segment_base_color(segment)
            colors.append(color)
            colors.append(color)
        return np.array(points, dtype=float), np.array(colors, dtype=float)

    def _resolve_stock_and_tool(self, layer_list: Sequence[Layer]) -> None:
        self._tool_diameter_mm = DEFAULT_TOOL_DIAMETER_MM
        self._stock_source_bounds = None
        for layer in layer_list:
            if layer.tool_diameter_mm > 0:
                self._tool_diameter_mm = layer.tool_diameter_mm
            if layer.stock_bounds is not None:
                self._stock_source_bounds = layer.stock_bounds
                break

    def _shifted_stock_bounds(self) -> Optional[Bounds3D]:
        if self._stock_source_bounds is None:
            return None
        return offset_bounds(
            self._stock_source_bounds,
            self._offset_x,
            self._offset_y,
        )

    def _init_stock_from_bounds(self) -> None:
        shifted = self._shifted_stock_bounds()
        if shifted is None:
            self._stock = None
            return
        self._stock = StockHeightMap.from_stock(
            shifted,
            self._tool_diameter_mm,
            precise=self._precise_enabled,
            max_bytes=STOCK_HEIGHTMAP_MAX_BYTES,
        )
        self._carved_segment_index = 0
        self._carved_progress = 0.0
        self._stock_dirty = True

    def _refresh_material_display(self, force_rebuild: bool) -> None:
        if not self._material_enabled:
            self._hide_stock_mesh()
            return
        self._init_stock_from_bounds()
        if self._stock is None:
            return
        self._reset_stock_carving()
        self._sync_stock_to_simulator(force_mesh=True)

    def _apply_stock_mesh(self, vertices: np.ndarray, faces: np.ndarray) -> None:
        self._stock_dirty = False
        self._last_stock_mesh_time = time.monotonic()
        if vertices.size == 0 or faces.size == 0:
            self._hide_stock_mesh()
            return
        mesh_data = gl.MeshData(vertexes=vertices, faces=faces)
        if self.stock_mesh_item is not None:
            try:
                self.stock_mesh_item.setMeshData(meshdata=mesh_data)
                return
            except Exception:  # noqa: BLE001
                self._hide_stock_mesh()
        item = gl.GLMeshItem(
            meshdata=mesh_data,
            smooth=False,
            color=STOCK_COLOR,
            shader="shaded",
            glOptions="opaque",
        )
        self.viewer.addItem(item)
        self.stock_mesh_item = item

    def _hide_stock_mesh(self) -> None:
        if self.stock_mesh_item is not None:
            try:
                self.viewer.removeItem(self.stock_mesh_item)
            except Exception:  # noqa: BLE001
                pass
            self.stock_mesh_item = None

    def _reset_stock_carving(self) -> None:
        if self._stock is None:
            return
        self._stock.reset()
        self._carved_segment_index = 0
        self._carved_progress = 0.0
        self._stock_dirty = True

    def _sync_stock_to_simulator(self, force_mesh: bool) -> None:
        if not self._material_enabled or self._stock is None:
            return
        target_index = self.simulator.segment_index
        target_progress = self.simulator.progress
        if self.simulator.is_finished and self.simulator.segments:
            target_index = len(self.simulator.segments) - 1
            target_progress = 1.0

        behind = (target_index, target_progress) < (
            self._carved_segment_index,
            self._carved_progress,
        )
        if behind:
            self._reset_stock_carving()

        changed = self._carve_forward(target_index, target_progress)
        if changed:
            self._stock_dirty = True

        now = time.monotonic()
        if force_mesh or (
            self._stock_dirty
            and (now - self._last_stock_mesh_time) >= STOCK_MESH_REBUILD_S
        ):
            self._rebuild_stock_mesh()

    def _carve_forward(self, target_index: int, target_progress: float) -> bool:
        assert self._stock is not None
        radius = max(self._tool_diameter_mm / 2.0, 0.1)
        changed = False
        segments = self.simulator.segments
        if not segments:
            return False

        index = self._carved_segment_index
        progress = self._carved_progress

        while index < target_index or (
            index == target_index and progress < target_progress - 1e-9
        ):
            if index >= len(segments):
                break
            segment = segments[index]
            end_progress = target_progress if index == target_index else 1.0
            if end_progress <= progress + 1e-12:
                if index < target_index:
                    index += 1
                    progress = 0.0
                    continue
                break

            if not segment.is_rapid:
                start_pt = _lerp_point(segment.start, segment.end, progress)
                end_pt = _lerp_point(segment.start, segment.end, end_progress)
                if self._stock.carve_segment(start_pt, end_pt, radius):
                    changed = True

            if index < target_index:
                index += 1
                progress = 0.0
            else:
                progress = end_progress
                break

        self._carved_segment_index = index
        self._carved_progress = progress
        return changed

    def _rebuild_stock_mesh(self) -> None:
        if self._stock is None:
            return
        mesh = self._stock.build_mesh()
        self._apply_stock_mesh(mesh.vertices, mesh.faces)

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
        self._offset_x = offset_x
        self._offset_y = offset_y
        self._resolve_stock_and_tool(layer_list)

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
            positions, base_colors = self._build_path_arrays(segments)
            self._path_positions = positions
            self._path_base_colors = base_colors
            self.path_item = gl.GLLinePlotItem(
                pos=positions,
                color=base_colors,
                width=2.0,
                mode="lines",
            )
            self.viewer.addItem(self.path_item)
            self.path_item.setVisible(self._toolpaths_visible)
            self.simulator.go_to_safe_start()
            start_pose = self.simulator.current_position() or segments[0].end
            self.tool_mesh = self._create_tool_mesh(start_pose)
            self.viewer.addItem(self.tool_mesh)
            self.controls.set_progress_value(self.simulator.segment_index)

        if self._material_enabled:
            self._refresh_material_display(force_rebuild=True)

        shifted_width = bounds.width
        shifted_depth = bounds.depth
        self.viewer.setCameraPosition(
            pos=QVector3D(shifted_width / 2.0, shifted_depth / 2.0, 0.0),
            distance=camera_distance_for_bounds(shifted_width, shifted_depth),
            elevation=45,
            azimuth=-45,
        )
        self._refresh_status()
