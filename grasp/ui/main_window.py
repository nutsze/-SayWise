"""Главное окно: боковая навигация, экраны, F11, масштаб шрифта, геометрия."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QByteArray, QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from grasp import __app_name__, __version__
from grasp.core.settings import FONT_SCALE_MAX, FONT_SCALE_MIN, FONT_SCALE_STEP
from grasp.ui import icons
from grasp.ui.context import AppContext
from grasp.ui.pages.dictionary import DictionaryPage
from grasp.ui.pages.grammar import GrammarPage
from grasp.ui.pages.home import HomePage
from grasp.ui.pages.settings_page import SettingsPage
from grasp.ui.pages.simple import MistakesPage, ReviewPage, ToeflPage
from grasp.ui.theme import Theme

log = logging.getLogger(__name__)

COMPACT_BELOW = 1100  # логических px: уже — сайдбар только с иконками
MIN_SIZE = QSize(760, 460)


@dataclass(frozen=True)
class NavItem:
    key: str
    title: str
    icon: str
    factory: Callable[[AppContext], QWidget]


NAV: tuple[NavItem, ...] = (
    NavItem("home", "Главная", "home", HomePage),
    NavItem("grammar", "Грамматика", "grammar", GrammarPage),
    NavItem("review", "Повторение", "review", ReviewPage),
    NavItem("mistakes", "Журнал ошибок", "mistakes", MistakesPage),
    NavItem("toefl", "TOEFL iBT", "toefl", ToeflPage),
    NavItem("dictionary", "Словарь", "dictionary", DictionaryPage),
    NavItem("settings", "Настройки", "settings", SettingsPage),
)


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        ctx.navigate = self.navigate
        ctx.on_font_scale = self.set_font_scale
        self.setObjectName("MainWindow")
        self.setWindowTitle(__app_name__)
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(MIN_SIZE)
        self._pre_fullscreen_maximized = False
        self._compact: bool | None = None

        root = QWidget()
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        self.setCentralWidget(root)

        # --- сайдбар -----------------------------------------------------
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sv = QVBoxLayout(self.sidebar)
        sv.setContentsMargins(12, 16, 12, 12)
        sv.setSpacing(4)
        self.brand = QLabel(__app_name__)
        self.brand.setProperty("role", "h2")
        self.brand.setContentsMargins(10, 0, 0, 12)
        sv.addWidget(self.brand)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QToolButton] = {}
        self.pages: dict[str, QWidget] = {}
        self.stack = QStackedWidget()
        self.stack.setObjectName("Pages")

        for i, item in enumerate(NAV):
            btn = QToolButton()
            btn.setObjectName("NavButton")
            btn.setProperty("navKey", item.key)
            btn.setText(f"  {item.title}")  # отступ от иконки
            btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            btn.setCheckable(True)
            btn.setToolTip(f"{item.title}  (Ctrl+{i + 1})")
            btn.setAccessibleName(item.title)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _=False, k=item.key: self.navigate(k))
            self.nav_group.addButton(btn)
            self.nav_buttons[item.key] = btn
            if item.key == "settings":
                sv.addStretch(1)
            sv.addWidget(btn)
            page = item.factory(ctx)
            page.setProperty("pageKey", item.key)
            self.pages[item.key] = page
            self.stack.addWidget(page)

        self.version = QLabel(f"v{__version__}")
        self.version.setProperty("role", "caption")
        self.version.setContentsMargins(10, 8, 0, 0)
        sv.addWidget(self.version)

        h.addWidget(self.sidebar)
        h.addWidget(self.stack, 1)

        self._install_shortcuts()
        ctx.themes.theme_changed.connect(self._on_theme_changed)
        self._on_theme_changed(ctx.themes.current)
        self.navigate(ctx.settings.last_page if ctx.settings.last_page in self.pages else "home", save=False)

    # --- навигация --------------------------------------------------------
    def navigate(self, key: str, save: bool = True) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        self.nav_buttons[key].setChecked(True)
        if save:
            self.ctx.settings.last_page = key
            self.ctx.save()

    def current_key(self) -> str:
        return str(self.stack.currentWidget().property("pageKey"))

    # --- горячие клавиши ---------------------------------------------------
    def _action(self, keys: list[QKeySequence | str], slot: Callable[[], None], name: str) -> QAction:
        act = QAction(name, self)
        act.setShortcuts([QKeySequence(k) if isinstance(k, str) else k for k in keys])
        act.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        act.triggered.connect(slot)
        self.addAction(act)
        return act

    def _install_shortcuts(self) -> None:
        mod_kp = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.KeypadModifier
        self.act_fullscreen = self._action(["F11"], self.toggle_fullscreen, "Полный экран")
        self.act_exit_fullscreen = self._action(["Esc"], self.exit_fullscreen, "Выйти из полноэкранного режима")
        self.act_exit_fullscreen.setEnabled(False)
        self._action(
            ["Ctrl++", "Ctrl+=", "Ctrl+Shift+=", QKeySequence(mod_kp | Qt.Key.Key_Plus)],
            lambda: self.set_font_scale(self.ctx.settings.font_scale + FONT_SCALE_STEP),
            "Крупнее",
        )
        self._action(
            ["Ctrl+-", QKeySequence(mod_kp | Qt.Key.Key_Minus)],
            lambda: self.set_font_scale(self.ctx.settings.font_scale - FONT_SCALE_STEP),
            "Мельче",
        )
        self._action(
            ["Ctrl+0", QKeySequence(mod_kp | Qt.Key.Key_0)], lambda: self.set_font_scale(100), "Обычный размер"
        )
        for i, item in enumerate(NAV):
            self._action([f"Ctrl+{i + 1}"], lambda _checked=False, k=item.key: self.navigate(k), item.title)

    # --- полноэкранный режим ----------------------------------------------
    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.exit_fullscreen()
        else:
            self._pre_fullscreen_maximized = self.isMaximized()
            self.showFullScreen()

    def exit_fullscreen(self) -> None:
        if not self.isFullScreen():
            return
        if self._pre_fullscreen_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self.act_exit_fullscreen.setEnabled(self.isFullScreen())

    # --- масштаб шрифта ----------------------------------------------------
    def set_font_scale(self, value: int) -> None:
        value = max(FONT_SCALE_MIN, min(FONT_SCALE_MAX, int(value)))
        if value == self.ctx.settings.font_scale and self.ctx.themes.font_scale == value:
            return
        self.ctx.settings.font_scale = value
        self.ctx.themes.set_font_scale(value)
        self.ctx.save()
        settings_page = self.pages.get("settings")
        if isinstance(settings_page, SettingsPage):
            settings_page.update_font_value()

    # --- тема и адаптивность -------------------------------------------------
    def _on_theme_changed(self, theme: Theme) -> None:
        color = theme.tokens["text"]
        for item in NAV:
            self.nav_buttons[item.key].setIcon(icons.icon(item.icon, color))
        self._apply_compact(force=True)

    def _apply_compact(self, force: bool = False) -> None:
        compact = self.width() < COMPACT_BELOW
        if compact == self._compact and not force:
            return
        self._compact = compact
        style = Qt.ToolButtonStyle.ToolButtonIconOnly if compact else Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        fm = self.fontMetrics()
        icon_px = max(20, round(fm.height() * 1.15))
        for btn in self.nav_buttons.values():
            btn.setToolButtonStyle(style)
            btn.setIconSize(QSize(icon_px, icon_px))
        self.brand.setText("G" if compact else __app_name__)
        self.version.setVisible(not compact)
        # Ширина сайдбара — по самой длинной кнопке (кнопки растут под текст).
        widest = max(b.sizeHint().width() for b in self.nav_buttons.values())
        m = self.sidebar.layout().contentsMargins()
        self.sidebar.setFixedWidth(widest + m.left() + m.right())

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_compact()

    def event(self, event: QEvent) -> bool:
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            # Таймер с контекстом self отменяется, если окно уже удалено.
            QTimer.singleShot(0, self, lambda: self._apply_compact(force=True))
        return super().event(event)

    # --- геометрия окна --------------------------------------------------------
    def restore_window(self) -> None:
        s = self.ctx.settings
        restored = False
        if s.window_geometry:
            restored = self.restoreGeometry(QByteArray.fromBase64(s.window_geometry.encode("ascii")))
        if not restored:
            screen = QGuiApplication.primaryScreen()
            avail = screen.availableGeometry() if screen else None
            if avail is not None:
                w = min(max(1280, int(avail.width() * 0.8)), avail.width())
                h = min(max(800, int(avail.height() * 0.85)), avail.height())
                self.resize(w, h)
                self.move(avail.center().x() - w // 2, avail.center().y() - h // 2)
            else:
                self.resize(1280, 800)
        if s.window_state == "fullscreen":
            self._pre_fullscreen_maximized = bool(s.extra.get("pre_fullscreen_maximized"))
            self.showFullScreen()
        elif s.window_state == "maximized":
            self.showMaximized()
        else:
            self.showNormal()
        # Стартовый фокус — на экран, а не на первую кнопку меню (иначе рамка
        # фокуса выглядит как второе выделение).
        self.stack.currentWidget().setFocus(Qt.FocusReason.OtherFocusReason)

    def save_window(self) -> None:
        s = self.ctx.settings
        state = "fullscreen" if self.isFullScreen() else "maximized" if self.isMaximized() else "normal"
        # Чтобы выход из F11 после перезапуска вернул развёрнутое окно.
        s.extra["pre_fullscreen_maximized"] = bool(state == "fullscreen" and self._pre_fullscreen_maximized)
        s.window_state = state
        s.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.ctx.save()

    def bring_to_front(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event) -> None:  # noqa: N802
        self.save_window()
        settings_page = self.pages.get("settings")
        if isinstance(settings_page, SettingsPage):
            settings_page.shutdown()
        super().closeEvent(event)
