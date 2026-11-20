# -*- mode: python ; coding: utf-8 -*-
# PyInstaller: onedir-сборка Grasp (папка с Grasp.exe и зависимостями).
# onefile не используем: с PySide6 он распаковывается при каждом запуске.
#
#   pyinstaller grasp.spec --noconfirm      (обычно через build.py)

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
sys.path.insert(0, str(ROOT))
from grasp import __app_name__  # noqa: E402

PKG = ROOT / "grasp"

# Ресурсы внутри сборки лежат по тем же относительным путям, что и в
# исходниках (_internal/grasp/...), поэтому grasp.paths.resource_path()
# одинаково работает в обоих режимах.
datas = [
    (str(PKG / "resources"), "grasp/resources"),
    (str(PKG / "content"), "grasp/content"),
    # Alembic читает env.py и ревизии как файлы — кладём исходники.
    (str(PKG / "data" / "migrations"), "grasp/data/migrations"),
]

hiddenimports = (
    collect_submodules("keyring.backends")  # Windows Credential Manager
    + collect_submodules("alembic", filter=lambda name: ".testing" not in name)
    # env.py и ревизии Alembic грузятся как файлы — PyInstaller не видит их
    # импорты, перечисляем вручную.
    + ["logging.config", "sqlalchemy.dialects.sqlite", "PySide6.QtSvg", "PySide6.QtNetwork"]
)

excludes = [
    "tkinter", "pytest", "pytestqt", "PIL", "fontTools", "IPython", "numpy",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia", "PySide6.QtPdf", "PySide6.QtDesigner",
]  # fmt: skip

version_file = ROOT / "build" / "version_info.txt"
icon_file = PKG / "resources" / "icons" / "app.ico"

a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=__app_name__,
    debug=False,
    strip=False,
    upx=False,  # UPX + Qt DLL = ложные срабатывания антивирусов
    console=False,  # без консольного окна
    disable_windowed_traceback=False,
    icon=str(icon_file) if sys.platform == "win32" else None,
    version=str(version_file) if sys.platform == "win32" and version_file.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name=__app_name__,
)
