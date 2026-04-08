"""
Main application window.

Layout
------
  ┌──────────┬──────────────────────────────────┐
  │          │  Title bar                        │
  │ Sidebar  ├──────────────────────────────────┤
  │  nav     │                                   │
  │ buttons  │   Stacked content panels          │
  │          │                                   │
  └──────────┴──────────────────────────────────┘
  │         Status bar                           │
  └──────────────────────────────────────────────┘
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize, QThreadPool
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QMessageBox,
    QFrame,
)

import config
from ui.home_tab import HomeTab
from ui.convert_tab import ConvertTab
from ui.ocr_tab import OCRTab
from ui.pdf_tools_tab import PDFToolsTab
from ui.docx_tools_tab import DocxToolsTab
from utils.recent_files import RecentFiles


class SidebarButton(QPushButton):
    """Checkable sidebar navigation button."""

    def __init__(self, icon: str, label: str, parent=None) -> None:
        super().__init__(f" {icon}  {label}", parent)
        self.setObjectName("sidebarButton")
        self.setCheckable(True)
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._recent = RecentFiles()
        self._setup_window()
        self._build_menu()
        self._build_ui()
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(config.APP_DISPLAY_NAME)
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)
        # Center on screen
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File menu
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

        # View menu
        view_menu = mb.addMenu("View")
        theme_act = QAction("Toggle Light/Dark Theme", self)
        theme_act.triggered.connect(self._toggle_theme)
        view_menu.addAction(theme_act)

        # Help menu
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

        # ---- Sidebar ----
        sidebar = self._build_sidebar()
        root.addWidget(sidebar)

        # Vertical separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Plain)
        sep.setStyleSheet("color: #313244;")
        root.addWidget(sep)

        # ---- Content stack ----
        self._stack = QStackedWidget()

        self._home_tab = HomeTab(self._recent)
        self._convert_tab = ConvertTab(self._recent)
        self._ocr_tab = OCRTab(self._recent)
        self._pdf_tools_tab = PDFToolsTab(self._recent)
        self._docx_tools_tab = DocxToolsTab(self._recent)

        self._stack.addWidget(self._home_tab)      # 0
        self._stack.addWidget(self._convert_tab)   # 1
        self._stack.addWidget(self._ocr_tab)       # 2
        self._stack.addWidget(self._pdf_tools_tab) # 3
        self._stack.addWidget(self._docx_tools_tab)# 4

        # Connect home tab navigation signal
        self._home_tab.navigate_to.connect(self._navigate_to)

        root.addWidget(self._stack, 1)

        # Activate first sidebar button
        self._sidebar_buttons[0].setChecked(True)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet("background: #181825;")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(4)

        # App brand
        brand = QLabel(config.APP_DISPLAY_NAME)
        brand.setStyleSheet(
            "color: #7c6af5; font-size: 14px; font-weight: bold; "
            "padding: 6px 8px 14px 8px; background: transparent;"
        )
        brand.setWordWrap(True)
        layout.addWidget(brand)

        # Navigation buttons
        nav_items = [
            ("🏠", "Home"),
            ("🔄", "Convert"),
            ("🔍", "OCR"),
            ("📄", "PDF Tools"),
            ("📝", "DOCX Tools"),
        ]

        self._sidebar_buttons: list[SidebarButton] = []
        for i, (icon, label) in enumerate(nav_items):
            btn = SidebarButton(icon, label, sidebar)
            btn.clicked.connect(lambda checked, idx=i: self._switch_tab(idx))
            self._sidebar_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Version label at bottom
        ver = QLabel(f"v{config.APP_VERSION}")
        ver.setStyleSheet("color: #45475a; font-size: 11px; padding: 4px 8px; background: transparent;")
        layout.addWidget(ver)

        return sidebar

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _switch_tab(self, index: int) -> None:
        for i, btn in enumerate(self._sidebar_buttons):
            btn.setChecked(i == index)
        self._stack.setCurrentIndex(index)

        names = ["Home", "Convert", "OCR", "PDF Tools", "DOCX Tools"]
        self._status_bar.showMessage(names[index])

    def _navigate_to(self, tab_key: str, files: list) -> None:
        """Handle navigation requests from the home tab."""
        tab_map = {
            "home": 0,
            "convert": 1,
            "ocr": 2,
            "pdf_tools": 3,
            "docx_tools": 4,
        }
        idx = tab_map.get(tab_key, 0)
        self._switch_tab(idx)

        # Pre-load files into the target tab
        if files:
            tab = self._stack.widget(idx)
            if hasattr(tab, "preload_files"):
                tab.preload_files(files)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open File", "",
            "Supported Files (*.pdf *.docx *.doc *.png *.jpg *.jpeg *.tiff *.bmp);;All Files (*)",
        )
        if paths:
            from utils.file_utils import detect_file_type
            file_type = detect_file_type(paths[0])
            if file_type == "pdf":
                self._navigate_to("pdf_tools", paths)
            elif file_type == "docx":
                self._navigate_to("convert", paths)
            elif file_type == "image":
                self._navigate_to("ocr", paths)
            else:
                self._home_tab._show_suggestions(paths)
                self._switch_tab(0)

    def _toggle_theme(self) -> None:
        QMessageBox.information(
            self, "Theme",
            "Dark theme is always active. Light theme will be available in a future update."
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            f"About {config.APP_DISPLAY_NAME}",
            f"<h3>{config.APP_DISPLAY_NAME}</h3>"
            f"<p>Version {config.APP_VERSION}</p>"
            "<p>A professional document processing tool supporting:</p>"
            "<ul>"
            "<li>PDF ↔ Word conversion</li>"
            "<li>OCR with Romanian &amp; Hungarian support</li>"
            "<li>PDF manipulation (split, merge, compress, …)</li>"
            "<li>DOCX tools</li>"
            "</ul>"
            "<p>Built with PyQt6, PyMuPDF, Tesseract &amp; LibreOffice.</p>"
        )

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        # Wait for any pending background tasks
        QThreadPool.globalInstance().waitForDone(3000)
        event.accept()
