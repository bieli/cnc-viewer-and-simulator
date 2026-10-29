from __future__ import annotations

import pytest

from gcode_viewer.utils.step_depth import analyze_z_steps, format_step_z_info


def test_analyze_z_steps_single_layer() -> None:
    stats = analyze_z_steps({-1.0})
    assert stats.is_single_layer
    assert stats.step_counts == {}
    assert format_step_z_info({-1.0}) == "Step Z: A single working layer"


def test_analyze_z_steps_uniform_histogram() -> None:
    stats = analyze_z_steps({-1.0, -2.0, -3.0})
    assert not stats.is_single_layer
    assert stats.step_counts == {1.0: 2}
    assert stats.percentages()[1.0] == 100.0
    assert "Step 1.000mm: 100.0%" in format_step_z_info(stats.levels)


def test_analyze_z_steps_mixed_depths() -> None:
    stats = analyze_z_steps({0.0, -0.5, -1.5, -2.5})
    assert stats.step_counts[0.5] == 1
    assert stats.step_counts[1.0] == 2
    percentages = stats.percentages()
    assert percentages[0.5] == pytest.approx(100.0 / 3.0)
    assert percentages[1.0] == pytest.approx(200.0 / 3.0)


def test_format_step_z_info_orders_largest_step_first() -> None:
    text = format_step_z_info({0.0, -0.5, -1.5})
    lines = text.splitlines()
    assert lines[0].startswith("Step 1.000mm")
    assert lines[1].startswith("Step 0.500mm")
