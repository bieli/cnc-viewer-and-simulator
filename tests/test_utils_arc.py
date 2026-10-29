from __future__ import annotations

import math

import pytest

from gcode_viewer.utils.arc import tessellate_arc


def test_quarter_circle_counterclockwise_ends_near_target() -> None:
    points = tessellate_arc(
        start=(10.0, 0.0, 0.0),
        end=(0.0, 10.0, 0.0),
        i_offset=-10.0,
        j_offset=0.0,
        clockwise=False,
    )
    assert len(points) >= 4
    assert points[-1][0] == pytest.approx(0.0, abs=1e-3)
    assert points[-1][1] == pytest.approx(10.0, abs=1e-3)
    assert points[-1][2] == pytest.approx(0.0, abs=1e-9)


def test_clockwise_arc_stays_on_radius() -> None:
    start = (10.0, 0.0, -1.0)
    end = (0.0, -10.0, -1.0)
    points = tessellate_arc(
        start=start,
        end=end,
        i_offset=-10.0,
        j_offset=0.0,
        clockwise=True,
    )
    for point in points:
        radius = math.hypot(point[0] - 0.0, point[1] - 0.0)
        assert radius == pytest.approx(10.0, abs=0.05)
    assert points[-1][0] == pytest.approx(0.0, abs=1e-2)
    assert points[-1][1] == pytest.approx(-10.0, abs=1e-2)


def test_arc_interpolates_z_linearly() -> None:
    points = tessellate_arc(
        start=(10.0, 0.0, 0.0),
        end=(0.0, 10.0, -2.0),
        i_offset=-10.0,
        j_offset=0.0,
        clockwise=False,
        min_segments=8,
        max_segments=8,
    )
    assert points[0][2] == pytest.approx(-2.0 / 8.0, abs=1e-9)
    assert points[-1][2] == pytest.approx(-2.0, abs=1e-9)


def test_short_arc_uses_minimum_segment_count() -> None:
    points = tessellate_arc(
        start=(1.0, 0.0, 0.0),
        end=(0.999, 0.045, 0.0),
        i_offset=-1.0,
        j_offset=0.0,
        clockwise=False,
        min_segments=4,
        max_segments=32,
    )
    assert len(points) == 4
