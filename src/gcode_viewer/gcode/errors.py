from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class GCodeValidationIssue:
    reason: str
    line_number: Optional[int] = None
    line_text: Optional[str] = None
    severity: str = "warning"

    def __str__(self) -> str:
        if self.line_number is not None:
            message = f"Line {self.line_number}: {self.reason}"
        else:
            message = self.reason
        if self.line_text:
            message = f"{message}\n  {self.line_text}"
        return message


@dataclass
class GCodeValidationError(Exception):
    reason: str
    line_number: Optional[int] = None
    line_text: Optional[str] = None
    file_path: Optional[str] = None

    def __str__(self) -> str:
        parts: list[str] = []
        if self.file_path:
            parts.append(f"File: {self.file_path}")
        if self.line_number is not None:
            parts.append(f"Line {self.line_number}: {self.reason}")
        else:
            parts.append(self.reason)
        if self.line_text:
            parts.append(f"  {self.line_text}")
        return "\n".join(parts)


def format_validation_issues(
    issues: Sequence[GCodeValidationIssue],
    file_path: Optional[str] = None,
    max_examples: int = 5,
) -> str:
    if not issues:
        return ""

    parts: list[str] = []
    if file_path:
        parts.append(f"File: {file_path}")

    parts.append(
        "This G-code can be previewed, but feed values look invalid "
        "(common with some FreeCAD Adaptive/clearance posts when HorizFeed/"
        "VertFeed is unset)."
    )
    parts.append("")
    parts.append(f"Found {len(issues)} issue(s). First examples:")
    for issue in issues[:max_examples]:
        parts.append(str(issue))
    if len(issues) > max_examples:
        parts.append(f"... and {len(issues) - max_examples} more")
    parts.append("")
    parts.append(
        "Tip: set a positive feed in the FreeCAD Tool Controller and re-export. "
        "Time estimate below may use a default feed until then."
    )
    return "\n".join(parts)
