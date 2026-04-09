"""
Main application window – refined sidebar + stacked content.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize, QThreadPool
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

import config
from ui.home_tab import HomeTab
from ui.convert_tab import ConvertTab
from ui.ocr_tab import OCRTab
from ui.pdf_tools_tab import PDFToolsTab
from ui.docx_tools_tab import DocxToolsTab
from ui.pdf_edit_tab import PDFEditTab
from utils.recent_files import RecentFiles


# ---------------------------------------------------------------------------
# Sidebar button
# ---------------------------------------------------------------------------

class NavButton(QPushButton):
    """Checkable sidebar navigation entry."""

    def __init__(self, icon: str, label: str, parent=None) -> None:
        super().__init__(parent)
        self._icon_ch = icon
        self._label = label
        self._update_text(False)
        self.setObjectName("sidebarButton")
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _update_text(self, collapsed: bool) -> None:
        self.setText(self._icon_ch if collapsed else f"  {self._icon_ch}  {self._label}")

    def set_collapsed(self, collapsed: bool) -> None:
        self._update_text(collapsed)
        self.setFixedWidth(52 if collapsed else 16_777_215)


# ---------------------------------------------------------------------------
# Section label inside sidebar
# ---------------------------------------------------------------------------

class SidebarSection(QLabel):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(text.upper(), parent)
        self.setObjectName("sectionHeader")
        self.setContentsMargins(14, 10, 0, 4)
        self._full_text = text.upper()

    def set_collapsed(self, collapsed: bool) -> None:
        self.setVisible(not collapsed)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._recent = RecentFiles()
        self._sidebar_collapsed = False
        self._setup_window()
        self._build_menu()
        self._build_ui()
        self._status = QStatusBar()
        self._status.setSizeGripEnabled(False)
        self.setStatusBar(self._status)
        self._status.showMessage("Ready")

    # ------------------------------------------------------------------
    # Window
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(config.APP_DISPLAY_NAME)
        self.setMinimumSize(1080, 680)
        self.resize(1280, 800)
        screen = self.screen()
        if screen:
            g = screen.availableGeometry()
            self.move(g.center().x() - self.width() // 2,
                      g.center().y() - self.height() // 2)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("File")
        open_act = QAction("Open File…", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self._open_file)
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        exit_act = QAction("Exit", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        view_menu = mb.addMenu("View")
        collapse_act = QAction("Toggle Sidebar", self)
        collapse_act.setShortcut("Ctrl+B")
        collapse_act.triggered.connect(self._toggle_sidebar)
        view_menu.addAction(collapse_act)

        help_menu = mb.addMenu("Help")
        about_act = QAction("About", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    # ------------------------------------------------------------------
    # Central widget
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self._sidebar_widget = self._build_sidebar()
        root.addWidget(self._sidebar_widget)

        # Thin vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedWidth(1)
        div.setStyleSheet("background:#3a3f4b;")
        root.addWidget(div)

        # Content stack
        self._stack = QStackedWidget()

        self._home_tab       = HomeTab(self._recent)
        self._convert_tab    = ConvertTab(self._recent)
        self._ocr_tab        = OCRTab(self._recent)
        self._pdf_tools_tab  = PDFToolsTab(self._recent)
        self._pdf_edit_tab   = PDFEditTab(self._recent)
        self._docx_tools_tab = DocxToolsTab(self._recent)

        for tab in (self._home_tab, self._convert_tab, self._ocr_tab,
                    self._pdf_tools_tab, self._pdf_edit_tab, self._docx_tools_tab):
            self._stack.addWidget(tab)

        self._home_tab.navigate_to.connect(self._navigate_to)

        root.addWidget(self._stack, 1)
        self._nav_buttons[0].setChecked(True)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        sidebar.setStyleSheet("QWidget#sidebar { background:#1a1d23; border-right:1px solid #3a3f4b; }")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(2)

        # Brand row
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(6, 0, 0, 0)
        self._brand_label = QLabel("PDF Editor")
        self._brand_label.setStyleSheet(
            "color:#e8eaed; font-size:15px; font-weight:700; "
            "letter-spacing:-0.3px; background:transparent;"
        )
        collapse_btn = QPushButton("‹")
        collapse_btn.setFixedSize(24, 24)
        collapse_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#5c6370;font-size:14px;}"
            "QPushButton:hover{color:#e8eaed;}"
        )
        collapse_btn.clicked.connect(self._toggle_sidebar)
        brand_row.addWidget(self._brand_label)
        brand_row.addStretch()
        brand_row.addWidget(collapse_btn)
        layout.addLayout(brand_row)

        # Spacer
        sp = QFrame(); sp.setFixedHeight(1)
        sp.setStyleSheet("background:#3a3f4b; margin: 8px 0;")
        layout.addWidget(sp)

        # Nav items:  (icon, label, tab_index, section_label_before)
        items = [
            (None, "GENERAL", None),
            ("🏠", "Home",       0),
            ("🔄", "Convert",    1),
            ("🔍", "OCR",        2),
            (None, "PDF", None),
            ("📄", "PDF Tools",  3),
            ("✏️", "PDF Edit",   4),
            (None, "DOCUMENTS", None),
            ("📝", "DOCX Tools", 5),
        ]

        self._nav_buttons: list[NavButton] = []
        self._section_labels: list[SidebarSection] = []

        for entry in items:
            if entry[0] is None:
                lbl = SidebarSection(entry[1])
                self._section_labels.append(lbl)
                layout.addWidget(lbl)
            else:
                icon, label, idx = entry
                btn = NavButton(icon, label)
                btn.clicked.connect(lambda checked, i=idx: self._switch_tab(i))
                self._nav_buttons.append(btn)
                layout.addWidget(btn)

        layout.addStretch()

        # Version
        self._ver_label = QLabel(f"v{config.APP_VERSION}")
        self._ver_label.setStyleSheet(
            "color:#5c6370; font-size:11px; padding:4px 8px; background:transparent;"
        )
        layout.addWidget(self._ver_label)

        return sidebar

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _switch_tab(self, index: int) -> None:
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)
        self._stack.setCurrentIndex(index)
        names = ["Home", "Convert", "OCR", "PDF Tools", "PDF Edit", "DOCX Tools"]
        self._status.showMessage(names[index] if index < len(names) else "")

    def _navigate_to(self, tab_key: str, files: list) -> None:
        key_map = {
            "home": 0, "convert": 1, "ocr": 2,
            "pdf_tools": 3, "pdf_edit": 4, "docx_tools": 5,
        }
        idx = key_map.get(tab_key, 0)
        self._switch_tab(idx)
        if files:
            tab = self._stack.widget(idx)
            if hasattr(tab, "preload_files"):
                tab.preload_files(files)

    # ------------------------------------------------------------------
    # Sidebar collapse
    # ------------------------------------------------------------------

    def _toggle_sidebar(self) -> None:
        self._sidebar_collapsed = not self._sidebar_collapsed
        w = 52 if self._sidebar_collapsed else 210
        self._sidebar_widget.setFixedWidth(w)
        self._brand_label.setVisible(not self._sidebar_collapsed)
        self._ver_label.setVisible(not self._sidebar_collapsed)
        for lbl in self._section_labels:
            lbl.set_collapsed(self._sidebar_collapsed)
        for btn in self._nav_buttons:
            btn.set_collapsed(self._sidebar_collapsed)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        from utils.file_utils import detect_file_type
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open File", "",
            "Supported Files (*.pdf *.docx *.doc *.png *.jpg *.jpeg *.tiff *.bmp);;All Files (*)",
        )
        if not paths:
            return
        ftype = detect_file_type(paths[0])
        if ftype == "pdf":
            self._navigate_to("pdf_tools", paths)
        elif ftype == "docx":
            self._navigate_to("convert", paths)
        elif ftype == "image":
            self._navigate_to("ocr", paths)
        else:
            self._home_tab._show_suggestions(paths)
            self._switch_tab(0)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {config.APP_DISPLAY_NAME}",
            f"<h3>{config.APP_DISPLAY_NAME}</h3>"
            f"<p>Version {config.APP_VERSION}</p>"
            "<p>Professional document processing suite:</p>"
            "<ul>"
            "<li>PDF ↔ Word conversion</li>"
            "<li>OCR – Romanian &amp; Hungarian</li>"
            "<li>PDF tools (split, merge, compress, …)</li>"
            "<li>PDF annotation &amp; editing</li>"
            "<li>DOCX tools</li>"
            "</ul>"
            "<p>Built with PyQt6 · PyMuPDF · Tesseract · LibreOffice</p>",
        )

    # ------------------------------------------------------------------
    # Close
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        QThreadPool.globalInstance().waitForDone(3000)
        event.accept()
