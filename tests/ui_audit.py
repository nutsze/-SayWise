"""Аудит отображения: каждый экран × разрешение × тема (× размер шрифта).

Запуск (масштаб Windows эмулируется через QT_SCALE_FACTOR, поэтому
каждый масштаб — отдельный процесс)::

    QT_QPA_PLATFORM=offscreen QT_SCALE_FACTOR=1.5 python -m tests.ui_audit --out build/ui-screens

Для каждого состояния:
* сохраняется скриншот (в физических пикселях: 4K → 3840×2160);
* проверяется, что ни один текст не обрезан: размер виджета сравнивается с
  ``sizeHint()``/``heightForWidth()``, самое длинное неразрывное слово — с
  шириной метки, геометрия — с родителем (ничего не вылезает за карточку),
  строки таблиц — с высотой текста.

Результат — JSON-отчёт ``report-<scale>.json`` в папке ``--out``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

RESOLUTIONS = ((1280, 720), (1920, 1080), (2560, 1440), (3840, 2160))
THEMES = ("light", "dark")
TOL = 1  # px


def _visible_widgets(root):
    from PySide6.QtWidgets import QWidget

    for w in root.findChildren(QWidget):
        if w.isVisibleTo(root) and w.window() is root.window():
            yield w


def _describe(w) -> str:
    name = w.objectName() or type(w).__name__
    text = ""
    if hasattr(w, "text"):
        try:
            text = re.sub(r"\s+", " ", w.text().replace("​", ""))[:60]
        except Exception:
            text = ""
    chain = []
    p = w.parentWidget()
    while p is not None and len(chain) < 4:
        if p.objectName():
            chain.append(p.objectName())
        p = p.parentWidget()
    return f"{name} «{text}» in {'/'.join(reversed(chain))}"


def _clipping_ancestor_overflow(w):
    """Вылезает ли виджет за пределы предков (до viewport прокрутки)."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QAbstractScrollArea

    p = w.parentWidget()
    while p is not None and p is not w.window():
        parent = p.parentWidget()
        if isinstance(parent, QAbstractScrollArea) and p is parent.viewport():
            return None  # дальше — прокрутка: выход за viewport допустим
        r = QRect(w.mapTo(p, QPoint(0, 0)), w.size())
        if not p.rect().adjusted(-TOL, -TOL, TOL, TOL).contains(r):
            return f"выходит за пределы {_describe(p)}: {r.getRect()} ⊄ {p.rect().getRect()}"
        p = parent
    return None


