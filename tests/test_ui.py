"""Главное окно: навигация, F11/Esc, шрифт, темы, геометрия, один экземпляр,
окно ошибки и матрица отображения (разрешения × масштаб × темы)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from grasp.core.settings import load_settings
from grasp.ui.main_window import NAV

ROOT = Path(__file__).resolve().parents[1]


def test_all_pages_open(ui, qtbot):
    ctx, window = ui
    window.show()
    for item in NAV:
        window.navigate(item.key)
        assert window.current_key() == item.key
        assert window.nav_buttons[item.key].isChecked()


def test_shortcuts_registered(ui):
    _ctx, window = ui
    shortcuts = {seq.toString() for act in window.actions() for seq in act.shortcuts()}
    assert {"F11", "Esc", "Ctrl++", "Ctrl+=", "Ctrl+-", "Ctrl+0", "Ctrl+1", "Ctrl+7"} <= shortcuts


def test_ctrl_number_navigation(ui):
    # offscreen-платформа не доставляет оконные шорткаты, поэтому вызываем
    # действие, привязанное к Ctrl+2, напрямую.
    _ctx, window = ui
    act = next(a for a in window.actions() if any(s.toString() == "Ctrl+2" for s in a.shortcuts()))
    act.trigger()
    assert window.current_key() == "grammar"


def test_f11_and_escape(ui, qtbot):
    _ctx, window = ui
    window.show()
    qtbot.waitExposed(window)
    window.act_fullscreen.trigger()
    qtbot.waitUntil(window.isFullScreen)
    assert window.act_exit_fullscreen.isEnabled()
    window.act_exit_fullscreen.trigger()
    qtbot.waitUntil(lambda: not window.isFullScreen())
    window.act_fullscreen.trigger()
    qtbot.waitUntil(window.isFullScreen)
    window.act_fullscreen.trigger()  # F11 повторно — выход
    qtbot.waitUntil(lambda: not window.isFullScreen())


def test_font_scale_shortcuts(ui, qtbot):
    ctx, window = ui
    base = QGuiApplication.font().pointSizeF()
    window.set_font_scale(120)
    assert ctx.settings.font_scale == 120
    assert QGuiApplication.font().pointSizeF() == pytest.approx(base * 1.2, rel=0.01)
    window.set_font_scale(999)
    assert ctx.settings.font_scale == 200
    window.set_font_scale(100)
    assert QGuiApplication.font().pointSizeF() == pytest.approx(base, rel=0.01)
    assert load_settings().font_scale == 100


def test_theme_switch_live(ui, qapp):
    ctx, window = ui
    ctx.themes.set_mode("dark")
    dark_bg = qapp.palette().window().color().name()
    assert dark_bg.lower() == ctx.themes.current.tokens["bg"].lower()
    ctx.themes.set_mode("light")
    assert qapp.palette().window().color().name().lower() == ctx.themes.current.tokens["bg"].lower()
    assert dark_bg != qapp.palette().window().color().name()


def test_window_geometry_persisted(qapp, data_dir, qtbot):
    from grasp.app import build_ui

    ctx, window = build_ui(qapp)
    window.restore_window()
    window.resize(781, 503)  # offscreen-экран маленький: держимся в его пределах
    window.move(20, 10)
    qtbot.wait(20)
    window.close()  # closeEvent сохраняет геометрию
    ctx.db.engine.dispose()

    saved = load_settings()
    assert saved.window_state == "normal" and saved.window_geometry
    ctx2, window2 = build_ui(qapp, settings=saved)
    window2.restore_window()
    assert (window2.width(), window2.height()) == (781, 503)
    window2.showFullScreen()
    window2.close()
    assert load_settings().window_state == "fullscreen"
    ctx2.db.engine.dispose()


def test_compact_sidebar(ui, qtbot):
    _ctx, window = ui
    window.show()
    window.resize(900, 600)
    qtbot.wait(10)
    btn = window.nav_buttons["home"]
    assert btn.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    window.resize(1600, 900)
    qtbot.wait(10)
    assert btn.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon


SECOND_INSTANCE = (
    "import sys;from PySide6.QtCore import QCoreApplication;app=QCoreApplication(sys.argv);"
    "from grasp.core.single_instance import SingleInstance;"
    "print('primary' if SingleInstance('GraspTest').is_primary else 'secondary')"
)


def test_single_instance(qapp, qtbot, monkeypatch):
    """Второй процесс видит запущенный экземпляр, первый получает сигнал
    «развернуть окно»."""
    from grasp.core.single_instance import SingleInstance

    name = f"grasp-si-{os.getpid()}"
    monkeypatch.setenv("GRASP_INSTANCE_NAME", name)
    first = SingleInstance("GraspTest")
    assert first.is_primary
    env = dict(os.environ, GRASP_INSTANCE_NAME=name)
    with qtbot.waitSignal(first.activation_requested, timeout=10000):
        proc = subprocess.Popen(
            [sys.executable, "-c", SECOND_INSTANCE], cwd=ROOT, env=env, stdout=subprocess.PIPE, text=True
        )
    out, _ = proc.communicate(timeout=30)
    assert out.strip() == "secondary"
    first.close()


def test_crash_dialog_copies_report(qapp, qtbot):
    from grasp.ui.crash_dialog import CrashDialog

    dlg = CrashDialog("Traceback: test report")
    qtbot.addWidget(dlg)
    dlg.copy_report()
    assert QGuiApplication.clipboard().text() == "Traceback: test report"
    assert "скопирован" in dlg.copied.text()


def test_smoke_run_as_process(tmp_path):
    """Тот же режим, которым CI проверяет собранный Grasp.exe."""
    out = tmp_path / "smoke.json"
    env = dict(os.environ, GRASP_DATA_DIR=str(tmp_path / "d"), QT_QPA_PLATFORM="offscreen")
    proc = subprocess.run(
        [sys.executable, "-m", "grasp", "--smoke-test", "--smoke-out", str(out)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )  # fmt: skip
    assert proc.returncode == 0, proc.stderr
    result = json.loads(out.read_text("utf-8"))
    assert result["ok"] and len(result["pages"]) == len(NAV)


# --- матрица отображения -------------------------------------------------------

SCALES = (1.0, 1.5, 2.0)


@pytest.mark.ui_matrix
@pytest.mark.skipif(os.environ.get("GRASP_SKIP_UI_MATRIX") == "1", reason="GRASP_SKIP_UI_MATRIX=1")
@pytest.mark.parametrize("scale", SCALES, ids=lambda s: f"{int(s * 100)}%")
def test_no_clipped_text(scale):
    """Каждый экран × 1280×720…3840×2160 × светлая/тёмная (+ шрифт 150/200 %).

    Скриншоты для ручной проверки — в build/ui-screens/.
    """
    out = ROOT / "build" / "ui-screens"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_SCALE_FACTOR=str(scale))
    fonts = "100,150,200" if scale == 1.0 else "100"
    proc = subprocess.run(
        [sys.executable, "-m", "tests.ui_audit", "--out", str(out), "--font-scales", fonts],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=1200,
    )  # fmt: skip
    report = json.loads((out / f"report-{int(scale * 100)}.json").read_text("utf-8"))
    assert report["states"] > 0, proc.stderr
    assert report["issues"] == [], "\n".join(report["issues"])
