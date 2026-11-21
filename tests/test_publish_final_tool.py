"""tools/publish_final.py: copy a finished video into the one shared final/ folder."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "publish_final.py"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("publish_final", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["publish_final"] = module
    spec.loader.exec_module(module)
    return module


def _render(tmp: Path, stem: str = "co_loa", body: bytes = b"MP4") -> tuple[Path, Path]:
    out = tmp / "output"
    out.mkdir(parents=True, exist_ok=True)
    video = out / f"{stem}.mp4"
    video.write_bytes(body)
    (out / f"{stem}.report.json").write_text('{"total_duration": 75.0}', encoding="utf-8")
    script = tmp / "examples" / "co_loa" / "script.json"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text('{"title": "Nỏ thần Cổ Loa", "slides": []}', encoding="utf-8")
    return video, script


def test_publish_copies_video_report_script_and_manifest(tool: ModuleType, tmp_path: Path) -> None:
    video, script = _render(tmp_path)
    final = tmp_path / "final"
    dest = tool.publish(video, script, None, final)
    assert dest == final / "co_loa"
    assert (dest / "co_loa.mp4").read_bytes() == b"MP4"
    report = json.loads((dest / "co_loa.report.json").read_text(encoding="utf-8"))
    assert report["total_duration"] == 75.0
    assert (dest / "script.json").read_text(encoding="utf-8") == script.read_text(encoding="utf-8")
    manifest = json.loads((dest / "final.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "co_loa"
    assert manifest["title"] == "Nỏ thần Cổ Loa"
    assert manifest["video"] == "co_loa.mp4"
    assert manifest["source_video"] == str(video)


def test_publish_replaces_the_previous_final(tool: ModuleType, tmp_path: Path) -> None:
    final = tmp_path / "final"
    video, script = _render(tmp_path / "a", body=b"OLD")
    tool.publish(video, script, "co_loa", final)
    video2, script2 = _render(tmp_path / "b", stem="co_loa_v3", body=b"NEW")
    dest = tool.publish(video2, script2, "co_loa", final)
    files = sorted(p.name for p in dest.iterdir())
    assert files == ["co_loa.mp4", "co_loa.report.json", "final.json", "script.json"]
    assert (dest / "co_loa.mp4").read_bytes() == b"NEW"
    assert sorted(p.name for p in final.iterdir()) == ["co_loa"]  # no temp or backup folders left


def test_name_defaults_to_script_folder(tool: ModuleType, tmp_path: Path) -> None:
    video, script = _render(tmp_path, stem="co_loa_draft_7")
    assert tool.publish(video, script, None, tmp_path / "final").name == "co_loa"


def test_missing_report_is_an_error(tool: ModuleType, tmp_path: Path) -> None:
    video, script = _render(tmp_path)
    video.with_name("co_loa.report.json").unlink()
    with pytest.raises(tool.PublishError, match="report"):
        tool.publish(video, script, None, tmp_path / "final")
    assert not (tmp_path / "final" / "co_loa").exists()


def test_bad_name_is_an_error(tool: ModuleType, tmp_path: Path) -> None:
    video, script = _render(tmp_path)
    with pytest.raises(tool.PublishError, match="name"):
        tool.publish(video, script, "../escape", tmp_path / "final")


def test_final_dir_is_the_main_repo_even_from_a_worktree(tool: ModuleType) -> None:
    main = Path("/r/make-video-free")
    assert tool.final_dir_for(main / "tools" / "publish_final.py") == main / "final"
    wt = main / ".claude" / "worktrees" / "co-loa-2f38f6" / "tools" / "publish_final.py"
    assert tool.final_dir_for(wt) == main / "final"
