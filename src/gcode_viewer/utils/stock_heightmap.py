from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from gcode_viewer.utils.geometry import Bounds3D, Point3D, distance_3d
from gcode_viewer.utils.stock_octree import StockMesh

Vertex = Tuple[float, float, float]
Face = Tuple[int, int, int]


def _estimate_cells(size_x: float, size_y: float, cell_mm: float) -> Tuple[int, int]:
    nx = max(2, int(math.ceil(size_x / max(cell_mm, 1e-6))) + 1)
    ny = max(2, int(math.ceil(size_y / max(cell_mm, 1e-6))) + 1)
    return nx, ny


def choose_cell_mm(
    bounds: Bounds3D,
    tool_diameter_mm: float,
    *,
    precise: bool,
    max_bytes: int = 8 * 1024**3,
) -> float:
    """
    Pick XY cell size for Fast/Precise.

    ``max_bytes`` caps height-array memory (default ~8 GiB of the 10 GiB budget,
    leaving headroom for meshes and the rest of the app).
    """
    if precise:
        # Target 0.05 mm XY resolution; may coarsen only if memory budget is hit.
        cell = 0.05
    else:
        cell = max(0.40, tool_diameter_mm / 4.0)

    size_x = max(bounds.size_x, 1e-6)
    size_y = max(bounds.size_y, 1e-6)
    # float32 heights + index scratch ~ 8 bytes/cell budgeted.
    bytes_per_cell = 8
    while True:
        nx, ny = _estimate_cells(size_x, size_y, cell)
        if nx * ny * bytes_per_cell <= max_bytes:
            return cell
        cell *= 1.2


