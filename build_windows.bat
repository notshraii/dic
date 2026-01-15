@echo off
REM Simple Windows build script for DICOM Tag Updater
REM This script builds the executable on Windows

echo Building DICOM Tag Updater for Windows...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.12 or later
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

REM Install required packages
echo Installing required packages...
python -m pip install pydicom -q
if errorlevel 1 (
    echo ERROR: Failed to install pydicom
    pause
    exit /b 1
)

REM Build the executable
echo.
echo Building executable...
python -m PyInstaller --name=DICOMTagUpdater --onefile --windowed --add-data "dcmutl.py;." update_dicom_tags.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo Build complete!
echo Executable location: dist\DICOMTagUpdater.exe
echo.
pause
