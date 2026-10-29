from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from matplotlib.collections import LineCollection
from PyQt5.QtWidgets import QGridLayout, QWidget

from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.layer import Layer
from gcode_viewer.gui.gcode_layer_viewer.gcode_canvas import GCodeCanvas

MatplotlibColor = Tuple[float, float, float, float]


def resolve_plot_color(color: str) -> MatplotlibColor:
    if color == "g":
        return (0.0, 1.0, 0.5, 1.0)
    if color == "b":
        return (0.2, 0.2, 1.0, 1.0)
    if color == "r":
        return (1.0, 0.3, 0.3, 0.8)
    return (0.5, 0.5, 0.5, 0.5)


class GCodeLayerViewerStatic(QWidget):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.layer_list: Optional[List[Layer]] = None
        self.zoomed_in = False
        self.settings = settings
        self.canvas = GCodeCanvas(self, width=5, height=4, dpi=100)
        self._init_ui()

    def _init_ui(self) -> None:
        grid = QGridLayout()
        grid.addWidget(self.canvas, 0, 0)
        self.setLayout(grid)

    def set_layer_list(self, layer_list: Sequence[Layer]) -> None:
        self.layer_list = list(layer_list)

    def load_layer(self, _index: int) -> None:
        if not self.layer_list:
            return
        self.start_showing_static()

    def start_showing_static(self) -> None:
        if not self.layer_list:
            return

        self.canvas.axes.cla()
        self.canvas.axes.set_xlabel("Object width X [mm]")
        self.canvas.axes.set_ylabel("Milling depth Z [mm]")
        self.canvas.axes.grid(True, linestyle="--", alpha=0.5)

        global_min_z = 0.0
        global_max_z = 0.0
        segments: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
        colors: List[MatplotlibColor] = []
        all_x_coords: List[float] = []

        for layer in self.layer_list:
            if not layer.x_data:
                continue
            for index in range(len(layer.x_data)):
                x_seg = layer.x_data[index]
                z_seg = layer.z_data[index]
                color_key = (
                    layer.matplot_color[index]
                    if index < len(layer.matplot_color)
                    else "g"
                )
                segments.append(((x_seg[0], z_seg[0]), (x_seg[1], z_seg[1])))
                colors.append(resolve_plot_color(color_key))
                all_x_coords.extend([x_seg[0], x_seg[1]])
                global_min_z = min(global_min_z, z_seg[0], z_seg[1])
                global_max_z = max(global_max_z, z_seg[0], z_seg[1])

        if segments:
            line_segments = LineCollection(segments, colors=colors, linewidths=1.5)
            self.canvas.axes.add_collection(line_segments)
            self.canvas.axes.axhline(
                y=global_min_z, color="darkgreen", linestyle=":", linewidth=1.2, alpha=0.8
            )
            self.canvas.axes.text(
                0.02,
                global_min_z,
                f" Min Z: {global_min_z:.2f} mm",
                transform=self.canvas.axes.get_yaxis_transform(),
                color="darkgreen",
                weight="bold",
                va="bottom",
                ha="left",
                fontsize=14,
                bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1},
            )
            self.canvas.axes.axhline(
                y=global_max_z, color="darkred", linestyle=":", linewidth=1.2, alpha=0.8
            )
            self.canvas.axes.text(
                0.02,
                global_max_z,
                f" Max Z: {global_max_z:.2f} mm",
                transform=self.canvas.axes.get_yaxis_transform(),
                color="darkred",
                weight="bold",
                va="bottom",
                ha="left",
                fontsize=14,
                bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none", "pad": 1},
            )

        if all_x_coords:
            global_min_x = min(all_x_coords)
            global_max_x = max(all_x_coords)
        else:
            global_min_x = 0.0
            global_max_x = float(self.settings.environment.printer.bed_width_x)

        padding_x = max(5.0, (global_max_x - global_min_x) * 0.1)
        padding_z = max(2.0, (global_max_z - global_min_z) * 0.2)

        if self.zoomed_in:
            self.canvas.axes.set_xlim(global_min_x - padding_x, global_max_x + padding_x)
        else:
            self.canvas.axes.set_xlim(
                0, float(self.settings.environment.printer.bed_width_x)
            )

        self.canvas.axes.set_ylim(global_min_z - padding_z, global_max_z + padding_z)
        self.canvas.draw()
        self.show()
