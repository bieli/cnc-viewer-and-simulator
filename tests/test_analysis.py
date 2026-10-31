from __future__ import annotations

import pytest

from gcode_viewer.gcode.analysis import analyze_machining
from gcode_viewer.utils.step_depth import format_step_z_info


def test_analyze_machining_reads_tool_and_spindle() -> None:
    lines = [
        "(TC: Endmill 6mm)",
        "G0 X0 Y0 Z5",
        "G1 Z-1 F1200 S18000",
        "G1 X10 Y0",
    ]
    stats = analyze_machining(lines)
    assert stats.tool_name == "Endmill 6mm"
    assert stats.max_spindle_rpm == 18000
    assert stats.max_feedrate_mm_min == 1200
    assert stats.cutting_time_seconds > 0
    assert "Endmill 6mm" in stats.tool_info
    assert stats.time_estimation.count(":") == 2


def test_override_feedrate_changes_time() -> None:
    lines = [
        "G0 X0 Y0 Z5",
        "G1 Z-1 F600",
        "G1 X60 Y0",
    ]
    slow = analyze_machining(lines, override_feedrate=600.0)
    fast = analyze_machining(lines, override_feedrate=1800.0)
    assert fast.cutting_time_seconds < slow.cutting_time_seconds


def test_machining_stats_use_utils_step_formatter() -> None:
    lines = [
        "G1 Z-1 F1000",
        "G1 X10",
        "G1 Z-2",
        "G1 X20",
    ]
    stats = analyze_machining(lines)
    assert stats.step_z_info == format_step_z_info(stats.unique_z_levels)


def test_analyze_machining_reports_required_material_size() -> None:
    lines = [
        "G0 X0 Y0 Z5",
        "G1 Z-2 F1000",
        "G1 X40 Y10",
        "G1 Z5",
        "G0 X100 Y100",
    ]
    stats = analyze_machining(lines)
    assert stats.stock_bounds is not None
    # Rapids / Z retracts must not inflate the required stock box.
    assert stats.stock_bounds.size_x == pytest.approx(40.0)
    assert stats.stock_bounds.size_y == pytest.approx(10.0)
    assert stats.stock_bounds.size_z == pytest.approx(2.0)
    assert stats.stock_bounds.min_z == pytest.approx(-2.0)
    assert stats.stock_bounds.max_z == pytest.approx(0.0)
    assert "X: 40.00 mm" in stats.material_size_info
    assert "Y: 10.00 mm" in stats.material_size_info
    assert "Z: 2.00 mm" in stats.material_size_info
