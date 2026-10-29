from __future__ import annotations

from typing import Any, Optional, Protocol

from PyQt5.QtWidgets import QAction, QMenuBar

from gcode_viewer.config.file_handler import FileHandler
from gcode_viewer.config.settings import Settings
from gcode_viewer.gui.menu_bar.change_environment_window import ChangeEnvironmentWindow


class SettingsObserver(Protocol):
    def on_menu_event(
        self,
        event_type: str,
        payload: Any,
        unused: Optional[Any] = None,
    ) -> None:
        ...


class MenuBar(QMenuBar):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.observer: Optional[SettingsObserver] = None
        self.file_handler = FileHandler()
        self._init_ui()

    def _init_ui(self) -> None:
        settings_menu = self.addMenu("Settings")
        assert settings_menu is not None
        change_settings_action = QAction("Change the Settings", self)
        settings_menu.addAction(change_settings_action)
        change_settings_action.triggered.connect(self.change_settings_action)

    def change_settings_action(self) -> None:
        changed_settings = ChangeEnvironmentWindow.change_environment(self.settings)
        self.notify_observer("new_settings", changed_settings)

    def notify_observer(
        self,
        event_type: str,
        payload: Any,
        unused: Optional[Any] = None,
    ) -> None:
        if self.observer is not None:
            self.observer.on_menu_event(event_type, payload, unused)
