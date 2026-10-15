"""Example-based tests for numeric tolerance in the tomlcmp CLI and library."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tomlcmp.cli import main
from tomlcmp.diff import diff_toml

EXAMPLE_OLD = """[server]
timeout = 30.0
ratio = 0.75
retries = 3
weights = [0.1, 0.2]
"""

EXAMPLE_NEW = """[server]
timeout = 30.4
ratio = 0.7501
retries = 4
weights = [0.1004, 0.25]
"""

EXACT_OUTPUT = (
    "~ server.ratio: 0.75 -> 0.7501\n"
    "~ server.retries: 3 -> 4\n"
    "~ server.timeout: 30.0 -> 30.4\n"
    "~ server.weights: [0.1, 0.2] -> [0.1004, 0.25]\n"
    "0 added, 0 removed, 4 changed\n"
)
MEDIUM_OUTPUT = (
    "~ server.retries: 3 -> 4\n"
    "~ server.timeout: 30.0 -> 30.4\n"
    "~ server.weights: [0.1, 0.2] -> [0.1004, 0.25]\n"
    "0 added, 0 removed, 3 changed\n"
)


def write_pair(tmp_path: Path, old_text: str, new_text: str) -> tuple[str, str]:
    old = tmp_path / "old.toml"
    new = tmp_path / "new.toml"
    old.write_text(old_text, encoding="utf-8")
    new.write_text(new_text, encoding="utf-8")
    return str(old), str(new)


@pytest.mark.parametrize(
    ("option", "expected_status", "expected_output"),
    [
        ([], 1, EXACT_OUTPUT),
        (["--tolerance", "0"], 1, EXACT_OUTPUT),
        (["--tolerance", "1e-6"], 1, EXACT_OUTPUT),
        (["--tolerance", "0.01"], 1, MEDIUM_OUTPUT),
        (["--tolerance", "1e-3"], 1, MEDIUM_OUTPUT),
        (
            ["--tolerance", "0.5"],
            1,
            "~ server.retries: 3 -> 4\n0 added, 0 removed, 1 changed\n",
        ),
        (["--tolerance", "1"], 0, "0 added, 0 removed, 0 changed\n"),
    ],
)
def test_worked_example_and_tolerance_boundaries(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: list[str],
    expected_status: int,
    expected_output: str,
) -> None:
    old, new = write_pair(tmp_path, EXAMPLE_OLD, EXAMPLE_NEW)

    assert main([old, new, *option]) == expected_status
    captured = capsys.readouterr()
    assert captured.out == expected_output
    assert captured.err == ""


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda old, new: ["--tolerance", "0.001", old, new],
        lambda old, new: [old, "--tolerance", "0.001", new],
        lambda old, new: [old, new, "--tolerance", "0.001"],
        lambda old, new: ["--tolerance=0.001", old, new],
        lambda old, new: [old, "--tolerance=0.001", new],
        lambda old, new: [old, new, "--tolerance=0.001"],
    ],
)
def test_tolerance_spellings_and_positions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], argv_builder
) -> None:
    old, new = write_pair(tmp_path, "value = 1.0\n", "value = 1.0005\n")

    assert main(argv_builder(old, new)) == 0
    captured = capsys.readouterr()
    assert captured.out == "0 added, 0 removed, 0 changed\n"
    assert captured.err == ""


def test_repeated_tolerance_uses_last_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, "value = 1.0\n", "value = 1.5\n")

    assert main([old, new, "--tolerance", "0", "--tolerance", "0.5"]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"

    assert main([old, new, "--tolerance=0.5", "--tolerance=0"]) == 1
    assert capsys.readouterr().out == "~ value: 1.0 -> 1.5\n0 added, 0 removed, 1 changed\n"


@pytest.mark.parametrize("value", ["0", "1", "0.001", "1e-6", "2.5E3"])
def test_decimal_and_exponent_forms_are_valid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    old, new = write_pair(tmp_path, "value = 4.0\n", "value = 4.0\n")

    assert main([old, new, "--tolerance", value]) == 0
    captured = capsys.readouterr()
    assert captured.out == "0 added, 0 removed, 0 changed\n"
    assert captured.err == ""


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("--tolerance", ""),
        ("--tolerance", "-1"),
        ("--tolerance=-1", None),
        ("--tolerance", "+1"),
        ("--tolerance", ".5"),
        ("--tolerance", "5."),
        ("--tolerance", "1_0"),
        ("--tolerance", "0x1"),
        ("--tolerance", "1,5"),
        ("--tolerance", "nan"),
        ("--tolerance", "inf"),
        ("--tolerance", "abc"),
        ("--tolerance", "1e999"),
    ],
)
def test_invalid_tolerance_is_a_usage_error_before_file_access(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: str,
    value: str | None,
) -> None:
    missing_old = str(tmp_path / "missing-old.toml")
    missing_new = str(tmp_path / "missing-new.toml")
    args = [missing_old, missing_new]
    if value is None:
        args.append(option)
        invalid_value = option.split("=", 1)[1]
    else:
        args.extend([option, value])
        invalid_value = value

    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        f'tomlcmp: --tolerance: invalid value "{invalid_value}" '
        "(expected a non-negative number such as 0.001 or 1e-6)\n"
    )


def test_tolerance_check_follows_only_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_old = str(tmp_path / "missing-old.toml")
    missing_new = str(tmp_path / "missing-new.toml")

    assert main([missing_old, missing_new, "--only", "bad", "--tolerance", "x"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        'tomlcmp: --only: unknown kind "bad" (use added, removed or changed)\n'
    )


def test_invalid_tolerance_is_not_suppressed_by_quiet_mode(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_old = str(tmp_path / "missing-old.toml")
    missing_new = str(tmp_path / "missing-new.toml")

    assert main([missing_old, missing_new, "-q", "--tolerance", "x"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        'tomlcmp: --tolerance: invalid value "x" '
        "(expected a non-negative number such as 0.001 or 1e-6)\n"
    )


def test_tolerance_without_value_is_an_argparse_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, "value = 1\n", "value = 2\n")

    with pytest.raises(SystemExit) as error:
        main([old, new, "--tolerance"])

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: tomlcmp" in captured.err
    assert "argument --tolerance: expected one argument" in captured.err


def test_json_quiet_only_and_ignore_apply_after_tolerance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, EXAMPLE_OLD, EXAMPLE_NEW)

    assert main([old, new, "--tolerance=0.5", "--format", "json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "added": [],
        "removed": [],
        "changed": [{"path": "server.retries", "old": 3, "new": 4}],
    }

    assert main([old, new, "--tolerance", "0.5", "--only", "changed"]) == 1
    assert capsys.readouterr().out == (
        "~ server.retries: 3 -> 4\n0 added, 0 removed, 1 changed\n"
    )

    assert main([old, new, "--tolerance", "0.5", "--ignore", "server.retries"]) == 0
    assert capsys.readouterr().out == "0 added, 0 removed, 0 changed\n"

    assert main([old, new, "--tolerance", "0.5", "-q"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


@pytest.mark.parametrize(
    ("option", "expected_status"),
    [
        (["--unordered", "v", "--tolerance", "0.02"], 0),
        (["--unordered", "v", "--tolerance", "0.005"], 1),
        (["--tolerance", "0.02"], 1),
    ],
)
def test_unordered_matching_uses_tolerance(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    option: list[str],
    expected_status: int,
) -> None:
    old, new = write_pair(
        tmp_path,
        "v = [1.0, 2.0, 3.0]\n",
        "v = [3.01, 1.0, 1.99]\n",
    )

    assert main([old, new, *option]) == expected_status
    captured = capsys.readouterr()
    if expected_status:
        assert captured.out == (
            "~ v: [1.0, 2.0, 3.0] -> [3.01, 1.0, 1.99]\n"
            "0 added, 0 removed, 1 changed\n"
        )
    else:
        assert captured.out == "0 added, 0 removed, 0 changed\n"
    assert captured.err == ""


def test_unordered_matching_finds_valid_competing_matches_and_keeps_duplicates() -> None:
    competing = diff_toml(
        {"items": [0.0, 0.15]},
        {"items": [0.1, -0.1]},
        unordered=["items"],
        tolerance=0.11,
    )
    assert competing.changed == []

    duplicates = diff_toml(
        {"items": [1.0, 1.0]},
        {"items": [1.0, 1.5]},
        unordered=["items"],
        tolerance=0.5,
    )
    assert duplicates.changed == []

    different_multiplicity = diff_toml(
        {"items": [1.0, 1.0]},
        {"items": [1.0, 1.0, 1.0]},
        unordered=["items"],
        tolerance=1.0,
    )
    assert len(different_multiplicity.changed) == 1


def test_tolerance_recurses_through_arrays_and_inline_tables(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(
        tmp_path,
        "value = { groups = [[1.0, {number = 2.0}], [3.0]] }\n",
        "value = { groups = [[1.01, {number = 2.01}], [3.01]] }\n",
    )

    assert main([old, new, "--tolerance", "0.011"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "0 added, 0 removed, 0 changed\n"
    assert captured.err == ""


def test_tolerance_keeps_booleans_strings_and_dates_distinct(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(
        tmp_path,
        'boolean = true\ninteger = 1\nstring = "1"\ndate = 1979-05-27\nnumber = 1.0\n',
        'boolean = 1\ninteger = true\nstring = 1\ndate = 1979-05-28\nnumber = 1.5\n',
    )

    assert main([old, new, "--tolerance", "1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == (
        "~ boolean: true -> 1\n"
        "~ date: 1979-05-27 -> 1979-05-28\n"
        "~ integer: 1 -> true\n"
        '~ string: "1" -> 1\n'
        "0 added, 0 removed, 4 changed\n"
    )
    assert captured.err == ""


def test_nan_and_infinity_keep_existing_equality_behavior() -> None:
    same_specials = diff_toml(
        {"nan_value": float("nan"), "positive": float("inf")},
        {"nan_value": float("nan"), "positive": float("inf")},
        tolerance=0.1,
    )
    assert same_specials.changed == []

    different_infinity = diff_toml(
        {"value": float("inf")},
        {"value": 1.0},
        tolerance=10.0,
    )
    assert len(different_infinity.changed) == 1


def test_public_library_keyword_tolerance_and_kind_distinction() -> None:
    assert diff_toml({"x": 1}, {"x": 1.5}, tolerance=0.5).changed == []

    boolean_difference = diff_toml({"a": True}, {"a": 1}, tolerance=0.5)
    assert [(change.path, change.old, change.new) for change in boolean_difference.changed] == [
        ("a", True, 1)
    ]

    exact_default = diff_toml({"x": 1}, {"x": 1.5})
    assert len(exact_default.changed) == 1


def test_added_and_removed_keys_are_unchanged_by_tolerance(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, new = write_pair(tmp_path, "old_value = 1\n", "new_value = 1.5\n")

    assert main([old, new, "--tolerance", "1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == (
        "+ new_value = 1.5\n- old_value = 1\n1 added, 1 removed, 0 changed\n"
    )
    assert captured.err == ""
