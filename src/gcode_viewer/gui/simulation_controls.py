from __future__ import annotations

from typing import Callable, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

PlayCallback = Callable[[], None]
SeekCallback = Callable[[int], None]

RECALCULATE_BUTTON_STYLE = (
    "font-weight: bold; font-size: 15px; padding: 5px 10px; "
    "background-color: #0066cc; color: white; border: none; border-radius: 4px;"
)
RECORD_BUTTON_STYLE = (
    "font-weight: bold; font-size: 15px; padding: 5px 10px; "
    "background-color: #c62828; color: white; border: none; border-radius: 4px;"
)
RECORD_BUTTON_ACTIVE_STYLE = (
    "font-weight: bold; font-size: 15px; padding: 5px 10px; "
    "background-color: #ad1457; color: white; border: 2px solid #ffcdd2; "
    "border-radius: 4px;"
)


class SimulationControls(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.on_play: Optional[PlayCallback] = None
        self.on_pause: Optional[PlayCallback] = None
        self.on_stop: Optional[PlayCallback] = None
        self.on_record: Optional[PlayCallback] = None
        self.on_next: Optional[PlayCallback] = None
        self.on_prev: Optional[PlayCallback] = None
        self.on_to_end: Optional[PlayCallback] = None
        self.on_seek: Optional[SeekCallback] = None
        self.on_speed_changed: Optional[Callable[[float], None]] = None

        self.status_label = QLabel("Simulation: idle")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.record_button = QPushButton("Recording")
        self.prev_button = QPushButton("Prev")
        self.next_button = QPushButton("Next")
        self.end_button = QPushButton("End")
        self.speed_combo = QComboBox()
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self._seeking = False
        self._recording = False
        self._init_ui()

    def _init_ui(self) -> None:
        root = QVBoxLayout()
        root.setContentsMargins(0, 6, 0, 0)
        root.setSpacing(6)

        self.status_label.setStyleSheet("font-size: 14px; color: #333;")
        root.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        for button, handler in (
            (self.play_button, self._emit_play),
            (self.pause_button, self._emit_pause),
            (self.stop_button, self._emit_stop),
            (self.record_button, self._emit_record),
            (self.prev_button, self._emit_prev),
            (self.next_button, self._emit_next),
            (self.end_button, self._emit_end),
        ):
            style = (
                RECORD_BUTTON_STYLE
                if button is self.record_button
                else RECALCULATE_BUTTON_STYLE
            )
            button.setStyleSheet(style)
            button.setMinimumHeight(36)
            button.setMinimumWidth(84)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        self.record_button.setToolTip(
            "Start Play and record the 3D view to MP4 in the current directory. "
            "Stop ends recording (mouse orbit is included)."
        )
        self.record_button.setMinimumWidth(110)

        speed_label = QLabel("Speed")
        speed_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #444;")
        self.speed_combo.setStyleSheet(
            "font-size: 15px; padding: 4px 8px; min-height: 28px;"
        )
        self.speed_combo.addItem("0.5x", 0.5)
        self.speed_combo.addItem("1x", 1.0)
        self.speed_combo.addItem("5x", 5.0)
        self.speed_combo.addItem("10x", 10.0)
        self.speed_combo.addItem("50x", 50.0)
        self.speed_combo.addItem("100x", 100.0)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.currentIndexChanged.connect(self._emit_speed)
        buttons.addWidget(speed_label)
        buttons.addWidget(self.speed_combo)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(0)
        self.progress_slider.setEnabled(False)
        self.progress_slider.setMinimumHeight(22)
        self.progress_slider.sliderPressed.connect(self._on_slider_pressed)
        self.progress_slider.sliderReleased.connect(self._on_slider_released)
        self.progress_slider.valueChanged.connect(self._on_slider_changed)
        root.addWidget(self.progress_slider)
        self.setLayout(root)

    def set_playing(self, playing: bool) -> None:
        self.play_button.setEnabled(not playing and not self._recording)
        self.pause_button.setEnabled(playing)
        self.record_button.setEnabled(not self._recording)

    def set_recording(self, recording: bool) -> None:
        self._recording = recording
        if recording:
            self.record_button.setText("Recording…")
            self.record_button.setStyleSheet(RECORD_BUTTON_ACTIVE_STYLE)
            self.record_button.setEnabled(False)
            self.play_button.setEnabled(False)
        else:
            self.record_button.setText("Recording")
            self.record_button.setStyleSheet(RECORD_BUTTON_STYLE)
            self.record_button.setEnabled(True)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_progress_range(self, maximum: int) -> None:
        self.progress_slider.setEnabled(maximum > 0)
        self.progress_slider.setMaximum(max(0, maximum))
        if maximum <= 0:
            self.progress_slider.setValue(0)

    def set_progress_value(self, value: int) -> None:
        if self._seeking:
            return
        self.progress_slider.blockSignals(True)
        self.progress_slider.setValue(max(0, value))
        self.progress_slider.blockSignals(False)

    def current_speed(self) -> float:
        data = self.speed_combo.currentData()
        return float(data) if data is not None else 1.0

    def _emit_play(self) -> None:
        if self.on_play:
            self.on_play()

    def _emit_pause(self) -> None:
        if self.on_pause:
            self.on_pause()

    def _emit_stop(self) -> None:
        if self.on_stop:
            self.on_stop()

    def _emit_record(self) -> None:
        if self.on_record:
            self.on_record()

    def _emit_prev(self) -> None:
        if self.on_prev:
            self.on_prev()

    def _emit_next(self) -> None:
        if self.on_next:
            self.on_next()

    def _emit_end(self) -> None:
        if self.on_to_end:
            self.on_to_end()

    def _emit_speed(self) -> None:
        if self.on_speed_changed:
            self.on_speed_changed(self.current_speed())

    def _on_slider_pressed(self) -> None:
        self._seeking = True

    def _on_slider_released(self) -> None:
        self._seeking = False
        if self.on_seek:
            self.on_seek(self.progress_slider.value())

    def _on_slider_changed(self, value: int) -> None:
        if self._seeking and self.on_seek:
            self.on_seek(value)
