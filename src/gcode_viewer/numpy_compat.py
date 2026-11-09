"""Restore NumPy APIs removed in 2.x that older pyqtgraph still calls."""

from __future__ import annotations

import numpy as np

# pyqtgraph<=0.12.4 uses np.product in GLMeshItem / functions; NumPy 2 removed it.
if not hasattr(np, "product"):
    np.product = np.prod  # type: ignore[attr-defined, assignment]
