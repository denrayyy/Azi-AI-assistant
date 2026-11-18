"""Command handling for launching apps and folders."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class CommandResult:
    """Structured result for a command execution."""

    success: bool
    message: str

    def as_dict(self) -> Dict[str, object]:
        return {"success": self.success, "message": self.message}


class AppLauncher:
    """Launches Windows applications using subprocess.Popen."""

    def __init__(self, apps: Dict[str, str], display_names: Dict[str, str]) -> None:
        self._apps = apps
        self._display_names = display_names

    def launch(self, app_key: str) -> CommandResult:
        command = self._apps.get(app_key)
        display_name = self._display_names.get(app_key, app_key)
        if not command:
            return CommandResult(False, "Application not found.")

        try:
            # Use the Windows shell to resolve PATH and app registrations.
            subprocess.Popen(
                ["cmd", "/c", "start", "", command],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return CommandResult(False, "Application not found.")
        except OSError as exc:
            return CommandResult(False, f"Failed to open {display_name}: {exc}")

        return CommandResult(True, f"Opening {display_name}...")


class FolderLauncher:
    """Opens common Windows folders in File Explorer."""

    def __init__(self, folders: Dict[str, Path], display_names: Dict[str, str]) -> None:
        self._folders = folders
        self._display_names = display_names

    def open(self, folder_key: str) -> CommandResult:
        target = self._folders.get(folder_key)
        display_name = self._display_names.get(folder_key, folder_key)
        if not target:
            return CommandResult(False, "Folder not found.")

        try:
            # Explorer handles folder paths directly.
            subprocess.Popen(
                ["explorer", str(target)],
                shell=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            return CommandResult(False, "Folder not found.")
        except OSError as exc:
            return CommandResult(False, f"Failed to open {display_name}: {exc}")

        return CommandResult(True, f"Opening {display_name}...")


class CommandManager:
    """Detects natural language launch commands and executes them."""

    def __init__(self, app_launcher: AppLauncher, folder_launcher: FolderLauncher) -> None:
        self._app_launcher = app_launcher
        self._folder_launcher = folder_launcher

        # Synonyms that indicate the user wants to open something.
        self._request_phrases = {
            "open",
            "launch",
            "start",
            "run",
            "please open",
            "can you open",
            "could you open",
            "would you open",
            "i need",
            "i want",
        }

        # Alias tables allow natural language variations for apps and folders.
        self._app_aliases = {
            "word": ["word", "microsoft word", "ms word"],
            "excel": ["excel", "microsoft excel"],
            "powerpoint": ["powerpoint", "power point", "microsoft powerpoint"],
            "chrome": ["chrome", "google chrome"],
            "edge": ["edge", "microsoft edge"],
            "vscode": ["vs code", "vscode", "visual studio code"],
            "discord": ["discord"],
            "steam": ["steam"],
            "calculator": ["calculator", "calc"],
            "notepad": ["notepad"],
        }
        self._folder_aliases = {
            "downloads": ["downloads", "download folder", "downloads folder", "my downloads"],
            "documents": ["documents", "document folder", "documents folder", "my documents"],
        }

    def try_handle(self, text: str) -> Optional[Dict[str, object]]:
        normalized = self._normalize(text)
        if not normalized:
            return None

        if not self._looks_like_request(normalized):
            return None

        app_key = self._match_alias(normalized, self._app_aliases)
        if app_key:
            return self._app_launcher.launch(app_key).as_dict()

        folder_key = self._match_alias(normalized, self._folder_aliases)
        if folder_key:
            return self._folder_launcher.open(folder_key).as_dict()

        return None

    def _looks_like_request(self, text: str) -> bool:
        return any(phrase in text for phrase in self._request_phrases)

    def _match_alias(self, text: str, alias_map: Dict[str, Iterable[str]]) -> Optional[str]:
        for key, aliases in alias_map.items():
            if any(alias in text for alias in aliases):
                return key
        return None

    def _normalize(self, text: str) -> str:
        lowered = text.lower().strip()
        # Remove punctuation while keeping spaces for phrase matching.
        return re.sub(r"[^a-z0-9\s]", "", lowered)


def build_default_command_manager() -> CommandManager:
    """Creates a CommandManager with default app and folder mappings."""

    apps = {
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "chrome": "chrome",
        "edge": "msedge",
        "vscode": "code",
        "discord": "discord",
        "steam": "steam",
        "calculator": "calc",
        "notepad": "notepad",
    }
    app_names = {
        "word": "Microsoft Word",
        "excel": "Microsoft Excel",
        "powerpoint": "Microsoft PowerPoint",
        "chrome": "Google Chrome",
        "edge": "Microsoft Edge",
        "vscode": "VS Code",
        "discord": "Discord",
        "steam": "Steam",
        "calculator": "Calculator",
        "notepad": "Notepad",
    }
    folders = {
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
    }
    folder_names = {
        "downloads": "Downloads folder",
        "documents": "Documents folder",
    }

    app_launcher = AppLauncher(apps, app_names)
    folder_launcher = FolderLauncher(folders, folder_names)
    return CommandManager(app_launcher, folder_launcher)