@dataclass
class StockHeightMap:
    """
    3-axis stock as a Z height field (dexel / Z-map).

    Each XY sample stores the current top surface Z. Flat-endmill cuts lower that
    height inside the tool disk.
    """

    bounds: Bounds3D
    cell_mm: float
    nx: int = field(init=False)
    ny: int = field(init=False)
    heights: np.ndarray = field(init=False)
    _xs: np.ndarray = field(init=False, repr=False)
    _ys: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.cell_mm <= 0:
            raise ValueError("cell_mm must be positive")
        size_x = max(self.bounds.size_x, self.cell_mm)
        size_y = max(self.bounds.size_y, self.cell_mm)
        self.nx, self.ny = _estimate_cells(size_x, size_y, self.cell_mm)
        self._xs = np.linspace(
            self.bounds.min_x, self.bounds.max_x, self.nx, dtype=np.float64
        )
        self._ys = np.linspace(
            self.bounds.min_y, self.bounds.max_y, self.ny, dtype=np.float64
        )
        self.heights = np.full(
            (self.ny, self.nx), self.bounds.max_z, dtype=np.float32
        )

    @classmethod
    def from_stock(
        cls,
        bounds: Bounds3D,
        tool_diameter_mm: float,
        *,
        precise: bool,
        max_bytes: int = 8 * 1024**3,
    ) -> "StockHeightMap":
        cell = choose_cell_mm(
            bounds,
            tool_diameter_mm,
            precise=precise,
            max_bytes=max_bytes,
        )
        return cls(bounds=bounds, cell_mm=cell)

    @property
    def memory_bytes(self) -> int:
        return int(self.heights.nbytes)

    def reset(self) -> None:
        self.heights.fill(self.bounds.max_z)

    def _world_to_index(self, x: float, y: float) -> Tuple[int, int]:
        if self.nx <= 1 or self.ny <= 1:
            return 0, 0
        ix = int(
            round(
                (x - self.bounds.min_x)
                / max(self.bounds.size_x, 1e-9)
                * (self.nx - 1)
            )
        )
        iy = int(
            round(
                (y - self.bounds.min_y)
                / max(self.bounds.size_y, 1e-9)
                * (self.ny - 1)
            )
        )
        return (
            int(min(max(ix, 0), self.nx - 1)),
            int(min(max(iy, 0), self.ny - 1)),
        )

    def carve_disk(self, x: float, y: float, z_tip: float, radius: float) -> bool:
        if radius <= 0:
            return False
        z_cut = max(float(z_tip), self.bounds.min_z)
        if z_cut >= self.bounds.max_z - 1e-12:
            return False

        rad_cells = int(math.ceil(radius / self.cell_mm)) + 1
        cx, cy = self._world_to_index(x, y)
        x0 = max(0, cx - rad_cells)
        x1 = min(self.nx - 1, cx + rad_cells)
        y0 = max(0, cy - rad_cells)
        y1 = min(self.ny - 1, cy + rad_cells)
        if x0 > x1 or y0 > y1:
            return False

        xs = self._xs[x0 : x1 + 1]
        ys = self._ys[y0 : y1 + 1]
        dx = xs[np.newaxis, :] - x
        dy = ys[:, np.newaxis] - y
        mask = (dx * dx + dy * dy) <= (radius * radius)
        if not np.any(mask):
            return False
        region = self.heights[y0 : y1 + 1, x0 : x1 + 1]
        before = region[mask].copy()
        region[mask] = np.minimum(before, np.float32(z_cut))
        return bool(np.any(region[mask] < before - np.float32(1e-6)))

    def carve_segment(
        self,
        start: Point3D,
        end: Point3D,
        radius: float,
    ) -> bool:
        if radius <= 0:
            return False
        length = distance_3d(start, end)
        # Dense enough stamps to keep circular walls round.
        step = max(self.cell_mm * 0.45, radius * 0.25, 0.08)
        samples = max(1, int(math.ceil(length / step))) if length > 1e-9 else 0
        changed = False
        for index in range(samples + 1):
            t = index / samples if samples else 0.0
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            z = start[2] + (end[2] - start[2]) * t
            if self.carve_disk(x, y, z, radius):
                changed = True
        return changed

    def build_mesh(self) -> StockMesh:
        """Top surface + thin vertical creases on grid edges + skirt + bottom."""
        z_bottom = float(self.bounds.min_z)
        z = np.maximum(self.heights.astype(np.float64), z_bottom)
        if not np.any(self.heights > z_bottom + 1e-6):
            return StockMesh(
                vertices=np.zeros((0, 3), dtype=float),
                faces=np.zeros((0, 3), dtype=int),
            )

        xx, yy = np.meshgrid(self._xs, self._ys)
        grid_vertices = np.column_stack((xx.ravel(), yy.ravel(), z.ravel()))

        z00 = z[:-1, :-1]
        z10 = z[:-1, 1:]
        z01 = z[1:, :-1]
        z11 = z[1:, 1:]
        keep = (z00 + z10 + z01 + z11) > (4.0 * z_bottom + 1e-6)
        iy, ix = np.nonzero(keep)
        if iy.size:
            i00 = iy * self.nx + ix
            i10 = iy * self.nx + (ix + 1)
            i01 = (iy + 1) * self.nx + ix
            i11 = (iy + 1) * self.nx + (ix + 1)
            top_faces = np.vstack(
                (
                    np.column_stack((i00, i10, i11)),
                    np.column_stack((i00, i11, i01)),
                )
            )
        else:
            top_faces = np.zeros((0, 3), dtype=int)

        extra_vertices: List[np.ndarray] = []
        extra_faces: List[np.ndarray] = []
        base = int(grid_vertices.shape[0])

        def append_wall_quads(
            p0: np.ndarray,
            p1: np.ndarray,
            p2: np.ndarray,
            p3: np.ndarray,
        ) -> None:
            nonlocal base
            count = int(p0.shape[0])
            if count == 0:
                return
            block = np.stack((p0, p1, p2, p3), axis=1).reshape(-1, 3)
            extra_vertices.append(block)
            idx = (np.arange(count) * 4 + base).astype(int)
            extra_faces.append(
                np.vstack(
                    (
                        np.column_stack((idx, idx + 1, idx + 2)),
                        np.column_stack((idx, idx + 2, idx + 3)),
                    )
                )
            )
            base += count * 4

        # Thin vertical curtains along grid edges (no ±cell extrusion → no thick bars).
        dz_x = z[:, 1:] - z[:, :-1]
        mask_x = np.abs(dz_x) > 1e-5
        iy_x, ix_x = np.nonzero(mask_x)
        if iy_x.size:
            x0 = self._xs[ix_x]
            x1 = self._xs[ix_x + 1]
            y = self._ys[iy_x]
            z0 = z[iy_x, ix_x]
            z1 = z[iy_x, ix_x + 1]
            z_lo = np.minimum(z0, z1)
            z_hi = np.maximum(z0, z1)
            p0 = np.column_stack((x0, y, z_lo))
            p1 = np.column_stack((x1, y, z_lo))
            p2 = np.column_stack((x1, y, z_hi))
            p3 = np.column_stack((x0, y, z_hi))
            append_wall_quads(p0, p1, p2, p3)

        dz_y = z[1:, :] - z[:-1, :]
        mask_y = np.abs(dz_y) > 1e-5
        iy_y, ix_y = np.nonzero(mask_y)
        if iy_y.size:
            y0 = self._ys[iy_y]
            y1 = self._ys[iy_y + 1]
            x = self._xs[ix_y]
            z0 = z[iy_y, ix_y]
            z1 = z[iy_y + 1, ix_y]
            z_lo = np.minimum(z0, z1)
            z_hi = np.maximum(z0, z1)
            p0 = np.column_stack((x, y0, z_lo))
            p1 = np.column_stack((x, y1, z_lo))
            p2 = np.column_stack((x, y1, z_hi))
            p3 = np.column_stack((x, y0, z_hi))
            append_wall_quads(p0, p1, p2, p3)

        x_min, x_max = float(self._xs[0]), float(self._xs[-1])
        y_min, y_max = float(self._ys[0]), float(self._ys[-1])

        def skirt_strip(
            xs0: np.ndarray,
            ys0: np.ndarray,
            zs0: np.ndarray,
            xs1: np.ndarray,
            ys1: np.ndarray,
            zs1: np.ndarray,
            outward_bottom_first: bool,
        ) -> None:
            z0 = np.maximum(zs0, z_bottom)
            z1 = np.maximum(zs1, z_bottom)
            if outward_bottom_first:
                p0 = np.column_stack((xs0, ys0, np.full_like(z0, z_bottom)))
                p1 = np.column_stack((xs1, ys1, np.full_like(z1, z_bottom)))
                p2 = np.column_stack((xs1, ys1, z1))
                p3 = np.column_stack((xs0, ys0, z0))
            else:
                p0 = np.column_stack((xs0, ys0, z0))
                p1 = np.column_stack((xs1, ys1, z1))
                p2 = np.column_stack((xs1, ys1, np.full_like(z1, z_bottom)))
                p3 = np.column_stack((xs0, ys0, np.full_like(z0, z_bottom)))
            append_wall_quads(p0, p1, p2, p3)

        skirt_strip(
            self._xs[:-1],
            np.full(self.nx - 1, y_min),
            z[0, :-1],
            self._xs[1:],
            np.full(self.nx - 1, y_min),
            z[0, 1:],
            True,
        )
        skirt_strip(
            self._xs[:-1],
            np.full(self.nx - 1, y_max),
            z[-1, :-1],
            self._xs[1:],
            np.full(self.nx - 1, y_max),
            z[-1, 1:],
            False,
        )
        skirt_strip(
            np.full(self.ny - 1, x_min),
            self._ys[:-1],
            z[:-1, 0],
            np.full(self.ny - 1, x_min),
            self._ys[1:],
            z[1:, 0],
            True,
        )
        skirt_strip(
            np.full(self.ny - 1, x_max),
            self._ys[:-1],
            z[:-1, -1],
            np.full(self.ny - 1, x_max),
            self._ys[1:],
            z[1:, -1],
            False,
        )

        bottom = np.array(
            [
                [x_min, y_min, z_bottom],
                [x_min, y_max, z_bottom],
                [x_max, y_max, z_bottom],
                [x_max, y_min, z_bottom],
            ],
            dtype=float,
        )
        extra_vertices.append(bottom)
        idx = np.array(
            [base, base + 1, base + 2, base, base + 2, base + 3], dtype=int
        )
        extra_faces.append(idx.reshape(2, 3))

        parts = [grid_vertices]
        if extra_vertices:
            parts.append(np.vstack(extra_vertices))
        vertices = np.vstack(parts)
        face_parts = [top_faces] if top_faces.size else []
        face_parts.extend(extra_faces)
        faces = (
            np.vstack(face_parts) if face_parts else np.zeros((0, 3), dtype=int)
        )
        return StockMesh(vertices=vertices, faces=faces)
