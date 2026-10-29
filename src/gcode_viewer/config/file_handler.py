from __future__ import annotations

import json
from pathlib import Path
from typing import List

from gcode_viewer.config.mapper import SettingsMapper
from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.line import GCodeLine


class FileHandler:
    def __init__(self, resources_root: Path | None = None) -> None:
        if resources_root is None:
            resources_root = Path(__file__).resolve().parents[1] / "resources"
        self.root = resources_root
        self.icon_path = self.root / "icons"
        self.settings_path = self.root / "settings"
        self.icon_ico_path = self.icon_path / "app_icon.ico"
        self.icon_png_path = self.icon_path / "app_icon.png"
        self.settings_file_path = self.settings_path / "settings_file.json"

    def read_gcode_file(self, file_path: str | Path) -> List[GCodeLine]:
        path = Path(file_path)
        lines: List[GCodeLine] = []
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for number, raw_line in enumerate(handle, start=1):
                text = raw_line.strip()
                if text:
                    lines.append(GCodeLine(number=number, text=text))
        return lines

    def read_settings(self) -> Settings:
        with self.settings_file_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return SettingsMapper.json_to_settings(payload)

    def settings_to_file(self, settings: Settings) -> None:
        payload = SettingsMapper.settings_to_json(settings)
        self.settings_path.mkdir(parents=True, exist_ok=True)
        with self.settings_file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
