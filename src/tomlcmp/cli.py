"""Command line interface for tomlcmp."""

from __future__ import annotations

import argparse
import sys
import tomllib
from collections.abc import Sequence

from tomlcmp.diff import diff_toml
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
    return parser


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
    diff = diff_toml(old, new, args.ignore, unordered=args.unordered)
    render = render_json if args.format == "json" else render_text
    sys.stdout.write(render(diff))
    return 1 if (diff.added or diff.removed or diff.changed) else 0
