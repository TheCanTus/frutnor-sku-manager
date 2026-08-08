# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[
        ('C:\\Program Files\\Python314\\python3.dll', '.'),
        ('C:\\Program Files\\Python314\\vcruntime140.dll', '.'),
        ('C:\\Program Files\\Python314\\vcruntime140_1.dll', '.'),
    ],
    datas=[('config.example.json', '.'), ('latest_version.json', '.')],
    hiddenimports=[
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.dialects.postgresql',
        'sqlalchemy.dialects.postgresql.psycopg2',
        'sqlalchemy.pool.impl',
        'sqlalchemy.sql.default_comparator',
        'psycopg2',
        'babel.numbers',
    ],
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
    name='SKU_Generator',
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
)
