"""Value-based comparison of parsed TOML documents."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class Added:
    path: str
    value: object


@dataclass(frozen=True)
class Removed:
    path: str
    value: object


@dataclass(frozen=True)
class Changed:
    path: str
    old: object
    new: object


@dataclass(frozen=True)
class Diff:
    added: list[Added] = field(default_factory=list)
    removed: list[Removed] = field(default_factory=list)
    changed: list[Changed] = field(default_factory=list)


def _format_key(key: str) -> str:
    if _BARE_KEY.fullmatch(key):
        return key
    return json.dumps(key)


def flatten(data: dict) -> dict[str, object]:
    """Flatten nested tables into dotted paths mapping to leaf values."""
    result: dict[str, object] = {}

    def walk(table: dict, prefix: str) -> None:
        for key, value in table.items():
            path = _format_key(key) if not prefix else prefix + "." + _format_key(key)
            if isinstance(value, dict) and value:
                walk(value, path)
            else:
                result[path] = value

    walk(data, "")
    return result


def _equal(a: object, b: object, tolerance: float | None = None) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
            return True
        return a == b or (tolerance is not None and tolerance > 0 and abs(a - b) <= tolerance)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            _equal(x, y, tolerance) for x, y in zip(a, b, strict=True)
        )
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return False
        return all(_equal(a[k], b[k], tolerance) for k in a)
    return type(a) is type(b) and a == b


def _ignored(path: str, ignore: Sequence[str]) -> bool:
    return any(path == entry or path.startswith(entry + ".") for entry in ignore)


def _multiset_equal(a: list, b: list, tolerance: float | None = None) -> bool:
    if len(a) != len(b):
        return False

    if tolerance is None or tolerance <= 0:
        remaining = list(b)
        for item in a:
            for index, other in enumerate(remaining):
                if _equal(item, other):
                    del remaining[index]
                    break
            else:
                return False
        return True

    matched: list[int | None] = [None] * len(b)
    for old_index, item in enumerate(a):
        for new_index, other in enumerate(b):
            if matched[new_index] is None and _equal(item, other):
                matched[new_index] = old_index
                break

    for root in range(len(a)):
        if root in matched:
            continue

        queue = [root]
        queue_index = 0
        seen_old = {root}
        seen_new: set[int] = set()
        parent_old: dict[int, int] = {}
        parent_new: dict[int, int] = {}
        free_new: int | None = None

        while queue_index < len(queue) and free_new is None:
            old_index = queue[queue_index]
            queue_index += 1
            for new_index, other in enumerate(b):
                if new_index in seen_new or not _equal(a[old_index], other, tolerance):
                    continue
                seen_new.add(new_index)
                parent_new[new_index] = old_index
                owner = matched[new_index]
                if owner is None:
                    free_new = new_index
                    break
                if owner not in seen_old:
                    seen_old.add(owner)
                    parent_old[owner] = new_index
                    queue.append(owner)

        if free_new is None:
            return False

        new_index = free_new
        while True:
            old_index = parent_new[new_index]
            matched[new_index] = old_index
            if old_index == root:
                break
            new_index = parent_old[old_index]

    return True


def _values_equal(
    path: str,
    a: object,
    b: object,
    unordered: Sequence[str],
    tolerance: float | None = None,
) -> bool:
    if isinstance(a, list) and isinstance(b, list) and _ignored(path, unordered):
        return _multiset_equal(a, b, tolerance)
    return _equal(a, b, tolerance)


def diff_toml(
    old: dict,
    new: dict,
    ignore: Sequence[str] = (),
    unordered: Sequence[str] = (),
    tolerance: float | None = None,
) -> Diff:
    """Compare two parsed TOML documents by value."""
    flat_old = {p: v for p, v in flatten(old).items() if not _ignored(p, ignore)}
    flat_new = {p: v for p, v in flatten(new).items() if not _ignored(p, ignore)}
    added = [Added(p, flat_new[p]) for p in sorted(flat_new.keys() - flat_old.keys())]
    removed = [Removed(p, flat_old[p]) for p in sorted(flat_old.keys() - flat_new.keys())]
    changed = [
        Changed(p, flat_old[p], flat_new[p])
        for p in sorted(flat_old.keys() & flat_new.keys())
        if not _values_equal(p, flat_old[p], flat_new[p], unordered, tolerance)
    ]
    return Diff(added=added, removed=removed, changed=changed)
