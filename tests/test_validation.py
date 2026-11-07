"""The generic path-tracking validator."""

from __future__ import annotations

from history_shorts.config import Ctx as ConfigCtx
from history_shorts.config import read_json_object as config_read_json_object
from history_shorts.errors import Issues
from history_shorts.validation import Ctx, read_json_object


def test_config_reexports_validator() -> None:
    assert ConfigCtx is Ctx
    assert config_read_json_object is read_json_object


def test_items_records_errors_without_iterating() -> None:
    issues = Issues()
    Ctx("f.json", issues, "xs").items("nope")
    Ctx("f.json", issues, "ys").items([], non_empty=True)
    assert [i.format() for i in issues.errors] == [
        "f.json › xs: must be an array",
        "f.json › ys: must be a non-empty array",
    ]


def test_items_pairs_carry_indexed_paths() -> None:
    issues = Issues()
    pairs = Ctx("f.json", issues, "xs").items([10, 20])
    assert [(c.path, v) for c, v in pairs] == [("xs[0]", 10), ("xs[1]", 20)]


def test_terse_style_is_inherited_and_theme_style_is_default() -> None:
    issues = Issues()
    plain, terse = Ctx("f", issues), Ctx("f", issues, terse=True)
    plain.num({"a": 9}, "a", hi=1)
    plain.num({}, "b")
    terse.at("c").num({"a": 9}, "a", hi=1)
    terse.idx(0).num({}, "b")
    assert [(i.path, i.message) for i in issues.errors] == [
        ("a", "must be a number ≤ 1"),
        ("b", "required key missing"),
        ("c.a", "must be ≤ 1"),
        ("[0].b", "required"),
    ]


def test_choice() -> None:
    issues = Issues()
    ctx = Ctx("f", issues)
    assert ctx.choice({"k": "b"}, "k", ("a", "b")) == "b"
    assert ctx.choice({}, "k", ("a", "b"), default="a") == "a"
    assert ctx.choice({"k": "z"}, "k", ("a", "b")) == ""
    assert [i.message for i in issues.errors] == ["must be one of a, b"]
