from __future__ import annotations

import pytest

from gcode_viewer.utils.endmill_mesh import build_endmill_mesh, mesh_as_arrays


def test_build_endmill_mesh_topology() -> None:
    sides = 16
    mesh = build_endmill_mesh(sides=sides)
    assert mesh.vertex_count == 1 + sides + sides + 1
    assert mesh.face_count == sides + (2 * sides) + sides
    assert mesh.vertices[0] == (0.0, 0.0, 0.0)
    tip_z = mesh.vertices[0][2]
    top_z = mesh.vertices[-1][2]
    assert tip_z == 0.0
    assert top_z == pytest.approx(16.0)


def test_mesh_as_arrays_roundtrip_shape() -> None:
    mesh = build_endmill_mesh(sides=8)
    vertices, faces = mesh_as_arrays(mesh)
    assert len(vertices) == mesh.vertex_count
    assert len(faces) == mesh.face_count
    assert all(len(face) == 3 for face in faces)
    assert max(index for face in faces for index in face) == mesh.vertex_count - 1


def test_build_endmill_mesh_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        build_endmill_mesh(sides=2)
    with pytest.raises(ValueError):
        build_endmill_mesh(radius=0.0)
