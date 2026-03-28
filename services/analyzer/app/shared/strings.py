from __future__ import annotations

import re


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "project"


def human_join(items: list[str]) -> str:
    values = [item for item in items if item]
    if not values:
        return "overall balance"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def dedupe_labels(labels: list[str]) -> list[str]:
    ordered: list[str] = []
    for label in labels:
        if label and label not in ordered:
            ordered.append(label)
    return ordered
