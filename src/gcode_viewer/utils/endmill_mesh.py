from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass(frozen=True)
class EndmillMesh:
    vertices: Tuple[Tuple[float, float, float], ...]
    faces: Tuple[Tuple[int, int, int], ...]

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)


def build_endmill_mesh(
    radius: float = 1.5,
    cylinder_height: float = 12.0,
    cone_height: float = 4.0,
    sides: int = 16,
) -> EndmillMesh:
    """Build a cone-tipped cylindrical endmill marker (tip at local Z=0)."""
    if sides < 3:
        raise ValueError("sides must be at least 3")
    if radius <= 0 or cylinder_height <= 0 or cone_height <= 0:
        raise ValueError("mesh dimensions must be positive")

    vertices: List[Tuple[float, float, float]] = [(0.0, 0.0, 0.0)]

    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append(
            (radius * math.cos(angle), radius * math.sin(angle), cone_height)
        )

    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append(
            (
                radius * math.cos(angle),
                radius * math.sin(angle),
                cone_height + cylinder_height,
            )
        )

    vertices.append((0.0, 0.0, cone_height + cylinder_height))

    faces: List[Tuple[int, int, int]] = []
    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append((0, index + 1, next_index + 1))

    for index in range(sides):
        next_index = (index + 1) % sides
        p1 = index + 1
        p2 = next_index + 1
        p3 = index + 1 + sides
        p4 = next_index + 1 + sides
        faces.append((p1, p2, p3))
        faces.append((p2, p4, p3))

    top_center_index = len(vertices) - 1
    for index in range(sides):
        next_index = (index + 1) % sides
        faces.append((top_center_index, index + 1 + sides, next_index + 1 + sides))

    return EndmillMesh(vertices=tuple(vertices), faces=tuple(faces))


def mesh_as_arrays(
    mesh: EndmillMesh,
) -> Tuple[Sequence[Sequence[float]], Sequence[Sequence[int]]]:
    return [list(vertex) for vertex in mesh.vertices], [list(face) for face in mesh.faces]
