import dataclasses
import datetime

import pytest

from tomlcmp import Diff, diff_toml, flatten
from tomlcmp.diff import Added, Changed, Removed


def test_flatten_nested_tables():
    data = {"project": {"version": "1", "urls": {"home": "x"}}, "top": 1}
    assert flatten(data) == {"project.version": "1", "project.urls.home": "x", "top": 1}


def test_flatten_quoted_and_empty_keys():
    data = {"tool": {"a.b": {"x": 1}}, "": 2, "sp ace": 3, "ok_k-1": 4}
    assert flatten(data) == {
        'tool."a.b".x': 1,
        '""': 2,
        '"sp ace"': 3,
        "ok_k-1": 4,
    }


def test_flatten_empty_tables_and_arrays_are_leaves():
    data = {"a": {}, "b": {"c": {}}, "arr": [1, 2], "tables": [{"x": 1}]}
    assert flatten(data) == {"a": {}, "b.c": {}, "arr": [1, 2], "tables": [{"x": 1}]}


@pytest.mark.parametrize(
    ("old", "new"),
    [(1, 1.0), (1.0, 1), (float("nan"), float("nan")), (True, True), ("a", "a")],
)
def test_equal_values_not_reported(old, new):
    d = diff_toml({"k": old}, {"k": new})
    assert d == Diff([], [], [])


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (1, True),
        (True, 1),
        (1, "1"),
        ([1, 2], [2, 1]),
        ([1], [True]),
        (datetime.datetime(2020, 1, 1), datetime.date(2020, 1, 1)),
        (1, 2),
    ],
)
def test_unequal_values_reported_changed(old, new):
    d = diff_toml({"k": old}, {"k": new})
    assert d.added == [] and d.removed == []
    assert d.changed == [Changed("k", old, new)]


def test_tables_in_arrays_ignore_key_order():
    old = {"a": [{"x": 1, "y": 2}]}
    new = {"a": [{"y": 2.0, "x": 1}]}
    assert diff_toml(old, new) == Diff([], [], [])


def test_tables_in_arrays_different_values():
    d = diff_toml({"a": [{"x": 1}]}, {"a": [{"x": 2}]})
    assert [c.path for c in d.changed] == ["a"]


def test_leaf_becomes_table():
    d = diff_toml({"a": 1}, {"a": {"b": 2}})
    assert d.removed == [Removed("a", 1)]
    assert d.added == [Added("a.b", 2)]
    assert d.changed == []


def test_table_becomes_leaf():
    d = diff_toml({"a": {"b": 2}}, {"a": 1})
    assert d.removed == [Removed("a.b", 2)]
    assert d.added == [Added("a", 1)]
    assert d.changed == []


def test_sorted_by_path():
    old = {"z": 1, "a": 1, "m": 1}
    new = {"z": 2, "a": 2, "m": 2, "b": 0, "y": 0}
    d = diff_toml(old, new)
    assert [c.path for c in d.changed] == ["a", "m", "z"]
    assert [a.path for a in d.added] == ["b", "y"]
    d2 = diff_toml(new, {})
    assert [r.path for r in d2.removed] == ["a", "b", "m", "y", "z"]


def test_dataclasses_are_frozen():
    for obj in (Added("a", 1), Removed("a", 1), Changed("a", 1, 2), Diff()):
        name = dataclasses.fields(obj)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(obj, name, None)


def test_ignore_prefix():
    old = {"project": {"version": "1"}, "other": 1}
    new = {"project": {"version": "2"}, "other": 2}
    d = diff_toml(old, new, ignore=["project"])
    assert [c.path for c in d.changed] == ["other"]


def test_ignore_exact_path():
    old = {"project": {"version": "1", "name": "a"}}
    new = {"project": {"version": "2", "name": "b"}}
    d = diff_toml(old, new, ignore=["project.version"])
    assert [c.path for c in d.changed] == ["project.name"]


def test_ignore_boundary_project_vs_project2():
    old = {"project": {"version": "1"}, "project2": {"x": 1}}
    new = {"project": {"version": "2"}, "project2": {"x": 2}}
    d = diff_toml(old, new, ignore=["project"])
    assert [c.path for c in d.changed] == ["project2.x"]


def test_ignore_non_matching_entry():
    d = diff_toml({"a": 1}, {"a": 2}, ignore=["nothing.here"])
    assert d.changed == [Changed("a", 1, 2)]


