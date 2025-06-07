# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[('\\Lib\\site-packages\\PySide6\\Qt6Core.dll', '.'), ('\\Lib\\site-packages\\PySide6\\Qt6Gui.dll', '.'), ('\\Lib\\site-packages\\PySide6\\Qt6Widgets.dll', '.'), ('\\Lib\\site-packages\\PySide6\\plugins\\platforms\\qwindows.dll', 'platforms'), ('\\Lib\\site-packages\\PySide6\\plugins\\imageformats\\qjpeg.dll', 'imageformats'), ('\\Lib\\site-packages\\PySide6\\plugins\\imageformats\\qgif.dll', 'imageformats')],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='BBH3ScanLunch',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['BHimage.ico'],
)
