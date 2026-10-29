from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Union


@dataclass(frozen=True)
class GCodeLine:
    number: int
    text: str


GCodeSource = Union[str, GCodeLine]


def normalize_gcode_lines(lines: Sequence[GCodeSource]) -> List[GCodeLine]:
    normalized: List[GCodeLine] = []
    for index, item in enumerate(lines, start=1):
        if isinstance(item, GCodeLine):
            text = item.text.strip()
            if not text:
                continue
            normalized.append(GCodeLine(number=item.number, text=text))
            continue
        text = item.strip()
        if text:
            normalized.append(GCodeLine(number=index, text=text))
    return normalized
