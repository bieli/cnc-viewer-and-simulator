from __future__ import annotations


LARGE_FEEDRATE_THRESHOLD = 10_000.0


def normalize_feedrate_mm_min(raw_value: float) -> float:
    """Normalize post-processor feed quirks into mm/min.

    Some CAM exports emit feed values that are effectively mm/s scaled by 60
    twice (or mm/min * 60). Values above the threshold are treated as that
    inflated unit and converted down by /60, then truncated to int like the
    original CNC viewer heuristic.
    """
    value = raw_value
    if value > LARGE_FEEDRATE_THRESHOLD:
        value = value / 60.0
    return float(int(value))
