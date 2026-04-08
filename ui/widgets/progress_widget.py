"""
Progress dialog shown during long background operations.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ProgressDialog(QDialog):
    """
    Modal progress dialog with a status label and progress bar.

    Usage
    -----
        dlg = ProgressDialog("Converting files…", parent=self)
        worker.signals.progress.connect(dlg.set_progress)
        worker.signals.status.connect(dlg.set_status)
        worker.signals.finished.connect(dlg.accept)
        dlg.exec()
    """

    def __init__(
        self,
        title: str = "Processing…",
        cancelable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        self.setModal(True)
        self.setMinimumWidth(420)
        self._cancelled = False
        self._build_ui(cancelable)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self, cancelable: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 24, 24, 20)

        self._status_label = QLabel("Starting…", self)
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #cdd6f4; font-size: 13px;")

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setMinimumHeight(22)

        layout.addWidget(self._status_label)
        layout.addWidget(self._progress_bar)

        if cancelable:
            self._cancel_btn = QPushButton("Cancel", self)
            self._cancel_btn.clicked.connect(self._on_cancel)
            layout.addWidget(
                self._cancel_btn, alignment=Qt.AlignmentFlag.AlignRight
            )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def set_progress(self, value: int) -> None:
        self._progress_bar.setValue(value)

    def set_status(self, message: str) -> None:
        self._status_label.setText(message)

    def mark_indeterminate(self) -> None:
        """Switch to an indeterminate (animated) progress bar."""
        self._progress_bar.setRange(0, 0)

    def mark_done(self) -> None:
        self._progress_bar.setValue(100)

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        self._cancelled = True
        self.reject()

    @property
    def cancelled(self) -> bool:
        return self._cancelled
