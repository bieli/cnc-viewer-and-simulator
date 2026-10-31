from __future__ import annotations

from pathlib import Path

from gcode_viewer.gcode.parser import LayerParser


def test_split_into_layers_by_z_change() -> None:
    lines = [
        "G0 Z5",
        "G1 Z-1",
        "G1 X10",
        "G1 Z-2",
        "G1 X20",
    ]
    parser = LayerParser()
    layers = parser.split_into_layers(lines)
    assert len(layers) == 3


def test_parse_layer_list_from_fixture(sample_freecad_nc: Path) -> None:
    lines = sample_freecad_nc.read_text(encoding="utf-8").splitlines()
    parser = LayerParser()
    layers = parser.parse_layer_list(lines)

    assert len(layers) >= 2
    assert layers[0].tool_info.startswith("Tool: Endmill 6mm")
    assert layers[0].time_estimation.count(":") == 2
    assert any(layer.x_data for layer in layers)
    assert any("g" in layer.matplot_color for layer in layers)


def test_parse_linear_and_arc_moves() -> None:
    lines = [
        "G0 X0 Y0 Z-1",
        "G1 X10 Y0 Z-1 F1000",
        "G2 X10 Y10 I0 J5",
    ]
    parser = LayerParser()
    layers = parser.parse_layer_list(lines)
    assert len(layers) == 1
    assert len(layers[0].x_data) > 2


def test_parse_n_prefixed_retract_and_rapid_above_material() -> None:
    """CAMotics-style line numbers must not drop G1 Z retract / G0 link moves."""
    lines = [
        "G1 X10 Y10 Z-1",
        "N951 G1 Y10 Z5.",
        "N952 G0 X20 Y20",
        "N955 G1 Z0.",
        "G1 X21 Y20 Z-1",
    ]
    parser = LayerParser()
    layers = parser.parse_layer_list(lines)
    segments = [
        (color, z, move)
        for layer in layers
        for color, z, move in zip(
            layer.matplot_color, layer.z_data, layer.move_data, strict=True
        )
    ]
    assert any(color == "g" and max(z) >= 5.0 for color, z, _ in segments)
    assert any(color == "r" and min(z) >= 5.0 for color, z, _ in segments)
    assert any("G0" in move for _, _, move in segments)
