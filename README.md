# Document Processor

A production-ready desktop application for document processing and conversion on Windows.

## Features

| Category | Features |
|----------|----------|
| **Convert** | DOCX → PDF, PDF → DOCX, batch conversion |
| **OCR** | Romanian, Hungarian, English + more; auto-detect scanned PDFs |
| **PDF Tools** | Split, Merge, Compress, Extract Images/Text, Arrange Pages, Delete, Rotate, Watermark, Password |
| **DOCX Tools** | Extract images, Convert to images, Document info |
| **UX** | Drag & drop, dark theme, progress bars, recent files, PDF preview |

---

## Prerequisites

### 1. Python 3.10+
Download from https://www.python.org/downloads/

### 2. Tesseract OCR (required for OCR features)

**Windows installer:** https://github.com/UB-Mannheim/tesseract/wiki

Steps:
1. Download the installer (e.g. `tesseract-ocr-w64-setup-5.x.x.exe`)
2. Run the installer
3. During installation, **check the "Additional language data" option** and select:
   - `ron` – Romanian
   - `hun` – Hungarian
   - `eng` – English (usually pre-selected)
4. Default install path: `C:\Program Files\Tesseract-OCR\`

To verify: open a terminal and run:
```
tesseract --version
tesseract --list-langs
```
You should see `ron` and `hun` in the list.

### 3. LibreOffice (required for DOCX→PDF fallback and DOCX→Images)

**Download:** https://www.libreoffice.org/download/download/

Steps:
1. Download and install the latest stable release
2. Default install path: `C:\Program Files\LibreOffice\`

> **Note:** For DOCX→PDF conversion, if Microsoft Word is installed, `docx2pdf` will use it automatically (better formatting fidelity). LibreOffice is used as a fallback.

---

## Installation

### Step 1 – Clone or extract the project

```
cd C:\Users\your_name\Desktop\projekt
```

### Step 2 – Create a virtual environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3 – Install Python dependencies

```bash
pip install -r requirements.txt
```

> If you encounter issues with `PyMuPDF`, try:
> ```bash
> pip install --upgrade pymupdf
> ```

### Step 4 – Run the application

```bash
python main.py
```

---

## Project Structure

```
projekt/
├── main.py                    # Entry point
├── config.py                  # App-wide constants and paths
├── requirements.txt
├── README.md
│
├── assets/
│   └── styles/
│       └── dark_theme.qss     # Dark theme stylesheet
│
├── core/                      # Business logic (no UI)
│   ├── worker.py              # QThreadPool background worker
│   ├── pdf_tools.py           # All PDF operations (PyMuPDF)
│   ├── docx_tools.py          # DOCX operations (python-docx)
│   ├── converter.py           # DOCX ↔ PDF conversion
│   └── ocr_engine.py          # OCR via Tesseract
│
├── ui/                        # PyQt6 UI layer
│   ├── main_window.py         # Main window (sidebar + stacked pages)
│   ├── home_tab.py            # Home / drag-drop dashboard
│   ├── convert_tab.py         # File conversion
│   ├── ocr_tab.py             # OCR
│   ├── pdf_tools_tab.py       # All PDF tools
│   ├── docx_tools_tab.py      # DOCX tools
│   ├── page_arranger.py       # Drag-drop PDF page arranger
│   ├── pdf_preview.py         # PDF preview widget
│   └── widgets/
│       ├── drop_zone.py       # Drag & drop zone
│       ├── progress_widget.py # Progress dialog
│       └── file_list.py       # File list with add/remove
│
└── utils/
    ├── logger.py              # Rotating file + console logger
    ├── file_utils.py          # File helpers
    └── recent_files.py        # Recent files (JSON persistence)
```

---

## Building a Standalone Executable (Optional)

Install PyInstaller:
```bash
pip install pyinstaller
```

Build:
```bash
pyinstaller --noconfirm --onedir --windowed ^
  --add-data "assets;assets" ^
  --name "DocumentProcessor" ^
  main.py
```

The executable will be in `dist\DocumentProcessor\DocumentProcessor.exe`.

> Make sure Tesseract and LibreOffice are installed on the target machine, or bundle their binaries manually.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `TesseractNotFoundError` | Ensure Tesseract is installed and its path is in `config.TESSERACT_PATHS` |
| `ron` / `hun` language not found | Reinstall Tesseract and select those language packs |
| DOCX→PDF fails | Install LibreOffice or Microsoft Word |
| `pdf2docx` conversion is slow | Normal for large PDFs — uses multi-page analysis |
| Page arranger is empty | Load a PDF first using the "Load PDF…" button |
| High memory usage on large PDFs | Use the Compress or Split tool to reduce file size before processing |

---

## Logs

Application logs are stored at:
```
C:\Users\<username>\.docprocessor\logs\docprocessor.log
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| PyQt6 | GUI framework |
| PyMuPDF (fitz) | PDF rendering, manipulation |
| pypdf | PDF utilities |
| pdfplumber | PDF text extraction |
| python-docx | DOCX reading/writing |
| pytesseract | Tesseract OCR wrapper |
| Pillow | Image processing |
| docx2pdf | DOCX→PDF via Word/LibreOffice |
| pdf2docx | PDF→DOCX conversion |
