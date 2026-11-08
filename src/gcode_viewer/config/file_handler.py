from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Tuple

from gcode_viewer.config.mapper import SettingsMapper
from gcode_viewer.config.settings import Settings
from gcode_viewer.gcode.line import GCodeLine
from gcode_viewer.gcode.safe_start import backup_path_for


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

    def read_gcode_text(self, file_path: str | Path) -> str:
        path = Path(file_path)
        return path.read_text(encoding="utf-8", errors="replace")

    def write_gcode_text(self, file_path: str | Path, text: str) -> None:
        path = Path(file_path)
        path.write_text(text, encoding="utf-8")

    def ensure_bak_copy(self, file_path: str | Path) -> Tuple[bool, Path]:
        """Copy ``file.nc`` → ``file.nc.bak`` only when the bak does not exist yet."""
        path = Path(file_path)
        bak_path = Path(backup_path_for(str(path)))
        if bak_path.exists():
            return False, bak_path
        shutil.copy2(path, bak_path)
        return True, bak_path

    def read_settings(self) -> Settings:
        with self.settings_file_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return SettingsMapper.json_to_settings(payload)

    def settings_to_file(self, settings: Settings) -> None:
        payload = SettingsMapper.settings_to_json(settings)
        self.settings_path.mkdir(parents=True, exist_ok=True)
        with self.settings_file_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle)
