"""Parses user text into assistant commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtWidgets import QMessageBox

from commands.windows_actions import ActionResult, WindowsActions


@dataclass(frozen=True)
class Command:
    """Represents a parsed command request."""

    name: str
    requires_confirmation: bool


class CommandParser:
    """Parses and executes assistant commands safely."""

    def __init__(self, actions: WindowsActions) -> None:
        self._actions = actions

    def try_parse(self, text: str) -> Optional[Command]:
        lowered = text.strip().lower()
        if not lowered:
            return None

        if any(keyword in lowered for keyword in ["shutdown", "format", "delete", "rm "]):
            return Command("dangerous", True)

        if "open chrome" in lowered:
            return Command("open_chrome", False)
        if "open vs code" in lowered or "open vscode" in lowered:
            return Command("open_vscode", False)
        if "open notepad" in lowered:
            return Command("open_notepad", False)
        if "open calculator" in lowered or "open calc" in lowered:
            return Command("open_calculator", False)

        return None

    def execute(self, command: Command, parent) -> str:
        if command.requires_confirmation:
            confirmed = self._confirm(parent, "This action may be unsafe. Proceed?")
            if not confirmed:
                return "Canceled."

        action_map = {
            "open_chrome": self._actions.open_chrome,
            "open_vscode": self._actions.open_vscode,
            "open_notepad": self._actions.open_notepad,
            "open_calculator": self._actions.open_calculator,
        }

        action = action_map.get(command.name)
        if not action:
            return "Command not supported."

        result: ActionResult = action()
        return result.message

    def _confirm(self, parent, message: str) -> bool:
        dialog = QMessageBox(parent)
        dialog.setWindowTitle("Confirm Action")
        dialog.setText(message)
        dialog.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return dialog.exec() == QMessageBox.StandardButton.Yes
