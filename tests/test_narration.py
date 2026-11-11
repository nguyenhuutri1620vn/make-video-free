"""Narration text rules and the 2.1 script fields (spec A.1.2, AC-16 text part)."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from pathlib import Path

import pytest

from history_shorts import narration
from history_shorts.config import load_script
from history_shorts.errors import ValidationFailed


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Xin chào\r\nthế giới", "Xin chào\nthế giới"),
        ("dòng một  \t\ndòng hai   ", "dòng một\ndòng hai"),
        ("\n\n  Một đoạn.\n\n", "  Một đoạn."),
        ("cr only\rline", "cr only\nline"),
    ],
)
def test_normalise_line_endings_and_blank_lines(raw: str, expected: str) -> None:
    assert narration.normalise(raw) == expected


def test_normalise_composes_nfd_vietnamese() -> None:
    composed = "Trưng"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed
    assert narration.normalise(decomposed) == composed


def test_file_bytes_utf8_lf_one_final_newline() -> None:
    data = narration.file_bytes("Dòng một\r\nDòng hai  \n\n")
    assert data == "Dòng một\nDòng hai\n".encode()
    assert b"\r" not in data
    assert not data.startswith(b"\xef\xbb\xbf")  # no BOM


def test_text_sha256_matches_file_bytes() -> None:
    import hashlib

    text = "Hai Bà Trưng khởi nghĩa."
    assert narration.text_sha256(text) == hashlib.sha256(narration.file_bytes(text)).hexdigest()


def test_text_sha256_ignores_trailing_spaces_and_crlf() -> None:
    assert narration.text_sha256("a \r\nb") == narration.text_sha256("a\nb")


@pytest.mark.parametrize("text", ["Nói [pause 50ms] tiếp", "[pause 3000ms]", "[pause 800ms]"])
def test_valid_pause_markers_pass(text: str) -> None:
    assert narration.pause_problems(text) == []


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("[pause 49ms]", "outside 50–3000 ms"),
        ("[pause 3001ms]", "outside 50–3000 ms"),
        ("[pause 500 ms]", "unknown tag"),
        ("[happy] xin chào", "unknown tag '[happy]'"),
        ("dở dang [pause 500ms", "unknown tag"),
    ],
)
def test_invalid_bracket_tags_are_reported(text: str, fragment: str) -> None:
    problems = narration.pause_problems(text)
    assert problems and any(fragment in p for p in problems)


# --------------------------------------------------------------------------------------
# Script 2.1 fields
# --------------------------------------------------------------------------------------


def test_2_0_script_still_loads_without_ids(tmp_script: Callable[..., Path]) -> None:
    script, _ = load_script(tmp_script(slides=[{"title": "A"}, {"title": "B"}]))
    assert [s.id for s in script.slides] == ["s01", "s02"]
    assert all(s.narration is None for s in script.slides)


def test_2_1_normalised_narration_and_explicit_ids(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[
            {"title": "A", "id": "intro", "narration": "Mở đầu.\r\n"},
            {"title": "B", "id": "outro", "narration": "Tiếp theo [pause 300ms] nữa."},
        ],
    )
    script, _ = load_script(path)
    assert [s.id for s in script.slides] == ["intro", "outro"]
    assert script.slides[0].narration == "Mở đầu."
    assert script.slides[1].narration == "Tiếp theo [pause 300ms] nữa."


def test_2_1_without_narration_gets_default_ids(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(extra={"schema_version": "2.1"}, slides=[{"title": "A"}, {"title": "B"}])
    script, _ = load_script(path)
    assert [s.id for s in script.slides] == ["s01", "s02"]


def test_narration_required_ids_on_every_slide(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[{"title": "A", "narration": "Một."}, {"title": "B", "id": "b"}],
    )
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    messages = [i.format() for i in excinfo.value.issues.errors]
    assert any("slides[0].id" in m and "required" in m for m in messages)


def test_duplicate_ids_are_rejected(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[{"title": "A", "id": "x"}, {"title": "B", "id": "x"}],
    )
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    assert any('duplicate id "x"' in i.message for i in excinfo.value.issues.errors)


@pytest.mark.parametrize("bad", ["Intro", "-x", "a" * 33, "a b"])
def test_bad_slide_ids_are_rejected(tmp_script: Callable[..., Path], bad: str) -> None:
    path = tmp_script(extra={"schema_version": "2.1"}, slides=[{"title": "A", "id": bad}])
    with pytest.raises(ValidationFailed):
        load_script(path)


def test_narration_in_2_0_script_is_an_error(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(slides=[{"title": "A", "narration": "Xin chào."}])
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    assert any('requires schema_version "2.1"' in i.message for i in excinfo.value.issues.errors)


def test_narration_length_limit(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[{"title": "A", "id": "a", "narration": "x" * 601}],
    )
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    assert any("at most 600 characters" in i.message for i in excinfo.value.issues.errors)


def test_narration_rejects_unknown_bracket_and_emoji(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[
            {"title": "A", "id": "a", "narration": "Vui [laugh] quá"},
            {"title": "B", "id": "b", "narration": "Hay 😀"},
        ],
    )
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    messages = [i.message for i in excinfo.value.issues.errors]
    assert any("unknown tag" in m for m in messages)
    assert any("emoji" in m for m in messages)


def test_blank_narration_is_an_error(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(
        extra={"schema_version": "2.1"},
        slides=[{"title": "A", "id": "a", "narration": "  \n  "}],
    )
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    assert any("must not be blank" in i.message for i in excinfo.value.issues.errors)


def test_unsupported_version_names_both_supported(tmp_script: Callable[..., Path]) -> None:
    path = tmp_script(extra={"schema_version": "3.0"})
    with pytest.raises(ValidationFailed) as excinfo:
        load_script(path)
    message = excinfo.value.issues.errors[0].message
    assert '"2.0" or "2.1"' in message
