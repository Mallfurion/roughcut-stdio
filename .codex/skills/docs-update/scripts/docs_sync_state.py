#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


DEFAULT_STATE_PATH = Path("docs/documentation-update-state.json")
DEFAULT_TRACKED_PATHS = ["README.md", "docs/**"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read or write the repo docs sync baseline state.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    show_parser = subparsers.add_parser("show", help="Print the current docs sync state as JSON.")
    show_parser.add_argument("--state", default=str(DEFAULT_STATE_PATH))

    write_parser = subparsers.add_parser("write", help="Write the docs sync baseline state.")
    write_parser.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    write_parser.add_argument("--commit", required=True)
    write_parser.add_argument("--repo-root", default=".")
    write_parser.add_argument(
        "--notes",
        default="Docs under docs/ plus the repo README are aligned through this implementation commit.",
    )

    return parser.parse_args()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {
            "schema_version": 1,
            "tracked_paths": list(DEFAULT_TRACKED_PATHS),
            "last_reviewed_commit": "",
            "updated_at_utc": "",
            "notes": "",
        }
    return json.loads(path.read_text(encoding="utf-8"))


def validate_commit(repo_root: Path, commit: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Invalid commit reference: {commit}")
    return result.stdout.strip()


def show_state(path: Path) -> int:
    payload = load_state(path)
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def write_state(path: Path, repo_root: Path, commit: str, notes: str) -> int:
    resolved_commit = validate_commit(repo_root, commit)
    payload = load_state(path)
    payload["schema_version"] = 1
    payload["tracked_paths"] = list(payload.get("tracked_paths") or DEFAULT_TRACKED_PATHS)
    payload["last_reviewed_commit"] = resolved_commit
    payload["updated_at_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    payload["notes"] = notes

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


def main() -> int:
    args = parse_args()
    state_path = Path(args.state)

    if args.command == "show":
        return show_state(state_path)
    if args.command == "write":
        return write_state(
            path=state_path,
            repo_root=Path(args.repo_root).resolve(),
            commit=args.commit,
            notes=args.notes,
        )
    raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