def test_ignore_quoted_key_syntax():
    old = {"tool": {"a.b": {"x": 1}}, "y": 1}
    new = {"tool": {"a.b": {"x": 2}}, "y": 2}
    d = diff_toml(old, new, ignore=['tool."a.b"'])
    assert [c.path for c in d.changed] == ["y"]


def test_unordered_reordered_equal_and_default_changed():
    old = {"x": ["a", "b", "c"]}
    new = {"x": ["c", "a", "b"]}
    assert diff_toml(old, new, unordered=["x"]) == Diff([], [], [])
    assert diff_toml(old, new).changed == [Changed("x", ["a", "b", "c"], ["c", "a", "b"])]


def test_unordered_duplicates_counted():
    old = {"x": ["a", "a", "b"]}
    new = {"x": ["a", "b", "b"]}
    d = diff_toml(old, new, unordered=["x"])
    assert [c.path for c in d.changed] == ["x"]


def test_unordered_different_length_changed():
    d = diff_toml({"x": [1, 2]}, {"x": [1, 2, 2]}, unordered=["x"])
    assert [c.path for c in d.changed] == ["x"]


def test_unordered_int_float_equal():
    assert diff_toml({"x": [1]}, {"x": [1.0]}, unordered=["x"]) == Diff([], [], [])


def test_unordered_bool_int_different():
    d = diff_toml({"x": [True]}, {"x": [1]}, unordered=["x"])
    assert [c.path for c in d.changed] == ["x"]


def test_unordered_nan_matches_nan():
    nan = float("nan")
    assert diff_toml({"x": [nan, 1]}, {"x": [1, nan]}, unordered=["x"]) == Diff([], [], [])


def test_unordered_nested_list_inner_order_matters():
    old = {"x": [[1, 2], [3]]}
    new = {"x": [[3], [2, 1]]}
    d = diff_toml(old, new, unordered=["x"])
    assert [c.path for c in d.changed] == ["x"]
    same = diff_toml({"x": [[1, 2], [3]]}, {"x": [[3], [1, 2]]}, unordered=["x"])
    assert same == Diff()


def test_unordered_boundary_project_vs_project2():
    old = {"project": {"dependencies": ["a", "b"]}, "project2": {"x": ["a", "b"]}}
    new = {"project": {"dependencies": ["b", "a"]}, "project2": {"x": ["b", "a"]}}
    d = diff_toml(old, new, unordered=["project"])
    assert [c.path for c in d.changed] == ["project2.x"]


def test_unordered_table_prefix_covers_several_arrays():
    old = {"t": {"a": [1, 2], "b": {"c": ["x", "y"]}}}
    new = {"t": {"a": [2, 1], "b": {"c": ["y", "x"]}}}
    assert diff_toml(old, new, unordered=["t"]) == Diff([], [], [])


def test_unordered_non_matching_entry_has_no_effect():
    old = {"x": [1, 2]}
    new = {"x": [2, 1]}
    d = diff_toml(old, new, unordered=["nothing.here"])
    assert d.changed == [Changed("x", [1, 2], [2, 1])]


def test_ignore_wins_over_unordered():
    old = {"x": [1, 2], "y": [1, 2]}
    new = {"x": [3], "y": [2, 1]}
    d = diff_toml(old, new, ignore=["x"], unordered=["x", "y"])
    assert d == Diff([], [], [])


def test_unordered_non_permutation_reports_original_order():
    old = {"x": ["b", "a"]}
    new = {"x": ["c", "a"]}
    d = diff_toml(old, new, unordered=["x"])
    assert d.changed == [Changed("x", ["b", "a"], ["c", "a"])]


def test_unordered_added_and_removed_paths():
    d = diff_toml({"x": [1]}, {"y": [1]}, unordered=["x", "y"])
    assert d.removed == [Removed("x", [1])]
    assert d.added == [Added("y", [1])]
    assert d.changed == []


def test_unordered_quoted_key_syntax():
    old = {"a.b": {"c": [1, 2]}}
    new = {"a.b": {"c": [2, 1]}}
    assert diff_toml(old, new, unordered=['"a.b".c']) == Diff([], [], [])


def test_unordered_positional_ignore_unchanged():
    old = {"a": 1, "b": 2}
    new = {"a": 2, "b": 3}
    assert diff_toml(old, new, ["a"]) == diff_toml(old, new, ignore=["a"], unordered=())
