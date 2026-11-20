"""M10: schema 2.3 character ids, poses and timed actions."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from history_shorts.characters.actions import ACTIONS, POSES
from history_shorts.checks import action_timing_problems, check_all
from history_shorts.config import load_script
from history_shorts.errors import ValidationFailed
from history_shorts.scene_config import POSE_NAMES
from history_shorts.script_config import ACTION_NAMES

ScriptFactory = Callable[..., Path]
V23 = {"schema_version": "2.3"}


def _people(*items: dict[str, Any]) -> dict[str, Any]:
    return {"type": "characters", "items": list(items)}


def _slide(actions: list[dict[str, Any]], *items: dict[str, Any], **kw: Any) -> dict[str, Any]:
    leader = {"role": "leader", "id": "ba_trac", "x": 400, "height": 400}
    general = {"role": "general", "id": "ba_nhi", "x": 700, "height": 380, "facing": -1}
    people = _people(*(items or (leader, general)))
    slide = {"title": "A", "duration": 5, "living": True, "scene": {"layers": [people]}}
    slide["actions"] = actions
    slide.update(kw)
    return slide


def _auto(script: Any, theme: Any) -> list[float]:
    from history_shorts.script_config import slide_duration

    return [slide_duration(s, theme.video.fps) for s in script.slides]


def _messages(tmp_script: ScriptFactory, theme: Any, slide: dict[str, Any]) -> list[str]:
    path = tmp_script(slides=[slide], extra=V23)
    try:
        script, issues = load_script(path)
    except ValidationFailed as exc:
        return [f"{i.path}: {i.message}" for i in exc.issues.items]
    issues = [
        *issues,
        *check_all(script, theme),
        *action_timing_problems(script, _auto(script, theme)),
    ]
    # a one-slide test script is shorter than a video may be; that warning is not under test
    return [f"{i.path}: {i.message}" for i in issues if "total duration" not in i.message]


def test_names_match_presets() -> None:
    assert set(POSE_NAMES) == set(POSES)
    assert set(ACTION_NAMES) == set(ACTIONS)


def test_valid_actions_load(tmp_script: ScriptFactory, theme: Any) -> None:
    actions = [
        {"who": "ba_trac", "do": "rally", "at": 1.0},
        {"who": "ba_nhi", "do": "bow", "at": 2},
    ]
    assert _messages(tmp_script, theme, _slide(actions)) == []
    script = load_script(tmp_script(slides=[_slide(actions)], extra=V23))[0]
    first = script.slides[0].actions[0]
    assert (first.who, first.do, first.at, first.duration) == ("ba_trac", "rally", 1.0, None)


@pytest.mark.parametrize(
    ("key", "value"), [("id", "x"), ("pose", "kneeling"), ("idle", False), ("on", 0)]
)
def test_character_keys_need_23(key: str, value: Any, tmp_script: ScriptFactory) -> None:
    item = {"role": "leader", "x": 400, key: value}
    slide = {"title": "A", "living": True, "scene": {"layers": [_people(item)]}}
    with pytest.raises(ValidationFailed) as exc:
        load_script(tmp_script(slides=[slide], extra={"schema_version": "2.2"}))
    assert any('requires schema_version "2.3"' in i.message for i in exc.value.issues.items)


def test_actions_need_23(tmp_script: ScriptFactory) -> None:
    slide = _slide([{"who": "ba_trac", "do": "rally", "at": 1}])
    with pytest.raises(ValidationFailed) as exc:
        load_script(tmp_script(slides=[slide], extra={"schema_version": "2.2"}))
    assert any(i.path.endswith("actions") for i in exc.value.issues.items)


def test_unknown_action(tmp_script: ScriptFactory, theme: Any) -> None:
    msgs = _messages(tmp_script, theme, _slide([{"who": "ba_trac", "do": "dance", "at": 1}]))
    assert any("actions[0].do" in m and "rally" in m for m in msgs)


def test_unknown_character_id(tmp_script: ScriptFactory, theme: Any) -> None:
    msgs = _messages(tmp_script, theme, _slide([{"who": "nobody", "do": "rally", "at": 1}]))
    assert any("actions[0].who" in m and "ba_nhi, ba_trac" in m for m in msgs)


def test_duplicate_character_id(tmp_script: ScriptFactory, theme: Any) -> None:
    a = {"role": "leader", "id": "same", "x": 400, "height": 400}
    b = {"role": "general", "id": "same", "x": 700, "height": 380}
    msgs = _messages(tmp_script, theme, _slide([], a, b))
    assert any("duplicate character id 'same'" in m for m in msgs)


def test_bad_id_pattern(tmp_script: ScriptFactory, theme: Any) -> None:
    a = {"role": "leader", "id": "Bà Trắc", "x": 400, "height": 400}
    msgs = _messages(tmp_script, theme, _slide([], a))
    assert any(".id" in m and "[a-z0-9_]" in m for m in msgs)


def test_overlapping_actions(tmp_script: ScriptFactory, theme: Any) -> None:
    actions = [{"who": "ba_trac", "do": "rally", "at": 1}, {"who": "ba_trac", "do": "bow", "at": 2}]
    msgs = _messages(tmp_script, theme, _slide(actions))
    assert any("actions[1]" in m and "overlaps" in m for m in msgs)


def test_action_past_slide_end(tmp_script: ScriptFactory, theme: Any) -> None:
    msgs = _messages(tmp_script, theme, _slide([{"who": "ba_trac", "do": "rally", "at": 4.0}]))
    assert any("actions[0]" in m and "ends after the slide" in m for m in msgs)


def test_stand_up_needs_crouch(tmp_script: ScriptFactory, theme: Any) -> None:
    msgs = _messages(tmp_script, theme, _slide([{"who": "ba_trac", "do": "stand_up", "at": 1}]))
    assert any("stand_up" in m and "kneeling or seated" in m for m in msgs)


def test_stand_up_after_kneel_ok(tmp_script: ScriptFactory, theme: Any) -> None:
    actions = [
        {"who": "ba_trac", "do": "kneel", "at": 0.5},
        {"who": "ba_trac", "do": "stand_up", "at": 2.5},
    ]
    assert _messages(tmp_script, theme, _slide(actions)) == []


def test_stand_up_from_kneeling_pose_ok(tmp_script: ScriptFactory, theme: Any) -> None:
    kneel = {"role": "leader", "id": "ba_trac", "x": 400, "height": 400, "pose": "kneeling"}
    slide = _slide([{"who": "ba_trac", "do": "stand_up", "at": 1}], kneel)
    assert _messages(tmp_script, theme, slide) == []


def test_raise_flag_needs_flag(tmp_script: ScriptFactory, theme: Any) -> None:
    msgs = _messages(tmp_script, theme, _slide([{"who": "ba_nhi", "do": "raise_flag", "at": 1}]))
    assert any("raise_flag" in m and "flag" in m for m in msgs)


def test_actions_on_still_slide_warn(tmp_script: ScriptFactory, theme: Any) -> None:
    slide = _slide([{"who": "ba_trac", "do": "rally", "at": 1}], living=False)
    msgs = _messages(tmp_script, theme, slide)
    assert any("actions" in m and "living" in m for m in msgs)


def test_raised_flag_hits_seal(tmp_script: ScriptFactory, theme: Any) -> None:
    """At rest the flag clears the seal by 8 px; raised, it reaches into it (FR-48 over time)."""
    from history_shorts.chrome import seal_box

    seal = seal_box(theme)
    height = 400.0
    unit = height / 100
    bearer = {
        "role": "leader",
        "id": "ba_trac",
        "facing": -1,  # the flag flies to the left, over the seal at the frame's left edge
        "x": round(seal.x1 + 15.5 * unit - 10),
        "baseline": round(seal.y1 + 139 * unit + 8),
        "height": height,
    }
    assert not _messages(tmp_script, theme, _slide([], bearer))
    msgs = _messages(
        tmp_script, theme, _slide([{"who": "ba_trac", "do": "raise_flag", "at": 1}], bearer)
    )
    assert any("overlaps seal" in m and "while moving" in m for m in msgs), msgs


def test_template_characters_have_ids(theme: Any) -> None:
    from history_shorts.scene.templates import GROUP_CHARACTERS, LANDSCAPE_BOATS

    ids = [c.id for c in GROUP_CHARACTERS] + [c.id for b in LANDSCAPE_BOATS for c in b.crew]
    assert all(ids) and len(set(ids)) == len(ids)


def test_bow_out_of_the_frame(tmp_script: ScriptFactory, theme: Any) -> None:  # final review 2
    edge = {"role": "leader", "prop": "none", "id": "a", "x": 992, "height": 400}
    assert not _messages(tmp_script, theme, _slide([], edge))
    msgs = _messages(tmp_script, theme, _slide([{"who": "a", "do": "bow", "at": 1}], edge))
    assert any("head box" in m and "outside the frame" in m and "while moving" in m for m in msgs)


def test_rally_over_a_back_head(tmp_script: ScriptFactory, theme: Any) -> None:
    back = {"role": "leader", "id": "back", "x": 540, "baseline": 1000, "height": 300}
    front = {"role": "general", "id": "front", "x": 480, "height": 400, "facing": -1}
    assert not _messages(tmp_script, theme, _slide([], back, front))
    msgs = _messages(
        tmp_script, theme, _slide([{"who": "front", "do": "rally", "at": 1}], back, front)
    )
    assert any("covers the head" in m and "while moving" in m for m in msgs), msgs


def test_action_timing_uses_the_voice_length(tmp_script: ScriptFactory, theme: Any) -> None:
    """A narrated slide is as long as its voice: a rally at 4 s fits a 7 s voice (review 3)."""
    slide = _slide([{"who": "ba_trac", "do": "rally", "at": 4.0}])
    del slide["duration"]
    script = load_script(tmp_script(slides=[slide], extra=V23))[0]
    assert action_timing_problems(script, [7.0]) == []
    (issue,) = action_timing_problems(script, [3.0])
    assert issue.path.endswith("actions[0]") and "ends after the slide" in issue.message
