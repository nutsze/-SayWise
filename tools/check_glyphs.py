"""Проверка покрытия глифов встроенными шрифтами.

Проходит по всему учебному контенту (grasp/content/**/*.json) и по
строкам интерфейса (строковые литералы в grasp/**/*.py) и сообщает о
символах, которых нет в шрифте. Дополнительно проверяет обязательный
набор: кириллица, латиница, IPA (ə ʃ ʒ θ ð ŋ ˈ ː …), типографские
кавычки и тире.

    python tools/check_glyphs.py          # код возврата 1, если чего-то нет
"""

from __future__ import annotations

import ast
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "grasp"
FONTS = PKG / "resources" / "fonts"
# Цепочка шрифтов интерфейса (см. grasp/ui/fonts.py: SANS_STACK). Основной
# текст проверяется по Noto Sans; символы, которых в нём нет, допускаются,
# только если они есть в запасных Noto Sans Math / Symbols 2.
SANS = ["NotoSans-Regular.ttf"]
FALLBACK = ["NotoSansMath-Regular.ttf", "NotoSansSymbols2-Regular.ttf"]
STYLES = ["NotoSans-Bold.ttf", "NotoSans-Italic.ttf", "NotoSans-SemiBold.ttf", "NotoSans-BoldItalic.ttf"]
MONO = ["NotoSansMono-Regular.ttf"]

CYRILLIC = "".join(chr(c) for c in range(0x0410, 0x0450)) + "Ёё"
LATIN = "".join(chr(c) for c in range(0x20, 0x7F))
IPA = "əʃʒθðŋˈˌːɪʊʌæɒɔɑɜɛɐʔɹɾʤʧəʊeɪaɪɔɪ"
TYPOGRAPHY = "«»„“”‘’‚—–…‑−×·•№°₽€$£→←↑↓≈✓✗"
REQUIRED = CYRILLIC + LATIN + IPA + TYPOGRAPHY

# Не рисуются шрифтом: управляющие и невидимые символы, которые Qt
# обрабатывает сам.
IGNORE = {"\n", "\r", "\t", "​", "­", "﻿"}


def cmap(files: list[str]) -> set[int]:
    cps: set[int] = set()
    for name in files:
        font = TTFont(FONTS / name, lazy=True)
        cps |= set(font.getBestCmap().keys())
        font.close()
    return cps


def _strings_in_json(node, where: str):
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _strings_in_json(v, f"{where}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings_in_json(v, f"{where}[{i}]")


def content_strings():
    for path in sorted((PKG / "content").rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for where, s in _strings_in_json(data, ""):
            yield f"{path.relative_to(ROOT)}{where}", s


def ui_strings():
    for path in sorted(PKG.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield f"{path.relative_to(ROOT)}:{node.lineno}", node.value


def check(sources, glyphs: set[int]) -> dict[str, list[str]]:
    missing: dict[str, list[str]] = defaultdict(list)
    for where, text in sources:
        for ch in text:
            if ch in IGNORE or ord(ch) in glyphs:
                continue
            missing[ch].append(where)
    return missing


def _fmt(ch: str) -> str:
    try:
        name = unicodedata.name(ch)
    except ValueError:
        name = "?"
    return f"U+{ord(ch):04X} {ch!r} {name}"


def main() -> int:
    base = cmap(SANS)
    sans = base | cmap(FALLBACK)
    mono = cmap(MONO)
    problems = 0

    # Начертания (bold/italic) должны покрывать то же, что и Regular,
    # иначе жирный текст «прыгнет» на другой шрифт.
    for style in STYLES:
        diff = [chr(c) for c in base - cmap([style]) if chr(c) in REQUIRED]
        if diff:
            problems += len(diff)
            print(f"{style}: нет {', '.join(_fmt(c) for c in diff)}")

    req_missing = [c for c in REQUIRED if ord(c) not in sans]
    print(f"Обязательный набор ({len(set(REQUIRED))} симв.) в Noto Sans + запасных: ", end="")
    if req_missing:
        problems += len(req_missing)
        print("НЕТ " + ", ".join(_fmt(c) for c in req_missing))
    else:
        print("OK")
    mono_missing = [c for c in CYRILLIC + LATIN + IPA if ord(c) not in mono]
    print("Кириллица/латиница/IPA в Noto Sans Mono: ", end="")
    if mono_missing:
        problems += len(mono_missing)
        print("НЕТ " + ", ".join(_fmt(c) for c in mono_missing))
    else:
        print("OK")

    for label, sources in (("Учебный контент", content_strings()), ("Строки интерфейса", ui_strings())):
        missing = check(sources, sans)
        print(f"{label}: ", end="")
        if not missing:
            print("все символы есть в шрифте")
            continue
        print(f"нет {len(missing)} символ(ов):")
        for ch, places in sorted(missing.items()):
            problems += 1
            print(f"  {_fmt(ch)} — {len(places)} раз, например {places[0]}")
    fallback_used = sorted({c for c in REQUIRED if ord(c) not in base and ord(c) in sans})
    if fallback_used:
        print("Из запасных шрифтов берутся: " + " ".join(fallback_used))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
