"""
Drag-and-drop PDF page arranger.

Shows thumbnails of all pages in a scrollable grid. The user can:
  • Drag pages to reorder them.
  • Click to select (multi-select with Ctrl/Shift).
  • Right-click for a context menu (delete, rotate).

Emits ``order_changed(list[int])`` when the page order changes.
"""

from __future__ import annotations

from typing import List

import fitz
from PyQt6.QtCore import QByteArray, QMimeData, QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QDrag,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QImage,
    QMouseEvent,
    QPixmap,
)
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QGridLayout,
    QFrame,
)

import config


class PageThumb(QFrame):
    """Single page thumbnail card inside the arranger."""

    NORMAL_STYLE = (
        "QFrame { background: #252537; border: 2px solid #313244; border-radius: 6px; }"
    )
    SELECTED_STYLE = (
        "QFrame { background: #313244; border: 2px solid #7c6af5; border-radius: 6px; }"
    )
    DROP_STYLE = (
        "QFrame { background: #252537; border: 2px dashed #7c6af5; border-radius: 6px; }"
    )

    def __init__(
        self,
        index: int,
        pixmap: QPixmap,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.page_index = index
        self._selected = False
        self.setFrameShape(QFrame.Shape.Box)
        self.setFixedSize(config.THUMBNAIL_WIDTH + 16, config.THUMBNAIL_HEIGHT + 32)
        self.setStyleSheet(self.NORMAL_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        img_label = QLabel(self)
        img_label.setPixmap(pixmap)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setScaledContents(True)
        img_label.setFixedSize(config.THUMBNAIL_WIDTH, config.THUMBNAIL_HEIGHT)

        num_label = QLabel(str(index + 1), self)
        num_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_label.setStyleSheet("color: #6c7086; font-size: 11px; background: transparent;")

        layout.addWidget(img_label)
        layout.addWidget(num_label)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setStyleSheet(self.SELECTED_STYLE if selected else self.NORMAL_STYLE)

    def set_drop_target(self, active: bool) -> None:
        if not self._selected:
            self.setStyleSheet(self.DROP_STYLE if active else self.NORMAL_STYLE)


class PageArrangerWidget(QWidget):
    """Full page arranger with drag-and-drop reordering."""

    order_changed = pyqtSignal(list)  # list[int] – new 0-based page order
    pages_deleted = pyqtSignal(list)   # list[int] – deleted 0-based indices
    page_rotated = pyqtSignal(int, int)  # (page_index, degrees)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._thumbs: List[PageThumb] = []
        self._selected: List[int] = []  # indices into _thumbs
        self._drag_start: QPoint | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background: #1e1e2e; border: none;")

        self._container = QWidget()
        self._container.setStyleSheet("background: #1e1e2e;")
        self._grid = QGridLayout(self._container)
        self._grid.setSpacing(10)
        self._grid.setContentsMargins(12, 12, 12, 12)

        self._scroll.setWidget(self._container)
        outer.addWidget(self._scroll)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_pdf(self, path: str) -> None:
        """Load a PDF and display thumbnails for all its pages."""
        self._clear()
        with fitz.open(path) as doc:
            total = doc.page_count
            cols = max(1, self._scroll.viewport().width() // (config.THUMBNAIL_WIDTH + 30))
            for i, page in enumerate(doc):
                mat = fitz.Matrix(
                    config.THUMBNAIL_WIDTH / page.rect.width,
                    config.THUMBNAIL_HEIGHT / page.rect.height,
                )
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = QImage(
                    pix.samples, pix.width, pix.height, pix.stride,
                    QImage.Format.Format_RGB888,
                )
                thumb = PageThumb(i, QPixmap.fromImage(img), self._container)
                thumb.installEventFilter(self)
                self._thumbs.append(thumb)
                self._grid.addWidget(thumb, i // cols, i % cols)

    def get_current_order(self) -> List[int]:
        """Return the current page order as a list of original 0-based indices."""
        return [t.page_index for t in self._thumbs]

    # ------------------------------------------------------------------
    # Event filter (mouse events on thumbnails)
    # ------------------------------------------------------------------

    def eventFilter(self, source, event) -> bool:
        if not isinstance(source, PageThumb):
            return super().eventFilter(source, event)

        idx = self._thumbs.index(source)

        if event.type() == event.Type.MouseButtonPress:
            self._handle_click(idx, event)
            self._drag_start = event.position().toPoint()
            return True

        if event.type() == event.Type.MouseMove:
            if (
                self._drag_start is not None
                and (event.position().toPoint() - self._drag_start).manhattanLength()
                > QApplication.startDragDistance()
            ):
                self._start_drag(idx)
            return True

        if event.type() == event.Type.MouseButtonRelease:
            self._drag_start = None
            return True

        if event.type() == event.Type.ContextMenu:
            self._show_context_menu(idx, event.globalPosition().toPoint())
            return True

        return super().eventFilter(source, event)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _handle_click(self, idx: int, event: QMouseEvent) -> None:
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            if idx in self._selected:
                self._selected.remove(idx)
            else:
                self._selected.append(idx)
        elif mods & Qt.KeyboardModifier.ShiftModifier and self._selected:
            last = self._selected[-1]
            rng = range(min(last, idx), max(last, idx) + 1)
            for i in rng:
                if i not in self._selected:
                    self._selected.append(i)
        else:
            self._selected = [idx]
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        for i, thumb in enumerate(self._thumbs):
            thumb.set_selected(i in self._selected)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def _start_drag(self, source_idx: int) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(str(source_idx))
        drag.setMimeData(mime)

        thumb = self._thumbs[source_idx]
        drag.setPixmap(thumb.grab().scaled(80, 100, Qt.AspectRatioMode.KeepAspectRatio))
        drag.setHotSpot(QPoint(40, 50))

        result = drag.exec(Qt.DropAction.MoveAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.acceptProposedAction()
        target = self._thumb_at(event.position().toPoint())
        for i, thumb in enumerate(self._thumbs):
            thumb.set_drop_target(thumb is target)

    def dropEvent(self, event: QDropEvent) -> None:
        for thumb in self._thumbs:
            thumb.set_drop_target(False)

        try:
            src_idx = int(event.mimeData().text())
        except ValueError:
            return

        target = self._thumb_at(event.position().toPoint())
        if target is None or target is self._thumbs[src_idx]:
            return

        dst_idx = self._thumbs.index(target)
        thumb = self._thumbs.pop(src_idx)
        self._thumbs.insert(dst_idx, thumb)
        self._rebuild_grid()
        self.order_changed.emit(self.get_current_order())
        event.acceptProposedAction()

    def _thumb_at(self, pos: QPoint) -> PageThumb | None:
        child = self._container.childAt(
            self._container.mapFromParent(pos)
        )
        if isinstance(child, PageThumb):
            return child
        if child and isinstance(child.parent(), PageThumb):
            return child.parent()
        return None

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, idx: int, global_pos: QPoint) -> None:
        menu = QMenu(self)
        rot90 = QAction("Rotate 90°", self)
        rot180 = QAction("Rotate 180°", self)
        rot270 = QAction("Rotate 270°", self)
        delete = QAction("Delete Page", self)

        rot90.triggered.connect(lambda: self.page_rotated.emit(self._thumbs[idx].page_index, 90))
        rot180.triggered.connect(lambda: self.page_rotated.emit(self._thumbs[idx].page_index, 180))
        rot270.triggered.connect(lambda: self.page_rotated.emit(self._thumbs[idx].page_index, 270))
        delete.triggered.connect(lambda: self._delete_selected_or(idx))

        menu.addAction(rot90)
        menu.addAction(rot180)
        menu.addAction(rot270)
        menu.addSeparator()
        menu.addAction(delete)
        menu.exec(global_pos)

    def _delete_selected_or(self, fallback_idx: int) -> None:
        indices = self._selected if self._selected else [fallback_idx]
        page_indices = [self._thumbs[i].page_index for i in indices]
        for i in sorted(indices, reverse=True):
            self._thumbs.pop(i)
        self._selected = []
        self._rebuild_grid()
        self.pages_deleted.emit(page_indices)
        self.order_changed.emit(self.get_current_order())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rebuild_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        cols = max(1, self._scroll.viewport().width() // (config.THUMBNAIL_WIDTH + 30))
        for i, thumb in enumerate(self._thumbs):
            self._grid.addWidget(thumb, i // cols, i % cols)
        self._container.adjustSize()

    def _clear(self) -> None:
        self._thumbs.clear()
        self._selected.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
