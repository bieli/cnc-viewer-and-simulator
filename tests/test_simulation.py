from __future__ import annotations

from gcode_viewer.gcode.layer import Layer
from gcode_viewer.utils.simulation import (
    SimSegment,
    ToolpathSimulator,
    build_simulation_segments,
)


def test_build_simulation_segments_skips_zero_length() -> None:
    layer = Layer(
        x_data=[(0.0, 10.0), (10.0, 10.0)],
        y_data=[(0.0, 0.0), (0.0, 0.0)],
        z_data=[(0.0, 0.0), (0.0, 0.0)],
        matplot_color=["g", "r"],
        move_data=["G1 X10 F1200", "G0 X10"],
    )
    segments = build_simulation_segments([layer], offset_x=1.0, offset_y=2.0)
    assert len(segments) == 1
    assert segments[0].start == (1.0, 2.0, 0.0)
    assert segments[0].end == (11.0, 2.0, 0.0)
    assert segments[0].is_rapid is False
    assert segments[0].file_feedrate_mm_min == 1200.0


def test_simulator_step_forward_and_backward() -> None:
    segments = [
        SimSegment((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), False, 1000.0),
        SimSegment((10.0, 0.0, 0.0), (10.0, 10.0, 0.0), True, None),
    ]
    sim = ToolpathSimulator(segments=segments)
    assert sim.current_position() == (0.0, 0.0, 0.0)
    assert sim.step_forward()
    assert sim.current_position() == (10.0, 0.0, 0.0)
    assert sim.step_forward()
    assert sim.current_position() == (10.0, 10.0, 0.0)
    assert sim.step_backward()
    assert sim.segment_index == 1
    assert sim.progress == 0.0
    assert sim.current_position() == (10.0, 0.0, 0.0)
    assert sim.step_backward()
    assert sim.segment_index == 0
    assert sim.current_position() == (0.0, 0.0, 0.0)


def test_simulator_advance_uses_override_feedrate() -> None:
    segments = [
        SimSegment((0.0, 0.0, 0.0), (60.0, 0.0, 0.0), False, 600.0),
    ]
    slow = ToolpathSimulator(
        segments=list(segments),
        override_cut_feedrate_mm_min=600.0,
        speed_multiplier=1.0,
    )
    fast = ToolpathSimulator(
        segments=list(segments),
        override_cut_feedrate_mm_min=1800.0,
        speed_multiplier=1.0,
    )
    slow.advance(1.0)
    fast.advance(1.0)
    assert fast.progress > slow.progress


def test_simulator_reset_and_jump_to_end() -> None:
    segments = [
        SimSegment((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), False, 1000.0),
        SimSegment((1.0, 0.0, 0.0), (2.0, 0.0, 0.0), False, 1000.0),
    ]
    sim = ToolpathSimulator(segments=segments)
    sim.jump_to_end()
    assert sim.is_finished
    assert sim.current_position() == (2.0, 0.0, 0.0)
    sim.reset()
    assert sim.is_before_first_move
    assert sim.current_position() == (0.0, 0.0, 0.0)
    sim.go_to_safe_start()
    assert sim.is_at_start
    # Idle at the beginning of the first move (stock-top / pre-raise), not mid-air.
    assert sim.current_position() == (0.0, 0.0, 0.0)
