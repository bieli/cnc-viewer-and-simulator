from __future__ import annotations

import sys
from typing import Optional

from gcode_viewer.application import Application


def main(argv: Optional[list[str]] = None) -> None:
    args = sys.argv if argv is None else argv
    file_argument = args[1] if len(args) > 1 else None
    Application(file_path=file_argument)


if __name__ == "__main__":
    main()
