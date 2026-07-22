# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# 只包含实际存在的数据目录
datas = []
for d in ['core', 'ui', 'libs']:
    if os.path.isdir(d):
        datas.append((d, d))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PIL', 'PIL.Image', 'PIL.ImageDraw', 'pystray'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Flet 相关（不再使用）
        'flet', 'flet_desktop', 'flet_core',
        # 大型不需要的库
        'numpy', 'matplotlib', 'IPython', 'pytest', 'black', 'jedi', 'zmq',
        'PyQt5', 'PySide6', 'pandas', 'scipy',
        'notebook', 'jupyter', 'pygments', 'sympy', 'sphinx', 'docutils',
        'babel', 'dateutil', 'pytz', 'chardet', 'rich',
        # Flutter/Flet 引擎相关
        'media_kit', 'rive', 'audioplayers', 'connectivity_plus',
        'flutter_secure_storage', 'geolocator', 'pasteboard',
        'permission_handler', 'screen_brightness', 'screen_retriever',
        'share_plus', 'url_launcher', 'window_manager', 'window_to_front',
        'battery_plus', 'record_windows',
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
    [],
    exclude_binaries=True,
    name='WindowLocker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if __import__('os').path.exists('icon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='WindowLocker',
)
