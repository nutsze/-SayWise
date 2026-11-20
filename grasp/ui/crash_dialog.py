"""Окно «Что-то пошло не так» с кнопкой «Скопировать отчёт»."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from grasp.paths import logs_dir
from grasp.ui.widgets.common import Label


class CrashDialog(QDialog):
    def __init__(self, report: str, fatal: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CrashDialog")
        self.setWindowTitle("Grasp — что-то пошло не так")
        self.setModal(True)
        self.report = report
        v = QVBoxLayout(self)
        v.setContentsMargins(24, 20, 24, 20)
        v.setSpacing(12)
        v.addWidget(Label("Что-то пошло не так", "h2"))
        v.addWidget(
            Label(
                "Произошла непредвиденная ошибка. Ваш прогресс сохранён. "
                "Скопируйте отчёт и отправьте его разработчикам — это поможет исправить проблему.",
                "secondary",
            )
        )
        text = QPlainTextEdit(report)
        text.setReadOnly(True)
        text.setObjectName("CrashReport")
        text.setMinimumHeight(220)
        v.addWidget(text, 1)
        self.copied = Label("", "caption")
        v.addWidget(self.copied)

        row = QHBoxLayout()
        copy = QPushButton("Скопировать отчёт")
        copy.setProperty("role", "primary")
        copy.clicked.connect(self.copy_report)
        logs = QPushButton("Открыть папку логов")
        logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir()))))
        row.addWidget(copy)
        row.addWidget(logs)
        row.addStretch(1)
        if not fatal:
            cont = QPushButton("Продолжить работу")
            cont.clicked.connect(self.accept)
            row.addWidget(cont)
        quit_btn = QPushButton("Закрыть приложение")
        quit_btn.clicked.connect(self._quit)
        row.addWidget(quit_btn)
        v.addLayout(row)
        self.resize(760, 520)

    def copy_report(self) -> None:
        QGuiApplication.clipboard().setText(self.report)
        self.copied.setText("Отчёт скопирован в буфер обмена.")

    def _quit(self) -> None:
        self.reject()
        app = QApplication.instance()
        if app is not None:
            app.exit(1)


def show_crash_dialog(report: str, fatal: bool = False) -> None:
    if QApplication.instance() is None:
        return
    parent = QApplication.activeWindow()
    CrashDialog(report, fatal=fatal, parent=parent).exec()
