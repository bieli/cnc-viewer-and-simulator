from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, cast

import numpy as np
from numpy.typing import NDArray
from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication, QWidget

DEFAULT_RECORD_FPS = 30


def default_recording_path(directory: Optional[Union[str, Path]] = None) -> Path:
    root = Path(directory) if directory is not None else Path.cwd()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return root / f"cnc_simulation_{stamp}.mp4"


def qimage_to_rgb_array(image: QImage) -> NDArray[np.uint8]:
    """Convert a QImage to an RGB uint8 array shaped (H, W, 3)."""
    converted = image.convertToFormat(QImage.Format_RGB888)
    width = converted.width()
    height = converted.height()
    bytes_per_line = converted.bytesPerLine()
    ptr = converted.bits()
    if ptr is None:
        raise RuntimeError("failed to read QImage bits")
    byte_count = (
        converted.sizeInBytes()
        if hasattr(converted, "sizeInBytes")
        else converted.byteCount()
    )
    ptr.setsize(byte_count)
    buffer = memoryview(cast(Any, ptr))
    raw = np.frombuffer(buffer, dtype=np.uint8).reshape((height, bytes_per_line))
    # bytesPerLine may include padding beyond width * 3
    rgb = raw[:, : width * 3].reshape((height, width, 3)).copy()
    return cast(NDArray[np.uint8], rgb)


def grab_widget_rgb_frame(widget: QWidget) -> Optional[np.ndarray]:
    """Grab the current widget pixels (OpenGL framebuffer when available)."""
    widget.update()
    QApplication.processEvents()

    image: Optional[QImage] = None
    grab_framebuffer = getattr(widget, "grabFramebuffer", None)
    if callable(grab_framebuffer):
        image = grab_framebuffer()
    if image is None:
        grab_frame_buffer = getattr(widget, "grabFrameBuffer", None)
        if callable(grab_frame_buffer):
            image = grab_frame_buffer()
    if image is None:
        pixmap = widget.grab()
        image = pixmap.toImage()

    if image is None or image.isNull() or image.width() <= 0 or image.height() <= 0:
        return None
    return qimage_to_rgb_array(image)


class SimulationRecorder:
    """Write RGB frames to an H.264 MP4 via imageio/ffmpeg."""

    def __init__(
        self,
        output_path: Union[str, Path],
        fps: int = DEFAULT_RECORD_FPS,
    ) -> None:
        self.output_path = Path(output_path)
        self.fps = max(1, fps)
        self._writer: Any = None
        self.frame_count = 0

    @property
    def is_open(self) -> bool:
        return self._writer is not None

    def start(self) -> None:
        if self._writer is not None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        import imageio.v2 as imageio

        self._writer = imageio.get_writer(
            self.output_path,
            fps=self.fps,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
            macro_block_size=1,
        )
        self.frame_count = 0

    def add_frame(self, frame: np.ndarray) -> None:
        if self._writer is None:
            raise RuntimeError("recorder is not started")
        if frame.ndim != 3 or frame.shape[2] != 3:
            raise ValueError("frame must be an RGB array with shape (H, W, 3)")
        # libx264 / yuv420p prefers even dimensions
        height, width = frame.shape[:2]
        even_h = height - (height % 2)
        even_w = width - (width % 2)
        if even_h <= 0 or even_w <= 0:
            return
        clipped = frame[:even_h, :even_w]
        self._writer.append_data(np.ascontiguousarray(clipped))
        self.frame_count += 1

    def close(self) -> Path:
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        return self.output_path
