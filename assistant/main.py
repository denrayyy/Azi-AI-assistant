"""Entry point for the desktop pet assistant."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from ai.memory import MemoryStore
from ai.ollama_client import OllamaClient
from commands.command_manager import build_default_command_manager
from ui.chat_window import ChatWindow
from ui.desktop_pet import DesktopPet


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for the assistant."""

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    memory_db_path: str = "data/conversations.db"


class AppController(QObject):
    """Coordinates UI, AI, memory, and command handling."""

    response_ready = pyqtSignal(str)

    def __init__(self, app: QApplication, config: AppConfig) -> None:
        super().__init__()
        self._app = app
        self._config = config

        self._memory = MemoryStore(self._config.memory_db_path)
        self._ollama = OllamaClient(
            base_url=self._config.ollama_base_url,
            model=self._config.ollama_model,
        )
        # Command manager handles app and folder launch requests.
        self._command_manager = build_default_command_manager()

        self._pet = DesktopPet()
        self._chat = ChatWindow()

        self._wire_signals()
        self._load_history()

    def _wire_signals(self) -> None:
        self._pet.clicked.connect(self._toggle_chat_window)
        self._chat.message_submitted.connect(self._handle_user_message)
        self._chat.new_chat_requested.connect(self._start_new_chat)
        self._chat.sleep_requested.connect(self._sleep_pet)
        self.response_ready.connect(self._handle_assistant_response)

    def _load_history(self) -> None:
        for role, text in self._memory.load_recent():
            self._chat.append_message(role, text)

    def _toggle_chat_window(self) -> None:
        if self._chat.isVisible():
            self._chat.archive_current_chat()
            self._chat.hide()
            self._pet.set_chat_open(False)
        else:
            self._chat.show()
            self._chat.raise_()
            self._chat.activateWindow()
            self._pet.set_chat_open(True)

    def _handle_user_message(self, text: str) -> None:
        if not text.strip():
            return

        self._chat.append_message("user", text)
        self._memory.save_message("user", text)

        # Check for app/folder commands before sending to Ollama.
        command_result = self._command_manager.try_handle(text)
        if command_result:
            self._handle_assistant_response(command_result["message"])
            return

        self._chat.set_busy(True)
        thread = threading.Thread(
            target=self._ollama_worker,
            args=(text,),
            daemon=True,
        )
        thread.start()

    def _ollama_worker(self, text: str) -> None:
        response = self._ollama.chat(self._memory.build_context(text))
        self.response_ready.emit(response)

    def _handle_assistant_response(self, response: str) -> None:
        self._chat.append_message("assistant", response)
        self._memory.save_message("assistant", response)
        self._pet.show_speech(response)
        self._chat.set_busy(False)

    def _start_new_chat(self) -> None:
        self._chat.archive_current_chat()
        self._memory.clear()
        self._chat.clear_history()
        self._pet.show_speech("New chat started.")

    def _sleep_pet(self) -> None:
        self._pet.sleep()
        self._pet.show_speech("Zzz...")

    def show(self) -> None:
        self._pet.show()


def _show_startup_error(message: str, detail: Optional[str] = None) -> None:
    error_box = QMessageBox()
    error_box.setWindowTitle("Assistant Startup Error")
    error_box.setText(message)
    if detail:
        error_box.setDetailedText(detail)
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.exec()


def main() -> int:
    app = QApplication(sys.argv)

    try:
        controller = AppController(app, AppConfig())
    except Exception as exc:  # pragma: no cover - UI error path
        _show_startup_error("Failed to start the assistant.", str(exc))
        return 1

    controller.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
