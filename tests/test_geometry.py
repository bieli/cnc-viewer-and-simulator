from __future__ import annotations

import pytest

from gcode_viewer.gcode.geometry import bounds_from_segment, distance_3d, tessellate_arc


def test_distance_3d() -> None:
    assert distance_3d((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == 5.0


def test_tessellate_arc_returns_points() -> None:
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


def test_bounds_from_segment() -> None:
    min_x, max_x, min_y, max_y = bounds_from_segment(
        1.0, 2.0, 5.0, -1.0, 10.0, 0.0, 10.0, 0.0
    )
    assert min_x == 1.0
    assert max_x == 5.0
    assert min_y == -1.0
    assert max_y == 2.0
