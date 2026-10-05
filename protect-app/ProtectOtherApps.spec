# -*- mode: python ; coding: utf-8 -*-
# Portable Windows 10/11 x64 build for Protect Other Apps.

from PyInstaller.utils.hooks import collect_all

datas = [('app.png', '.'), ('app.ico', '.')]
binaries = []
hiddenimports = []

tmp_ret = collect_all('pystray')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_ret = collect_all('PIL')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='ProtectOtherApps',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX breaks on many PCs / triggers antivirus
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
    uac_admin=True,  # elevation needed to protect other apps reliably
    uac_uiaccess=False,
)
