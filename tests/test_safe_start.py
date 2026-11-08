from __future__ import annotations

from pathlib import Path

import pytest

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.gcode.analysis import analyze_machining
from gcode_viewer.gcode.parser import LayerParser
from gcode_viewer.gcode.safe_start import (
    SAFE_START_MARKER,
    build_safe_start_plan,
    choose_clearance_z,
    compute_safe_start_pose,
    inject_safe_start_lines,
    left_nearest_corner,
    rewrite_gcode_safe_start,
    shift_xy_words,
)
from gcode_viewer.utils.geometry import Bounds3D
from gcode_viewer.utils.simulation import ToolpathSimulator, build_simulation_segments


def test_left_nearest_corner_picks_closer_left_vertex() -> None:
    bounds = Bounds3D(min_x=10.0, max_x=40.0, min_y=-5.0, max_y=20.0, min_z=-2.0, max_z=0.0)
    assert left_nearest_corner(bounds) == (10.0, -5.0)


def test_choose_clearance_uses_rapid_height_above_stock() -> None:
    lines = [
        "G0 Z5",
        "G0 X25 Y0",
        "G1 Z-6 F200",
        "G1 X20 Y0",
    ]
    assert choose_clearance_z(0.0, lines) == pytest.approx(5.0)


def test_compute_safe_start_pose_uses_max_cutting_z() -> None:
    lines = [
        "G0 X0 Y0 Z5",
        "G1 Z-1 F1000",
        "G1 X40 Y10",
        "G1 X40 Y-8",
        "G0 Z5",
    ]
    pose = compute_safe_start_pose(analyze_machining(lines))
    assert pose.x == pytest.approx(0.0)
    assert pose.y == pytest.approx(-8.0)
    assert pose.z == pytest.approx(0.0)


def test_shift_xy_words_keeps_ij_relative() -> None:
    assert shift_xy_words("G2 X10 Y0 I5 J0", 2.0, 3.0) == "G2 X12.000000 Y3.000000 I5 J0"


def test_lead_in_parks_on_stock_then_raises_then_travels() -> None:
    lines = [
        "(Job)",
        "G0 Z5.",
        "G0 X25. Y0.",
        "G1 Z-6. F200",
        "G1 X24 Y0",
        "G1 X-30 Y-30",
    ]
    plan = build_safe_start_plan(lines)
    rewritten = inject_safe_start_lines(lines, plan)
    assert rewritten.count(SAFE_START_MARKER) == 1
    assert any(line.startswith("G0 X0.000000 Y0.000000 Z0.000000") for line in rewritten)
    assert any(line == "G0 Z5.000000" for line in rewritten)
    assert any(
        line.startswith("G0 X") and "Y" in line and "Z5.000000" in line for line in rewritten
    )

    segments = build_simulation_segments(LayerParser().parse_layer_list(rewritten))
    # Skip zero-length park if present; find raise then travel then plunge.
    rapid_segs = [segment for segment in segments if segment.is_rapid]
    assert rapid_segs[0].start[0] == pytest.approx(0.0)
    assert rapid_segs[0].start[1] == pytest.approx(0.0)
    assert rapid_segs[0].start[2] == pytest.approx(0.0)
    assert rapid_segs[0].end[2] == pytest.approx(5.0)
    assert rapid_segs[1].end[2] == pytest.approx(5.0)
    assert abs(rapid_segs[1].end[0]) > 1.0 or abs(rapid_segs[1].end[1]) > 1.0

    sim = ToolpathSimulator(segments=segments)
    sim.go_to_safe_start()
    idle = sim.current_position()
    assert idle is not None
    assert idle[0] == pytest.approx(0.0)
    assert idle[1] == pytest.approx(0.0)
    assert idle[2] == pytest.approx(0.0)

    again, pose = rewrite_gcode_safe_start("\n".join(rewritten))
    assert pose.z == pytest.approx(0.0)
    again_segs = build_simulation_segments(
        LayerParser().parse_layer_list(again.splitlines())
    )
    again_rapids = [segment for segment in again_segs if segment.is_rapid]
    assert again_rapids[0].end[2] == pytest.approx(5.0)
    assert again_rapids[1].is_rapid and again_rapids[1].end[2] == pytest.approx(5.0)
    assert not again_segs[again_segs.index(again_rapids[1]) + 1].is_rapid


def test_rewrite_gcode_safe_start_preserves_newline_style() -> None:
    text = "(Demo)\r\nG0 Z5\r\nG0 X10 Y0\r\nG1 Z-2 F1000\r\nG1 X10 Y-4\r\n"
    rewritten, pose = rewrite_gcode_safe_start(text)
    assert "\r\n" in rewritten
    assert SAFE_START_MARKER in rewritten
    assert pose.x == pytest.approx(0.0)
    assert pose.y == pytest.approx(0.0)
    assert pose.z == pytest.approx(0.0)


def test_ensure_bak_copy_only_once(tmp_path: Path) -> None:
    handler = FileHandler()
    gcode = tmp_path / "part.nc"
    gcode.write_text("G0 X0\nG1 X1 F100\n", encoding="utf-8")
    created, bak = handler.ensure_bak_copy(gcode)
    assert created is True
    gcode.write_text("G0 X9\n", encoding="utf-8")
    created_again, _ = handler.ensure_bak_copy(gcode)
    assert created_again is False
    assert bak.read_text(encoding="utf-8") == "G0 X0\nG1 X1 F100\n"
