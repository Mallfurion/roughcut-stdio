#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.service import export_project_fcpxml  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: export_fcpxml.py <project-json>\n")
        return 1

    project_path = Path(sys.argv[1]).resolve()
    sys.stdout.write(export_project_fcpxml(project_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
