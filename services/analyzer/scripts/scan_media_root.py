#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.analyzer.app.service import scan_and_analyze_media_root  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        sys.stderr.write("usage: scan_media_root.py <project-name> <media-root> [story-prompt]\n")
        return 1

    project_name = sys.argv[1]
    media_root = sys.argv[2]
    story_prompt = sys.argv[3] if len(sys.argv) > 3 else "Build a coherent rough cut."

    project = scan_and_analyze_media_root(
        project_name=project_name,
        media_roots=[media_root],
        story_prompt=story_prompt,
    )
    sys.stdout.write(__import__("json").dumps(project.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
