"""Экраны приложения."""

from PySide6.QtWidgets import QMessageBox, QWidget


def coming_soon(parent: QWidget, what: str, version: str) -> None:
    QMessageBox.information(
        parent,
        "Скоро",
        f"{what} появится в версии {version}.\n\n"
        "Сейчас (0.1) готов каркас: окно, навигация, темы, шрифты, настройки.",
    )
