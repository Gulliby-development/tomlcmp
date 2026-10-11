"""Rendering of diffs as text or JSON."""

from __future__ import annotations

import datetime
import json

from tomlcmp.diff import Diff


def iso_default(obj: object) -> str:
    """json.dumps default converter: dates and times become ISO strings."""
    if isinstance(obj, (datetime.datetime, datetime.date, datetime.time)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _value(value: object) -> str:
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return json.dumps(value, default=iso_default)


def render_text(diff: Diff) -> str:
    lines: list[tuple[str, str]] = []
    for a in diff.added:
        lines.append((a.path, f"+ {a.path} = {_value(a.value)}"))
    for r in diff.removed:
        lines.append((r.path, f"- {r.path} = {_value(r.value)}"))
    for c in diff.changed:
        lines.append((c.path, f"~ {c.path}: {_value(c.old)} -> {_value(c.new)}"))
    lines.sort(key=lambda item: item[0])
    out = [text for _, text in lines]
    out.append(f"{len(diff.added)} added, {len(diff.removed)} removed, {len(diff.changed)} changed")
    return "\n".join(out) + "\n"


def render_json(diff: Diff) -> str:
    payload = {
        "added": [{"path": a.path, "value": a.value} for a in diff.added],
        "removed": [{"path": r.path, "value": r.value} for r in diff.removed],
        "changed": [{"path": c.path, "old": c.old, "new": c.new} for c in diff.changed],
    }
    return json.dumps(payload, indent=2, default=iso_default) + "\n"
