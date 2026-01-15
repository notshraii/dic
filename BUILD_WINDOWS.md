# Building Windows Executable

To build a Windows `.exe` file, you need to build it **on a Windows machine**.

## Prerequisites on Windows

1. Install Python 3.12 (or compatible version)
2. Install PyInstaller:
   ```cmd
   pip install pyinstaller
   ```

3. Install project dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

## Building on Windows

### Option 1: Use the existing spec file

```cmd
pyinstaller build_exe.spec
```

This will create `dist\DICOMTagUpdater.exe`

### Option 2: Simple command-line build

```cmd
pyinstaller --name=DICOMTagUpdater --onefile --windowed --add-data "dcmutl.py;." update_dicom_tags.py
```

Note: On Windows, use semicolon (`;`) in `--add-data`, not colon (`:`)

### Option 3: Minimal build

```cmd
pyinstaller --onefile --windowed update_dicom_tags.py
```

## Notes for Windows

- The `--windowed` flag hides the console window (appropriate for GUI apps)
- The executable will be `DICOMTagUpdater.exe` in the `dist\` folder
- Make sure `dcmutl.py` is accessible (either in the same directory or included via `--add-data`)

## Alternative: Use GitHub Actions or CI/CD

If you don't have a Windows machine, you can use GitHub Actions or other CI/CD services to build the Windows executable automatically.

Example GitHub Actions workflow:

```yaml
name: Build Windows Executable

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: windows-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'
    - name: Install dependencies
      run: |
        pip install pyinstaller
        pip install -r requirements.txt
    - name: Build executable
      run: pyinstaller --onefile --windowed update_dicom_tags.py
    - name: Upload artifact
      uses: actions/upload-artifact@v2
      with:
        name: DICOMTagUpdater.exe
        path: dist/DICOMTagUpdater.exe
```
