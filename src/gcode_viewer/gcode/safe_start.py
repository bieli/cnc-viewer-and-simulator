from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from gcode_viewer.gcode.analysis import MachiningStats, analyze_machining
from gcode_viewer.gcode.words import (
    extract_motion_command,
    extract_xyz,
    tokenize,
)
from gcode_viewer.utils.geometry import Bounds3D

SAFE_START_MARKER = (
    "(CNC Viewer: safe start at left-near corner + clearance above stock)"
)
SAFE_START_MARKER_PREFIX = "(CNC Viewer: safe start"
_XY_WORD_RE = re.compile(r"([XY])([-+]?(?:\d+\.?\d*|\.\d+))", re.IGNORECASE)
_APPROACH_NOTE_RE = re.compile(
    r"approach X([-+]?(?:\d+\.?\d*|\.\d+)) Y([-+]?(?:\d+\.?\d*|\.\d+))",
    re.IGNORECASE,
)
_CLEARANCE_NOTE_RE = re.compile(
    r"Clearance Z([-+]?(?:\d+\.?\d*|\.\d+))",
    re.IGNORECASE,
)
_MAX_CUT_NOTE_RE = re.compile(
    r"max cut Z([-+]?(?:\d+\.?\d*|\.\d+))",
    re.IGNORECASE,
)
_ORIGIN_EPS = 1e-6
DEFAULT_CLEARANCE_MARGIN_MM = 5.0


@dataclass(frozen=True)
class SafeStartPose:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class SafeStartPlan:
    """Corner in pre-shift coords, stock top, clearance, and first cut XY."""

    corner_x: float
    corner_y: float
    max_cut_z: float
    clearance_z: float
    approach_x: float
    approach_y: float


def left_nearest_corner(bounds: Bounds3D) -> Tuple[float, float]:
    """Left edge of the stock box; pick the corner nearer to machine origin."""
    candidates = (
        (bounds.min_x, bounds.min_y),
        (bounds.min_x, bounds.max_y),
    )
    return min(candidates, key=lambda point: point[0] ** 2 + point[1] ** 2)


def compute_safe_start_pose(stats: MachiningStats) -> SafeStartPose:
    if stats.stock_bounds is None:
        raise ValueError("cannot compute safe start without a cutting envelope")
    corner_x, corner_y = left_nearest_corner(stats.stock_bounds)
    return SafeStartPose(
        x=corner_x,
        y=corner_y,
        z=stats.stock_bounds.max_z,
    )


def detect_rapid_clearance_z(lines: Sequence[str]) -> Optional[float]:
    """Highest Z reached by G0 moves (typical safe / link height)."""
    position_x = 0.0
    position_y = 0.0
    position_z = 0.0
    max_rapid_z: Optional[float] = None
    for line in lines:
        words = tokenize(line)
        command = extract_motion_command(words)
        if command is None:
            continue
        next_x, next_y, next_z = extract_xyz(
            words, position_x, position_y, position_z
        )
        if command == "G0":
            max_rapid_z = (
                next_z if max_rapid_z is None else max(max_rapid_z, next_z)
            )
        position_x, position_y, position_z = next_x, next_y, next_z
    return max_rapid_z


def choose_clearance_z(max_cut_z: float, lines: Sequence[str]) -> float:
    """Clearance must be above stock/cutting top so XY travel never skims material."""
    margin_clearance = max_cut_z + DEFAULT_CLEARANCE_MARGIN_MM
    rapid_clearance = detect_rapid_clearance_z(lines)
    if rapid_clearance is None:
        return margin_clearance
    return max(margin_clearance, rapid_clearance)


def find_first_cut_approach_xy(lines: Sequence[str]) -> Tuple[float, float]:
    """Modal XY at the first cutting move (G1/G2/G3) - the first process point."""
    position_x = 0.0
    position_y = 0.0
    position_z = 0.0
    for line in lines:
        words = tokenize(line)
        command = extract_motion_command(words)
        if command is None:
            continue
        next_x, next_y, next_z = extract_xyz(
            words, position_x, position_y, position_z
        )
        if command in {"G1", "G2", "G3"}:
            return position_x, position_y
        position_x, position_y, position_z = next_x, next_y, next_z
    return position_x, position_y


