"""Сборка одной командой: тесты → Grasp.exe (onedir) → проверка сборки →
установщик GraspSetup.exe → портативный zip. Всё готовое — в dist/.

    python build.py                    # всё
    python build.py --skip-ui-matrix   # без долгой матрицы скриншотов
    python build.py --skip-tests       # только сборка

На Windows нужен Inno Setup 6 (ISCC.exe в PATH или в Program Files).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
DIST = ROOT / "dist"
PYI_DIST = BUILD / "pyinstaller"
IS_WIN = sys.platform == "win32"

sys.path.insert(0, str(ROOT))
from grasp import __app_name__, __description__, __publisher__, __version__  # noqa: E402

VERSION_INFO = """# Сгенерировано build.py — не редактировать.
VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041904B0', [
      StringStruct('CompanyName', '{publisher}'),
      StringStruct('FileDescription', '{description}'),
      StringStruct('FileVersion', '{version}'),
      StringStruct('InternalName', '{name}'),
      StringStruct('LegalCopyright', '© {year} {publisher}'),
      StringStruct('OriginalFilename', '{name}.exe'),
      StringStruct('ProductName', '{name}'),
      StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [0x0419, 1200])])
  ]
)
"""


def step(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


def run(cmd: list[str], env: dict | None = None) -> None:
    print("$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def run_tests(skip_ui_matrix: bool) -> None:
    step("Тесты")
    env = dict(os.environ)
    if skip_ui_matrix:
        env["GRASP_SKIP_UI_MATRIX"] = "1"
    run([sys.executable, "-m", "pytest", "-q"], env)


def write_version_info() -> Path:
    parts = [int(x) for x in __version__.split(".")] + [0] * 4
    path = BUILD / "version_info.txt"
    BUILD.mkdir(exist_ok=True)
    path.write_text(
        VERSION_INFO.format(
            t=tuple(parts[:4]),
            version=__version__,
            name=__app_name__,
            publisher=__publisher__,
            description=__description__,
            year=time.localtime().tm_year,
        ),
        encoding="utf-8",
    )
    return path


def build_exe() -> Path:
    step("PyInstaller (onedir)")
    icon = ROOT / "grasp" / "resources" / "icons" / "app.ico"
    if not icon.exists():
        run([sys.executable, "tools/make_icon.py"])
    write_version_info()
    run(
        [
            sys.executable, "-m", "PyInstaller", "grasp.spec", "--noconfirm", "--clean",
            "--distpath", str(PYI_DIST), "--workpath", str(BUILD / "work"),
        ]
    )  # fmt: skip
    app_dir = PYI_DIST / __app_name__
    exe = app_dir / (f"{__app_name__}.exe" if IS_WIN else __app_name__)
    if not exe.exists():
        raise SystemExit(f"Не найден {exe}")
    return app_dir


def smoke_test(app_dir: Path) -> None:
    """Запуск собранного приложения: все экраны, темы, F11 — и выход."""
    step("Проверка сборки (smoke-test)")
    exe = app_dir / (f"{__app_name__}.exe" if IS_WIN else __app_name__)
    out = BUILD / "smoke.json"
    out.unlink(missing_ok=True)
    env = dict(os.environ, GRASP_DATA_DIR=str(BUILD / "smoke-data"))
    env.pop("PYTHONPATH", None)
    if not IS_WIN:
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
    subprocess.run([str(exe), "--smoke-test", "--smoke-out", str(out)], env=env, timeout=180, check=False)
    if not out.exists():
        raise SystemExit("smoke-test: приложение не записало результат (см. build/smoke-data/logs)")
    result = json.loads(out.read_text("utf-8"))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok") or not result.get("frozen"):
        raise SystemExit("smoke-test не пройден")


def find_iscc() -> str | None:
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidate = Path(base) / "Inno Setup 6" / "ISCC.exe"
            if candidate.exists():
                return str(candidate)
    return None


def build_installer(app_dir: Path) -> Path | None:
    step("Установщик (Inno Setup)")
    if not IS_WIN:
        print("Пропущено: Inno Setup работает только на Windows.")
        return None
    iscc = find_iscc()
    if not iscc:
        raise SystemExit("Не найден ISCC.exe (Inno Setup 6). Установите: winget install JRSoftware.InnoSetup")
    run(
        [
            iscc, f"/DAppVersion={__version__}", f"/DSourceDir={app_dir}", f"/DOutputDir={DIST}",
            str(ROOT / "installer" / "grasp.iss"),
        ]
    )  # fmt: skip
    setup = DIST / f"GraspSetup-{__version__}.exe"
    return setup if setup.exists() else None


def build_portable_zip(app_dir: Path) -> Path:
    step("Портативный zip")
    tag = "win64" if IS_WIN else f"{platform.system().lower()}-{platform.machine().lower()}"
    target = DIST / f"Grasp-{__version__}-portable-{tag}.zip"
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                zf.write(path, Path(__app_name__) / path.relative_to(app_dir))
        # Маркер портативного режима: данные — в папке GraspData рядом с exe
        # (если туда нельзя писать — в %APPDATA%\Grasp).
        zf.writestr(f"{__app_name__}/portable.flag", "Grasp portable mode\n")
        zf.writestr(
            f"{__app_name__}/ПРОЧТИ.txt",
            "Grasp — портативная версия.\r\n\r\nРаспакуйте папку куда угодно и запустите Grasp.exe.\r\n"
            "Прогресс хранится в папке GraspData рядом с программой.\r\n",
        )
    return target


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--skip-ui-matrix", action="store_true", help="не гонять матрицу разрешений × масштаб × темы")
    ap.add_argument("--skip-installer", action="store_true")
    ap.add_argument("--skip-zip", action="store_true")
    args = ap.parse_args()

    started = time.monotonic()
    if not args.skip_tests:
        run_tests(args.skip_ui_matrix)
    DIST.mkdir(exist_ok=True)
    app_dir = build_exe()
    smoke_test(app_dir)
    outputs = []
    if not args.skip_installer:
        setup = build_installer(app_dir)
        if setup:
            outputs.append(setup)
    if not args.skip_zip:
        outputs.append(build_portable_zip(app_dir))

    step("Готово")
    print(f"Сборка: {app_dir}")
    for path in outputs:
        print(f"  {path.relative_to(ROOT)}  ({path.stat().st_size / 2**20:.1f} МБ)")
    print(f"Время: {time.monotonic() - started:.0f} с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
