import tomllib
from pathlib import Path

import tomlcmp
from tomlcmp.cli import main

ROOT = Path(__file__).resolve().parent.parent

EXAMPLE_LINES = [
    '~ project.dependencies: ["a", "b"] -> ["a", "b", "c"]',
    '+ project.requires-python = ">=3.11"',
    '~ project.version: "1.0.0" -> "1.1.0"',
    "1 added, 0 removed, 2 changed",
]

OLD = '[project]\nname = "demo"\nversion = "1.0.0"\ndependencies = ["a", "b"]\n'
NEW = (
    '[project]\nname = "demo"\nversion = "1.1.0"\n'
    'dependencies = ["a", "b", "c"]\nrequires-python = ">=3.11"\n'
)


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_readme_contains_example_lines_in_order():
    assert "\n".join(EXAMPLE_LINES) in _readme().replace("\r\n", "\n")


def test_readme_example_matches_cli_output(tmp_path, capsys):
    old = tmp_path / "old.toml"
    new = tmp_path / "new.toml"
    old.write_text(OLD, encoding="utf-8")
    new.write_text(NEW, encoding="utf-8")
    assert main([str(old), str(new)]) == 1
    assert capsys.readouterr().out == "\n".join(EXAMPLE_LINES) + "\n"
    readme = _readme().replace("\r\n", "\n")
    assert OLD.strip() in readme
    assert NEW.strip() in readme


def test_readme_reordered_arrays_example_matches_cli_output(tmp_path, capsys):
    old_text = '[project]\ndependencies = ["a", "b", "c"]\n'
    new_text = '[project]\ndependencies = ["c", "a", "b"]\n'
    plain = (
        '~ project.dependencies: ["a", "b", "c"] -> ["c", "a", "b"]\n'
        "0 added, 0 removed, 1 changed\n"
    )
    unordered = "0 added, 0 removed, 0 changed\n"
    old = tmp_path / "old.toml"
    new = tmp_path / "new.toml"
    old.write_text(old_text, encoding="utf-8")
    new.write_text(new_text, encoding="utf-8")
    assert main([str(old), str(new)]) == 1
    assert capsys.readouterr().out == plain
    assert main([str(old), str(new), "--unordered", "project.dependencies"]) == 0
    assert capsys.readouterr().out == unordered
    readme = _readme().replace("\r\n", "\n")
    assert "### Reordered arrays" in readme
    assert old_text.strip() in readme
    assert new_text.strip() in readme
    assert plain.strip() in readme
    assert unordered.strip() in readme


def test_readme_commands():
    readme = _readme()
    assert "pip install -e ." in readme
    assert 'python -m pip install -e ".[dev]"' in readme
    assert "python -m pytest -q" in readme
    assert "python -m ruff check ." in readme


def test_pyproject_script_and_dev_extra():
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["project"]["scripts"]["tomlcmp"] == "tomlcmp.cli:main"
    dev = data["project"]["optional-dependencies"]["dev"]
    assert any(d.startswith("pytest") for d in dev)
    assert any(d.startswith("ruff") for d in dev)


def test_package_exports():
    assert callable(tomlcmp.diff_toml)
    assert callable(tomlcmp.flatten)
    assert tomlcmp.Diff.__name__ == "Diff"
    for name in ("diff_toml", "flatten", "Diff"):
        assert name in tomlcmp.__all__


def test_license_is_mit():
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Permission is hereby granted, free of charge" in text


def test_readme_only_example_matches_cli_output(tmp_path, capsys):
    old = tmp_path / "old.toml"
    new = tmp_path / "new.toml"
    old.write_text(OLD, encoding="utf-8")
    new.write_text(NEW, encoding="utf-8")

    added_output = '+ project.requires-python = ">=3.11"\n1 added, 0 removed, 0 changed\n'
    assert main([str(old), str(new), "--only", "added"]) == 1
    assert capsys.readouterr().out == added_output

    removed_output = "0 added, 0 removed, 0 changed\n"
    assert main([str(old), str(new), "--only", "removed"]) == 0
    assert capsys.readouterr().out == removed_output

    readme = _readme().replace("\r\n", "\n")
    assert (
        "tomlcmp OLD NEW [--format text|json] [--ignore PATH]... "
        "[--unordered PATH]... [--only KIND]..."
    ) in readme
    assert readme.index("### Reordered arrays") < readme.index(
        "### Only some kinds of change"
    ) < readme.index("### Library")

    section = readme.split("### Only some kinds of change", 1)[1].split("### Library", 1)[0]
    assert "`tomlcmp old.toml new.toml --only added`" in section
    assert "prints exactly these lines and exits with code 1:" in section
    assert f"```\n{added_output.rstrip()}\n```" in section
    assert "`tomlcmp old.toml new.toml --only removed`" in section
    assert "prints exactly this line and exits with code 0:" in section
    assert f"```\n{removed_output.rstrip()}\n```" in section
    assert "Repeat the option or provide a comma-separated list" in section
    assert "Unselected kinds are counted as 0 and do not affect the exit code." in section

    assert (
        "| `--only KIND` | Repeatable, comma lists allowed. Report only `added`, `removed` "
        "or `changed` keys; the other kinds count as 0 and do not set the exit code. |"
    ) in readme
    assert (
        'tomlcmp: --only: unknown kind "Added" (use added, removed or changed)'
    ) in section
