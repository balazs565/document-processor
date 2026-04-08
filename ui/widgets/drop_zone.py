"""
Drag-and-drop file zone widget.
Emits ``files_dropped(list[str])`` when files are released onto it.
"""

from __future__ import annotations

from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QColor, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DropZone(QWidget):
    """A bordered area the user can drop files onto."""

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
        self.setMinimumHeight(140)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel("📂", self)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setStyleSheet("font-size: 36px; background: transparent;")

        self._text_label = QLabel(self._label_text, self)
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setWordWrap(True)
        self._text_label.setStyleSheet(
            "color: #9399b2; font-size: 13px; background: transparent;"
        )

        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)

    def set_label(self, text: str) -> None:
        self._text_label.setText(text)

    # ------------------------------------------------------------------
    # Drag & Drop events
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if self._any_accepted(urls):
                self._hovered = True
                self.update()
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._hovered = False
        self.update()

    def dropEvent(self, event: QDropEvent) -> None:
        self._hovered = False
        self.update()
        paths = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if self._is_accepted(path):
                    paths.append(path)
        if paths:
            self.files_dropped.emit(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        border_color = QColor("#7c6af5") if self._hovered else QColor("#44465a")
        bg_color = QColor("#2a2a3e") if self._hovered else QColor("#1e1e2e")

        pen = QPen(border_color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 10, 10)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_accepted(self, path: str) -> bool:
        if not self._accepted:
            return True
        return any(path.lower().endswith(ext) for ext in self._accepted)

    def _any_accepted(self, urls) -> bool:
        if not self._accepted:
            return True
        return any(self._is_accepted(u.toLocalFile()) for u in urls if u.isLocalFile())
