from __future__ import annotations

import numpy as np

import gcode_viewer.numpy_compat  # noqa: F401


def test_numpy_product_alias_available() -> None:
    assert hasattr(np, "product")
    assert np.product([2, 3]) == 6
    assert np.product((4, 5, 1)) == 20
