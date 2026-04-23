# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys


project_dir = Path(SPECPATH)
vendor_dir = project_dir / "_vendor"

if vendor_dir.exists():
    sys.path.insert(0, str(vendor_dir))


def collect_dir(dirname: str):
    source_dir = project_dir / dirname
    collected = []
    if not source_dir.exists():
        return collected
    for file_path in source_dir.rglob("*"):
        if not file_path.is_file():
            continue
        destination = str(file_path.parent.relative_to(project_dir))
        collected.append((str(file_path), destination))
    return collected


datas = []
datas += collect_dir("assets")
datas += collect_dir("discordrpc")
datas += collect_dir("bad_apple")
datas += collect_dir("_vendor")

for extra_name in ("editor_layout.json", "app_settings.json", "README.md", "icon.ico"):
    extra_path = project_dir / extra_name
    if extra_path.exists():
        datas.append((str(extra_path), "."))


a = Analysis(
    ["sg-editor.py"],
    pathex=[str(project_dir), str(vendor_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
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
    name="SGMEditor",
    icon=str(project_dir / "icon.ico") if (project_dir / "icon.ico").exists() else None,
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
