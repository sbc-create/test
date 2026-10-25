"""Изменение реестра источников определяется по СОДЕРЖИМОМУ, а не по mtime.

Этот момент снимает удержание отказов `REVIEW_ON_NEW_SOURCES`: появился новый
путь к фактам — отказ «нет источника» пересматривается. Пока он брался из
`mtime`, «изменением» считалось любое прикосновение к файлу, а в рабочей копии
файл трогает git: checkout и слияние ветки переписывают его с тем же
содержимым.

Следствие посчитано заранее, 25.10: удержание держало 266 заданий с исходом
`SOURCES_MISSING`, и первое же слияние ветки сняло бы их все разом — редактор
перебрал бы те же адреса заново примерно за $40 (при измеренных $0,154 за
материал), ничего не найдя, потому что источники не менялись.

Второй случай столь же важен и противоположен: человек ПРАВДА изменил реестр,
и тогда пересмотр обязан открыться. Поэтому «нет отметки о содержимом» само по
себе ничего не решает: сверяется, совпадает ли рабочая копия с закоммиченной.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from seo_operator import regular  # noqa: E402

ВРЕМЯ_КОММИТА = dt.datetime(2026, 10, 9, 12, 17, 11, tzinfo=dt.timezone.utc)
СЕЙЧАС = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)


@pytest.fixture()
def реестр(tmp_path, monkeypatch):
    """Крошечный git-репозиторий с реестром источников в коммите."""
    (tmp_path / "config").mkdir()
    файл = tmp_path / "config" / "editorial-sources.json"
    файл.write_text('{"sources": ["shikimori"]}', encoding="utf-8")
    env = dict(os.environ,
               GIT_AUTHOR_NAME="т", GIT_AUTHOR_EMAIL="t@example.invalid",
               GIT_COMMITTER_NAME="т", GIT_COMMITTER_EMAIL="t@example.invalid",
               GIT_AUTHOR_DATE=ВРЕМЯ_КОММИТА.isoformat(),
               GIT_COMMITTER_DATE=ВРЕМЯ_КОММИТА.isoformat(),
               GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
    for команда in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "commit", "-q", "-m", "реестр"]):
        subprocess.run(команда, cwd=tmp_path, env=env, check=True,
                       capture_output=True, timeout=60)
    monkeypatch.setattr(regular, "REPO_ROOT", tmp_path)
    return файл


def test_первая_встреча_берёт_время_коммита(реестр, tmp_path) -> None:
    """Содержимое старое — значит удержание отказов остаётся в силе."""
    assert regular._source_policy_changed_at(
        реестр, tmp_path / "seen.json", СЕЙЧАС) == ВРЕМЯ_КОММИТА


def test_повторный_вызов_даёт_то_же_время(реестр, tmp_path) -> None:
    состояние = tmp_path / "seen.json"
    первый = regular._source_policy_changed_at(реестр, состояние, СЕЙЧАС)
    позже = regular._source_policy_changed_at(
        реестр, состояние, СЕЙЧАС + dt.timedelta(days=3))
    assert первый == позже == ВРЕМЯ_КОММИТА


def test_прикосновение_к_файлу_изменением_не_считается(реестр, tmp_path) -> None:
    """Главное: git-операция меняет mtime, но не содержимое."""
    состояние = tmp_path / "seen.json"
    до = regular._source_policy_changed_at(реестр, состояние, СЕЙЧАС)
    os.utime(реестр, (СЕЙЧАС.timestamp(), СЕЙЧАС.timestamp()))
    после = regular._source_policy_changed_at(реестр, состояние, СЕЙЧАС)
    assert после == до, "mtime снова решает за содержимое"


def test_настоящая_правка_открывает_пересмотр(реестр, tmp_path) -> None:
    реестр.write_text('{"sources": ["shikimori", "wikidata"]}', encoding="utf-8")
    assert regular._source_policy_changed_at(
        реестр, tmp_path / "seen.json", СЕЙЧАС) == СЕЙЧАС


def test_нечитаемый_реестр_ничего_не_утверждает(tmp_path) -> None:
    assert regular._source_policy_changed_at(
        tmp_path / "нет.json", tmp_path / "seen.json") is None


def test_незаписываемое_состояние_не_роняет_правило(реестр, tmp_path) -> None:
    """Потерять пересмотр хуже, чем не сохранить отметку."""
    состояние = tmp_path / "каталог-вместо-файла"
    состояние.mkdir()
    assert regular._source_policy_changed_at(реестр, состояние, СЕЙЧАС) is not None


# --- связь с удержанием отказов ---------------------------------------------

def журнал_отказа(tmp_path: pathlib.Path, когда: str) -> pathlib.Path:
    п = tmp_path / "queue_events.jsonl"
    п.write_text("\n".join(json.dumps(з, ensure_ascii=False) for з in [
        {"event": "task_registered", "task_id": "t1",
         "canonical_url": "https://animedia.space/title/x", "at": когда},
        {"event": "task_result", "task_id": "t1", "outcome": "SOURCES_MISSING",
         "at": когда},
    ]) + "\n", encoding="utf-8")
    return п


def test_отказ_после_правки_реестра_держится(tmp_path) -> None:
    урлы, _ = regular.result_holds(
        журнал_отказа(tmp_path, "2026-10-24T10:00:00Z"), СЕЙЧАС,
        policy_changed_at=dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc))
    assert "https://animedia.space/title/x" in урлы


def test_отказ_до_правки_реестра_пересматривается(tmp_path) -> None:
    урлы, _ = regular.result_holds(
        журнал_отказа(tmp_path, "2026-10-08T10:00:00Z"), СЕЙЧАС,
        policy_changed_at=dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc))
    assert "https://animedia.space/title/x" not in урлы


def test_мост_и_цикл_решают_одним_правилом() -> None:
    """Два перечня «что считать изменением» держали бы разное."""
    from factory.qwen import queue_bridge
    текст = (КОРЕНЬ / "factory/qwen/queue_bridge.py").read_text(encoding="utf-8")
    assert "_source_policy_changed_at" in текст
    assert "st_mtime" not in текст, "мост снова судит по mtime"
    assert queue_bridge.РЕЕСТР_ИСТОЧНИКОВ.name == regular.SOURCE_POLICY.name
