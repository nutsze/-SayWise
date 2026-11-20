"""Пути, уровни, контент, настройки, секреты, crash-отчёт."""

from __future__ import annotations

import json
import sys

import pytest

from grasp import paths
from grasp.core import content, crash, secrets
from grasp.core.levels import (
    SUBLEVEL_CODES,
    Level,
    expected_toefl,
    is_valid_level,
    load_sublevels,
)
from grasp.core.settings import Settings, load_settings, save_settings

# --- пути -------------------------------------------------------------------


def test_resource_path_from_sources():
    assert paths.resource_path("resources", "fonts", "NotoSans-Regular.ttf").is_file()
    assert paths.content_path("levels.json").is_file()
    assert paths.resource_path("data", "migrations", "env.py").is_file()


def test_resource_path_when_frozen(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    paths.reset_caches()
    try:
        assert paths.resource_path("content", "levels.json") == tmp_path / "grasp" / "content" / "levels.json"
        assert paths.is_frozen()
    finally:
        monkeypatch.delattr(sys, "_MEIPASS")
        paths.reset_caches()


def test_user_data_dir_override(data_dir):
    assert paths.user_data_dir() == data_dir
    assert paths.database_path().parent == data_dir
    assert paths.logs_dir().is_dir()


def test_appdata_on_windows(monkeypatch, tmp_path):
    monkeypatch.delenv("GRASP_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    paths.reset_caches()
    try:
        assert paths.user_data_dir() == tmp_path / "Roaming" / "Grasp"
    finally:
        paths.reset_caches()


def test_portable_mode(monkeypatch, tmp_path):
    exe_dir = tmp_path / "Grasp"
    exe_dir.mkdir()
    (exe_dir / paths.PORTABLE_FLAG).write_text("")
    monkeypatch.delenv("GRASP_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "Grasp.exe"))
    paths.reset_caches()
    try:
        assert paths.user_data_dir() == exe_dir / paths.PORTABLE_DATA_DIR
    finally:
        monkeypatch.setattr(sys, "frozen", False, raising=False)
        paths.reset_caches()


# --- уровни -----------------------------------------------------------------


def test_twelve_sublevels_in_order():
    assert SUBLEVEL_CODES == (
        "A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2",
        "B2.1", "B2.2", "C1.1", "C1.2", "C2.1", "C2.2",
    )  # fmt: skip
    assert Level("B1.2") < Level("B2.1")
    assert Level("A1.1").prev() is None and Level("C2.2").next() is None
    assert Level("B1.2").next() == Level("B2.1")
    with pytest.raises(ValueError):
        Level("B3.1")
    assert not is_valid_level("b1.1")


@pytest.mark.parametrize(
    ("code", "band"), [("A1.1", 1), ("A2.2", 2), ("B1.1", 3), ("B2.2", 4), ("C1.1", 5), ("C2.2", 6)]
)
def test_toefl_mapping(code, band):
    assert Level(code).toefl_band == band
    assert expected_toefl(code) == band


def test_toefl_half_band_and_cap():
    assert expected_toefl("B1.2", 0.6) == 3.5
    assert expected_toefl("B1.1", 0.9) == 3.0
    assert expected_toefl("C2.2", 1.0) == 6.0


def test_levels_content_complete():
    levels = load_sublevels()
    assert list(levels) == list(SUBLEVEL_CODES)
    targets = [levels[c].vocab_target for c in SUBLEVEL_CODES]
    assert targets == sorted(targets)
    assert levels["A1.2"].vocab_target == 600 and levels["C2.2"].vocab_target >= 9000
    for info in levels.values():
        assert set(info.can_do) == {"reading", "listening", "writing", "speaking"}


# --- контент ----------------------------------------------------------------


def test_all_level_fields_valid():
    assert content.validate_levels() == []


def test_content_is_valid_json():
    for path in content.iter_content_files():
        json.loads(path.read_text(encoding="utf-8"))


def test_tenses_distribution_matches_plan():
    tenses = next(t for t in content.load_topics() if t.id == "tenses")
    by_id = {r.id: r.level for r in tenses.rules}
    assert by_id["to-be"] == "A1.1" and by_id["present-simple"] == "A1.1"
    assert by_id["present-perfect"] == "A2.2"
    assert by_id["future-perfect-continuous"] == "B2.2"
    assert by_id["aspect-academic-literary"] == "C2.2"
    # каждая ступень A1.1 → C2.2 содержит хотя бы одно правило о временах
    assert {r.level for r in tenses.rules} == set(SUBLEVEL_CODES)


def test_topics_and_levels_views_share_rules():
    total = sum(len(t.rules) for t in content.load_topics())
    grouped = content.rules_by_level()
    assert sum(len(v) for v in grouped.values()) == total
    ids = [(r.topic_id, r.id) for t in content.load_topics() for r in t.rules]
    assert len(ids) == len(set(ids)), "дубли id правил"


def test_vocabulary_has_ipa_and_level():
    words = content.load_vocabulary()
    assert words
    for w in words:
        assert is_valid_level(w["level"])
        assert w["ipa"].startswith("/") and w["ipa"].endswith("/")


# --- настройки ----------------------------------------------------------------


def test_settings_roundtrip(tmp_path):
    p = tmp_path / "settings.json"
    s = Settings(theme="dark", font_scale=130, exam_date="2027-03-01", minutes_per_day=45)
    save_settings(s, p)
    loaded = load_settings(p)
    assert loaded.theme == "dark" and loaded.font_scale == 130
    assert loaded.exam_date == "2027-03-01" and loaded.minutes_per_day == 45


def test_settings_normalized_and_corrupt(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"theme": "neon", "font_scale": 999, "target_toefl": 4.3, "unknown": 1}), "utf-8")
    s = load_settings(p)
    assert s.theme == "system" and s.font_scale == 200 and s.target_toefl == 4.5
    p.write_text("{not json", "utf-8")
    assert load_settings(p) == Settings()


def test_api_key_never_in_settings_file(data_dir, memory_keyring):
    secrets.set_api_key("anthropic", "sk-test-1234567890")
    save_settings(Settings())
    assert "sk-test" not in paths.settings_path().read_text("utf-8")
    assert secrets.get_api_key("anthropic") == "sk-test-1234567890"
    assert secrets.mask("sk-test-1234567890") == "sk-t…7890"
    secrets.delete_api_key("anthropic")
    assert not secrets.has_api_key("anthropic")


# --- отчёт об ошибке ------------------------------------------------------------


def test_crash_report_contains_traceback():
    try:
        raise RuntimeError("boom")
    except RuntimeError:
        report = crash.build_report(*sys.exc_info())
    assert "RuntimeError: boom" in report and "Grasp" in report and "Логи:" in report
