from __future__ import annotations

import pytest

from gcode_viewer.utils.geometry import (
    Bounds2D,
    bounds_from_segment,
    camera_distance_for_bounds,
    distance_3d,
    grid_spacing_for_bed,
    origin_alignment_offset,
    padded_limits,
    xy_bounds_from_segments,
)


def test_distance_3d_pythagorean() -> None:
    assert distance_3d((0.0, 0.0, 0.0), (3.0, 4.0, 0.0)) == 5.0
    assert distance_3d((0.0, 0.0, 0.0), (0.0, 0.0, 0.0)) == 0.0


def test_bounds_from_segment_expands_box() -> None:
    min_x, max_x, min_y, max_y = bounds_from_segment(
        1.0, 2.0, 5.0, -1.0, 10.0, 0.0, 10.0, 0.0
    )
    assert (min_x, max_x, min_y, max_y) == (1.0, 5.0, -1.0, 2.0)


def test_xy_bounds_from_segments() -> None:
    bounds = xy_bounds_from_segments(
        x_segments=[(10.0, 20.0), (5.0, 15.0)],
        y_segments=[(1.0, 2.0), (-3.0, 4.0)],
    )
    assert bounds is not None
    assert bounds == Bounds2D(5.0, 20.0, -3.0, 4.0)
    assert bounds.width == 15.0
    assert bounds.depth == 7.0
    assert bounds.center == (12.5, 0.5)


def test_xy_bounds_empty() -> None:
    assert xy_bounds_from_segments([], []) is None


def test_origin_alignment_offset() -> None:
    assert origin_alignment_offset(Bounds2D(12.0, 40.0, -5.0, 10.0)) == (-12.0, 5.0)


def test_camera_distance_for_bounds() -> None:
    assert camera_distance_for_bounds(100.0, 40.0, margin=1.5) == 150.0
    assert camera_distance_for_bounds(1.0, 1.0, margin=1.5, minimum_distance=40.0) == 40.0


def test_grid_spacing_for_bed() -> None:
    assert grid_spacing_for_bed(200.0) == 10.0
    assert grid_spacing_for_bed(500.0) == 50.0


def test_padded_limits() -> None:
    low, high = padded_limits(0.0, 100.0, relative_padding=0.1, absolute_padding=5.0)
    assert low == pytest.approx(-10.0)
    assert high == pytest.approx(110.0)
    low, high = padded_limits(0.0, 10.0, relative_padding=0.1, absolute_padding=5.0)
    assert low == pytest.approx(-5.0)
    assert high == pytest.approx(15.0)
