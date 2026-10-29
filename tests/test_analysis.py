from __future__ import annotations

from gcode_viewer.gcode.analysis import analyze_machining, format_step_z_info


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


def test_override_feedrate_changes_time() -> None:
    lines = [
        "G0 X0 Y0 Z5",
        "G1 Z-1 F600",
        "G1 X60 Y0",
    ]
    slow = analyze_machining(lines, override_feedrate=600.0)
    fast = analyze_machining(lines, override_feedrate=1800.0)
    assert fast.cutting_time_seconds < slow.cutting_time_seconds


def test_format_step_z_info_single_layer() -> None:
    assert format_step_z_info({-1.0}) == "Step Z: A single working layer"


def test_format_step_z_info_multiple_steps() -> None:
    info = format_step_z_info({-1.0, -2.0, -3.0})
    assert "Step 1.000mm" in info
