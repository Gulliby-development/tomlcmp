"""Example-based tests for the --only CLI option."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tomlcmp.cli import main

OLD_EXAMPLE = """[project]
name = "demo"
version = "1.0.0"
dependencies = ["a", "b"]
license = "MIT"
"""

NEW_EXAMPLE = """[project]
name = "demo"
version = "1.1.0"
dependencies = ["a", "b", "c"]
requires-python = ">=3.11"
"""

FULL_OUTPUT = (
    '~ project.dependencies: ["a", "b"] -> ["a", "b", "c"]\n'
    '- project.license = "MIT"\n'
    '+ project.requires-python = ">=3.11"\n'
    '~ project.version: "1.0.0" -> "1.1.0"\n'
    "1 added, 1 removed, 2 changed\n"
)

ADDED_OUTPUT = '+ project.requires-python = ">=3.11"\n1 added, 0 removed, 0 changed\n'
REMOVED_OUTPUT = '- project.license = "MIT"\n0 added, 1 removed, 0 changed\n'
CHANGED_OUTPUT = (
    '~ project.dependencies: ["a", "b"] -> ["a", "b", "c"]\n'
    '~ project.version: "1.0.0" -> "1.1.0"\n'
    "0 added, 0 removed, 2 changed\n"
)
EMPTY_OUTPUT = "0 added, 0 removed, 0 changed\n"


def write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def example_files(tmp_path: Path) -> tuple[str, str]:
    return (
        write(tmp_path, "old.toml", OLD_EXAMPLE),
        write(tmp_path, "new.toml", NEW_EXAMPLE),
    )


def test_without_only_preserves_full_report(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    old, new = example_files(tmp_path)

    assert main([old, new]) == 1
    captured = capsys.readouterr()
    assert captured.out == FULL_OUTPUT
    assert captured.err == ""


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("added", ADDED_OUTPUT),
        ("removed", REMOVED_OUTPUT),
        ("changed", CHANGED_OUTPUT),
    ],
)
def test_only_single_kind_text(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    selection: str,
    expected: str,
) -> None:
    old, new = example_files(tmp_path)

    assert main([old, new, "--only", selection]) == 1
    captured = capsys.readouterr()
    assert captured.out == expected
    assert captured.err == ""


def test_only_removed_when_diff_has_only_added_key(tmp_path: Path, capsys) -> None:
    old = write(tmp_path, "old.toml", "a = 1\n")
    new = write(tmp_path, "new.toml", "a = 1\nb = 2\n")

    assert main([old, new, "--only", "removed"]) == 0
    captured = capsys.readouterr()
    assert captured.out == EMPTY_OUTPUT
    assert captured.err == ""


def test_repeated_comma_duplicate_and_all_selections(tmp_path: Path, capsys) -> None:
    old, new = example_files(tmp_path)
    combined = (
        '- project.license = "MIT"\n'
        '+ project.requires-python = ">=3.11"\n'
        "1 added, 1 removed, 0 changed\n"
    )

    assert main([old, new, "--only", "added", "--only", "removed"]) == 1
    assert capsys.readouterr().out == combined

    assert main([old, new, "--only", "removed,added"]) == 1
    assert capsys.readouterr().out == combined

    assert main([old, new, "--only=removed,added"]) == 1
    assert capsys.readouterr().out == combined

    assert main([old, new, "--only", "added,added"]) == 1
    assert capsys.readouterr().out == ADDED_OUTPUT

    assert main([old, new, "--only", "added,removed,changed"]) == 1
    assert capsys.readouterr().out == FULL_OUTPUT


def test_only_can_precede_file_arguments(tmp_path: Path, capsys) -> None:
    old, new = example_files(tmp_path)

    assert main(["--only=added", old, new]) == 1
    captured = capsys.readouterr()
    assert captured.out == ADDED_OUTPUT
    assert captured.err == ""


def test_only_json_keeps_all_category_keys(tmp_path: Path, capsys) -> None:
    old, new = example_files(tmp_path)

    assert main([old, new, "--only", "removed", "--format", "json"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "added": [],
        "removed": [{"path": "project.license", "value": "MIT"}],
        "changed": [],
    }
    assert captured.err == ""


def test_unselected_only_kinds_do_not_set_exit_code(tmp_path: Path, capsys) -> None:
    old = write(tmp_path, "old.toml", "a = 1\nb = 2\n")
    new = write(tmp_path, "new.toml", "a = 9\nb = 2\n")

    assert main([old, new, "--only", "added,removed"]) == 0
    captured = capsys.readouterr()
    assert captured.out == EMPTY_OUTPUT
    assert captured.err == ""

    assert main([old, new, "--only", "added,removed", "--format", "json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"added": [], "removed": [], "changed": []}
    assert captured.err == ""

    assert main([old, new, "--only", "changed"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "~ a: 1 -> 9\n0 added, 0 removed, 1 changed\n"
    assert captured.err == ""


def test_ignore_and_unordered_are_applied_before_only(tmp_path: Path, capsys) -> None:
    old = write(tmp_path, "old.toml", 'ignored = 1\nitems = [1, 2]\nvalue = 1\n')
    new = write(tmp_path, "new.toml", 'extra = 3\nignored = 9\nitems = [2, 1]\nvalue = 2\n')

    args = [
        old,
        new,
        "--only",
        "changed",
        "--ignore",
        "ignored",
        "--unordered",
        "items",
    ]
    assert main(args) == 1
    captured = capsys.readouterr()
    assert captured.out == "~ value: 1 -> 2\n0 added, 0 removed, 1 changed\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("values", "bad_piece"),
    [
        (["Added"], "Added"),
        (["added,"], ""),
        ([""], ""),
        (["x,added"], "x"),
        (["added,nope", "other"], "nope"),
    ],
)
def test_invalid_only_kind_reports_first_bad_piece_before_file_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    values: list[str],
    bad_piece: str,
) -> None:
    missing_old = str(tmp_path / "missing-old.toml")
    missing_new = str(tmp_path / "missing-new.toml")
    args = [missing_old, missing_new]
    for value in values:
        args.extend(["--only", value])

    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f'tomlcmp: --only: unknown kind "{bad_piece}" '
        "(use added, removed or changed)\n"
    )


def test_only_without_value_is_an_argparse_error(tmp_path: Path, capsys) -> None:
    missing_old = str(tmp_path / "missing-old.toml")
    missing_new = str(tmp_path / "missing-new.toml")

    with pytest.raises(SystemExit) as error:
        main([missing_old, missing_new, "--only"])

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: tomlcmp" in captured.err
