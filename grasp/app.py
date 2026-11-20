"""Запуск приложения: DPI, единственный экземпляр, шрифты, тема, БД, окно."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from grasp import __app_name__, __publisher__, __version__

log = logging.getLogger("grasp")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="Grasp", add_help=True)
    p.add_argument("--smoke-test", action="store_true", help="открыть все экраны и выйти (проверка сборки)")
    p.add_argument("--smoke-out", default="", help="куда записать JSON-результат smoke-теста")
    # Qt-аргументы (например -platform) пропускаем дальше.
    args, _unknown = p.parse_known_args(argv[1:])
    return args


def _windows_app_id() -> None:
    """Своя группа на панели задач и наша иконка вместо иконки python."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{__publisher__}.{__app_name__}")
    except Exception:  # pragma: no cover
        pass


def create_application(argv: list[str]):
    """QApplication с High DPI. Вызывать до создания любых виджетов."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication

    # Дробные коэффициенты масштаба Windows (125/150/175/250 %) без округления.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName(__app_name__)
    app.setApplicationDisplayName(__app_name__)
    app.setOrganizationName(__publisher__)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")  # одинаковый вид на всех версиях Windows, полностью подчиняется QSS
    return app


def build_ui(app, settings=None, db=None):
    """Собрать контекст и главное окно (используется и тестами)."""
    from grasp.core.settings import load_settings
    from grasp.data.db import open_database
    from grasp.ui import fonts, icons
    from grasp.ui.context import AppContext
    from grasp.ui.main_window import MainWindow
    from grasp.ui.theme import ThemeManager

    fonts.load_fonts()
    app.setWindowIcon(icons.app_icon())
    settings = settings or load_settings()
    themes = ThemeManager(app, settings.theme, settings.font_scale)
    themes.apply()
    db = db or open_database()
    ctx = AppContext(settings=settings, db=db, themes=themes)
    window = MainWindow(ctx)
    return ctx, window


def _write_smoke_result(result: dict, out_path: str) -> None:
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(payload)
    elif sys.stdout is not None:
        print(payload)


def _run_smoke_test(app, window, out_path: str) -> None:
    """Пройти по всем экранам, переключить тему и F11 — и выйти."""
    from PySide6.QtCore import QTimer

    from grasp.ui.main_window import NAV

    result: dict = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)), "pages": []}
    started = time.monotonic()

    def step() -> None:
        try:
            for item in NAV:
                window.navigate(item.key, save=False)
                app.processEvents()
                result["pages"].append(item.key)
            for mode in ("dark", "light"):
                window.ctx.themes.set_mode(mode)
                app.processEvents()
            window.toggle_fullscreen()
            app.processEvents()
            result["fullscreen"] = window.isFullScreen() or window.windowState().name
            window.exit_fullscreen()
            app.processEvents()
            from grasp.paths import user_data_dir

            result["data_dir"] = str(user_data_dir())
            result["ok"] = True
        except Exception as exc:  # pragma: no cover
            log.exception("smoke-test")
            result["ok"] = False
            result["error"] = repr(exc)
        result["seconds"] = round(time.monotonic() - started, 2)
        _write_smoke_result(result, out_path)
        app.exit(0 if result.get("ok") else 1)

    QTimer.singleShot(300, step)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    args = _parse_args(argv)

    from grasp.core import crash
    from grasp.core.logging_setup import setup_logging

    setup_logging()
    crash.install()  # до появления окна — пишем в лог
    log.info("Grasp %s запускается (%s)", __version__, "frozen" if getattr(sys, "frozen", False) else "source")
    _windows_app_id()

    app = create_application(argv)

    from grasp.core.single_instance import SingleInstance

    if args.smoke_test:
        os.environ.setdefault("GRASP_INSTANCE_NAME", f"Grasp-smoke-{os.getpid()}")
    instance = SingleInstance("Grasp")
    if not instance.is_primary:
        return 0

    from grasp.ui.crash_dialog import show_crash_dialog

    crash.install(show_crash_dialog)

    try:
        ctx, window = build_ui(app)
    except Exception:
        report = crash.build_report(*sys.exc_info())
        log.critical("Ошибка запуска\n%s", report)
        if args.smoke_test:  # без модального окна — CI не должен зависнуть
            _write_smoke_result({"ok": False, "error": report}, args.smoke_out)
        else:
            show_crash_dialog(report, fatal=True)
        return 1

    instance.activation_requested.connect(window.bring_to_front)
    window.restore_window()

    if args.smoke_test:
        _run_smoke_test(app, window, args.smoke_out)

    code = app.exec()
    instance.close()
    log.info("Grasp завершён (код %s)", code)
    return code
