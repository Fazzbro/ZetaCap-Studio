# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=copy_metadata('imageio') + copy_metadata('imageio_ffmpeg') + copy_metadata('tqdm') + copy_metadata('moviepy') + collect_data_files('whisper') + collect_data_files('tiktoken') + collect_data_files('mediapipe') + [('*.ttf', '.'), ('*.OTF', '.'), ('icon.png', '.'), ('icon.ico', '.'), ('project/assets/*', 'assets'), ('project/ui/themes/*', 'project/ui/themes'), ('presets/*', 'presets'), ('D:\\ai_models\\opencv\\*.onnx', 'ai_models\\opencv'), ('D:\\ai_models\\whisper\\whisper\\*.pt', 'ai_models\\whisper\\whisper')],
    hiddenimports=['whisper_timestamped', 'moviepy', 'torchvision', 'torchvision.models.mobilenetv3', 'PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'project.mcp_server', 'project.services.preset_choreographer', 'project.services.color_grading', 'project.services.text_effect', 'pillow_lut'] + collect_submodules('mediapipe') + collect_submodules('mcp'),
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
    [],
    exclude_binaries=True,
    name='ZetaCap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ZetaCap',
)
