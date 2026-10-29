from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from gcode_viewer.utils.feedrate import normalize_feedrate_mm_min


def strip_comments(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""
    if stripped.startswith("(") or stripped.startswith(";"):
        return ""
    return stripped


def is_comment_line(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and (stripped.startswith("(") or stripped.startswith(";"))


def tokenize(line: str) -> List[str]:
    cleaned = strip_comments(line)
    return cleaned.split() if cleaned else []


def parse_float_word(word: str, letter: str) -> Optional[float]:
    if not word.upper().startswith(letter.upper()):
        return None
    try:
        return float(word[1:])
    except ValueError:
        return None


def parse_int_word(word: str, letter: str) -> Optional[int]:
    value = parse_float_word(word, letter)
    if value is None:
        return None
    return int(value)


def extract_xyz(
    words: Iterable[str],
    current_x: float,
    current_y: float,
    current_z: float,
) -> Tuple[float, float, float]:
    next_x, next_y, next_z = current_x, current_y, current_z
    for word in words:
        upper = word.upper()
        if upper.startswith("X"):
            value = parse_float_word(word, "X")
            if value is not None:
                next_x = value
        elif upper.startswith("Y"):
            value = parse_float_word(word, "Y")
            if value is not None:
                next_y = value
        elif upper.startswith("Z"):
            value = parse_float_word(word, "Z")
            if value is not None:
                next_z = value
    return next_x, next_y, next_z


def extract_ij(words: Iterable[str]) -> Tuple[float, float]:
    i_val = 0.0
    j_val = 0.0
    for word in words:
        upper = word.upper()
        if upper.startswith("I"):
            value = parse_float_word(word, "I")
            if value is not None:
                i_val = value
        elif upper.startswith("J"):
            value = parse_float_word(word, "J")
            if value is not None:
                j_val = value
    return i_val, j_val


def extract_feedrate(words: Iterable[str]) -> Optional[float]:
    for word in words:
        if word.upper().startswith("F"):
            value = parse_float_word(word, "F")
            if value is None:
                continue
            return normalize_feedrate_mm_min(value)
    return None


def extract_spindle(words: Iterable[str]) -> Optional[int]:
    for word in words:
        if word.upper().startswith("S"):
            return parse_int_word(word, "S")
    return None


def extract_tool_name_from_comment(line: str) -> Optional[str]:
    stripped = line.strip()
    if not (stripped.startswith("(") and ("TC:" in stripped or "Endmill" in stripped or "Tool" in stripped)):
        return None
    text = (
        stripped.replace("(", "")
        .replace(")", "")
        .replace("Begin operation:", "")
        .replace("Finish operation:", "")
        .replace("Path:", "")
        .replace("TC:", "")
        .strip()
    )
    if not text:
        return None
    if "Default Tool" in text:
        text = text.replace("Default Tool", "Tool ")
    return text
