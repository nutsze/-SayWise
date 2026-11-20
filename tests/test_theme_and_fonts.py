"""Контраст WCAG AA, токены тем, встроенные шрифты и покрытие глифов."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from grasp.ui.theme import TOKEN_NAMES, load_theme

ROOT = Path(__file__).resolve().parents[1]


def _lum(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    rgb = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# (текст, фон) — все сочетания, которые реально используются в QSS.
PAIRS = [
    ("text", "bg"), ("text", "surface"), ("text", "surface_alt"), ("text", "accent_soft"),
    ("text_secondary", "bg"), ("text_secondary", "surface"), ("text_secondary", "surface_alt"),
    ("accent_text", "accent"), ("accent", "bg"), ("accent", "surface"),
    ("success", "success_bg"), ("error", "error_bg"), ("warning", "warning_bg"),
    ("success", "surface"), ("error", "surface"), ("warning", "surface"),
    ("success", "bg"), ("error", "bg"), ("warning", "bg"),
    ("text", "success_bg"), ("text", "error_bg"), ("text", "warning_bg"),
]  # fmt: skip


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize(("fg", "bg"), PAIRS)
def test_wcag_aa_contrast(theme, fg, bg):
    t = load_theme(theme).tokens
    ratio = contrast(t[fg], t[bg])
    assert ratio >= 4.5, f"{theme}: {fg} на {bg} = {ratio:.2f}:1 (< 4.5)"


def test_themes_have_all_tokens():
    for name in ("light", "dark"):
        assert set(load_theme(name).tokens) >= set(TOKEN_NAMES)


def test_no_hardcoded_colors_in_widgets():
    """Все цвета — только из файла темы."""
    pattern = re.compile(r"#[0-9a-fA-F]{6}\b|rgba?\(|QColor\(\s*['\"]?#|Qt\.GlobalColor\.(?!transparent)")
    offenders = []
    for path in (ROOT / "grasp" / "ui").rglob("*.py"):
        if path.name == "theme.py":
            continue
        for i, line in enumerate(path.read_text("utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


def test_fonts_registered(qapp):
    from grasp.ui import fonts

    families = fonts.load_fonts()
    assert {fonts.SANS, fonts.MONO, *fonts.SANS_STACK} <= families


def test_glyph_coverage():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_glyphs", ROOT / "tools" / "check_glyphs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    assert mod.main() == 0


def test_app_icon_has_all_sizes():
    from PIL import Image

    with Image.open(ROOT / "grasp" / "resources" / "icons" / "app.ico") as ico:
        sizes = set(ico.info["sizes"])
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= sizes