def check_widget_tree(root) -> list[str]:
    """Список проблем отображения внутри ``root``."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QTableWidget

    issues: list[str] = []
    for w in _visible_widgets(root):
        if w.width() <= 0 or w.height() <= 0:
            continue
        problem = None
        if isinstance(w, QLabel) and w.text() and w.pixmap().isNull():
            cr = w.contentsRect()
            if w.wordWrap():
                need_h = w.heightForWidth(w.width())
                if need_h > w.height() + TOL:
                    problem = f"текст обрезан по высоте: нужно {need_h}, есть {w.height()}"
                elif w.textFormat() != Qt.TextFormat.RichText:
                    fm = w.fontMetrics()
                    tokens = re.split(r"[\s​]+", w.text())
                    longest = max((fm.horizontalAdvance(t) for t in tokens if t), default=0)
                    if longest > cr.width() + TOL:
                        problem = f"неразрывное слово шире метки: {longest} > {cr.width()}"
            else:
                hint = w.sizeHint()
                if hint.width() > w.width() + TOL or hint.height() > w.height() + TOL:
                    problem = f"текст не помещается: нужно {hint.width()}×{hint.height()}, есть {w.width()}×{w.height()}"
        elif isinstance(w, (QAbstractButton, QComboBox)):
            hint = w.sizeHint()
            if hint.width() > w.width() + TOL or hint.height() > w.height() + TOL:
                problem = f"кнопка меньше текста: нужно {hint.width()}×{hint.height()}, есть {w.width()}×{w.height()}"
        elif isinstance(w, QTableWidget):
            if w.verticalScrollBar().maximum() > 0 and w.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff:
                problem = "таблица обрезана по высоте (скрытые строки)"
            fm = w.fontMetrics()
            for r in range(w.rowCount()):
                for c in range(w.columnCount()):
                    item = w.item(r, c)
                    if item is None or not item.text():
                        continue
                    colw = w.columnWidth(c) - 12
                    need = fm.boundingRect(QRect(0, 0, max(colw, 1), 100000), Qt.TextFlag.TextWordWrap, item.text()).height()
                    if need > w.rowHeight(r) + TOL:
                        problem = f"ячейка [{r},{c}] обрезана: нужно {need}, есть {w.rowHeight(r)}"
                        break
                if problem:
                    break
        if problem is None and isinstance(w, (QLabel, QAbstractButton)):
            problem = _clipping_ancestor_overflow(w)
        if problem:
            issues.append(f"{_describe(w)}: {problem}")
    return issues


def settle(app, window, rounds: int = 4) -> None:
    for _ in range(rounds):
        app.processEvents()
        if window.layout() is not None:
            window.layout().activate()


def run(out: Path, themes, resolutions, font_scales, screenshots: bool) -> dict:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    data_dir = tempfile.mkdtemp(prefix="grasp-audit-")
    os.environ["GRASP_DATA_DIR"] = data_dir
    os.environ["GRASP_INSTANCE_NAME"] = f"grasp-audit-{os.getpid()}"

    from grasp.app import build_ui, create_application
    from grasp.core.settings import Settings
    from grasp.ui.main_window import NAV

    app = create_application([sys.argv[0]])
    scale = float(os.environ.get("QT_SCALE_FACTOR", "1") or 1)
    ctx, window = build_ui(app, settings=Settings(theme="light"))
    window.show()
    out.mkdir(parents=True, exist_ok=True)

    report: dict = {"scale": scale, "states": 0, "issues": [], "notes": [], "screenshots": []}
    combos = []
    for res_i, (pw, ph) in enumerate(resolutions):
        for fs in font_scales if res_i == 0 else [100]:
            for theme in themes:
                combos.append((pw, ph, fs, theme))

    page_states = [(item.key, None) for item in NAV] + [("grammar", "levels")]
    for pw, ph, fs, theme in combos:
        ctx.themes.set_mode(theme)
        ctx.themes.set_font_scale(fs)
        ctx.settings.font_scale = fs
        lw, lh = round(pw / scale), round(ph / scale)
        min_size = window.minimumSize()
        w, h = max(lw, min_size.width()), max(lh, min_size.height())
        if (w, h) != (lw, lh):
            report["notes"].append(
                f"{pw}×{ph}@{int(scale * 100)}%: логический экран {lw}×{lh} меньше минимального окна — окно {w}×{h}"
            )
        window.resize(w, h)
        for key, variant in page_states:
            window.navigate(key, save=False)
            page = window.pages[key]
            if key == "grammar":
                page._set_view(variant or "topics", save=False)
            settle(app, window)
            tag = f"{key}{'-' + variant if variant else ''}_{theme}_{pw}x{ph}@{int(scale * 100)}_font{fs}"
            for issue in check_widget_tree(window):
                report["issues"].append(f"[{tag}] {issue}")
            if screenshots:
                path = out / f"{tag}.png"
                window.grab().save(str(path))
                report["screenshots"].append(path.name)
            report["states"] += 1
        # сайдбар и окно целиком
        for issue in check_widget_tree(window.sidebar):
            report["issues"].append(f"[sidebar_{theme}_{pw}x{ph}@{int(scale * 100)}_font{fs}] {issue}")
    window.pages["grammar"]._set_view("topics", save=False)
    window.close()
    (out / f"report-{int(scale * 100)}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/ui-screens")
    ap.add_argument("--themes", default=",".join(THEMES))
    ap.add_argument("--resolutions", default=",".join(f"{w}x{h}" for w, h in RESOLUTIONS))
    ap.add_argument("--font-scales", default="100", help="доп. размеры шрифта (для первого разрешения)")
    ap.add_argument("--no-screenshots", action="store_true")
    a = ap.parse_args()
    resolutions = [tuple(int(x) for x in r.split("x")) for r in a.resolutions.split(",")]
    report = run(
        Path(a.out),
        a.themes.split(","),
        resolutions,
        [int(x) for x in a.font_scales.split(",")],
        not a.no_screenshots,
    )
    print(json.dumps({k: (v if k != "screenshots" else len(v)) for k, v in report.items()}, ensure_ascii=False, indent=2))
    return 1 if report["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
