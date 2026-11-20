"""Загрузка модели faster-whisper по кнопке в настройках.

Модель не входит в установщик (сотни мегабайт). Файлы качаются в
``%APPDATA%\\Grasp\\models\\faster-whisper-<size>``: сначала ``*.part``,
после успешной загрузки — переименование, поэтому оборванная загрузка
не оставляет «битую» модель.
"""

from __future__ import annotations

import logging
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from grasp.paths import models_dir

log = logging.getLogger(__name__)

HF_BASE = "https://huggingface.co/Systran/faster-whisper-{size}/resolve/main/{file}"
MODEL_FILES = ("config.json", "tokenizer.json", "vocabulary.txt", "model.bin")
MODEL_SIZES_MB = {"base": 145, "small": 484}
CHUNK = 256 * 1024


@dataclass
class ModelInfo:
    size: str

    @property
    def folder(self) -> Path:
        return models_dir() / f"faster-whisper-{self.size}"

    @property
    def is_installed(self) -> bool:
        return all((self.folder / f).is_file() for f in MODEL_FILES)

    def url(self, file: str) -> str:
        return HF_BASE.format(size=self.size, file=file)

    def remove(self) -> None:
        shutil.rmtree(self.folder, ignore_errors=True)


class DownloadCancelled(Exception):
    pass


class DownloadError(Exception):
    """Ошибка загрузки с сообщением для пользователя (на русском)."""


ProgressCb = Callable[[int, int, str], None]  # (загружено байт, всего байт, файл)


def download_model(
    info: ModelInfo,
    progress: ProgressCb | None = None,
    is_cancelled: Callable[[], bool] = lambda: False,
    url_for: Callable[[str], str] | None = None,
    timeout: float = 30.0,
) -> Path:
    """Скачать все файлы модели. Блокирующая функция — вызывать из потока."""
    url_for = url_for or info.url
    info.folder.mkdir(parents=True, exist_ok=True)

    # Сначала узнаём размеры, чтобы показать общий прогресс.
    sizes: dict[str, int] = {}
    for name in MODEL_FILES:
        try:
            req = urllib.request.Request(url_for(name), method="HEAD")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                sizes[name] = int(resp.headers.get("Content-Length") or 0)
        except (urllib.error.URLError, OSError, ValueError):
            sizes[name] = 0
    total = sum(sizes.values())
    done = 0

    for name in MODEL_FILES:
        target = info.folder / name
        if target.is_file() and sizes[name] and target.stat().st_size == sizes[name]:
            done += sizes[name]
            continue
        part = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(url_for(name), timeout=timeout) as resp, open(part, "wb") as out:
                while True:
                    if is_cancelled():
                        raise DownloadCancelled()
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total, name)
        except DownloadCancelled:
            part.unlink(missing_ok=True)
            raise
        except urllib.error.HTTPError as exc:
            part.unlink(missing_ok=True)
            raise DownloadError(f"Сервер ответил ошибкой {exc.code} при загрузке {name}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            part.unlink(missing_ok=True)
            log.warning("Ошибка загрузки модели: %s", exc)
            raise DownloadError(
                "Не удалось скачать модель: нет подключения к интернету "
                "или сервер недоступен. Проверьте соединение и попробуйте снова."
            ) from exc
        part.replace(target)
    log.info("Модель %s загружена в %s", info.size, info.folder)
    return info.folder
