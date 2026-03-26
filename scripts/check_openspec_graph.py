#!/usr/bin/env python3

from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
CHANGES_DIR = ROOT / "openspec" / "changes"


class ChangeMeta:
    def __init__(
        self,
        *,
        name: str,
        schema: str = "",
        created: str = "",
        kind: str = "implementation",
        parent: str | None = None,
        phase: int | None = None,
        depends_on: list[str] | None = None,
    ) -> None:
        self.name = name
        self.schema = schema
        self.created = created
        self.kind = kind
        self.parent = parent
        self.phase = phase
        self.depends_on = depends_on or []


def parse_openspec_yaml(path: Path) -> ChangeMeta:
    lines = path.read_text(encoding="utf-8").splitlines()
    name = path.parent.name
    schema = ""
    created = ""
    kind = "implementation"
    parent: str | None = None
    phase: int | None = None
    depends_on: list[str] = []

    in_x_roughcut = False
    in_depends = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith(" "):
            in_x_roughcut = stripped == "x-roughcut:"
            in_depends = False
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                value = value.strip()
                if key == "schema":
                    schema = value
                elif key == "created":
                    created = value
            continue

        if not in_x_roughcut:
            continue

        indent = len(line) - len(line.lstrip(" "))
        if indent == 2:
            in_depends = False
            if stripped == "depends_on: []":
                depends_on = []
                continue
            if stripped == "depends_on:":
                depends_on = []
                in_depends = True
                continue
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            value = value.strip() or None
            if key == "kind" and value is not None:
                kind = value
            elif key == "parent":
                parent = value
            elif key == "phase" and value is not None:
                try:
                    phase = int(value)
                except ValueError:
                    raise ValueError(f"{path}: invalid phase value {value!r}") from None
            continue

        if in_depends and indent >= 4 and stripped.startswith("- "):
            depends_on.append(stripped[2:].strip())

    return ChangeMeta(
        name=name,
        schema=schema,
        created=created,
        kind=kind,
        parent=parent,
        phase=phase,
        depends_on=depends_on,
    )


def load_changes() -> dict[str, ChangeMeta]:
    changes: dict[str, ChangeMeta] = {}
    for path in sorted(CHANGES_DIR.glob("*/.openspec.yaml")):
        meta = parse_openspec_yaml(path)
        changes[meta.name] = meta
    return changes


def validate(changes: dict[str, ChangeMeta]) -> tuple[list[str], dict[str, list[str]]]:
    errors: list[str] = []
    blocks: dict[str, list[str]] = defaultdict(list)

    for name, meta in changes.items():
        if meta.kind not in {"umbrella", "implementation"}:
            errors.append(f"{name}: x-roughcut.kind must be 'umbrella' or 'implementation'")

        if meta.kind == "umbrella" and meta.parent:
            errors.append(f"{name}: umbrella changes must not declare x-roughcut.parent")

        if meta.kind == "implementation" and meta.parent and meta.parent not in changes:
            errors.append(f"{name}: parent '{meta.parent}' does not exist")

        for dependency in meta.depends_on:
            if dependency not in changes:
                errors.append(f"{name}: dependency '{dependency}' does not exist")
                continue
            blocks[dependency].append(name)

            dep_meta = changes[dependency]
            if meta.phase is not None and dep_meta.phase is not None and meta.phase <= dep_meta.phase:
                errors.append(
                    f"{name}: phase {meta.phase} must be greater than dependency {dependency} phase {dep_meta.phase}"
                )

    # cycle detection
    indegree = {name: 0 for name in changes}
    for meta in changes.values():
        for dep in meta.depends_on:
            if dep in indegree:
                indegree[meta.name] += 1

    queue = deque(sorted(name for name, degree in indegree.items() if degree == 0))
    visited: list[str] = []
    adjacency: dict[str, list[str]] = defaultdict(list)
    for meta in changes.values():
        for dep in meta.depends_on:
            adjacency[dep].append(meta.name)

    while queue:
        node = queue.popleft()
        visited.append(node)
        for target in sorted(adjacency[node]):
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(visited) != len(changes):
        cycle_nodes = sorted(name for name, degree in indegree.items() if degree > 0)
        errors.append(f"dependency cycle detected among: {', '.join(cycle_nodes)}")

    return errors, {key: sorted(value) for key, value in sorted(blocks.items())}


def main() -> int:
    changes = load_changes()
    errors, blocks = validate(changes)

    if errors:
        print("OpenSpec change graph errors:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("OpenSpec change graph OK")
    for name in sorted(changes):
        meta = changes[name]
        parent = f", parent={meta.parent}" if meta.parent else ""
        phase = f", phase={meta.phase}" if meta.phase is not None else ""
        depends = ", ".join(meta.depends_on) if meta.depends_on else "none"
        blocked_by = ", ".join(blocks.get(name, [])) if blocks.get(name) else "none"
        print(
            f"- {name}: kind={meta.kind}{parent}{phase}, depends_on={depends}, blocks={blocked_by}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
