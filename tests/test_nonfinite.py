"""Regression tests for JSON rendering of non-finite TOML floats."""

from __future__ import annotations

import json

from tomlcmp.cli import main


def _write_toml(tmp_path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _reject_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant: {value}")


def _json_report(capsys):
    return json.loads(capsys.readouterr().out, parse_constant=_reject_constant)


def test_json_added_non_finite_floats(tmp_path, capsys):
    old = _write_toml(tmp_path, "old.toml", "")
    new = _write_toml(tmp_path, "new.toml", "a = nan\nb = inf\nc = -inf\n")

    assert main([old, new, "--format", "json"]) == 1
    assert _json_report(capsys) == {
        "added": [
            {"path": "a", "value": "nan"},
            {"path": "b", "value": "inf"},
            {"path": "c", "value": "-inf"},
        ],
        "removed": [],
        "changed": [],
    }


def test_json_changed_and_removed_non_finite_floats(tmp_path, capsys):
    old = _write_toml(tmp_path, "old.toml", "a = inf\nb = -inf\n")
    new = _write_toml(tmp_path, "new.toml", "a = 1.5\n")

    assert main([old, new, "--format", "json"]) == 1
    assert _json_report(capsys) == {
        "added": [],
        "removed": [{"path": "b", "value": "-inf"}],
        "changed": [{"path": "a", "old": "inf", "new": 1.5}],
    }


def test_json_non_finite_floats_in_arrays_and_tables(tmp_path, capsys):
    old = _write_toml(tmp_path, "old.toml", "")
    new = _write_toml(tmp_path, "new.toml", "list = [nan, 1.5]\n\n[t]\nx = inf\n")

    assert main([old, new, "--format", "json"]) == 1
    assert _json_report(capsys) == {
        "added": [
            {"path": "list", "value": ["nan", 1.5]},
            {"path": "t.x", "value": "inf"},
        ],
        "removed": [],
        "changed": [],
    }


def test_text_non_finite_float_output_is_unchanged(tmp_path, capsys):
    old = _write_toml(tmp_path, "old.toml", "")
    new = _write_toml(tmp_path, "new.toml", "a = nan\n")

    assert main([old, new]) == 1
    assert capsys.readouterr().out == "+ a = NaN\n1 added, 0 removed, 0 changed\n"
