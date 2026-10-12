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


def _equal(a: object, b: object) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
            return True
        return a == b
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return False
        return all(_equal(a[k], b[k]) for k in a)
    return type(a) is type(b) and a == b


def _ignored(path: str, ignore: Sequence[str]) -> bool:
    return any(path == entry or path.startswith(entry + ".") for entry in ignore)


def _multiset_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    remaining = list(b)
    for item in a:
        for i, other in enumerate(remaining):
            if _equal(item, other):
                del remaining[i]
                break
        else:
            return False
    return True


def _values_equal(path: str, a: object, b: object, unordered: Sequence[str]) -> bool:
    if isinstance(a, list) and isinstance(b, list) and _ignored(path, unordered):
        return _multiset_equal(a, b)
    return _equal(a, b)


def diff_toml(
    old: dict,
    new: dict,
    ignore: Sequence[str] = (),
    unordered: Sequence[str] = (),
) -> Diff:
    """Compare two parsed TOML documents by value."""
    flat_old = {p: v for p, v in flatten(old).items() if not _ignored(p, ignore)}
    flat_new = {p: v for p, v in flatten(new).items() if not _ignored(p, ignore)}
    added = [Added(p, flat_new[p]) for p in sorted(flat_new.keys() - flat_old.keys())]
    removed = [Removed(p, flat_old[p]) for p in sorted(flat_old.keys() - flat_new.keys())]
    changed = [
        Changed(p, flat_old[p], flat_new[p])
        for p in sorted(flat_old.keys() & flat_new.keys())
        if not _values_equal(p, flat_old[p], flat_new[p], unordered)
    ]
    return Diff(added=added, removed=removed, changed=changed)
