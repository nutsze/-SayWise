"""Темы: светлая, тёмная, как в системе. Переключение на лету.

Все цвета — только из токенов в ``resources/themes/*.json``. Виджеты не
содержат захардкоженных цветов: они получают роль через динамические
свойства (``role``, ``tone``, ``state``), а QSS собирается здесь.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from grasp.paths import resource_path
from grasp.ui import fonts

TOKEN_NAMES = (
    "bg", "surface", "surface_alt", "border", "text", "text_secondary",
    "accent", "accent_text", "accent_soft", "success", "success_bg",
    "error", "error_bg", "warning", "warning_bg", "focus", "scrollbar",
)  # fmt: skip

BASE_POINT_SIZE = 11.0  # базовый размер шрифта при 100 %


@dataclass(frozen=True)
class Theme:
    name: str
    title_ru: str
    tokens: dict[str, str]

    def color(self, token: str) -> QColor:
        return QColor(self.tokens[token])

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


@lru_cache(maxsize=None)
def load_theme(name: str) -> Theme:
    data = json.loads(resource_path("resources", "themes", f"{name}.json").read_text("utf-8"))
    tokens = data["tokens"]
    missing = set(TOKEN_NAMES) - set(tokens)
    if missing:
        raise ValueError(f"В теме {name} нет токенов: {sorted(missing)}")
    return Theme(data["name"], data["title_ru"], dict(tokens))


def system_prefers_dark() -> bool:
    hints = QGuiApplication.styleHints()
    try:
        return hints.colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:  # Qt < 6.5
        return QGuiApplication.palette().window().color().lightness() < 128


def build_palette(t: Theme) -> QPalette:
    p = QPalette()
    c = t.color
    roles = {
        QPalette.ColorRole.Window: "bg",
        QPalette.ColorRole.WindowText: "text",
        QPalette.ColorRole.Base: "surface",
        QPalette.ColorRole.AlternateBase: "surface_alt",
        QPalette.ColorRole.Text: "text",
        QPalette.ColorRole.Button: "surface",
        QPalette.ColorRole.ButtonText: "text",
        QPalette.ColorRole.Highlight: "accent",
        QPalette.ColorRole.HighlightedText: "accent_text",
        QPalette.ColorRole.ToolTipBase: "surface",
        QPalette.ColorRole.ToolTipText: "text",
        QPalette.ColorRole.PlaceholderText: "text_secondary",
        QPalette.ColorRole.Link: "accent",
        QPalette.ColorRole.Mid: "border",
        QPalette.ColorRole.Midlight: "surface_alt",
        QPalette.ColorRole.Dark: "border",
    }
    for role, token in roles.items():
        p.setColor(role, c(token))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, c("text_secondary"))
    return p


_ASSETS = {
    "chevron-up": '<path d="M6 15l6-6 6 6" fill="none" stroke="{c}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6" fill="none" stroke="{c}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="{c}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
    "dot": '<circle cx="12" cy="12" r="5.5" fill="{c}"/>',
}


def theme_assets(t: Theme) -> dict[str, str]:
    """SVG для стрелок и галочек, окрашенные токенами темы.

    QSS не умеет перекрашивать картинки, а стандартные стрелки Fusion
    пропадают, как только виджет стилизован. Файлы пишутся в кэш папки
    данных (там есть права на запись) и подставляются в QSS.
    """
    from grasp.paths import user_data_dir

    folder = user_data_dir() / "cache" / f"theme-{t.name}"
    folder.mkdir(parents=True, exist_ok=True)
    colors = {
        "chevron-up": t.tokens["text"],
        "chevron-down": t.tokens["text"],
        "check": t.tokens["accent_text"],
        "dot": t.tokens["accent_text"],
    }
    paths: dict[str, str] = {}
    for name, body in _ASSETS.items():
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">{body.format(c=colors[name])}</svg>'
        path = folder / f"{name}.svg"
        if not path.exists() or path.read_text("utf-8") != svg:
            path.write_text(svg, "utf-8")
        paths[name] = path.as_posix()
    return paths


def build_stylesheet(t: Theme, font_scale: int) -> str:
    """QSS из токенов. Размеры — в pt и логических px (Qt масштабирует под DPI)."""
    k = t.tokens
    a = theme_assets(t)
    base = BASE_POINT_SIZE * font_scale / 100.0

    def pt(mult: float) -> str:
        return f"{base * mult:.1f}pt"

    return f"""
* {{ font-family: {fonts.qss_family()}; font-size: {pt(1)}; }}
QMainWindow, QWidget#Page, QWidget#PageContent, QStackedWidget {{ background: {k['bg']}; color: {k['text']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QToolTip {{ background: {k['surface']}; color: {k['text']}; border: 1px solid {k['border']}; padding: 6px; }}

