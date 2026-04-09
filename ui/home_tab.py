"""
Home / dashboard tab with drag-drop + smart action cards.
"""
from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.widgets.drop_zone import DropZone
from utils.file_utils import detect_file_type, format_size
from utils.recent_files import RecentFiles


# ---------------------------------------------------------------------------
# Action card
# ---------------------------------------------------------------------------

class ActionCard(QWidget):
    clicked = pyqtSignal(str)

    def __init__(self, icon: str, title: str, desc: str, action_key: str) -> None:
        super().__init__()
        self._action = action_key
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(68)
        self.setStyleSheet(
            "QWidget{background:#252830;border:1px solid #3a3f4b;border-radius:6px;}"
            "QWidget:hover{background:#2d3139;border-color:#0078d4;}"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedWidth(32)
        icon_lbl.setStyleSheet("font-size:22px;background:transparent;border:none;")

        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("font-weight:600;font-size:13px;background:transparent;border:none;")
        d = QLabel(desc)
        d.setStyleSheet("color:#9aa0ac;font-size:11px;background:transparent;border:none;")
        col.addWidget(t)
        col.addWidget(d)

        arrow = QLabel("›")
        arrow.setStyleSheet("color:#0078d4;font-size:18px;background:transparent;border:none;")

        row.addWidget(icon_lbl)
        row.addLayout(col)
        row.addStretch()
        row.addWidget(arrow)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._action)


# ---------------------------------------------------------------------------
# Tab
# ---------------------------------------------------------------------------

class HomeTab(QWidget):
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
        # Outer layout holds only the scroll area — no collapsing
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # Heading
        heading = QLabel("PDF Editor")
        heading.setObjectName("titleLabel")
        sub = QLabel("Drop a file below to get started, or pick a tool from the sidebar.")
        sub.setObjectName("subtitleLabel")
        layout.addWidget(heading)
        layout.addWidget(sub)

        # Drop zone — fixed height so it never collapses
        self._drop_zone = DropZone(
            "Drop PDF or Word files here\nor click Browse to select",
            accepted_extensions=[".pdf", ".docx", ".doc"],
        )
        self._drop_zone.setMinimumHeight(150)
        self._drop_zone.setMaximumHeight(190)
        self._drop_zone.files_dropped.connect(self._on_files_dropped)
        layout.addWidget(self._drop_zone)

        # Browse button
        browse_btn = QPushButton("Browse Files…")
        browse_btn.setObjectName("primaryButton")
        browse_btn.setFixedWidth(150)
        browse_btn.clicked.connect(self._browse)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        # Divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("background:#3a3f4b;max-height:1px;")
        layout.addWidget(div)

        # Suggested actions — always present, hidden until files arrive
        self._file_info = QLabel()
        self._file_info.setStyleSheet("color:#9aa0ac;font-size:12px;")
        self._file_info.setVisible(False)
        layout.addWidget(self._file_info)

        self._cards_container = QWidget()
        self._cards_container.setVisible(False)
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(8)
        layout.addWidget(self._cards_container)

        # Recent files
        recent_lbl = QLabel("Recent Files")
        recent_lbl.setObjectName("sectionHeader")
        layout.addWidget(recent_lbl)

        self._recent_list = QListWidget()
        self._recent_list.setMaximumHeight(170)
        self._recent_list.setAlternatingRowColors(True)
        self._recent_list.itemDoubleClicked.connect(self._open_recent)
        layout.addWidget(self._recent_list)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._refresh_recent()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_files_dropped(self, paths: List[str]) -> None:
        self._dropped_files = paths
        self._show_suggestions(paths)

    def _browse(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Files", "",
            "Supported Files (*.pdf *.docx *.doc);;All Files (*)",
        )
        if paths:
            self._dropped_files = paths
            self._show_suggestions(paths)

    def _show_suggestions(self, paths: List[str]) -> None:
        # Clear old cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        ftype = detect_file_type(paths[0]) if paths else "unknown"
        total = sum(os.path.getsize(p) for p in paths if os.path.isfile(p))
        self._file_info.setText(
            f"{len(paths)} file(s) selected  ·  {format_size(total)}"
        )
        self._file_info.setVisible(True)

        if ftype == "pdf":
            cards = [
                ("🔄", "Convert to DOCX",   "Extract text and layout into Word format",    "convert"),
                ("🔍", "OCR – Extract Text", "Recognise text in scanned PDFs",              "ocr"),
                ("✏️", "Edit PDF",           "Add annotations, text overlays and stamps",   "pdf_edit"),
                ("✂️", "Split PDF",          "Divide by page range",                        "pdf_tools"),
                ("🗜️", "Compress PDF",       "Reduce file size with adjustable quality",    "pdf_tools"),
                ("🔒", "Protect PDF",        "Add password encryption",                     "pdf_tools"),
            ]
        elif ftype == "docx":
            cards = [
                ("🔄", "Convert to PDF",   "Export as a PDF document",                    "convert"),
                ("🖼️", "Extract Images",   "Save all embedded images",                    "docx_tools"),
                ("📸", "Convert to Images","Render each page as a PNG",                   "docx_tools"),
            ]
        elif ftype == "image":
            cards = [("🔍", "OCR – Extract Text", "Run OCR on this image", "ocr")]
        else:
            cards = []

        for icon, title, desc, action in cards:
            card = ActionCard(icon, title, desc, action)
            card.clicked.connect(self._on_card_clicked)
            self._cards_layout.addWidget(card)

        self._cards_container.setVisible(bool(cards))

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
        for path in self._recent.get_all()[:12]:
            item = QListWidgetItem(f"  {os.path.basename(path)}")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._recent_list.addItem(item)
