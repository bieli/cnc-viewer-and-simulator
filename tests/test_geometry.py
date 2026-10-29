from __future__ import annotations

"""Compatibility imports from gcode.geometry still resolve to utils."""

import pytest

from gcode_viewer.gcode.geometry import bounds_from_segment, distance_3d, tessellate_arc


def test_compat_distance_3d() -> None:
    assert distance_3d((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == 5.0


def test_compat_tessellate_arc() -> None:
    points = tessellate_arc(
        start=(10.0, 0.0, 0.0),
        end=(0.0, 10.0, 0.0),
        i_offset=-10.0,
        j_offset=0.0,
        clockwise=False,
    )
    assert points[-1][0] == pytest.approx(0.0, abs=1e-3)


def test_compat_bounds_from_segment() -> None:
    assert bounds_from_segment(1.0, 2.0, 5.0, -1.0, 10.0, 0.0, 10.0, 0.0) == (
        1.0,
        5.0,
        -1.0,
        2.0,
    )
