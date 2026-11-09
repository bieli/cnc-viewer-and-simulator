from __future__ import annotations

from gcode_viewer.utils.geometry import Bounds3D
from gcode_viewer.utils.stock_octree import StockOctree, offset_bounds


def _point_in_solid(stock: StockOctree, x: float, y: float, z: float) -> bool:
    return stock.is_solid_at(x, y, z)


def test_stock_octree_carves_cylinder_and_builds_mesh() -> None:
    bounds = Bounds3D(0.0, 10.0, 0.0, 10.0, -5.0, 0.0)
    stock = StockOctree.from_stock(bounds, tool_diameter_mm=3.0, max_depth_cap=6)
    assert len(stock.collect_solid_leaves()) == 1
    assert _point_in_solid(stock, 5.0, 5.0, -1.0)

    changed = stock.carve_cylinder(5.0, 5.0, z_bottom=-1.0, z_top=0.0, radius=2.0)
    assert changed is True
    assert not _point_in_solid(stock, 5.0, 5.0, -0.5)
    assert _point_in_solid(stock, 5.0, 5.0, -3.0)

    mesh = stock.build_mesh()
    assert mesh.vertices.shape[0] > 0
    assert mesh.faces.shape[0] > 0


def test_carve_segment_clears_second_z_layer() -> None:
    """Lower step-down must remove material below the first pocket floor."""
    bounds = Bounds3D(0.0, 20.0, 0.0, 12.0, -4.0, 0.0)
    stock = StockOctree.from_stock(bounds, tool_diameter_mm=4.0, max_depth_cap=6)
    flute = bounds.size_z + 4.0

    # First layer at Z=-1
    stock.carve_segment((2.0, 6.0, -1.0), (18.0, 6.0, -1.0), radius=2.0, flute_height=flute)
    assert not _point_in_solid(stock, 10.0, 6.0, -0.5)
    assert _point_in_solid(stock, 10.0, 6.0, -2.5)

    # Second layer at Z=-2.5
    stock.carve_segment(
        (2.0, 6.0, -2.5), (18.0, 6.0, -2.5), radius=2.0, flute_height=flute
    )
    assert not _point_in_solid(stock, 10.0, 6.0, -2.5)
    # Outside tool corridor still solid
    assert _point_in_solid(stock, 10.0, 1.0, -2.5)


def test_mesh_hides_internal_faces_after_layered_carve() -> None:
    bounds = Bounds3D(0.0, 8.0, 0.0, 8.0, -3.0, 0.0)
    stock = StockOctree.from_stock(bounds, tool_diameter_mm=2.0, max_depth_cap=5)
    stock.carve_cylinder(4.0, 4.0, -1.0, 0.0, radius=1.5)
    stock.carve_cylinder(4.0, 4.0, -2.5, 0.0, radius=1.0)
    mesh = stock.build_mesh()
    assert mesh.faces.shape[0] > 0
    # Pocket center above tip should be empty; mesh should still exist around it.
    assert not stock.is_solid_at(4.0, 4.0, -0.5)
    assert not stock.is_solid_at(4.0, 4.0, -2.0)


def test_offset_bounds_shifts_xy_only() -> None:
    bounds = Bounds3D(1.0, 2.0, 3.0, 4.0, -5.0, 0.0)
    shifted = offset_bounds(bounds, 10.0, -2.0)
    assert shifted.min_x == 11.0
    assert shifted.max_x == 12.0
    assert shifted.min_y == 1.0
    assert shifted.max_y == 2.0
    assert shifted.min_z == -5.0
    assert shifted.max_z == 0.0


def test_reset_restores_solid_root() -> None:
    bounds = Bounds3D(0.0, 4.0, 0.0, 4.0, -2.0, 0.0)
    stock = StockOctree.from_stock(bounds, tool_diameter_mm=2.0, max_depth_cap=5)
    stock.carve_cylinder(2.0, 2.0, -1.0, 0.0, 1.5)
    assert len(stock.collect_solid_leaves()) > 1
    stock.reset()
    leaves = stock.collect_solid_leaves()
    assert len(leaves) == 1
    assert leaves[0].solid is True
