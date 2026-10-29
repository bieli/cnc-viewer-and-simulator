from __future__ import annotations

from pathlib import Path

import pytest

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.gcode.analysis import analyze_machining
from gcode_viewer.gcode.errors import GCodeValidationError
from gcode_viewer.gcode.line import GCodeLine
from gcode_viewer.gcode.parser import LayerParser


def test_zero_feedrate_is_warning_with_line_number_and_still_analyzes(
    tmp_path: Path,
) -> None:
    nc_path = tmp_path / "bad_feed.nc"
    nc_path.write_text(
        "\n".join(
            [
                "(header)",
                "",
                "G0 Z5",
                "G1 F0.000000 X10 Y0 Z-1",
                "G1 X20",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    lines = FileHandler(resources_root=tmp_path).read_gcode_file(nc_path)
    stats = analyze_machining(lines)

    assert stats.warnings
    assert stats.warnings[0].line_number == 4
    assert stats.warnings[0].line_text == "G1 F0.000000 X10 Y0 Z-1"
    assert "non-positive feedrate" in stats.warnings[0].reason
    assert stats.used_default_cut_feedrate
    assert stats.cutting_time_seconds > 0


def test_parser_loads_despite_zero_feed_and_keeps_warnings() -> None:
    lines = [
        GCodeLine(7, "G0 F0.000000 Z24.000000"),
        GCodeLine(8, "G1 F0.000000 X1 Y0"),
    ]
    parser = LayerParser()
    layers = parser.parse_layer_list(lines)
    assert layers
    assert parser.warnings
    assert parser.warnings[0].line_number == 7


def test_negative_feedrate_word_is_warned_not_fatal() -> None:
    stats = analyze_machining(["G1 F-100 X10"])
    assert stats.warnings[0].line_number == 1
    assert "F-100" in (stats.warnings[0].line_text or "")


def test_override_feedrate_must_be_positive() -> None:
    with pytest.raises(GCodeValidationError) as exc_info:
        analyze_machining(["G1 X10 F1000"], override_feedrate=0.0)
    assert "override feedrate" in exc_info.value.reason


def test_many_invalid_feeds_are_summarized() -> None:
    lines = [f"G1 F0 X{index}" for index in range(20)]
    stats = analyze_machining(lines)
    assert len(stats.warnings) == 6
    assert "more non-positive F values" in stats.warnings[-1].reason


def test_read_gcode_file_preserves_blank_line_numbering(tmp_path: Path) -> None:
    path = tmp_path / "spaced.nc"
    path.write_text("(a)\n\nG0 X0\n\nG1 F1000 X1\n", encoding="utf-8")
    lines = FileHandler(resources_root=tmp_path).read_gcode_file(path)
    assert [line.number for line in lines] == [1, 3, 5]
    assert lines[1].text == "G0 X0"