QLabel {{ color: {k['text']}; background: transparent; }}
QLabel[role="title"] {{ font-size: {pt(1.9)}; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: {pt(1.35)}; font-weight: 700; }}
QLabel[role="h3"] {{ font-size: {pt(1.12)}; font-weight: 600; }}
QLabel[role="display"] {{ font-size: {pt(3.0)}; font-weight: 700; color: {k['accent']}; }}
QLabel[role="secondary"] {{ color: {k['text_secondary']}; }}
QLabel[role="caption"] {{ color: {k['text_secondary']}; font-size: {pt(0.9)}; }}
QLabel[role="mono"] {{ font-family: {fonts.qss_family((fonts.MONO, *fonts.SANS_STACK[1:]))}; }}
QLabel[role="ipa"] {{ color: {k['text_secondary']}; }}
QLabel[tone="success"] {{ color: {k['success']}; background: {k['success_bg']}; border-radius: 6px; padding: 6px 10px; }}
QLabel[tone="error"] {{ color: {k['error']}; background: {k['error_bg']}; border-radius: 6px; padding: 6px 10px; }}
QLabel[tone="warning"] {{ color: {k['warning']}; background: {k['warning_bg']}; border-radius: 6px; padding: 6px 10px; }}
QLabel[tone="info"] {{ color: {k['text']}; background: {k['accent_soft']}; border-radius: 6px; padding: 6px 10px; }}

QFrame[card="true"] {{ background: {k['surface']}; border: 1px solid {k['border']}; border-radius: 12px; }}
QFrame#Sidebar {{ background: {k['surface']}; border-right: 1px solid {k['border']}; }}
QFrame#SidePanel {{ background: transparent; }}

QLabel[chip="true"] {{ border-radius: 8px; padding: 6px 10px; font-weight: 600; border: 1px solid {k['border']}; }}
QLabel[chip="true"][state="done"] {{ background: {k['success_bg']}; color: {k['success']}; border-color: {k['success_bg']}; }}
QLabel[chip="true"][state="current"] {{ background: {k['accent']}; color: {k['accent_text']}; border-color: {k['accent']}; }}
QLabel[chip="true"][state="future"] {{ background: {k['surface']}; color: {k['text_secondary']}; }}
QLabel[chip="true"][state="tag"] {{ background: {k['accent_soft']}; color: {k['text']}; border-color: {k['accent_soft']}; font-weight: 500; padding: 3px 8px; }}

QToolButton#NavButton {{
    background: transparent; color: {k['text']}; border: none; border-radius: 8px;
    padding: 9px 12px; text-align: left;
}}
QToolButton#NavButton:hover {{ background: {k['surface_alt']}; }}
QToolButton#NavButton:checked {{ background: {k['accent_soft']}; color: {k['text']}; font-weight: 600; }}
QToolButton#NavButton:focus {{ outline: none; border: 2px solid {k['focus']}; }}

QPushButton, QToolButton {{
    background: {k['surface']}; color: {k['text']}; border: 1px solid {k['border']};
    border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover, QToolButton:hover {{ background: {k['surface_alt']}; }}
QPushButton:pressed {{ background: {k['border']}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {k['focus']}; }}
QPushButton:disabled {{ color: {k['text_secondary']}; background: {k['surface_alt']}; }}
QPushButton[role="primary"] {{ background: {k['accent']}; color: {k['accent_text']}; border-color: {k['accent']}; font-weight: 600; }}
QPushButton[role="primary"]:hover {{ background: {k['focus']}; }}
QPushButton[role="primary"]:disabled {{ background: {k['surface_alt']}; color: {k['text_secondary']}; border-color: {k['border']}; }}
QPushButton[segment="true"] {{ border-radius: 0; padding: 7px 16px; }}
QPushButton[segment="true"]:checked {{ background: {k['accent']}; color: {k['accent_text']}; border-color: {k['accent']}; }}
QPushButton[segment="first"] {{ border-top-right-radius: 0; border-bottom-right-radius: 0; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {k['surface']}; color: {k['text']}; border: 1px solid {k['border']};
    border-radius: 8px; padding: 6px 8px; selection-background-color: {k['accent']};
    selection-color: {k['accent_text']};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QComboBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {k['focus']}; }}
QComboBox QAbstractItemView {{ background: {k['surface']}; color: {k['text']};
    selection-background-color: {k['accent_soft']}; selection-color: {k['text']}; border: 1px solid {k['border']}; }}
QRadioButton, QCheckBox {{ color: {k['text']}; spacing: 8px; background: transparent; }}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px; height: 16px; border: 2px solid {k['text_secondary']}; background: {k['surface']}; }}
QRadioButton::indicator {{ border-radius: 10px; }}
QCheckBox::indicator {{ border-radius: 5px; }}
QRadioButton::indicator:hover, QCheckBox::indicator:hover {{ border-color: {k['accent']}; }}
QRadioButton::indicator:checked {{ background: {k['accent']}; border-color: {k['accent']}; image: url("{a['dot']}"); }}
QCheckBox::indicator:checked {{ background: {k['accent']}; border-color: {k['accent']}; image: url("{a['check']}"); }}
QRadioButton:focus, QCheckBox:focus {{ outline: none; }}
QRadioButton::indicator:focus, QCheckBox::indicator:focus {{ border-color: {k['focus']}; }}

