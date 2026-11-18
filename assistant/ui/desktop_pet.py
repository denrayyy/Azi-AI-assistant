"""Desktop pet widget that stays on top and supports animation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import random

from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal
from PyQt6.QtGui import QMouseEvent, QPixmap, QPainter, QColor, QTransform, QFontMetrics
from PyQt6.QtWidgets import QLabel, QWidget


@dataclass
class SpriteConfig:
    """Configuration for idle sprite animation."""

    frame_interval_ms: int = 200
    sprite_size: int = 72
    move_interval_ms: int = 80
    move_step_px: int = 2
    direction_change_ms: int = 2500
    sleep_after_ms: int = 0
    sleep_duration_ms: int = 30_000


class DesktopPet(QWidget):
    """Transparent always-on-top pet widget with optional speech bubble."""

    clicked = pyqtSignal()

    def __init__(self, sprite_dir: str = "assets/sprites", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._sprite_dir = Path(sprite_dir)
        self._config = SpriteConfig()
        self._frames: List[QPixmap] = []
        self._sprites: Dict[str, QPixmap] = {}
        self._walk_frames: List[Optional[QPixmap]] = []
        self._walk_up_frames: List[Optional[QPixmap]] = []
        self._walk_down_frames: List[Optional[QPixmap]] = []
        self._frame_index = 0
        self._drag_offset: Optional[QPoint] = None
        self._move_delta = QPoint(self._config.move_step_px, 0)
        self._state = "walk"
        self._chat_open = False
        self._hovered = False
        self._greeted = False
        self._manual_sleep = False

        self._sprite_label = QLabel(self)
        self._bubble_label = QLabel(self)

        self._load_frames()
        self._setup_window()
        self._setup_labels()
        self._start_animation()
        self._start_movement()
        self._start_direction_changes()
        self._schedule_sleep()

    def _setup_window(self) -> None:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        sprite_size = self._sprite_size()
        widget_width = 520
        widget_height = sprite_size + 180
        self.setFixedSize(widget_width, widget_height)

        screen = self.screen()
        if screen:
            geometry = screen.availableGeometry()
            x = geometry.right() - self.width() - 20
            y = geometry.bottom() - self.height() - 20
            self.move(x, y)

    def _setup_labels(self) -> None:
        sprite_size = self._sprite_size()
        self._sprite_label.setFixedSize(sprite_size, sprite_size)
        sprite_x = (self.width() - sprite_size) // 2
        sprite_y = self.height() - sprite_size - 20
        self._sprite_label.move(sprite_x, sprite_y)
        self._sprite_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._bubble_label.setWordWrap(True)
        self._bubble_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bubble_label.setStyleSheet(
            "background-color: rgba(255, 255, 255, 230);"
            "border: 1px solid #333333;"
            "border-radius: 8px;"
            "padding: 10px;"
            "color: #111111;"
            "font-size: 12px;"
        )
        self._bubble_label.hide()

    def _load_frames(self) -> None:
        base_dir = Path(__file__).resolve().parent.parent
        sprite_dir = self._sprite_dir if self._sprite_dir.is_absolute() else (base_dir / self._sprite_dir)
        if not sprite_dir.exists():
            return

        frame_files = sorted(sprite_dir.glob("*.png"))
        for frame in frame_files:
            pixmap = QPixmap(str(frame))
            if pixmap.isNull():
                continue
            self._frames.append(pixmap)
            key = frame.stem.lower().replace("-", "_")
            self._sprites[key] = pixmap

        self._walk_frames = [
            self._sprites.get("dog_walk1"),
            self._sprites.get("dog_walk2"),
        ]
        self._walk_up_frames = [
            self._sprites.get("dog_walk_up1"),
            self._sprites.get("dog_walk_up2"),
        ]
        self._walk_down_frames = [
            self._sprites.get("dog_walk_down1"),
            self._sprites.get("dog_walk_down2"),
        ]

    def _start_animation(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)
        self._timer.start(self._config.frame_interval_ms)

    def _advance_frame(self) -> None:
        sprite = self._current_sprite()
        if sprite is None:
            self._sprite_label.setPixmap(self._placeholder_pixmap())
            return

        sprite_size = self._sprite_size()
        frame = sprite.scaled(
            sprite_size,
            sprite_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if self._state == "walk" and self._move_delta.x() < 0:
            frame = frame.transformed(QTransform().scale(-1, 1))
        self._sprite_label.setPixmap(frame)

    def _start_movement(self) -> None:
        self._move_timer = QTimer(self)
        self._move_timer.timeout.connect(self._advance_position)
        self._move_timer.start(self._config.move_interval_ms)

    def _start_direction_changes(self) -> None:
        self._direction_timer = QTimer(self)
        self._direction_timer.timeout.connect(self._randomize_direction)
        self._direction_timer.start(self._config.direction_change_ms)

    def _advance_position(self) -> None:
        if self._drag_offset is not None:
            return

        if self._state != "walk":
            return

        if self._move_delta.x() == 0 and self._move_delta.y() == 0:
            self._randomize_direction()

        screen = self.screen()
        if not screen:
            return

        geometry = screen.availableGeometry()
        next_pos = self.pos() + self._move_delta

        if next_pos.x() <= geometry.left() or next_pos.x() + self.width() >= geometry.right():
            self._move_delta.setX(-self._move_delta.x())
            next_pos = self.pos() + self._move_delta

        if next_pos.y() <= geometry.top() or next_pos.y() + self.height() >= geometry.bottom():
            self._move_delta.setY(-self._move_delta.y())
            next_pos = self.pos() + self._move_delta

        self.move(next_pos)

    def _randomize_direction(self) -> None:
        if self._state != "walk" or self._drag_offset is not None:
            return

        directions = [
            QPoint(self._config.move_step_px, 0),
            QPoint(-self._config.move_step_px, 0),
            QPoint(0, self._config.move_step_px),
            QPoint(0, -self._config.move_step_px),
        ]
        self._move_delta = random.choice(directions)

    def _sprite_size(self) -> int:
        if self._frames:
            return max(40, min(self._frames[0].width(), 128))
        return self._config.sprite_size

    def _current_sprite(self) -> Optional[QPixmap]:
        if self._state == "happy":
            return self._sprites.get("dog_happy")
        if self._state == "idle":
            return self._sprites.get("dog_idle")
        if self._state == "sleep":
            return self._sprites.get("dog_sleeping")
        if self._state == "walk":
            if self._move_delta.y() < 0 and any(self._walk_up_frames):
                self._frame_index = (self._frame_index + 1) % len(self._walk_up_frames)
                return self._walk_up_frames[self._frame_index] or self._walk_up_frames[0]
            if self._move_delta.y() > 0 and any(self._walk_down_frames):
                self._frame_index = (self._frame_index + 1) % len(self._walk_down_frames)
                return self._walk_down_frames[self._frame_index] or self._walk_down_frames[0]
            if any(self._walk_frames):
                self._frame_index = (self._frame_index + 1) % len(self._walk_frames)
                return self._walk_frames[self._frame_index] or self._walk_frames[0]
        return self._frames[self._frame_index] if self._frames else None

    def _schedule_sleep(self) -> None:
        if self._config.sleep_after_ms <= 0:
            return
        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self._enter_sleep)
        self._sleep_timer.start(self._config.sleep_after_ms)

    def _enter_sleep(self) -> None:
        if self._manual_sleep:
            return
        if self._hovered or self._chat_open:
            self._schedule_sleep()
            return

        self._state = "sleep"
        QTimer.singleShot(self._config.sleep_duration_ms, self._wake_from_sleep)

    def _wake_from_sleep(self) -> None:
        if self._manual_sleep:
            return
        if self._hovered:
            self._state = "happy"
        elif self._chat_open:
            self._state = "idle"
        else:
            self._state = "walk"
        self._schedule_sleep()

    def _placeholder_pixmap(self) -> QPixmap:
        pixmap = QPixmap(self._config.sprite_size, self._config.sprite_size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor(255, 220, 120, 220))
        painter.setPen(QColor(100, 60, 20))
        size = self._config.sprite_size - 12
        painter.drawEllipse(6, 6, size, size)
        painter.end()
        return pixmap

    def show_speech(self, text: str, duration_ms: int = 3500) -> None:
        if not text:
            return

        self._bubble_label.setText(text)
        bubble_width = 400
        metrics = QFontMetrics(self._bubble_label.font())
        wrapped = metrics.boundingRect(
            0,
            0,
            bubble_width,
            1000,
            Qt.TextFlag.TextWordWrap,
            text,
        )
        bubble_height = wrapped.height() + 20
        self._bubble_label.setFixedSize(bubble_width, bubble_height)

        bubble_x = (self.width() - bubble_width) // 2
        bubble_y = max(10, self._sprite_label.y() - bubble_height - 10)
        self._bubble_label.move(bubble_x, bubble_y)
        self._bubble_label.show()
        self._bubble_label.raise_()

        QTimer.singleShot(duration_ms, self._bubble_label.hide)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:
        if self._state == "sleep":
            super().enterEvent(event)
            return

        self._hovered = True
        if not self._greeted:
            self.show_speech("Hi, my name is Azi.")
            self._greeted = True
        if not self._chat_open:
            self._state = "happy"
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._state == "sleep":
            super().leaveEvent(event)
            return

        self._hovered = False
        self._greeted = False
        if self._chat_open:
            self._state = "idle"
        elif self._state != "sleep":
            self._state = "walk"
        super().leaveEvent(event)

    def set_chat_open(self, open_state: bool) -> None:
        self._chat_open = open_state
        if self._chat_open:
            self._state = "idle"
        elif self._hovered:
            self._state = "happy"
        elif self._state != "sleep":
            self._state = "walk"

    def sleep(self) -> None:
        self._manual_sleep = True
        self._hovered = False
        self._greeted = False
        self._state = "sleep"

    def wake(self) -> None:
        self._manual_sleep = False
        if self._hovered:
            self._state = "happy"
        elif self._chat_open:
            self._state = "idle"
        else:
            self._state = "walk"
