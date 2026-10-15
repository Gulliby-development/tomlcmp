"""Regression tests for quiet mode in the tomlcmp CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tomlcmp.cli import main

README_OLD = """[project]
name = "demo"
version = "1.0.0"
dependencies = ["a", "b"]
"""

README_NEW = """[project]
name = "demo"
version = "1.1.0"
dependencies = ["a", "b", "c"]
requires-python = ">=3.11"
"""

QUIET_SECTION = """### Quiet mode

Use `-q` or `--quiet` in a script that only needs to know whether two files differ. Nothing is printed to standard output, in either format, and the exit code is the same as without it (`0` for no differences, `1` for differences). It works together with `--ignore`, `--unordered` and `--only`, which still decide what counts as a difference. Errors (a usage error, an unreadable or invalid file) are still printed to standard error and exit with code 2.

```sh
if tomlcmp -q old.toml new.toml; then
  echo "settings unchanged"
fi
```
"""


def write_toml(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def readme_files(tmp_path: Path) -> tuple[str, str]:
    return (
        write_toml(tmp_path, "old.toml", README_OLD),
        write_toml(tmp_path, "new.toml", README_NEW),
    )


def test_quiet_aliases_work_at_any_position_and_can_repeat(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = readme_files(tmp_path)
    variants = [
        ["-q", old, new],
        [old, "--quiet", new],
        [old, new, "--quiet"],
        ["-q", old, "--quiet", new, "-q"],
    ]

    for argv in variants:
        assert main(argv) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


def test_quiet_suppresses_both_report_formats(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = readme_files(tmp_path)

    for option, output_format in (("-q", "text"), ("--quiet", "json")):
        assert main([old, new, option, "--format", output_format]) == 1
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


def test_quiet_identical_files_return_zero_without_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old = write_toml(tmp_path, "old.toml", README_OLD)
    new = write_toml(tmp_path, "new.toml", README_OLD)

    assert main([old, new, "-q"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_only_filters_keep_their_exit_statuses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = readme_files(tmp_path)
    selections = [
        (["--only", "removed"], 0),
        (["--only", "added"], 1),
        (["--only=changed,removed"], 1),
    ]

    for only_args, expected_status in selections:
        assert main([old, new, "-q", *only_args]) == expected_status
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


def test_quiet_ignore_and_unordered_keep_their_filtering_semantics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = readme_files(tmp_path)
    assert main([old, new, "--ignore", "project", "-q"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    old = write_toml(tmp_path, "reordered-old.toml", "items = [1, 2]\n")
    new = write_toml(tmp_path, "reordered-new.toml", "items = [2, 1]\n")
    assert main([old, new]) == 1
    assert capsys.readouterr().out
    assert main([old, new, "-q", "--unordered", "items"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_without_quiet_still_prints_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = readme_files(tmp_path)

    for output_format in ("text", "json"):
        assert main([old, new, "--format", output_format]) == 1
        captured = capsys.readouterr()
        assert captured.err == ""
        if output_format == "text":
            assert captured.out == (
                '~ project.dependencies: ["a", "b"] -> ["a", "b", "c"]\n'
                '+ project.requires-python = ">=3.11"\n'
                '~ project.version: "1.0.0" -> "1.1.0"\n'
                "1 added, 0 removed, 2 changed\n"
            )
        else:
            report = json.loads(captured.out)
            assert report["added"]
            assert report["changed"]
            assert report["removed"] == []


def test_quiet_keeps_application_errors_visible(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    valid = write_toml(tmp_path, "valid.toml", "value = 1\n")
    missing = str(tmp_path / "missing.toml")
    invalid = write_toml(tmp_path, "invalid.toml", "value = \n")
    cases = [
        ([valid, missing, "-q"], f"tomlcmp: {missing}: ", False),
        ([invalid, valid, "--quiet"], f"tomlcmp: {invalid}: ", False),
        (
            ["missing-old.toml", "missing-new.toml", "-q", "--only", "Added"],
            (
                  'tomlcmp: --only: unknown kind "Added" '
                  + "(use added, removed or changed)\n"
              ),
            True,
        ),
    ]

    for argv, expected_error, exact_error in cases:
        assert main(argv) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        if exact_error:
            assert captured.err == expected_error
        else:
            assert captured.err.startswith(expected_error)
            assert captured.err[len(expected_error) :].strip()


def test_parser_rejects_quiet_values_and_help_lists_quiet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = readme_files(tmp_path)
    with pytest.raises(SystemExit) as error:
        main([old, new, "--quiet=yes"])

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: tomlcmp" in captured.err
    assert "argument -q/--quiet: ignored explicit argument 'yes'" in captured.err

    with pytest.raises(SystemExit) as error:
        main(["--help"])

    assert error.value.code == 0
    captured = capsys.readouterr()
    assert "-q, --quiet" in captured.out
    assert captured.err == ""


def test_readme_documents_quiet_mode() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8").replace("\r\n", "\n")

    usage = (
        "tomlcmp OLD NEW [--format text|json] [--ignore PATH]... "
        "[--unordered PATH]... [--only KIND]... [--tolerance NUMBER] [-q | --quiet]"
    )
    quiet_option = (
        "| `-q`, `--quiet` | Print nothing to standard output; the exit code alone "
        "tells whether the files differ. Errors are still printed to standard error. |"
    )

    assert usage in readme
    assert QUIET_SECTION in readme
    assert quiet_option in readme
    assert readme.index("### Only some kinds of change") < readme.index("### Quiet mode")
    assert readme.index("### Quiet mode") < readme.index("### Library")
    assert readme.index("| `--only KIND`") < readme.index(quiet_option)
