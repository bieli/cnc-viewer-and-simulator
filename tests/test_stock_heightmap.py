from __future__ import annotations

import pytest

from gcode_viewer.utils.geometry import Bounds3D
from gcode_viewer.utils.stock_heightmap import StockHeightMap, choose_cell_mm


def test_choose_cell_respects_memory_budget() -> None:
    bounds = Bounds3D(0.0, 500.0, 0.0, 500.0, -10.0, 0.0)
    cell = choose_cell_mm(
        bounds,
        tool_diameter_mm=3.0,
        precise=True,
        max_bytes=64 * 1024 * 1024,
    )
    stock = StockHeightMap(bounds=bounds, cell_mm=cell)
    # Budget accounts for scratch; array itself is float32.
    assert stock.memory_bytes <= 64 * 1024 * 1024


def test_heightmap_carves_second_layer() -> None:
    bounds = Bounds3D(0.0, 20.0, 0.0, 10.0, -4.0, 0.0)
    stock = StockHeightMap.from_stock(bounds, tool_diameter_mm=4.0, precise=False)
    stock.carve_segment((2.0, 5.0, -1.0), (18.0, 5.0, -1.0), radius=2.0)
    mid = stock._world_to_index(10.0, 5.0)
    assert stock.heights[mid[1], mid[0]] == -1.0

    stock.carve_segment((2.0, 5.0, -2.5), (18.0, 5.0, -2.5), radius=2.0)
    assert stock.heights[mid[1], mid[0]] == -2.5

    outside = stock._world_to_index(10.0, 1.0)
    assert stock.heights[outside[1], outside[0]] == 0.0


def test_heightmap_build_mesh_nonempty() -> None:
    bounds = Bounds3D(0.0, 12.0, 0.0, 8.0, -3.0, 0.0)
    stock = StockHeightMap.from_stock(bounds, tool_diameter_mm=3.0, precise=True)
    stock.carve_disk(6.0, 4.0, -1.5, radius=2.0)
    mesh = stock.build_mesh()
    assert mesh.vertices.shape[0] > 0
    assert mesh.faces.shape[0] > 0


def test_precise_cell_finer_than_fast() -> None:
    bounds = Bounds3D(0.0, 40.0, 0.0, 20.0, -5.0, 0.0)
    fast = choose_cell_mm(bounds, 6.0, precise=False)
    precise = choose_cell_mm(bounds, 6.0, precise=True)
    assert precise == pytest.approx(0.05)
    assert precise < fast
