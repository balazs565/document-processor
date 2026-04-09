@echo off
setlocal enabledelayedexpansion
title PDF Editor – Build Script

echo.
echo  ============================================
echo   PDF Editor – Build Pipeline
echo  ============================================
echo.

:: ── Step 1: Activate virtual environment ────────────────────────────
if exist "venv\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [1/4] No venv found – using system Python
)

:: ── Step 2: Install / upgrade dependencies ──────────────────────────
echo [2/4] Installing dependencies...
pip install -r requirements.txt --quiet
pip install pyinstaller --quiet

:: ── Step 3: Build with PyInstaller ──────────────────────────────────
echo [3/4] Building executable with PyInstaller...
pyinstaller DocumentProcessor.spec --noconfirm --clean

if errorlevel 1 (
    echo.
    echo  ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo  PyInstaller build complete.
echo  Output: dist\PDFEditor\PDFEditor.exe
echo.

:: ── Step 4: Inno Setup installer (optional) ─────────────────────────
echo [4/4] Looking for Inno Setup to build installer...

set ISCC=
for %%p in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
) do (
    if exist %%p set ISCC=%%p
)

if defined ISCC (
    echo     Found Inno Setup at !ISCC!
    echo     Compiling installer...
    !ISCC! installer\setup.iss
    if errorlevel 1 (
        echo  WARNING: Inno Setup compilation failed.
    ) else (
        echo  Installer: installer\Output\PDFEditor_Setup.exe
    )
) else (
    echo     Inno Setup not found – skipping installer creation.
    echo     Install from: https://jrsoftware.org/isinfo.php
)

:: ── Done ─────────────────────────────────────────────────────────────
echo.
echo  ============================================
echo   Build complete!
echo.
echo   Executable : dist\PDFEditor\PDFEditor.exe
if defined ISCC (
echo   Installer  : installer\Output\PDFEditor_Setup.exe
)
echo  ============================================
echo.

:: Open dist folder
explorer dist\PDFEditor

pause
