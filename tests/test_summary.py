"""Tests for the --summary option of the tomlcmp CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tomlcmp import diff_toml
from tomlcmp.cli import main

OLD = '[project]\nname = "demo"\nversion = "1.0.0"\ndependencies = ["a", "b"]\n'
NEW = (
    '[project]\nname = "demo"\nversion = "1.1.0"\n'
    'dependencies = ["a", "b", "c"]\nrequires-python = ">=3.11"\n'
)


def write_pair(tmp_path: Path, old: str, new: str) -> tuple[str, str]:
    (tmp_path / "old.toml").write_text(old, encoding="utf-8")
    (tmp_path / "new.toml").write_text(new, encoding="utf-8")
    return str(tmp_path / "old.toml"), str(tmp_path / "new.toml")


def test_summary_text_prints_only_the_counts_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, OLD, NEW)
    assert main([old, new, "--summary"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "1 added, 0 removed, 2 changed\n"
    assert captured.err == ""


def test_summary_json_prints_an_object_of_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, OLD, NEW)
    assert main([old, new, "--summary", "--format", "json"]) == 1
    out = capsys.readouterr().out
    assert out == '{\n  "added": 1,\n  "removed": 0,\n  "changed": 2\n}\n'
    assert json.loads(out) == {"added": 1, "removed": 0, "changed": 2}


def test_summary_of_equal_files_exits_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, OLD, OLD)
    assert main(["--summary", old, new]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"


def test_summary_counts_follow_only_and_ignore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, OLD, NEW)
    assert main([old, new, "--summary", "--only", "changed"]) == 1
    assert capsys.readouterr().out == "0 added, 0 removed, 2 changed\n"
    assert main([old, new, "--summary", "--only", "removed"]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"
    assert main([old, new, "--summary", "--ignore", "project"]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"


def test_quiet_wins_over_summary_in_both_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, OLD, NEW)
    assert main([old, new, "-q", "--summary"]) == 1
    assert main([old, new, "--summary", "--format", "json", "--quiet"]) == 1
    assert capsys.readouterr().out == ""


def test_summary_takes_no_value_and_help_lists_it(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["old.toml", "new.toml", "--summary=yes"])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "argument --summary: ignored explicit argument 'yes'" in captured.err

    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "--summary" in capsys.readouterr().out


def test_library_diff_counts_matches_the_summary() -> None:
    result = diff_toml({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 5, "d": 4})
    assert result.counts == {"added": 1, "removed": 1, "changed": 1}
    assert list(result.counts) == ["added", "removed", "changed"]
