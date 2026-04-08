"""
Home tab – drop zone for quick file detection and action suggestions.
"""

from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QFrame,
)

from ui.widgets.drop_zone import DropZone
from utils.file_utils import detect_file_type, format_size
from utils.recent_files import RecentFiles


class ActionCard(QWidget):
    """A clickable suggestion card shown after a file is dropped."""

    clicked = pyqtSignal(str)  # emits action key

    def __init__(self, icon: str, title: str, description: str, action_key: str) -> None:
        super().__init__()
        self._action = action_key
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QWidget { background: #252537; border: 1px solid #313244; border-radius: 8px; }"
            "QWidget:hover { background: #313244; border-color: #7c6af5; }"
        )
        self.setFixedHeight(74)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 24px; background: transparent; border: none;")
        icon_lbl.setFixedWidth(36)

        text_col = QVBoxLayout()
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-weight: bold; font-size: 13px; background: transparent; border: none;"
        )
        desc_lbl = QLabel(description)
        desc_lbl.setStyleSheet(
            "color: #6c7086; font-size: 11px; background: transparent; border: none;"
        )
        text_col.addWidget(title_lbl)
        text_col.addWidget(desc_lbl)

        arrow = QLabel("→")
        arrow.setStyleSheet("color: #7c6af5; font-size: 16px; background: transparent; border: none;")

        layout.addWidget(icon_lbl)
        layout.addLayout(text_col)
        layout.addStretch()
        layout.addWidget(arrow)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._action)


class HomeTab(QWidget):
    """
    Home / dashboard tab.

    Signals
    -------
    navigate_to(str, list[str])  – request main window to switch tab & pre-load files.
    """

    navigate_to = pyqtSignal(str, list)

    def __init__(self, recent_files: RecentFiles, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._recent = recent_files
        self._dropped_files: List[str] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        # Heading
        heading = QLabel("Document Processor")
        heading.setObjectName("titleLabel")
        sub = QLabel("Drop a file to get started, or choose a tool from the sidebar.")
        sub.setObjectName("subtitleLabel")
        layout.addWidget(heading)
        layout.addWidget(sub)

        # Drop zone
        self._drop_zone = DropZone(
            "Drop PDF or DOCX files here\nor click Browse to select",
            accepted_extensions=[".pdf", ".docx", ".doc"],
        )
        self._drop_zone.setMinimumHeight(160)
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self._drop_zone)

        # Browse button
        browse_btn = QPushButton("Browse Files…")
        browse_btn.setObjectName("primaryButton")
        browse_btn.setFixedWidth(140)
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Suggested actions section
        self._actions_section = QWidget()
        self._actions_section.setVisible(False)
        actions_layout = QVBoxLayout(self._actions_section)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self._file_info_label = QLabel()
        self._file_info_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        actions_layout.addWidget(self._file_info_label)

        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(8)
        actions_layout.addLayout(self._cards_layout)

        layout.addWidget(self._actions_section)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Recent files section
        recent_lbl = QLabel("Recent Files")
        recent_lbl.setObjectName("sectionHeader")
        layout.addWidget(recent_lbl)

        self._recent_list = QListWidget()
        self._recent_list.setMaximumHeight(180)
        self._recent_list.itemDoubleClicked.connect(self._open_recent)
        layout.addWidget(self._recent_list)

        self._refresh_recent()
        layout.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_files_dropped(self, paths: List[str]) -> None:
        if not paths:
            return
        self._dropped_files = paths
        self._show_suggestions(paths)

    def _browse(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files",
            "",
            "Supported Files (*.pdf *.docx *.doc);;All Files (*)",
        )
        if paths:
            self._dropped_files = paths
            self._show_suggestions(paths)

    def _show_suggestions(self, paths: List[str]) -> None:
        """Display action cards based on the dropped file types."""
        # Clear old cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        file_type = detect_file_type(paths[0]) if paths else "unknown"
        count = len(paths)
        size_sum = sum(os.path.getsize(p) for p in paths if os.path.isfile(p))

        self._file_info_label.setText(
            f"{count} file(s) selected  •  {format_size(size_sum)}"
        )

        if file_type == "pdf":
            cards = [
                ("🔄", "Convert to DOCX", "Extract text and layout into Word format", "convert"),
                ("🔍", "OCR – Extract Text", "Recognise text in scanned PDFs", "ocr"),
                ("✂️", "Split PDF", "Divide into smaller files by page range", "pdf_tools"),
                ("🗜️", "Compress PDF", "Reduce file size with adjustable quality", "pdf_tools"),
                ("🔒", "Protect PDF", "Add password encryption", "pdf_tools"),
                ("📄", "Arrange Pages", "Reorder, rotate or delete pages", "pdf_tools"),
            ]
        elif file_type == "docx":
            cards = [
                ("🔄", "Convert to PDF", "Export as a PDF document", "convert"),
                ("🖼️", "Extract Images", "Save all embedded images", "docx_tools"),
                ("📸", "Convert to Images", "Render each page as an image", "docx_tools"),
            ]
        else:
            if file_type == "image":
                cards = [("🔍", "OCR – Extract Text", "Run OCR on this image", "ocr")]
            else:
                cards = []

        for icon, title, desc, action in cards:
            card = ActionCard(icon, title, desc, action)
            card.clicked.connect(self._on_card_clicked)
            self._cards_layout.addWidget(card)

        self._actions_section.setVisible(True)

        # Add to recent
        for p in paths:
            self._recent.add(p)
        self._refresh_recent()

    def _on_card_clicked(self, action: str) -> None:
        self.navigate_to.emit(action, self._dropped_files)

    def _open_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self._dropped_files = [path]
            self._show_suggestions([path])

    def _refresh_recent(self) -> None:
        self._recent_list.clear()
        for path in self._recent.get_all()[:10]:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._recent_list.addItem(item)
