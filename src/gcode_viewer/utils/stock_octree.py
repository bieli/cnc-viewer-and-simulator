from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from gcode_viewer.utils.geometry import Bounds3D, Point3D, distance_3d

Vertex = Tuple[float, float, float]
Face = Tuple[int, int, int]
ClipXY = Tuple[float, float, float, float]  # min_x, max_x, min_y, max_y (half-open)

# Child octant order: ---, +--, -+-, ++-, --+, +-+, -++, +++
_OCTANT_SIGNS = (
    (-1, -1, -1),
    (1, -1, -1),
    (-1, 1, -1),
    (1, 1, -1),
    (-1, -1, 1),
    (1, -1, 1),
    (-1, 1, 1),
    (1, 1, 1),
)


@dataclass
class OctreeNode:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float
    solid: bool = True
    children: Optional[List["OctreeNode"]] = None

    @property
    def is_leaf(self) -> bool:
        return self.children is None

    @property
    def center(self) -> Point3D:
        return (
            0.5 * (self.min_x + self.max_x),
            0.5 * (self.min_y + self.max_y),
            0.5 * (self.min_z + self.max_z),
        )

    @property
    def size(self) -> float:
        return max(
            self.max_x - self.min_x,
            self.max_y - self.min_y,
            self.max_z - self.min_z,
        )

    def subdivide(self) -> None:
        if self.children is not None:
            return
        cx, cy, cz = self.center
        kids: List[OctreeNode] = []
        for sx, sy, sz in _OCTANT_SIGNS:
            child_min_x = self.min_x if sx < 0 else cx
            child_max_x = cx if sx < 0 else self.max_x
            child_min_y = self.min_y if sy < 0 else cy
            child_max_y = cy if sy < 0 else self.max_y
            child_min_z = self.min_z if sz < 0 else cz
            child_max_z = cz if sz < 0 else self.max_z
            kids.append(
                OctreeNode(
                    child_min_x,
                    child_max_x,
                    child_min_y,
                    child_max_y,
                    child_min_z,
                    child_max_z,
                    solid=self.solid,
                )
            )
        self.children = kids
        self.solid = False


def _clamp(value: float, low: float, high: float) -> float:
    return low if value < low else high if value > high else value


def _child_index(x: float, y: float, z: float, node: OctreeNode) -> int:
    cx, cy, cz = node.center
    index = 0
    if x >= cx:
        index |= 1
    if y >= cy:
        index |= 2
    if z >= cz:
        index |= 4
    return index


def _vertical_cylinder_intersects_aabb(
    cx: float,
    cy: float,
    z_bottom: float,
    z_top: float,
    radius: float,
    node: OctreeNode,
) -> bool:
    if node.max_z < z_bottom or node.min_z > z_top:
        return False
    nearest_x = _clamp(cx, node.min_x, node.max_x)
    nearest_y = _clamp(cy, node.min_y, node.max_y)
    dx = cx - nearest_x
    dy = cy - nearest_y
    return (dx * dx + dy * dy) <= (radius * radius)


def _aabb_inside_vertical_cylinder(
    cx: float,
    cy: float,
    z_bottom: float,
    z_top: float,
    radius: float,
    node: OctreeNode,
) -> bool:
    if node.min_z < z_bottom - 1e-9 or node.max_z > z_top + 1e-9:
        return False
    r2 = radius * radius
    for x in (node.min_x, node.max_x):
        for y in (node.min_y, node.max_y):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy > r2:
                return False
    return True


@dataclass
class StockMesh:
    vertices: np.ndarray  # (N, 3)
    faces: np.ndarray  # (M, 3)