def _parse_stored_approach(lines: Sequence[str]) -> Optional[Tuple[float, float]]:
    for line in lines:
        match = _APPROACH_NOTE_RE.search(line)
        if match:
            return float(match.group(1)), float(match.group(2))
    return None


def _parse_stored_clearance(lines: Sequence[str]) -> Optional[float]:
    for line in lines:
        match = _CLEARANCE_NOTE_RE.search(line)
        if match:
            return float(match.group(1))
    return None


def _parse_stored_max_cut(lines: Sequence[str]) -> Optional[float]:
    for line in lines:
        match = _MAX_CUT_NOTE_RE.search(line)
        if match:
            return float(match.group(1))
    return None


def build_safe_start_plan(lines: Sequence[str]) -> SafeStartPlan:
    stored_approach = _parse_stored_approach(lines)
    stored_clearance = _parse_stored_clearance(lines)
    stored_max_cut = _parse_stored_max_cut(lines)
    cleaned = strip_existing_safe_start_block(lines)
    stats = analyze_machining(cleaned)
    if stats.stock_bounds is None:
        raise ValueError("cannot compute safe start without a cutting envelope")
    corner_x, corner_y = left_nearest_corner(stats.stock_bounds)
    max_cut_z = (
        stored_max_cut
        if stored_max_cut is not None
        else stats.stock_bounds.max_z
    )
    clearance_z = (
        stored_clearance
        if stored_clearance is not None
        else choose_clearance_z(max_cut_z, cleaned)
    )
    if stored_approach is not None:
        approach_x, approach_y = stored_approach
    else:
        approach_x, approach_y = find_first_cut_approach_xy(cleaned)
    return SafeStartPlan(
        corner_x=corner_x,
        corner_y=corner_y,
        max_cut_z=max_cut_z,
        clearance_z=clearance_z,
        approach_x=approach_x,
        approach_y=approach_y,
    )


def format_safe_start_block(plan: SafeStartPlan) -> List[str]:
    """
    After XY shift the corner is (0,0). Sequence:

    1. park on stock top at the corner (material height)
    2. raise to clearance
    3. rapid above stock to the first process XY
    """
    approach_x = plan.approach_x - plan.corner_x
    approach_y = plan.approach_y - plan.corner_y
    return [
        SAFE_START_MARKER,
        (
            f"(WCS shifted: left-near corner was "
            f"X{plan.corner_x:.6f} Y{plan.corner_y:.6f}; now X0 Y0)"
        ),
        (
            f"(Clearance Z{plan.clearance_z:.6f} above max cut "
            f"Z{plan.max_cut_z:.6f}; "
            f"approach X{approach_x:.6f} Y{approach_y:.6f})"
        ),
        # Explicit stock-top park so machine/sim start at material height.
        f"G0 X0.000000 Y0.000000 Z{plan.max_cut_z:.6f}",
        f"G0 Z{plan.clearance_z:.6f}",
        (
            f"G0 X{approach_x:.6f} Y{approach_y:.6f} "
            f"Z{plan.clearance_z:.6f}"
        ),
    ]


def _is_motion_line(line: str) -> bool:
    return extract_motion_command(tokenize(line)) is not None


def _is_safe_start_marker(line: str) -> bool:
    return line.strip().startswith(SAFE_START_MARKER_PREFIX)


