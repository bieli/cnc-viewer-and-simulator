from __future__ import annotations

import json
from pathlib import Path

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.config.mapper import SettingsMapper
from gcode_viewer.config.settings import MachineBed, Settings, Workspace


def test_settings_roundtrip() -> None:
    settings = Settings(
        workspace=Workspace(machine_bed=MachineBed(300.0, 200.0, 80.0))
    )
    payload = SettingsMapper.settings_to_json(settings)
    restored = SettingsMapper.json_to_settings(payload)
    assert restored.workspace.machine_bed.width_x == 300.0
    assert restored.environment.printer.bed_depth_y == 200.0
    assert restored.workspace.machine_bed.height_z == 80.0


def test_float_to_settings() -> None:
    settings = SettingsMapper.float_to_settings([100.0, 150.0, 60.0])
    assert settings.workspace.machine_bed.width_x == 100.0
    assert settings.workspace.machine_bed.depth_y == 150.0
    assert settings.workspace.machine_bed.height_z == 60.0


def test_file_handler_reads_and_writes(tmp_path: Path) -> None:
    resources = tmp_path / "resources"
    icons = resources / "icons"
    settings_dir = resources / "settings"
    icons.mkdir(parents=True)
    settings_dir.mkdir(parents=True)
    settings_file = settings_dir / "settings_file.json"
    settings_file.write_text(
        json.dumps(
            {
                "environment": {
                    "printer": {
                        "bed_width_x": 220.0,
                        "bed_depth_y": 220.0,
                        "height_z": 50.0,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    handler = FileHandler(resources_root=resources)
    loaded = handler.read_settings()
    assert loaded.workspace.machine_bed.width_x == 220.0

    loaded.workspace.machine_bed.width_x = 330.0
    handler.settings_to_file(loaded)
    reloaded = handler.read_settings()
    assert reloaded.workspace.machine_bed.width_x == 330.0


def test_read_gcode_file(sample_freecad_nc: Path, tmp_path: Path) -> None:
    handler = FileHandler(resources_root=tmp_path)
    lines = handler.read_gcode_file(sample_freecad_nc)
    assert lines
    assert any(line.text.startswith("G1") for line in lines)
    assert all(line.number >= 1 for line in lines)
