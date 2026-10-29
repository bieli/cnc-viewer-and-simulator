from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from gcode_viewer.config.settings import MachineBed, Settings, Workspace

SettingsDict = Dict[str, Any]


class SettingsMapper:
    @staticmethod
    def json_to_settings(payload: Mapping[str, Any]) -> Settings:
        environment = payload["environment"]
        printer = environment["printer"]
        machine_bed = MachineBed(
            width_x=float(printer["bed_width_x"]),
            depth_y=float(printer["bed_depth_y"]),
            height_z=float(printer["height_z"]),
        )
        return Settings(workspace=Workspace(machine_bed=machine_bed))

    @staticmethod
    def float_to_settings(values: Sequence[float]) -> Settings:
        if len(values) < 3:
            raise ValueError("Expected at least three dimension values")
        machine_bed = MachineBed(
            width_x=float(values[0]),
            depth_y=float(values[1]),
            height_z=float(values[2]),
        )
        return Settings(workspace=Workspace(machine_bed=machine_bed))

    @staticmethod
    def settings_to_json(settings: Settings) -> SettingsDict:
        bed = settings.workspace.machine_bed
        return {
            "environment": {
                "printer": {
                    "bed_width_x": bed.width_x,
                    "bed_depth_y": bed.depth_y,
                    "height_z": bed.height_z,
                }
            }
        }
