from __future__ import annotations

import pytest

from history_shorts import __version__
from history_shorts.cli import main


def test_version_prints_package_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "history-shorts 2.0.0"


def test_package_version_constant() -> None:
    assert __version__ == "2.0.0"


def test_no_subcommand_is_usage_error() -> None:
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2
