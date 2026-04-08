"""Application-wide configuration constants."""
import os
import tempfile

APP_NAME = "DocProcessor"
APP_VERSION = "1.0.0"
ORG_NAME = "DocProcessor"
APP_DISPLAY_NAME = "Document Processor"

# Supported file types
SUPPORTED_PDF = [".pdf"]
SUPPORTED_DOCX = [".docx", ".doc"]
SUPPORTED_IMAGES = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"]

# OCR Languages (display name -> tesseract code)
OCR_LANGUAGES = {
    "Romanian": "ron",
    "Hungarian": "hun",
    "English": "eng",
    "German": "deu",
    "French": "fra",
    "Spanish": "spa",
    "Italian": "ita",
}

# Default settings
DEFAULT_COMPRESSION_QUALITY = 75  # percent (1-100)
MAX_RECENT_FILES = 20
THREAD_COUNT = 4

# Thumbnail settings
THUMBNAIL_WIDTH = 120
THUMBNAIL_HEIGHT = 160

# Paths
TEMP_DIR = os.path.join(tempfile.gettempdir(), "docprocessor")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".docprocessor")
LOG_DIR = os.path.join(CONFIG_DIR, "logs")
RECENT_FILES_PATH = os.path.join(CONFIG_DIR, "recent_files.json")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")

# LibreOffice paths (Windows)
LIBREOFFICE_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]

# Tesseract paths (Windows)
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe".format(
        os.environ.get("USERNAME", "")
    ),
]
