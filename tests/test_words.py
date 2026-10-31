from __future__ import annotations

from gcode_viewer.gcode.words import (
    extract_feedrate,
    extract_motion_command,
    extract_spindle,
    extract_tool_name_from_comment,
    extract_xyz,
    is_comment_line,
    normalize_motion_command,
    tokenize,
)


def test_tokenize_ignores_comments() -> None:
    assert tokenize("(comment)") == []
    assert tokenize("G1 X10 Y20") == ["G1", "X10", "Y20"]


def test_is_comment_line() -> None:
    assert is_comment_line("(Begin operation)")
    assert is_comment_line("; note")
    assert not is_comment_line("G0 X1")


def test_extract_xyz_keeps_current_when_missing() -> None:
    assert extract_xyz(["G1", "X5"], 1.0, 2.0, 3.0) == (5.0, 2.0, 3.0)


def test_extract_feedrate_converts_large_values() -> None:
    assert extract_feedrate(["F120000"]) == 2000.0
    assert extract_feedrate(["F1200"]) == 1200.0


def test_extract_spindle() -> None:
    assert extract_spindle(["S12000"]) == 12000


def test_extract_tool_name_from_freecad_comment() -> None:
    assert extract_tool_name_from_comment("(TC: Endmill 6mm)") == "Endmill 6mm"


def test_extract_motion_command_skips_line_numbers() -> None:
    assert extract_motion_command(["N952", "G0", "X20.234", "Y5.079"]) == "G0"
    assert extract_motion_command(["N951", "G1", "Z5."]) == "G1"
    assert extract_motion_command(["N41", "G00", "X1", "Y2", "Z5"]) == "G0"
    assert extract_motion_command(["G2", "X1", "Y2", "I0", "J1"]) == "G2"
    assert extract_motion_command(["M3", "S10000"]) is None


def test_normalize_motion_command_aliases() -> None:
    assert normalize_motion_command("G01") == "G1"
    assert normalize_motion_command("g03") == "G3"
    assert normalize_motion_command("N10") is None
