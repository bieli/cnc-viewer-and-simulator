from __future__ import annotations


def travel_time_seconds(distance_mm: float, feedrate_mm_min: float) -> float:
    """Convert path length and feed (mm/min) into seconds of motion."""
    if distance_mm <= 0:
        return 0.0
    if feedrate_mm_min <= 0:
        raise ValueError("feedrate_mm_min must be positive")
    return (distance_mm / feedrate_mm_min) * 60.0


def format_duration(total_seconds: float) -> str:
    clamped = max(0.0, total_seconds)
    hours = int(clamped // 3600)
    minutes = int((clamped % 3600) // 60)
    seconds = int(clamped % 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
