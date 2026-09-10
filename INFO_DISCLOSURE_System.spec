# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_all

datas = [('app/templates', 'app/templates'), ('app/static', 'app/static'), ('data/models', 'data/models')]
binaries = []
hiddenimports = ['app.main', 'app.db', 'app.config', 'app.services.ai_client', 'app.services.request_processor', 'app.services.foia_core', 'app.services.local_ai_server', 'app.ai_runtime.api', 'app.ai_runtime.utils_text', 'xgboost', 'xgboost.sklearn']
datas += collect_data_files('xgboost')
binaries += collect_dynamic_libs('xgboost')
tmp_ret = collect_all('sklearn')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
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
    name='INFO_DISCLOSURE_System',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
