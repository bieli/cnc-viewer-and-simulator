from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PyQt5.QtGui import QColor, QImage, QPainter

from gcode_viewer.utils.recording import (
    SimulationRecorder,
    default_recording_path,
    qimage_to_rgb_array,
)


def test_default_recording_path_uses_cwd_and_mp4_suffix(tmp_path: Path) -> None:
    path = default_recording_path(tmp_path)
    assert path.parent == tmp_path
    assert path.name.startswith("cnc_simulation_")
    assert path.suffix == ".mp4"


def test_qimage_to_rgb_array_shape_and_color() -> None:
    image = QImage(8, 6, QImage.Format_RGB888)
    image.fill(QColor(10, 20, 30))
    array = qimage_to_rgb_array(image)
    assert array.shape == (6, 8, 3)
    assert array.dtype == np.uint8
    assert tuple(array[0, 0].tolist()) == (10, 20, 30)


def test_simulation_recorder_writes_mp4(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    recorder = SimulationRecorder(output, fps=10)
    recorder.start()
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    frame[:, :] = (0, 255, 0)
    for _ in range(5):
        recorder.add_frame(frame)
    saved = recorder.close()
    assert saved == output
    assert output.exists()
    assert output.stat().st_size > 0
    assert recorder.frame_count == 5


def test_simulation_recorder_rejects_bad_frame(tmp_path: Path) -> None:
    recorder = SimulationRecorder(tmp_path / "bad.mp4", fps=10)
    recorder.start()
    with pytest.raises(ValueError):
        recorder.add_frame(np.zeros((10, 10), dtype=np.uint8))
    recorder.close()


def test_qimage_with_painter_roundtrip_not_null() -> None:
    image = QImage(16, 16, QImage.Format_ARGB32)
    image.fill(QColor("black"))
    painter = QPainter(image)
    painter.fillRect(0, 0, 8, 8, QColor("cyan"))
    painter.end()
    array = qimage_to_rgb_array(image)
    assert array.shape == (16, 16, 3)
