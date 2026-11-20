"""Настройки: тема, шрифт, API-ключ, модель речи, цель и дата экзамена."""

from __future__ import annotations

from PySide6.QtCore import QDate, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
)

from grasp.core import secrets
from grasp.core.model_download import MODEL_SIZES_MB, DownloadCancelled, DownloadError, ModelInfo, download_model
from grasp.core.settings import FONT_SCALE_MAX, FONT_SCALE_MIN, FONT_SCALE_STEP
from grasp.paths import logs_dir, user_data_dir
from grasp.ui.context import AppContext
from grasp.ui.widgets.common import Card, Label, Page, tone_label

PROVIDERS = (("anthropic", "Anthropic (Claude)"), ("openai", "OpenAI-совместимый API"))


class DownloadThread(QThread):
    progress = Signal(int, int, str)
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, info: ModelInfo) -> None:
        super().__init__()
        self.info = info
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            path = download_model(self.info, self.progress.emit, lambda: self._cancel)
            self.done.emit(str(path))
        except DownloadCancelled:
            self.failed.emit("Загрузка отменена.")
        except DownloadError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover
            self.failed.emit(f"Неожиданная ошибка: {exc}")


def _form() -> QFormLayout:
    form = QFormLayout()
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    return form


class SettingsPage(Page):
    def __init__(self, ctx: AppContext) -> None:
        super().__init__("Настройки", "Все данные хранятся локально на этом компьютере.")
        self.ctx = ctx
        s = ctx.settings
        self._thread: DownloadThread | None = None

        # --- оформление ---------------------------------------------------
        look = Card("Оформление")
        row = QHBoxLayout()
        row.setSpacing(16)
        self.theme_group = QButtonGroup(self)
        for key, title in (("light", "Светлая"), ("dark", "Тёмная"), ("system", "Как в системе")):
            rb = QRadioButton(title)
            rb.setObjectName(f"Theme-{key}")
            rb.setChecked(s.theme == key)
            rb.toggled.connect(lambda on, k=key: on and self._set_theme(k))
            self.theme_group.addButton(rb)
            row.addWidget(rb)
        row.addStretch(1)
        look.body.addLayout(row)

        fs = QHBoxLayout()
        fs.setSpacing(8)
        fs.addWidget(Label("Размер шрифта:", wrap=False))
        minus = QPushButton("A−")
        minus.setToolTip("Ctrl −")
        minus.setAccessibleName("Уменьшить шрифт")
        minus.clicked.connect(lambda: ctx.on_font_scale(self.ctx.settings.font_scale - FONT_SCALE_STEP))
        self.font_value = Label("", wrap=False)
        self.font_value.setObjectName("FontScaleValue")
        plus = QPushButton("A+")
        plus.setToolTip("Ctrl +")
        plus.setAccessibleName("Увеличить шрифт")
        plus.clicked.connect(lambda: ctx.on_font_scale(self.ctx.settings.font_scale + FONT_SCALE_STEP))
        reset = QPushButton("Сбросить")
        reset.setToolTip("Ctrl 0")
        reset.clicked.connect(lambda: ctx.on_font_scale(100))
        for w in (minus, self.font_value, plus, reset):
            fs.addWidget(w)
        fs.addStretch(1)
        look.body.addLayout(fs)
        look.add(
            Label(
                f"От {FONT_SCALE_MIN} до {FONT_SCALE_MAX} % поверх масштаба Windows. "
                "F11 — полноэкранный режим, Esc — выход из него.",
                "caption",
            )
        )
        self.add(look)
        self.update_font_value()

        # --- цель ---------------------------------------------------------
        goal = Card("Цель")
        form = _form()
        self.goal = QComboBox()
        self.goal.addItem("Подготовка к TOEFL iBT", "toefl")
        self.goal.addItem("Общий английский", "general")
        self.goal.setCurrentIndex(0 if s.goal == "toefl" else 1)
        self.goal.currentIndexChanged.connect(lambda: self._set("goal", self.goal.currentData()))
        form.addRow("Цель обучения", self.goal)

        self.target = QDoubleSpinBox()
        self.target.setRange(1.0, 6.0)
        self.target.setSingleStep(0.5)
        self.target.setDecimals(1)
        self.target.setValue(s.target_toefl)
        self.target.valueChanged.connect(lambda v: self._set("target_toefl", float(v)))
        form.addRow("Желаемый балл TOEFL (1–6)", self.target)

        date_row = QHBoxLayout()
        self.has_exam = QCheckBox("Задана")
        self.exam_date = QDateEdit()
        self.exam_date.setCalendarPopup(True)
        self.exam_date.setDisplayFormat("dd.MM.yyyy")
        self.exam_date.setMinimumDate(QDate.currentDate())
        if s.exam_date:
            self.exam_date.setDate(QDate.fromString(s.exam_date, "yyyy-MM-dd"))
            self.has_exam.setChecked(True)
        else:
            self.exam_date.setDate(QDate.currentDate().addMonths(3))
        self.exam_date.setEnabled(self.has_exam.isChecked())
        self.has_exam.toggled.connect(self._exam_changed)
        self.exam_date.dateChanged.connect(self._exam_changed)
        date_row.addWidget(self.has_exam)
        date_row.addWidget(self.exam_date)
        date_row.addStretch(1)
        form.addRow("Дата экзамена", date_row)

        self.minutes = QSpinBox()
        self.minutes.setRange(5, 240)
        self.minutes.setSingleStep(5)
        self.minutes.setSuffix(" мин")
        self.minutes.setValue(s.minutes_per_day)
        self.minutes.valueChanged.connect(lambda v: self._set("minutes_per_day", int(v)))
        form.addRow("Минут в день", self.minutes)
        goal.body.addLayout(form)
        self.add(goal)

        # --- AI -----------------------------------------------------------
        ai = Card("AI-проверка")
        ai.add(
            Label(
                "Ключ LLM API нужен для проверки письма и речи, генерации заданий и объяснений. "
                "Без ключа Grasp работает на встроенном контенте. Ключ хранится в защищённом "
                "хранилище Windows (Диспетчер учётных данных), а не в файлах программы.",
                "secondary",
            )
        )
        form = _form()
        self.provider = QComboBox()
        for key, title in PROVIDERS:
            self.provider.addItem(title, key)
        idx = next((i for i, (k, _t) in enumerate(PROVIDERS) if k == s.ai_provider), 0)
        self.provider.setCurrentIndex(idx)
        self.provider.currentIndexChanged.connect(self._provider_changed)
        form.addRow("Провайдер", self.provider)
        self.key_edit = QLineEdit()
        self.key_edit.setObjectName("ApiKeyEdit")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("Вставьте API-ключ")
        form.addRow("API-ключ", self.key_edit)
        ai.body.addLayout(form)
        btns = QHBoxLayout()
        save = QPushButton("Сохранить ключ")
        save.setProperty("role", "primary")
        save.clicked.connect(self._save_key)
        delete = QPushButton("Удалить ключ")
        delete.clicked.connect(self._delete_key)
        btns.addWidget(save)
        btns.addWidget(delete)
        btns.addStretch(1)
        ai.body.addLayout(btns)
        self.key_status = Label("", "secondary")
        self.key_status.setObjectName("ApiKeyStatus")
        ai.add(self.key_status)
        self.add(ai)
        self._refresh_key_status()

        # --- речь ---------------------------------------------------------
        speech = Card("Озвучка и распознавание речи")
        form = _form()
        self.tts = QComboBox()
        self.tts.addItem("Онлайн (edge-tts) + офлайн-запас", "edge")
        self.tts.addItem("Только офлайн (голос Windows)", "offline")
        self.tts.setCurrentIndex(0 if s.tts_engine == "edge" else 1)
        self.tts.currentIndexChanged.connect(lambda: self._set("tts_engine", self.tts.currentData()))
        form.addRow("Озвучка", self.tts)
        self.stt_model = QComboBox()
        for size, mb in MODEL_SIZES_MB.items():
            self.stt_model.addItem(f"faster-whisper {size} (≈ {mb} МБ)", size)
        self.stt_model.setCurrentIndex(list(MODEL_SIZES_MB).index(s.stt_model))
        self.stt_model.currentIndexChanged.connect(self._stt_model_changed)
        form.addRow("Модель распознавания", self.stt_model)
        speech.body.addLayout(form)
        speech.add(
            Label(
                "Модель не входит в установщик: она нужна только для раздела Speaking и "
                "скачивается один раз. Без неё работает всё, кроме локального распознавания речи.",
                "caption",
            )
        )
        dl = QHBoxLayout()
        self.dl_button = QPushButton("Скачать модель")
        self.dl_button.setObjectName("ModelDownload")
        self.dl_button.clicked.connect(self._download)
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._cancel_download)
        self.remove_button = QPushButton("Удалить модель")
        self.remove_button.clicked.connect(self._remove_model)
        dl.addWidget(self.dl_button)
        dl.addWidget(self.cancel_button)
        dl.addWidget(self.remove_button)
        dl.addStretch(1)
        speech.body.addLayout(dl)
        self.dl_progress = QProgressBar()
        self.dl_progress.setRange(0, 1000)
        self.dl_progress.setVisible(False)
        speech.add(self.dl_progress)
        self.dl_status = Label("", "secondary")
        self.dl_status.setObjectName("ModelStatus")
        speech.add(self.dl_status)
        self.add(speech)
        self._refresh_model_status()

        # --- данные -------------------------------------------------------
        data = Card("Данные")
        data.add(Label(f"Прогресс, настройки и записи: {user_data_dir()}", "secondary", selectable=True))
        row = QHBoxLayout()
        open_data = QPushButton("Открыть папку данных")
        open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(user_data_dir()))))
        open_logs = QPushButton("Открыть логи")
        open_logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir()))))
        row.addWidget(open_data)
        row.addWidget(open_logs)
        row.addStretch(1)
        data.body.addLayout(row)
        self.add(data)
        # Выпадающие списки не сжимаются уже своего текста: при нехватке места
        # страница прокручивается по горизонтали, а текст не обрезается.
        for combo in self.findChildren(QComboBox):
            combo.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.finish()

    # --- обработчики ------------------------------------------------------
    def _set(self, name: str, value) -> None:
        setattr(self.ctx.settings, name, value)
        self.ctx.save()

    def _set_theme(self, key: str) -> None:
        self._set("theme", key)
        self.ctx.themes.set_mode(key)

    def update_font_value(self) -> None:
        self.font_value.setText(f"{self.ctx.settings.font_scale} %")

    def _exam_changed(self, *_args) -> None:
        on = self.has_exam.isChecked()
        self.exam_date.setEnabled(on)
        self._set("exam_date", self.exam_date.date().toString("yyyy-MM-dd") if on else "")

    def _provider_changed(self) -> None:
        self._set("ai_provider", self.provider.currentData())
        self._refresh_key_status()

    def _refresh_key_status(self) -> None:
        key = secrets.get_api_key(self.provider.currentData())
        if key:
            self.key_status.setText(f"Ключ сохранён: {secrets.mask(key)}")
        else:
            self.key_status.setText("Ключ не задан — AI-проверка выключена, работает встроенный контент.")

    def _save_key(self) -> None:
        key = self.key_edit.text().strip()
        if not key:
            self.key_status.setText("Введите ключ.")
            return
        try:
            secrets.set_api_key(self.provider.currentData(), key)
        except secrets.SecretStoreError as exc:
            self.key_status.setText(f"Не удалось сохранить ключ в защищённом хранилище: {exc}")
            return
        self.key_edit.clear()
        self._refresh_key_status()

    def _delete_key(self) -> None:
        try:
            secrets.delete_api_key(self.provider.currentData())
        except secrets.SecretStoreError as exc:
            self.key_status.setText(str(exc))
            return
        self._refresh_key_status()

    def _model(self) -> ModelInfo:
        return ModelInfo(self.stt_model.currentData())

    def _stt_model_changed(self) -> None:
        self._set("stt_model", self.stt_model.currentData())
        self.dl_status.setText("")
        self._refresh_model_status()

    def _refresh_model_status(self) -> None:
        info = self._model()
        busy = self._thread is not None and self._thread.isRunning()
        if info.is_installed:
            self.dl_status.setText(f"Модель {info.size} установлена: {info.folder}")
        elif not busy and not self.dl_status.text():
            self.dl_status.setText("Модель не загружена.")
        self.dl_button.setVisible(not info.is_installed and not busy)
        self.remove_button.setVisible(info.is_installed and not busy)
        self.cancel_button.setVisible(busy)
        self.stt_model.setEnabled(not busy)

    def _download(self) -> None:
        self._thread = DownloadThread(self._model())
        self._thread.progress.connect(self._on_progress)
        self._thread.done.connect(self._on_done)
        self._thread.failed.connect(self._on_failed)
        self._thread.finished.connect(self._refresh_model_status)
        self.dl_progress.setValue(0)
        self.dl_progress.setVisible(True)
        self.dl_status.setText("Подключение…")
        self._thread.start()
        self._refresh_model_status()

    def _on_progress(self, done: int, total: int, name: str) -> None:
        if total:
            self.dl_progress.setValue(int(done / total * 1000))
            self.dl_status.setText(f"Загрузка {name}: {done / 2**20:.0f} из {total / 2**20:.0f} МБ")
        else:
            self.dl_status.setText(f"Загрузка {name}: {done / 2**20:.0f} МБ")

    def _on_done(self, path: str) -> None:
        self.dl_progress.setVisible(False)
        self.dl_status.setText(f"Готово: {path}")

    def _on_failed(self, message: str) -> None:
        self.dl_progress.setVisible(False)
        self.dl_status.setText(message)

    def _cancel_download(self) -> None:
        if self._thread:
            self._thread.cancel()

    def _remove_model(self) -> None:
        self._model().remove()
        self.dl_status.setText("")
        self._refresh_model_status()

    def shutdown(self) -> None:
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._thread.wait(3000)
