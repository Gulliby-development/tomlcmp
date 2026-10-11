"""Tests for the tomlcmp command line interface."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tomlcmp.cli import main

OLD_EXAMPLE = """[project]
name = "demo"
version = "1.0.0"
dependencies = ["a", "b"]
"""

NEW_EXAMPLE = """[project]
name = "demo"
version = "1.1.0"
dependencies = ["a", "b", "c"]
requires-python = ">=3.11"
"""

EXAMPLE_OUTPUT = (
    '~ project.dependencies: ["a", "b"] -> ["a", "b", "c"]\n'
    '+ project.requires-python = ">=3.11"\n'
    '~ project.version: "1.0.0" -> "1.1.0"\n'
    "1 added, 0 removed, 2 changed\n"
)

EMPTY_JSON = '{\n  "added": [],\n  "removed": [],\n  "changed": []\n}\n'


def write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_readme_example(tmp_path, capsys):
    old = write(tmp_path, "old.toml", OLD_EXAMPLE)
    new = write(tmp_path, "new.toml", NEW_EXAMPLE)
    assert main([old, new]) == 1
    captured = capsys.readouterr()
    assert captured.out == EXAMPLE_OUTPUT
    assert captured.err == ""


def test_no_differences_text(tmp_path, capsys):
    old = write(tmp_path, "old.toml", OLD_EXAMPLE)
    reordered = (
        "# comment\n[project]\ndependencies = [\"a\", \"b\"]\n"
        'version = "1.0.0"\nname = "demo"\n'
    )
    new = write(tmp_path, "new.toml", reordered)
    assert main([old, new]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"


def test_no_differences_json(tmp_path, capsys):
    old = write(tmp_path, "old.toml", OLD_EXAMPLE)
    new = write(tmp_path, "new.toml", OLD_EXAMPLE)
    assert main([old, new, "--format", "json"]) == 0
    assert capsys.readouterr().out == EMPTY_JSON


DT_OLD = "t = 2024-01-01T00:00:00\narr = [2024-01-01T00:00:00]\n"
DT_NEW = "t = 2024-01-02T00:00:00\narr = [2024-01-02T00:00:00]\n"


def test_datetimes_text(tmp_path, capsys):
    old = write(tmp_path, "old.toml", DT_OLD)
    new = write(tmp_path, "new.toml", DT_NEW)
    assert main([old, new]) == 1
    assert capsys.readouterr().out == (
        '~ arr: ["2024-01-01T00:00:00"] -> ["2024-01-02T00:00:00"]\n'
        "~ t: 2024-01-01T00:00:00 -> 2024-01-02T00:00:00\n"
        "0 added, 0 removed, 2 changed\n"
    )


def test_datetimes_json(tmp_path, capsys):
    old = write(tmp_path, "old.toml", DT_OLD)
    new = write(tmp_path, "new.toml", DT_NEW)
    assert main([old, new, "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["added"] == []
    assert data["removed"] == []
    assert data["changed"] == [
        {"path": "arr", "old": ["2024-01-01T00:00:00"], "new": ["2024-01-02T00:00:00"]},
        {"path": "t", "old": "2024-01-01T00:00:00", "new": "2024-01-02T00:00:00"},
    ]


def test_added_and_removed_text(tmp_path, capsys):
    old = write(tmp_path, "old.toml", "a = 1\nc = 3\n")
    new = write(tmp_path, "new.toml", "b = 2\nc = 4\n")
    assert main([old, new]) == 1
    assert capsys.readouterr().out == (
        "- a = 1\n+ b = 2\n~ c: 3 -> 4\n1 added, 1 removed, 1 changed\n"
    )


def test_added_and_removed_json(tmp_path, capsys):
    old = write(tmp_path, "old.toml", "a = 1\nz = 1\ny = 1\n")
    new = write(tmp_path, "new.toml", "b = 2\nx = 1\n")
    assert main([old, new, "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert [r["path"] for r in data["removed"]] == ["a", "y", "z"]
    assert [a["path"] for a in data["added"]] == ["b", "x"]
    assert data["changed"] == []


def test_ignore_option(tmp_path, capsys):
    old = write(tmp_path, "old.toml", OLD_EXAMPLE)
    new = write(tmp_path, "new.toml", NEW_EXAMPLE)
    assert main([old, new, "--ignore", "project"]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"


def test_invalid_toml(tmp_path, capsys):
    old = write(tmp_path, "old.toml", "a b c\n")
    new = write(tmp_path, "new.toml", "a = 1\n")
    assert main([old, new]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"tomlcmp: {old}: ")
    assert "line 1" in captured.err


def test_missing_file(tmp_path, capsys):
    missing = str(tmp_path / "missing.toml")
    new = write(tmp_path, "new.toml", "a = 1\n")
    assert main([missing, new]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"tomlcmp: {missing}: ")


def test_old_is_checked_first(tmp_path, capsys):
    missing = str(tmp_path / "missing.toml")
    bad = write(tmp_path, "bad.toml", "a b c\n")
    assert main([missing, bad]) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"tomlcmp: {missing}: ")
    assert err.count("tomlcmp:") == 1


def test_non_utf8_file(tmp_path, capsys):
    bad = tmp_path / "bad.toml"
    bad.write_bytes(b'a = "\xff"\n')
    new = write(tmp_path, "new.toml", "a = 1\n")
    assert main([new, str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith(f"tomlcmp: {bad}: ")


@pytest.mark.parametrize(
    "argv",
    [
        ["a.toml", "b.toml", "--bogus"],
        ["a.toml", "b.toml", "--format", "xml"],
        ["a.toml"],
        [],
    ],
)
def test_argparse_errors(argv, capsys):
    with pytest.raises(SystemExit) as info:
        main(argv)
    assert info.value.code == 2
    assert capsys.readouterr().out == ""


def test_python_dash_m(tmp_path):
    old = write(tmp_path, "old.toml", OLD_EXAMPLE)
    new = write(tmp_path, "new.toml", NEW_EXAMPLE)
    src = Path(__file__).resolve().parents[1] / "src"
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src)
    result = subprocess.run(
        [sys.executable, "-m", "tomlcmp", old, new],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout.replace("\r\n", "\n") == EXAMPLE_OUTPUT
