"""
Reusable file list widget.

Displays file names, sizes, and allows removing items. Supports drag-drop
addition of files.
"""

from __future__ import annotations

import os
from typing import List

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.file_utils import format_size


class FileListWidget(QWidget):
    """
    A list widget that shows file paths and lets the user add/remove them.

    Signals
    -------
    files_changed(list[str])  — emitted whenever the file list changes.
    """

    files_changed = pyqtSignal(list)

    def __init__(
        self,
        accepted_extensions: List[str] | None = None,
        allow_reorder: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accepted = [e.lower() for e in (accepted_extensions or [])]
        self._allow_reorder = allow_reorder
        self.setAcceptDrops(True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar row
        toolbar = QHBoxLayout()
        self._count_label = QLabel("No files added", self)
        self._count_label.setStyleSheet("color: #9399b2; font-size: 12px;")

        clear_btn = QPushButton("Clear All", self)
        clear_btn.setFixedWidth(80)
        clear_btn.clicked.connect(self.clear_files)

        toolbar.addWidget(self._count_label)
        toolbar.addStretch()
        toolbar.addWidget(clear_btn)

        # List
        self._list = QListWidget(self)
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        if self._allow_reorder:
            self._list.setDragDropMode(
                QListWidget.DragDropMode.InternalMove
            )

        # Bottom toolbar
        bottom = QHBoxLayout()
        remove_btn = QPushButton("Remove Selected", self)
        remove_btn.clicked.connect(self._remove_selected)
        bottom.addStretch()
        bottom.addWidget(remove_btn)

        layout.addLayout(toolbar)
        layout.addWidget(self._list)
        layout.addLayout(bottom)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_files(self, paths: List[str]) -> None:
        """Add files to the list, skipping duplicates and unsupported types."""
        existing = set(self.get_files())
        for path in paths:
            if path in existing:
                continue
            if self._accepted and not self._is_accepted(path):
                continue
            item = QListWidgetItem()
            size = format_size(os.path.getsize(path)) if os.path.isfile(path) else "?"
            item.setText(f"{os.path.basename(path)}  [{size}]")
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            self._list.addItem(item)
            existing.add(path)
        self._update_count()
        self.files_changed.emit(self.get_files())

    def get_files(self) -> List[str]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
        ]

    def clear_files(self) -> None:
        self._list.clear()
        self._update_count()
        self.files_changed.emit([])

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self._update_count()
        self.files_changed.emit(self.get_files())

    def _update_count(self) -> None:
        n = self._list.count()
        if n == 0:
            self._count_label.setText("No files added")
        elif n == 1:
            self._count_label.setText("1 file")
        else:
            self._count_label.setText(f"{n} files")

    # ------------------------------------------------------------------
    # Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [
            u.toLocalFile()
            for u in event.mimeData().urls()
            if u.isLocalFile()
        ]
        self.add_files(paths)
        event.acceptProposedAction()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_accepted(self, path: str) -> bool:
        return any(path.lower().endswith(ext) for ext in self._accepted)
