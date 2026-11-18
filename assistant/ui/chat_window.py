"""Chat window for interacting with the assistant."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

try:
    import speech_recognition as sr
except ImportError:  # pragma: no cover - optional dependency
    sr = None

try:
    import pyaudio
except ImportError:  # pragma: no cover - optional dependency
    pyaudio = None

try:
    import vosk
except ImportError:  # pragma: no cover - optional dependency
    vosk = None

try:
    import pyttsx3
except ImportError:  # pragma: no cover - optional dependency
    pyttsx3 = None


@dataclass
class VoiceConfig:
    """Configuration for optional voice features."""

    enable_tts: bool = True


class SidebarWidget(QWidget):
    """Left sidebar with chat controls and history."""

    new_chat_clicked = pyqtSignal()
    conversation_selected = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("sidebar")

        self._title = QLabel("Chats")
        self._title.setObjectName("sidebarTitle")

        header = QHBoxLayout()
        header.addWidget(self._title)
        header.addStretch(1)

        self._new_chat_button = QToolButton()
        self._new_chat_button.setText("New Chat")
        self._new_chat_button.setObjectName("primaryButton")
        self._new_chat_button.clicked.connect(self.new_chat_clicked.emit)

        self._history = QListWidget()
        self._history.setObjectName("historyList")
        self._history.itemClicked.connect(self._handle_item_clicked)

        layout = QVBoxLayout()
        layout.addLayout(header)
        layout.addWidget(self._new_chat_button)
        layout.addWidget(self._history, 1)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        self.setLayout(layout)

    def add_conversation(self, title: str, messages: list[tuple[str, str]]) -> None:
        if not title:
            return

        item = QListWidgetItem()
        item.setSizeHint(QSize(200, 44))
        item.setData(Qt.ItemDataRole.UserRole, messages)
        widget = RecentChatItem(title)
        widget.delete_requested.connect(lambda: self._confirm_remove_item(item, widget.title()))
        self._history.addItem(item)
        self._history.setItemWidget(item, widget)

    def _handle_item_clicked(self, item: QListWidgetItem) -> None:
        messages = item.data(Qt.ItemDataRole.UserRole)
        if messages:
            self.conversation_selected.emit(messages)

    def _confirm_remove_item(self, item: QListWidgetItem, title: str) -> None:
        message = f"Delete chat: {title}?"
        reply = QMessageBox.question(
            self,
            "Delete Chat",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._remove_item(item)

    def _remove_item(self, item: QListWidgetItem) -> None:
        row = self._history.row(item)
        if row >= 0:
            self._history.takeItem(row)


class RecentChatItem(QWidget):
    """Conversation list item with a delete button."""

    delete_requested = pyqtSignal()

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("recentChatItem")
        self._title = title

        label = QLabel(title)
        label.setObjectName("recentChatTitle")

        delete_button = QToolButton()
        delete_button.setText("🗑")
        delete_button.setToolTip("Delete chat")
        delete_button.setObjectName("deleteButton")
        delete_button.clicked.connect(self.delete_requested.emit)

        layout = QHBoxLayout()
        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(delete_button)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.setLayout(layout)

    def title(self) -> str:
        return self._title


class HeaderWidget(QWidget):
    """Header with avatar and settings."""

    settings_clicked = pyqtSignal()
    sleep_clicked = pyqtSignal()
    sidebar_toggle_clicked = pyqtSignal()
    theme_toggle_clicked = pyqtSignal()

    def __init__(
        self,
        avatar_path: Optional[Path],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("header")

        self._avatar = QLabel()
        self._avatar.setFixedSize(44, 44)
        self._avatar.setObjectName("avatar")
        self._set_avatar(avatar_path)

        self._sidebar_toggle = QToolButton()
        self._sidebar_toggle.setText("≡")
        self._sidebar_toggle.setToolTip("Toggle sidebar")
        self._sidebar_toggle.setObjectName("iconButton")
        self._sidebar_toggle.clicked.connect(self.sidebar_toggle_clicked.emit)

        self._name_label = QLabel("Azi")
        self._name_label.setObjectName("assistantName")

        self._settings_button = QToolButton()
        self._settings_button.setText("⚙")
        self._settings_button.setToolTip("Settings")
        self._settings_button.clicked.connect(self.settings_clicked.emit)

        self._sleep_button = QToolButton()
        self._sleep_button.setToolTip("Make Azi Sleep")
        self._sleep_button.setObjectName("iconButton")
        self._sleep_button.clicked.connect(self.sleep_clicked.emit)

        self._theme_button = QToolButton()
        self._theme_button.setText("☀")
        self._theme_button.setToolTip("Toggle theme")
        self._theme_button.setObjectName("iconButton")
        self._theme_button.clicked.connect(self.theme_toggle_clicked.emit)

        left = QHBoxLayout()
        left.addWidget(self._sidebar_toggle)
        left.addWidget(self._avatar)
        left.addWidget(self._name_label)
        left.addStretch(1)
        left.addWidget(self._sleep_button)
        left.addWidget(self._theme_button)
        left.addWidget(self._settings_button)
        left.setSpacing(12)

        layout = QVBoxLayout()
        layout.addLayout(left)
        layout.setContentsMargins(18, 12, 18, 12)

        self.setLayout(layout)

    def _set_avatar(self, avatar_path: Optional[Path]) -> None:
        if avatar_path and avatar_path.exists():
            pixmap = QPixmap(str(avatar_path))
            if not pixmap.isNull():
                self._avatar.setPixmap(
                    pixmap.scaled(
                        44,
                        44,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                return
        self._avatar.setText("A")
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_sleep_icon(self, icon: QIcon) -> None:
        self._sleep_button.setIcon(icon)

    def set_theme_icon(self, text: str) -> None:
        self._theme_button.setText(text)


class ChatBubbleWidget(QWidget):
    """Message bubble for user or assistant."""

    def __init__(self, text: str, is_user: bool, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        container = QFrame()
        container.setObjectName("bubbleUser" if is_user else "bubbleAssistant")
        container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setObjectName("bubbleText")

        inner = QVBoxLayout(container)
        inner.addWidget(label)
        inner.setContentsMargins(14, 10, 14, 10)

        layout = QHBoxLayout()
        if is_user:
            layout.addStretch(1)
            layout.addWidget(container, 0)
        else:
            layout.addWidget(container, 0)
            layout.addStretch(1)
        layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(layout)


class MessageInputWidget(QWidget):
    """Input row with rounded text box and icon buttons."""

    text_submitted = pyqtSignal(str)
    mic_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.setObjectName("inputContainer")

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a message...")
        self._input.returnPressed.connect(self._emit_submit)

        self._send_button = QToolButton()
        self._send_button.setText("➤")
        self._send_button.setToolTip("Send")
        self._send_button.clicked.connect(self._emit_submit)

        self._mic_button = QToolButton()
        self._mic_button.setText("🎤")
        self._mic_button.setToolTip("Voice input")
        self._mic_button.clicked.connect(self.mic_clicked.emit)

        layout = QHBoxLayout()
        layout.addWidget(self._input, 1)
        layout.addWidget(self._send_button)
        layout.addWidget(self._mic_button)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        self.setLayout(layout)

    def _emit_submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.text_submitted.emit(text)

    def set_text(self, text: str) -> None:
        self._input.setText(text)

    def set_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_button.setEnabled(enabled)
        self._mic_button.setEnabled(enabled)

    def set_mic_enabled(self, enabled: bool, tooltip: Optional[str] = None) -> None:
        self._mic_button.setEnabled(enabled)
        if tooltip:
            self._mic_button.setToolTip(tooltip)


class ChatWindow(QWidget):
    """Chat UI widget with history, input, and optional voice support."""

    message_submitted = pyqtSignal(str)
    new_chat_requested = pyqtSignal()
    sleep_requested = pyqtSignal()
    status_changed = pyqtSignal(str)
    transcript_ready = pyqtSignal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chat With Azi")
        self.setWindowIcon(QIcon(str(Path("assets/sprites/dog_happy.png"))))
        self.setMinimumSize(920, 620)
        self._sidebar_visible = True
        self._current_chat_messages: list[tuple[str, str]] = []
        self._current_chat_archived = False
        self._thinking_bubble: Optional[ChatBubbleWidget] = None
        self._theme_mode = "dark"

        self._voice_config = VoiceConfig()
        self._tts_engine = self._init_tts_engine()
        self._tts_queue: "queue.Queue[str]" = queue.Queue()
        self._tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self._tts_thread.start()

        self._sidebar = SidebarWidget()
        self._sidebar.new_chat_clicked.connect(self.new_chat_requested.emit)
        self._sidebar.conversation_selected.connect(self._load_conversation)
        avatar_path = Path("assets/sprites/dog_happy.png")
        self._header = HeaderWidget(avatar_path)
        self._header.sidebar_toggle_clicked.connect(self._toggle_sidebar)
        self._header.sleep_clicked.connect(self._request_sleep)
        self._header.theme_toggle_clicked.connect(self._toggle_theme)
        self._set_sleep_icon()

        self._status = QLabel("")
        self._status.setVisible(False)
        self.status_changed.connect(self._status.setText)
        self.transcript_ready.connect(self._handle_transcript)

        self._messages = QWidget()
        self._messages.setObjectName("messageArea")
        self._message_layout = QVBoxLayout(self._messages)
        self._message_layout.setContentsMargins(12, 18, 12, 18)
        self._message_layout.setSpacing(16)
        self._message_layout.addStretch(1)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._messages)
        self._scroll_area.setObjectName("chatScroll")
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self._input_widget = MessageInputWidget()
        self._input_widget.text_submitted.connect(self._submit_message)
        self._input_widget.mic_clicked.connect(self._start_listen)

        if not self._voice_input_available():
            self._input_widget.set_mic_enabled(False, "Install PyAudio to enable mic input")

        self._build_layout()
        self._apply_styles()

    def _build_layout(self) -> None:
        main_column = QVBoxLayout()
        main_column.addWidget(self._header)
        main_column.addWidget(self._scroll_area, 1)
        main_column.addWidget(self._input_widget)
        main_column.setSpacing(10)
        main_column.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setLayout(main_column)

        layout = QHBoxLayout()
        layout.addWidget(self._sidebar)
        layout.addWidget(content, 1)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setLayout(layout)

    def append_message(self, role: str, text: str) -> None:
        self._render_message(role, text, track=True, play_tts=True)

    def _render_message(self, role: str, text: str, track: bool, play_tts: bool) -> None:
        self._clear_thinking_bubble()
        is_user = role == "user"
        bubble = ChatBubbleWidget(text, is_user)
        self._message_layout.insertWidget(self._message_layout.count() - 1, bubble)
        self._scroll_to_bottom()
        if track:
            self._current_chat_messages.append((role, text))
            self._current_chat_archived = False
        if play_tts and (
            role == "assistant"
            and self._voice_config.enable_tts
            and not text.startswith("[Ollama error]")
        ):
            self._enqueue_tts(text)

    def _submit_message(self, text: str) -> None:
        if not text:
            return
        self.message_submitted.emit(text)

    def set_busy(self, busy: bool) -> None:
        self._input_widget.set_enabled(not busy)
        self._status.setText("Thinking..." if busy else "")
        if busy:
            self._show_thinking_bubble()
        else:
            self._clear_thinking_bubble()

    def clear_history(self) -> None:
        for index in reversed(range(self._message_layout.count() - 1)):
            item = self._message_layout.itemAt(index)
            widget = item.widget() if item else None
            if widget:
                widget.setParent(None)
        self._current_chat_messages = []
        self._current_chat_archived = False

    def _request_sleep(self) -> None:
        self.sleep_requested.emit()

    def _start_listen(self) -> None:
        if not self._voice_input_available():
            self._status.setText("Offline speech not configured")
            return

        self._status.setText("Listening...")
        thread = threading.Thread(target=self._listen_worker, daemon=True)
        thread.start()

    def _listen_worker(self) -> None:
        if not self._voice_input_available():
            self.status_changed.emit("Offline speech not configured")
            return

        recognizer = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5)
                result = recognizer.recognize_vosk(audio)
                text = result.get("text", "") if isinstance(result, dict) else ""
        except Exception as exc:
            self.status_changed.emit(f"Mic error: {exc}")
            return

        if text:
            self.transcript_ready.emit(text)
        self.status_changed.emit("")

    def _voice_input_available(self) -> bool:
        return sr is not None and vosk is not None and pyaudio is not None

    def _handle_transcript(self, text: str) -> None:
        self._input_widget.set_text(text)
        self._submit_message(text)

    def archive_current_chat(self) -> None:
        if self._current_chat_archived or not self._current_chat_messages:
            return
        title = self._make_chat_title()
        self._sidebar.add_conversation(title, list(self._current_chat_messages))
        self._current_chat_archived = True

    def _load_conversation(self, messages: list[tuple[str, str]]) -> None:
        self.clear_history()
        for role, content in messages:
            self._render_message(role, content, track=True, play_tts=False)
        self._current_chat_archived = True

    def _make_chat_title(self) -> str:
        for role, content in self._current_chat_messages:
            if role == "user" and content.strip():
                return self._truncate_title(content)
        return self._truncate_title(self._current_chat_messages[0][1])

    def _truncate_title(self, text: str, limit: int = 38) -> str:
        cleaned = " ".join(text.split())
        return cleaned if len(cleaned) <= limit else f"{cleaned[:limit - 1]}…"

    def _toggle_sidebar(self) -> None:
        self._sidebar_visible = not self._sidebar_visible
        self._sidebar.setVisible(self._sidebar_visible)

    def _scroll_to_bottom(self) -> None:
        def _scroll():
            bar = self._scroll_area.verticalScrollBar()
            bar.setValue(bar.maximum())

        QTimer.singleShot(0, _scroll)

    def _show_thinking_bubble(self) -> None:
        if self._thinking_bubble:
            return
        self._thinking_bubble = ChatBubbleWidget("thinking...", False)
        self._message_layout.insertWidget(self._message_layout.count() - 1, self._thinking_bubble)
        self._scroll_to_bottom()

    def _clear_thinking_bubble(self) -> None:
        if not self._thinking_bubble:
            return
        self._thinking_bubble.setParent(None)
        self._thinking_bubble = None

    def _set_sleep_icon(self) -> None:
        icon_path = Path("assets/sprites/dog_sleeping.png")
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                self._header.set_sleep_icon(QIcon(pixmap))

    def _toggle_theme(self) -> None:
        self._theme_mode = "light" if self._theme_mode == "dark" else "dark"
        self._header.set_theme_icon("☀" if self._theme_mode == "dark" else "☾")
        self._apply_styles()

    def _apply_styles(self) -> None:
        if self._theme_mode == "light":
            self.setStyleSheet(
                """
                QWidget {
                    background-color: #f6f7fb;
                    color: #1f2937;
                    font-family: "Segoe UI";
                    font-size: 12px;
                }
                #sidebar {
                    background-color: #ffffff;
                    border-right: 1px solid #e5e7eb;
                    min-width: 240px;
                    max-width: 280px;
                }
                #sidebarTitle {
                    font-size: 14px;
                    font-weight: 600;
                }
                #primaryButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    padding: 8px 14px;
                    border-radius: 10px;
                }
                #primaryButton:hover {
                    background-color: #1d4ed8;
                }
                #historyList {
                    background-color: #f6f7fb;
                    border: 1px solid #e5e7eb;
                    border-radius: 12px;
                    padding: 6px;
                }
                #historyList::item:selected {
                    background-color: #e2e8f0;
                }
                #recentChatTitle {
                    color: #334155;
                }
                #deleteButton:hover {
                    background-color: #e2e8f0;
                    border-radius: 8px;
                }
                #header {
                    background-color: #ffffff;
                    border-bottom: 1px solid #e5e7eb;
                }
                #assistantName {
                    font-size: 14px;
                    font-weight: 600;
                }
                #avatar {
                    border-radius: 22px;
                    background-color: #e2e8f0;
                    color: #1f2937;
                    font-weight: 700;
                }
                #chatScroll {
                    background-color: #f6f7fb;
                }
                #chatScroll QWidget {
                    background-color: #f6f7fb;
                }
                #messageArea {
                    background-color: #f6f7fb;
                }
                #bubbleAssistant {
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-radius: 14px;
                }
                #bubbleUser {
                    background-color: #2563eb;
                    border-radius: 14px;
                    color: #ffffff;
                }
                #bubbleText {
                    font-size: 12px;
                    line-height: 1.4;
                    selection-background-color: #2563eb;
                    selection-color: #ffffff;
                }
                #inputContainer {
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    border-radius: 16px;
                    margin-left: 18px;
                    margin-right: 18px;
                }
                QLineEdit {
                    background-color: #ffffff;
                    border: 1px solid #e5e7eb;
                    padding: 10px 12px;
                    border-radius: 12px;
                }
                QToolButton {
                    background-color: #eef2ff;
                    border: 1px solid #e5e7eb;
                    border-radius: 10px;
                    padding: 6px 10px;
                }
                QToolButton:hover {
                    background-color: #e0e7ff;
                }
                #iconButton {
                    background-color: #eef2ff;
                    border-radius: 10px;
                    padding: 6px 10px;
                }
                """
            )
            return

        self.setStyleSheet(
            """
            QWidget {
                background-color: #0f1115;
                color: #e5e7eb;
                font-family: "Segoe UI";
                font-size: 12px;
            }
            #sidebar {
                background-color: #12151c;
                border-right: 1px solid #1f2430;
                min-width: 240px;
                max-width: 280px;
            }
            #sidebarTitle {
                font-size: 14px;
                font-weight: 600;
            }
            #primaryButton {
                background-color: #2f6fed;
                color: #ffffff;
                padding: 8px 14px;
                border-radius: 10px;
            }
            #primaryButton:hover {
                background-color: #3a7bff;
            }
            #historyList {
                background-color: #0f1115;
                border: 1px solid #1f2430;
                border-radius: 12px;
                padding: 6px;
            }
            #historyList::item {
                padding: 8px 10px;
                border-radius: 8px;
            }
            #historyList::item:selected {
                background-color: #1a2233;
            }
            #recentChatItem {
                background-color: transparent;
            }
            #recentChatTitle {
                color: #cbd5e1;
            }
            #deleteButton {
                background-color: transparent;
                border: none;
                padding: 2px 6px;
            }
            #deleteButton:hover {
                background-color: #273045;
                border-radius: 8px;
            }
            #header {
                background-color: #12151c;
                border-bottom: 1px solid #1f2430;
            }
            #assistantName {
                font-size: 14px;
                font-weight: 600;
            }
            #avatar {
                border-radius: 22px;
                background-color: #1a2233;
                color: #e5e7eb;
                font-weight: 700;
            }
            #chatScroll {
                background-color: #0f1115;
            }
            #chatScroll QWidget {
                background-color: #0f1115;
            }
            #messageArea {
                background-color: #0f1115;
            }
            #bubbleAssistant {
                background-color: #171b24;
                border: 1px solid #202534;
                border-radius: 14px;
            }
            #bubbleUser {
                background-color: #2f6fed;
                border-radius: 14px;
                color: #ffffff;
            }
            #bubbleText {
                font-size: 12px;
                line-height: 1.4;
                selection-background-color: #2f6fed;
                selection-color: #ffffff;
            }
            #inputContainer {
                background-color: #12151c;
                border: 1px solid #1f2430;
                border-radius: 16px;
                margin-left: 18px;
                margin-right: 18px;
            }
            QLineEdit {
                background-color: #0f1115;
                border: 1px solid #1f2430;
                padding: 10px 12px;
                border-radius: 12px;
            }
            QToolButton {
                background-color: #1a2233;
                border: 1px solid #273045;
                border-radius: 10px;
                padding: 6px 10px;
            }
            QToolButton:hover {
                background-color: #243049;
            }
            #iconButton {
                background-color: #1a2233;
                border-radius: 10px;
                padding: 6px 10px;
            }
            """
        )

    def _init_tts_engine(self):
        if not pyttsx3:
            return None
        try:
            return pyttsx3.init()
        except Exception:
            return None

    def _enqueue_tts(self, text: str) -> None:
        if not self._tts_engine:
            return
        self._tts_queue.put(text)

    def _tts_worker(self) -> None:
        while True:
            text = self._tts_queue.get()
            try:
                engine = self._tts_engine or self._init_tts_engine()
                if not engine:
                    continue
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except RuntimeError:
                engine = self._init_tts_engine()
                if not engine:
                    continue
                engine.say(text)
                engine.runAndWait()
                engine.stop()
