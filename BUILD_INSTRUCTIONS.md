# Building DICOM Tag Updater Executable

This guide explains how to build a standalone executable from `update_dicom_tags.py` using PyInstaller.

**Note**: Executables are platform-specific. The executable built on macOS will only run on macOS. To build for Windows, you must build on a Windows machine. See `BUILD_WINDOWS.md` for Windows-specific instructions.

## Prerequisites

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Ensure all dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

## Building the Executable

### Option 1: Using the spec file (Recommended)

```bash
pyinstaller build_exe.spec
```

This will create a `dist/DICOMTagUpdater.exe` file (on Windows) or `dist/DICOMTagUpdater` (on macOS/Linux).

### Option 2: Using command line

For Windows:
```bash
pyinstaller --name=DICOMTagUpdater --onefile --windowed --add-data "dcmutl.py;." update_dicom_tags.py
```

For macOS/Linux:
```bash
pyinstaller --name=DICOMTagUpdater --onefile --windowed --add-data "dcmutl.py:." update_dicom_tags.py
```

### Option 3: Simple one-file build

```bash
pyinstaller --onefile --windowed update_dicom_tags.py
```

## Notes

- The `--windowed` flag (or `console=False` in spec file) hides the console window, which is appropriate for a GUI application.
- If you want to see console output for debugging, remove `--windowed` or set `console=True` in the spec file.
- The executable will be in the `dist/` directory after building.
- Make sure `dcmutl.py` is in the same directory as `update_dicom_tags.py` or adjust the paths accordingly.

## Testing

After building, test the executable:
1. Run the executable
2. Select a DICOM file or folder
3. Verify that tags can be edited and new tags can be added
4. Process the files and verify the output

## Troubleshooting

If you encounter import errors:
- Add missing modules to `hiddenimports` in the spec file
- Use `--hidden-import` flag in command line: `--hidden-import=module_name`

If the executable is large:
- The `--onefile` option bundles everything into a single file, which can be large
- Consider using `--onedir` instead to create a directory with multiple files (smaller, but requires all files to be distributed together)
