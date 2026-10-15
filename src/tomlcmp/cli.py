"""Command line interface for tomlcmp."""

from __future__ import annotations

import argparse
import math
import re
import sys
import tomllib
from collections.abc import Sequence

from tomlcmp.diff import Diff, diff_toml
from tomlcmp.render import render_json, render_text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tomlcmp",
        description="Compare two TOML files by value.",
    )
    parser.add_argument("old", metavar="OLD", help="the old TOML file")
    parser.add_argument("new", metavar="NEW", help="the new TOML file")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="output format")
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PATH",
        help="dotted path to ignore (repeatable)",
    )
    parser.add_argument(
        "--unordered",
        action="append",
        default=[],
        metavar="PATH",
        help="dotted path whose arrays are compared as multisets (repeatable)",
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="KIND",
        help="report only added, removed, or changed keys (repeatable)",
    )
    parser.add_argument(
        "--tolerance",
        action="append",
        default=None,
        metavar="NUMBER",
        help="treat numbers that differ by at most NUMBER as equal",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="suppress the comparison report"
    )
    return parser


def _parse_only(values: Sequence[str]) -> tuple[set[str] | None, str | None]:
    if not values:
        return None, None

    selected: set[str] = set()
    for value in values:
        for kind in value.split(","):
            if kind not in {"added", "removed", "changed"}:
                return None, (
                    f'tomlcmp: --only: unknown kind "{kind}" '
                    "(use added, removed or changed)"
                )
            selected.add(kind)
    return selected, None


def _print_tolerance_error(value: str) -> None:
    print(
        f'tomlcmp: --tolerance: invalid value "{value}" '
        "(expected a non-negative number such as 0.001 or 1e-6)",
        file=sys.stderr,
    )


class _FileError(Exception):
    pass


def _load(path: str) -> dict:
    try:
        with open(path, "rb") as handle:
            return tomllib.load(handle)
    except OSError as exc:
        raise _FileError(exc.strerror or str(exc)) from exc
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise _FileError(str(exc)) from exc


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    selected_kinds, only_error = _parse_only(args.only)
    if only_error:
        print(only_error, file=sys.stderr)
        return 2

    tolerance = None
    if args.tolerance:
        raw_tolerance = args.tolerance[-1]
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", raw_tolerance):
            _print_tolerance_error(raw_tolerance)
            return 2
        tolerance = float(raw_tolerance)
        if not math.isfinite(tolerance):
            _print_tolerance_error(raw_tolerance)
            return 2

    try:
        old = _load(args.old)
    except _FileError as exc:
        print(f"tomlcmp: {args.old}: {exc}", file=sys.stderr)
        return 2
    try:
        new = _load(args.new)
    except _FileError as exc:
        print(f"tomlcmp: {args.new}: {exc}", file=sys.stderr)
        return 2
    diff = diff_toml(
        old, new, args.ignore, unordered=args.unordered, tolerance=tolerance
    )
    if selected_kinds is not None:
        diff = Diff(
            added=diff.added if "added" in selected_kinds else [],
            removed=diff.removed if "removed" in selected_kinds else [],
            changed=diff.changed if "changed" in selected_kinds else [],
        )
    render = render_json if args.format == "json" else render_text
    if not args.quiet:
        sys.stdout.write(render(diff))
    return 1 if (diff.added or diff.removed or diff.changed) else 0