QSpinBox, QDoubleSpinBox, QDateEdit {{ padding-right: 28px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QDateEdit::up-button {{
    subcontrol-origin: border; subcontrol-position: top right; width: 26px;
    border: none; border-left: 1px solid {k['border']}; border-top-right-radius: 8px; background: {k['surface_alt']}; }}
QSpinBox::down-button, QDoubleSpinBox::down-button, QDateEdit::down-button {{
    subcontrol-origin: border; subcontrol-position: bottom right; width: 26px;
    border: none; border-left: 1px solid {k['border']}; border-bottom-right-radius: 8px; background: {k['surface_alt']}; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{ background: {k['border']}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow, QDateEdit::up-arrow {{ image: url("{a['chevron-up']}"); width: 12px; height: 12px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow, QDateEdit::down-arrow {{ image: url("{a['chevron-down']}"); width: 12px; height: 12px; }}
QComboBox, QDateEdit[calendarPopup="true"] {{ padding-right: 30px; }}
QComboBox::drop-down, QDateEdit::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right; width: 28px; border: none; }}
QComboBox::down-arrow, QDateEdit::down-arrow {{ image: url("{a['chevron-down']}"); width: 14px; height: 14px; }}

QProgressBar {{ background: {k['surface_alt']}; border: none; border-radius: 5px; min-height: 10px; max-height: 10px; color: transparent; }}
QProgressBar::chunk {{ background: {k['accent']}; border-radius: 5px; }}
QProgressBar[tone="success"]::chunk {{ background: {k['success']}; }}

QTableView, QTableWidget, QTreeWidget, QListWidget {{
    background: {k['surface']}; color: {k['text']}; border: 1px solid {k['border']}; border-radius: 8px;
    gridline-color: {k['border']}; alternate-background-color: {k['surface_alt']};
    selection-background-color: {k['accent_soft']}; selection-color: {k['text']};
}}
QHeaderView::section {{ background: {k['surface_alt']}; color: {k['text']}; border: none;
    border-right: 1px solid {k['border']}; border-bottom: 1px solid {k['border']}; padding: 6px 8px; font-weight: 600; }}
QTableCornerButton::section {{ background: {k['surface_alt']}; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle {{ background: {k['scrollbar']}; border-radius: 4px; min-height: 28px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSlider::groove:horizontal {{ background: {k['surface_alt']}; height: 6px; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {k['accent']}; width: 16px; margin: -6px 0; border-radius: 8px; }}
"""


class ThemeManager(QObject):
    """Применяет тему и размер шрифта ко всему приложению."""

    theme_changed = Signal(object)  # Theme

    def __init__(self, app: QApplication, mode: str = "system", font_scale: int = 100) -> None:
        super().__init__(app)
        self.app = app
        self.mode = mode
        self.font_scale = font_scale
        self.current: Theme = load_theme("light")
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)

    def resolve(self) -> Theme:
        if self.mode == "system":
            return load_theme("dark" if system_prefers_dark() else "light")
        return load_theme(self.mode)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.apply()

    def set_font_scale(self, scale: int) -> None:
        self.font_scale = scale
        self.apply()

    def apply(self) -> None:
        theme = self.resolve()
        self.current = theme
        font = QFont()
        font.setFamilies(list(fonts.SANS_STACK))
        font.setPointSizeF(BASE_POINT_SIZE * self.font_scale / 100.0)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        self.app.setFont(font)
        self.app.setPalette(build_palette(theme))
        self.app.setStyleSheet(build_stylesheet(theme, self.font_scale))
        self.theme_changed.emit(theme)

    def _on_system_scheme_changed(self, *_args) -> None:
        if self.mode == "system":
            self.apply()


def repolish(widget) -> None:
    """Перечитать QSS после смены динамического свойства (role/state/tone)."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
