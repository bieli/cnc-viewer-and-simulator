from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MachineBed:
    width_x: float
    depth_y: float
    height_z: float

    @property
    def bed_width_x(self) -> float:
        return self.width_x

    @property
    def bed_depth_y(self) -> float:
        return self.depth_y


@dataclass
class Workspace:
    machine_bed: MachineBed

    @property
    def printer(self) -> MachineBed:
        return self.machine_bed


@dataclass
class Settings:
    workspace: Workspace

    @property
    def environment(self) -> Workspace:
        return self.workspace