@dataclass
class StockOctree:
    """
    Sparse voxel octree for 3-axis stock removal visualization.

    Flat endmill carving uses a vertical cylinder (tool axis = Z) swept along
    cut moves. Mesh faces are emitted only where a solid leaf borders empty space,
    tested with point queries so mixed-resolution leaves stay consistent.
    """

    bounds: Bounds3D
    max_depth: int = 7
    root: OctreeNode = field(init=False)

    def __post_init__(self) -> None:
        if self.max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        self.root = OctreeNode(
            self.bounds.min_x,
            self.bounds.max_x,
            self.bounds.min_y,
            self.bounds.max_y,
            self.bounds.min_z,
            self.bounds.max_z,
            solid=True,
        )

    @classmethod
    def from_stock(
        cls,
        bounds: Bounds3D,
        tool_diameter_mm: float,
        max_depth_cap: int = 7,
        min_leaf_mm: float = 0.5,
        leaf_divisor: float = 4.0,
    ) -> "StockOctree":
        size = max(bounds.size_x, bounds.size_y, bounds.size_z, 1e-6)
        target_leaf = max(min_leaf_mm, tool_diameter_mm / max(leaf_divisor, 1.0))
        depth = 0
        while size / (2**depth) > target_leaf and depth < max_depth_cap:
            depth += 1
        return cls(bounds=bounds, max_depth=depth)

    @classmethod
    def from_stock_fast(
        cls,
        bounds: Bounds3D,
        tool_diameter_mm: float,
    ) -> "StockOctree":
        return cls.from_stock(
            bounds,
            tool_diameter_mm,
            max_depth_cap=6,
            min_leaf_mm=0.75,
            leaf_divisor=3.0,
        )

    @classmethod
    def from_stock_precise(
        cls,
        bounds: Bounds3D,
        tool_diameter_mm: float,
    ) -> "StockOctree":
        return cls.from_stock(
            bounds,
            tool_diameter_mm,
            max_depth_cap=9,
            min_leaf_mm=0.15,
            leaf_divisor=10.0,
        )

    def reset(self) -> None:
        self.root = OctreeNode(
            self.bounds.min_x,
            self.bounds.max_x,
            self.bounds.min_y,
            self.bounds.max_y,
            self.bounds.min_z,
            self.bounds.max_z,
            solid=True,
        )

    def is_solid_at(self, x: float, y: float, z: float) -> bool:
        if (
            x < self.root.min_x
            or x > self.root.max_x
            or y < self.root.min_y
            or y > self.root.max_y
            or z < self.root.min_z
            or z > self.root.max_z
        ):
            return False
        node = self.root
        while True:
            if node.is_leaf:
                return node.solid
            assert node.children is not None
            node = node.children[_child_index(x, y, z, node)]

    def carve_cylinder(
        self,
        x: float,
        y: float,
        z_bottom: float,
        z_top: float,
        radius: float,
    ) -> bool:
        if radius <= 0 or z_top < z_bottom:
            return False
        return self._carve_cylinder_node(self.root, x, y, z_bottom, z_top, radius, 0)

    def carve_segment(
        self,
        start: Point3D,
        end: Point3D,
        radius: float,
        flute_height: float,
    ) -> bool:
        """Carve a flat endmill: vertical cylinder swept along the tip path."""
        if radius <= 0 or flute_height <= 0:
            return False
        length = distance_3d(start, end)
        leaf = self.root.size / max(2**self.max_depth, 1)
        step = max(leaf * 0.65, radius * 0.45, 0.25)
        samples = max(1, int(math.ceil(length / step))) if length > 1e-9 else 0
        changed = False
        for index in range(samples + 1):
            t = index / samples if samples else 0.0
            x = start[0] + (end[0] - start[0]) * t
            y = start[1] + (end[1] - start[1]) * t
            z = start[2] + (end[2] - start[2]) * t
            if self.carve_cylinder(x, y, z, z + flute_height, radius):
                changed = True
        return changed

    def _carve_cylinder_node(
        self,
        node: OctreeNode,
        cx: float,
        cy: float,
        z_bottom: float,
        z_top: float,
        radius: float,
        depth: int,
    ) -> bool:
        if not _vertical_cylinder_intersects_aabb(
            cx, cy, z_bottom, z_top, radius, node
        ):
            return False

        if node.is_leaf and not node.solid:
            return False

        if _aabb_inside_vertical_cylinder(cx, cy, z_bottom, z_top, radius, node):
            node.children = None
            node.solid = False
            return True

        if node.is_leaf:
            if depth >= self.max_depth:
                node.solid = False
                return True
            node.subdivide()

        assert node.children is not None
        changed = False
        for child in node.children:
            if self._carve_cylinder_node(
                child, cx, cy, z_bottom, z_top, radius, depth + 1
            ):
                changed = True
        self._try_collapse(node)
        return changed

    def _try_collapse(self, node: OctreeNode) -> None:
        if node.children is None:
            return
        if all(child.is_leaf and not child.solid for child in node.children):
            node.children = None
            node.solid = False
            return
        if all(child.is_leaf and child.solid for child in node.children):
            node.children = None
            node.solid = True

    def collect_solid_leaves(self) -> List[OctreeNode]:
        leaves: List[OctreeNode] = []
        self._collect_solid(self.root, leaves)
        return leaves

    def _collect_solid(self, node: OctreeNode, out: List[OctreeNode]) -> None:
        if node.is_leaf:
            if node.solid:
                out.append(node)
            return
        assert node.children is not None
        for child in node.children:
            self._collect_solid(child, out)

    def build_mesh(self, clip_xy: Optional[ClipXY] = None) -> StockMesh:
        """Emit only faces of solid leaves that border empty space (point-tested)."""
        solid_leaves = self.collect_solid_leaves()
        if not solid_leaves:
            return StockMesh(
                vertices=np.zeros((0, 3), dtype=float),
                faces=np.zeros((0, 3), dtype=int),
            )

        vertices: List[Vertex] = []
        faces: List[Face] = []

        def add_quad(
            p0: Vertex,
            p1: Vertex,
            p2: Vertex,
            p3: Vertex,
        ) -> None:
            base = len(vertices)
            vertices.extend((p0, p1, p2, p3))
            faces.append((base, base + 1, base + 2))
            faces.append((base, base + 2, base + 3))

        for leaf in solid_leaves:
            cx, cy, cz = leaf.center
            if clip_xy is not None:
                min_x, max_x, min_y, max_y = clip_xy
                if cx < min_x or cx >= max_x or cy < min_y or cy >= max_y:
                    continue
            x0, x1 = leaf.min_x, leaf.max_x
            y0, y1 = leaf.min_y, leaf.max_y
            z0, z1 = leaf.min_z, leaf.max_z
            # Probe just outside each face so mixed-resolution neighbors work.
            eps = max(1e-4, 1e-3 * leaf.size)

            if not self.is_solid_at(x0 - eps, cy, cz):
                add_quad((x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1))
            if not self.is_solid_at(x1 + eps, cy, cz):
                add_quad((x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0))
            if not self.is_solid_at(cx, y0 - eps, cz):
                add_quad((x0, y0, z0), (x0, y0, z1), (x1, y0, z1), (x1, y0, z0))
            if not self.is_solid_at(cx, y1 + eps, cz):
                add_quad((x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1))
            if not self.is_solid_at(cx, cy, z0 - eps):
                add_quad((x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0))
            if not self.is_solid_at(cx, cy, z1 + eps):
                add_quad((x0, y0, z1), (x0, y1, z1), (x1, y1, z1), (x1, y0, z1))

        if not vertices:
            return StockMesh(
                vertices=np.zeros((0, 3), dtype=float),
                faces=np.zeros((0, 3), dtype=int),
            )
        return StockMesh(
            vertices=np.array(vertices, dtype=float),
            faces=np.array(faces, dtype=int),
        )


def expand_bounds_for_tool(bounds: Bounds3D, tool_radius_mm: float) -> Bounds3D:
    pad = max(tool_radius_mm, 0.0)
    return Bounds3D(
        bounds.min_x - pad,
        bounds.max_x + pad,
        bounds.min_y - pad,
        bounds.max_y + pad,
        bounds.min_z,
        bounds.max_z,
    )


def offset_bounds(bounds: Bounds3D, offset_x: float, offset_y: float) -> Bounds3D:
    return Bounds3D(
        bounds.min_x + offset_x,
        bounds.max_x + offset_x,
        bounds.min_y + offset_y,
        bounds.max_y + offset_y,
        bounds.min_z,
        bounds.max_z,
    )
