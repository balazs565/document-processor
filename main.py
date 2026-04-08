"""
Document Processor – application entry point.
"""

import os
import sys

# Ensure the project root is in PYTHONPATH when run directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

import config
from utils.logger import setup_logger


def main() -> int:
    logger = setup_logger()
    logger.info("Starting %s %s", config.APP_DISPLAY_NAME, config.APP_VERSION)

    # Ensure required directories exist
    os.makedirs(config.CONFIG_DIR, exist_ok=True)
    os.makedirs(config.TEMP_DIR, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationDisplayName(config.APP_DISPLAY_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setOrganizationName(config.ORG_NAME)

    # Default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Load dark theme stylesheet
    style_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "assets", "styles", "dark_theme.qss",
    )
    if os.path.isfile(style_path):
        with open(style_path, "r", encoding="utf-8") as fh:
            app.setStyleSheet(fh.read())
    else:
        logger.warning("Stylesheet not found: %s", style_path)

    # Import here to avoid issues before QApplication exists
    from ui.main_window import MainWindow

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    logger.info("Application exited with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
