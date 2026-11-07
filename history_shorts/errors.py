"""Error types and validation issue collection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


class HistoryShortsError(Exception):
    """Base class for expected, user-facing failures."""

    exit_code: int = 1


@dataclass(frozen=True, slots=True)
class Issue:
    """One validation problem: where it is and what is wrong."""

    file: str
    path: str
    message: str
    severity: Literal["error", "warning"]

    def format(self) -> str:
        return f"{self.file} › {self.path}: {self.message}"


@dataclass(slots=True)
class Issues:
    """Collects every problem found so they can be reported together (FR-11)."""

    items: list[Issue] = field(default_factory=list)

    def error(self, file: str, path: str, msg: str) -> None:
        self.items.append(Issue(file, path, msg, "error"))

    def warning(self, file: str, path: str, msg: str) -> None:
        self.items.append(Issue(file, path, msg, "warning"))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.items if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.items if i.severity == "warning"]

    def raise_if_errors(self) -> None:
        if self.errors:
            raise ValidationFailed(self)


class ValidationFailed(HistoryShortsError):
    exit_code = 3

    def __init__(self, issues: Issues) -> None:
        self.issues = issues
        count = len(issues.errors)
        super().__init__(f"validation failed with {count} error(s)")


class FfmpegMissing(HistoryShortsError):
    exit_code = 4


class FfmpegTooOld(HistoryShortsError):
    exit_code = 4


class FfmpegFailed(HistoryShortsError):
    exit_code = 5

    def __init__(self, command: list[str], stderr_tail: str) -> None:
        self.command = command
        self.stderr_tail = stderr_tail
        super().__init__(f"ffmpeg failed: {' '.join(command)}\n{stderr_tail}")
