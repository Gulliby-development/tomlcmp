<p align="center"><img src="docs/logo.svg" width="96" alt="" /></p>

# tomlcmp

Compare two TOML files by value and list the added, removed and changed keys, as a command line tool or a Python library.

[![CI](https://github.com/Gulliby-development/tomlcmp/actions/workflows/ci.yml/badge.svg)](https://github.com/Gulliby-development/tomlcmp/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Why

After bumping a `pyproject.toml` or a Cargo manifest, a text diff is full of reordered keys and comment noise. `tomlcmp` compares the parsed values instead, so you see only the settings that really changed. Python 3.11+, standard library only.

## Install

```
pip install -e .
```

## Usage

```
tomlcmp OLD NEW [--format text|json] [--ignore PATH]...
```

`old.toml`:

```toml
[project]
name = "demo"
version = "1.0.0"
dependencies = ["a", "b"]
```

`new.toml`:

```toml
[project]
name = "demo"
version = "1.1.0"
dependencies = ["a", "b", "c"]
requires-python = ">=3.11"
```

`tomlcmp old.toml new.toml` prints exactly these lines and exits with code 1:

```
~ project.dependencies: ["a", "b"] -> ["a", "b", "c"]
+ project.requires-python = ">=3.11"
~ project.version: "1.0.0" -> "1.1.0"
1 added, 0 removed, 2 changed
```

`+` is an added key, `-` a removed one, `~` a changed one. It also runs as `python -m tomlcmp old.toml new.toml`. With `--format json` the same result is printed as JSON.

### Library

```python
import tomllib

from tomlcmp import diff_toml

with open("old.toml", "rb") as f:
    old = tomllib.load(f)
with open("new.toml", "rb") as f:
    new = tomllib.load(f)

result = diff_toml(old, new, ignore=["project.version"])
for change in result.changed:
    print(change.path, change.old, change.new)
```

With the files above this prints `project.dependencies ['a', 'b'] ['a', 'b', 'c']`. `diff_toml` returns a frozen `Diff` with sorted lists `added`, `removed` and `changed`; `flatten` turns a table into dotted paths.

### Options

| Option | Description |
|---|---|
| `--format text\|json` | Output format, default `text`. |
| `--ignore PATH` | Dotted path to skip, repeatable. `project` skips `project.version` but not `project2.x`. Keys with characters other than `A-Za-z0-9_-` are JSON-quoted, e.g. `tool."a.b".x`. |

### Exit codes

| Code | Meaning |
|---|---|
| `0` | No differences. |
| `1` | Differences found. |
| `2` | Usage error, or an unreadable or invalid file (`tomlcmp: <path>: <message>` on stderr). |

## Development

```
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
```

## License

MIT, see [LICENSE](LICENSE).

---

Built with BAKED, an open-source coding agent (bench loop round 04, BAKED 883fd99).
