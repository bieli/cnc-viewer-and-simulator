from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class StepDepthStats:
    levels: Tuple[float, ...]
    step_counts: Dict[float, int]

    @property
    def is_single_layer(self) -> bool:
        return len(self.levels) <= 1 or self.total_steps == 0

    @property
    def total_steps(self) -> int:
        return sum(self.step_counts.values())

    def percentages(self) -> Dict[float, float]:
        total = self.total_steps
        if total == 0:
            return {}
        return {
            step: (count / total) * 100.0
            for step, count in self.step_counts.items()
        }


def analyze_z_steps(
    unique_z_levels: Iterable[float],
    min_step: float = 0.001,
    precision: int = 3,
) -> StepDepthStats:
    """Histogram of consecutive Z step-downs from FreeCAD/CAM layer depths."""
    levels = tuple(sorted(set(unique_z_levels), reverse=True))
    if len(levels) <= 1:
        return StepDepthStats(levels=levels, step_counts={})

    step_counts: Counter[float] = Counter()
    for index in range(len(levels) - 1):
        step = round(abs(levels[index] - levels[index + 1]), precision)
        if step > min_step:
            step_counts[step] += 1

    return StepDepthStats(levels=levels, step_counts=dict(step_counts))


def format_step_z_info(unique_z_levels: Iterable[float]) -> str:
    stats = analyze_z_steps(unique_z_levels)
    if stats.is_single_layer:
        return "Step Z: A single working layer"

    lines: List[str] = []
    percentages = stats.percentages()
    for step in sorted(percentages.keys(), reverse=True):
        lines.append(f"Step {step:.3f}mm: {percentages[step]:.1f}%")
    return "\n".join(lines)