def _is_wcs_shift_note(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("(WCS shifted:") or stripped.startswith(
        "(Clearance Z"
    )


def strip_existing_safe_start_block(lines: Sequence[str]) -> List[str]:
    """Remove our marker/notes and the injected lead-in G0 block (park/raise/travel)."""
    result: List[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not _is_safe_start_marker(line):
            result.append(line)
            index += 1
            continue
        index += 1
        while index < len(lines):
            candidate = lines[index].strip()
            if not candidate:
                index += 1
                continue
            if _is_wcs_shift_note(candidate):
                index += 1
                continue
            words = tokenize(candidate)
            command = extract_motion_command(words)
            if command == "G0":
                index += 1
                continue
            break
    return result


def strip_leading_rapids_before_first_cut(lines: Sequence[str]) -> List[str]:
    """Drop opening G0 approach moves; keep header + from first cut onward."""
    first_cut_index: Optional[int] = None
    for index, line in enumerate(lines):
        words = tokenize(line)
        command = extract_motion_command(words)
        if command in {"G1", "G2", "G3"}:
            first_cut_index = index
            break
    if first_cut_index is None:
        return list(lines)

    kept: List[str] = []
    for index, line in enumerate(lines):
        if index >= first_cut_index:
            kept.append(line)
            continue
        words = tokenize(line)
        command = extract_motion_command(words)
        if command == "G0":
            continue
        kept.append(line)
    return kept


def shift_xy_words(line: str, delta_x: float, delta_y: float) -> str:
    """Translate absolute X/Y words. I/J stay relative and are untouched."""

    def replacer(match: re.Match[str]) -> str:
        axis = match.group(1).upper()
        value = float(match.group(2))
        if axis == "X":
            value += delta_x
        else:
            value += delta_y
        return f"{axis}{value:.6f}"

    if abs(delta_x) <= _ORIGIN_EPS and abs(delta_y) <= _ORIGIN_EPS:
        return line
    if line.lstrip().startswith("(") or line.lstrip().startswith(";"):
        return line
    return _XY_WORD_RE.sub(replacer, line)


def shift_gcode_xy(lines: Sequence[str], delta_x: float, delta_y: float) -> List[str]:
    return [shift_xy_words(line, delta_x, delta_y) for line in lines]


def inject_safe_start_lines(lines: Sequence[str], plan: SafeStartPlan) -> List[str]:
    """
    Corner becomes (0,0). Start parked on stock top, raise, travel above stock
    to the first process XY, then continue with original cutting moves.
    """
    cleaned = strip_existing_safe_start_block(lines)
    without_old_approach = strip_leading_rapids_before_first_cut(cleaned)
    shifted = shift_gcode_xy(
        without_old_approach, -plan.corner_x, -plan.corner_y
    )
    # After a previous shift, corner is already ~0; keep stored approach absolute
    # in post-shift coordinates (comments store approach after shift).
    block_plan = plan
    if abs(plan.corner_x) <= _ORIGIN_EPS and abs(plan.corner_y) <= _ORIGIN_EPS:
        block_plan = SafeStartPlan(
            corner_x=0.0,
            corner_y=0.0,
            max_cut_z=plan.max_cut_z,
            clearance_z=plan.clearance_z,
            approach_x=plan.approach_x,
            approach_y=plan.approach_y,
        )
    block = format_safe_start_block(block_plan)
    insert_at = 0
    for index, line in enumerate(shifted):
        if _is_motion_line(line):
            insert_at = index
            break
        insert_at = index + 1
    return shifted[:insert_at] + block + shifted[insert_at:]


def rewrite_gcode_safe_start(gcode_text: str) -> Tuple[str, SafeStartPose]:
    newline = "\r\n" if "\r\n" in gcode_text else "\n"
    raw_lines = gcode_text.splitlines()
    plan = build_safe_start_plan(raw_lines)
    rewritten = inject_safe_start_lines(raw_lines, plan)
    body = newline.join(rewritten)
    if gcode_text.endswith(("\n", "\r\n")):
        body += newline
    # Idle / machine start: corner on stock top (material height).
    return body, SafeStartPose(x=0.0, y=0.0, z=plan.max_cut_z)


def backup_path_for(gcode_path: str) -> str:
    return f"{gcode_path}.bak"
