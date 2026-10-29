from __future__ import annotations

import pytest

from gcode_viewer.utils.feedrate import normalize_feedrate_mm_min
from gcode_viewer.utils.time_estimate import format_duration, travel_time_seconds


def test_travel_time_seconds() -> None:
    assert travel_time_seconds(1000.0, 1000.0) == 60.0
    assert travel_time_seconds(0.0, 1000.0) == 0.0
    with pytest.raises(ValueError):
        travel_time_seconds(10.0, 0.0)


def test_format_duration() -> None:
    assert format_duration(0.0) == "00:00:00"
    assert format_duration(3661.0) == "01:01:01"
    assert format_duration(-5.0) == "00:00:00"


def test_normalize_feedrate_mm_min() -> None:
    assert normalize_feedrate_mm_min(1200.0) == 1200.0
    assert normalize_feedrate_mm_min(120000.0) == 2000.0
    assert normalize_feedrate_mm_min(1200.9) == 1200.0
