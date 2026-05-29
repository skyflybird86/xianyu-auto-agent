# -*- mode: python ; coding: utf-8 -*-

import sys
import os

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
except NameError:
    current_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        ('prompts', 'prompts'),
        ('templates', 'templates'),
        ('chrome-extension', 'chrome-extension'),
        ('utils', 'utils'),
        ('data', 'data'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'flask',
        'flask_cors',
        'requests',
        'aiohttp',
        'websockets',
        'openai',
        'pydantic',
        'python_dotenv',
        'loguru',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='XianyuAutoBot',
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
    icon=None,
)

if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='XianyuAutoBot.app',
        icon=None,
        bundle_identifier=None,
    )
