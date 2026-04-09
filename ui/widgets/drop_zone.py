"""
Drag-and-drop file zone widget.
Emits ``files_dropped(list[str])`` when valid files are released onto it.
Validates files on drop – corrupted or unreadable files are silently skipped
with a warning shown in the status area.
"""
from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QColor, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


def _is_readable(path: str) -> bool:
    """Quick check: file exists, is non-empty, and can be opened for reading."""
    try:
        if not os.path.isfile(path):
            return False
        if os.path.getsize(path) == 0:
            return False
        with open(path, "rb") as fh:
            fh.read(16)
        return True
    except OSError:
        return False


class DropZone(QWidget):
    files_dropped = pyqtSignal(list)

    def __init__(
        self,
        label: str = "Drop files here\nor click to browse",
        accepted_extensions: List[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label_text = label
        self._accepted = [e.lower() for e in (accepted_extensions or [])]
        self._hovered = False
        self.setAcceptDrops(True)
        self.setMinimumHeight(110)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(4)

        self._icon_label = QLabel("📂")
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size:30px;background:transparent;")

        self._text_label = QLabel(self._label_text)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._text_label.setStyleSheet("color:#9aa0ac;font-size:12px;background:transparent;")

        self._warn_label = QLabel("")
        self._warn_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._warn_label.setStyleSheet("color:#d7ba7d;font-size:11px;background:transparent;")
        self._warn_label.setVisible(False)

        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        layout.addWidget(self._warn_label)

    def set_label(self, text: str) -> None:
        self._text_label.setText(text)

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and self._any_accepted(event.mimeData().urls()):
            self._hovered = True
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def dropEvent(self, event: QDropEvent) -> None:
        self._hovered = False
        self.update()
        self._warn_label.setVisible(False)

        valid, skipped = [], 0
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if not self._is_accepted(path):
                continue
            if _is_readable(path):
                valid.append(path)
            else:
                skipped += 1

        if skipped:
            self._warn_label.setText(
                f"⚠  {skipped} file(s) skipped (unreadable or empty)"
            )
            self._warn_label.setVisible(True)

        if valid:
            self.files_dropped.emit(valid)
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Paint – border rectangle
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QColor("#0078d4") if self._hovered else QColor("#3a3f4b")
        bg     = QColor("#252830") if self._hovered else QColor("#1e2025")
        pen = QPen(border, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(bg)
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 8, 8)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_accepted(self, path: str) -> bool:
        if not self._accepted:
            return True
        return any(path.lower().endswith(ext) for ext in self._accepted)

    def _any_accepted(self, urls) -> bool:
        return any(self._is_accepted(u.toLocalFile()) for u in urls if u.isLocalFile())
