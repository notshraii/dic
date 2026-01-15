# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['update_dicom_tags.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pydicom',
        'pydicom.datadict',
        'pydicom.uid',
        'pydicom.errors',
        'dcmutl',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pandas',
        'torch',
        'matplotlib',
        'scipy',
        'sklearn',
        'tensorflow',
        'keras',
        'pyarrow',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DICOMTagUpdater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False to hide console window for GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # You can add an icon file path here if you have one
)
