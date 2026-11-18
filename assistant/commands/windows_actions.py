"""Windows-specific actions for the assistant."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ActionResult:
    """Result of a Windows action execution."""

    success: bool
    message: str


class WindowsActions:
    """Executes safe Windows actions for the assistant."""

    def open_chrome(self) -> ActionResult:
        return self._launch("chrome", "Chrome")

    def open_vscode(self) -> ActionResult:
        return self._launch("code", "VS Code")

    def open_notepad(self) -> ActionResult:
        return self._launch("notepad", "Notepad")

    def open_calculator(self) -> ActionResult:
        return self._launch("calc", "Calculator")

    def _launch(self, command: str, display_name: str) -> ActionResult:
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", "", command],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            return ActionResult(False, f"Failed to open {display_name}: {exc}")

        return ActionResult(True, f"Opening {display_name}...")
