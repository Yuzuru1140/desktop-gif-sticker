# -*- mode: python ; coding: utf-8 -*-
# One build, two outputs:
#   dist/DesktopSticker/              onedir app used by the installer (fast start, no temp extraction)
#   dist/DesktopSticker_Portable.exe  single-file portable version


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

common = dict(
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX is known to corrupt Qt DLLs, so never compress even if UPX gets installed
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app_icon.ico'],
)

# --- Onedir (installer) ---
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DesktopSticker',
    **common,
)
coll = COLLECT(
    exe_dir,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='DesktopSticker',
)

# --- Onefile (portable) ---
exe_portable = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DesktopSticker_Portable',
    runtime_tmpdir=None,
    **common,
)
