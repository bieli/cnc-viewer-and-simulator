from __future__ import annotations

from typing import Optional

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QWidget


class GCodeCanvas(FigureCanvas):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        width: float = 5.0,
        height: float = 4.0,
        dpi: int = 100,
    ) -> None:
        figure = Figure(figsize=(width, height), dpi=dpi)
        self.axes = figure.add_subplot(111)
        super().__init__(figure)
        self.setParent(parent)
