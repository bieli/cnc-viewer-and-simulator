from __future__ import annotations

from gcode_viewer.gcode.words import (
    extract_feedrate,
    extract_spindle,
    extract_tool_name_from_comment,
    extract_xyz,
    is_comment_line,
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
