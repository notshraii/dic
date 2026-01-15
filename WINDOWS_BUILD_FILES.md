# Windows Build - Required Files

To build the Windows executable, you only need to copy these files to your Windows machine:

## Required Files (Copy these to Windows)

1. **update_dicom_tags.py** - Main script with GUI
2. **dcmutl.py** - Utility module (must be in same folder)
3. **build_windows.bat** - Build script (optional, but makes it easier)

## Quick Build Steps on Windows

### Method 1: Using the batch script (Easiest)

1. Copy the 3 files above to a folder on Windows
2. Double-click `build_windows.bat`
3. Wait for the build to complete
4. Find `DICOMTagUpdater.exe` in the `dist\` folder

### Method 2: Manual build

1. Copy `update_dicom_tags.py` and `dcmutl.py` to a folder on Windows
2. Open Command Prompt in that folder
3. Run these commands:

```cmd
pip install pyinstaller pydicom
pyinstaller --name=DICOMTagUpdater --onefile --windowed --add-data "dcmutl.py;." update_dicom_tags.py
```

4. Find `DICOMTagUpdater.exe` in the `dist\` folder

## What Gets Created

After building, you'll have:
- `dist\DICOMTagUpdater.exe` - The standalone executable (this is what you need)
- `build\` folder - Temporary build files (can be deleted)
- `DICOMTagUpdater.spec` - PyInstaller spec file (can be deleted)

## Notes

- The executable is standalone - no Python or dependencies needed to run it
- The `--windowed` flag means no console window will appear (GUI only)
- The executable will be quite large (~30-50MB) because it bundles Python and all dependencies
- Make sure `dcmutl.py` is in the same folder as `update_dicom_tags.py` when building

## Troubleshooting

**"Python is not recognized"**
- Install Python from python.org
- Make sure "Add Python to PATH" is checked during installation

**"No module named 'pydicom'"**
- Run: `pip install pydicom`

**"No module named 'dcmutl'"**
- Make sure `dcmutl.py` is in the same folder as `update_dicom_tags.py`

**Build succeeds but executable doesn't run**
- Try building with `--console` instead of `--windowed` to see error messages:
  ```cmd
  pyinstaller --name=DICOMTagUpdater --onefile --console --add-data "dcmutl.py;." update_dicom_tags.py
  ```
