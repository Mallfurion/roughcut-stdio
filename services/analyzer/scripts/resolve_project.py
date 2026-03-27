#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.service import load_project_with_override_file  # noqa: E402


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        sys.stderr.write("usage: resolve_project.py <project-json> [override-json]\n")
        return 1

    project_path = Path(sys.argv[1]).resolve()
    override_path = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else None
    project = load_project_with_override_file(project_path, override_path)
    sys.stdout.write(json.dumps(project.to_dict()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
