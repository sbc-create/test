"""Быстрый путь вызывается так, как его вызывает конвейер.

Регрессия к отказу второго настоящего цикла 2026-09-02 01:56:

    IncrementalError: цель уже существует: /tmp/tmp.oLkxTcppsA
    [lords-refresh] lords-01: быстрый путь неприменим (код 1) — полная сборка

Конвейер создаёт каталог сборки заранее (`staging="$(mktemp -d)"`), а прежние
проверки передавали несуществующий путь — и потому проверяли не тот вызов.
Отказ был безопасным (полная сборка вместо быстрой), но быстрый путь не
срабатывал ни разу.

Проверка обязана доходить до `incremental.clone`: с пустым кэшем сценарий
выходит раньше, и такая проверка проходит даже на сломанном коде. Поэтому здесь
собирается настоящий маленький каталог и записывается снимок.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
СЦЕНАРИЙ = КОРЕНЬ / "automation" / "host" / "lords-fast-render.py"

СОБРАН, НУЖЕН_ПОЛНЫЙ, НЕЧЕГО = 0, 2, 10


def _запись(идентификатор: str, имя: str, год: int) -> dict:
    """Запись каталога с полями, которые читает разбор живого каталога."""
    return {
        "external_id": идентификатор,
        "external_ids": {"kinopoisk": None, "imdb": None},
        "name": имя,
        "type": "movies",
        "year": год,
        "is_series": False,
        "licensed": True,
        "playback": {"aggregator": "cdnvideohub", "id": идентификатор},
        "poster_url": f"https://poster.example/{идентификатор}.jpg",
        "tags": [],
        "imdb_rating": 6.0,
        "kinopoisk_rating": 6.5,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _запустить(*, repo, staging, current, cache, var, record=False):
    аргументы = [sys.executable, str(СЦЕНАРИЙ), "lords-01",
                 "--repo", str(repo), "--staging", str(staging),
                 "--current", str(current), "--cache", str(cache), "--var", str(var)]
    if record:
        аргументы.append("--record")
    готово = subprocess.run(аргументы, capture_output=True, text=True, cwd=str(КОРЕНЬ))
    строки = [s for s in готово.stdout.strip().splitlines() if s.startswith("{")]
    return готово.returncode, (json.loads(строки[-1]) if строки else {}), готово.stderr


@pytest.fixture
def стенд(tmp_path):
    """Кэш каталога, записанный снимок и собранный базовый релиз."""
    кэш = tmp_path / "cache"
    кэш.mkdir()
    записи = [_запись("t1", "Первый", 2001), _запись("t2", "Второй", 2002)]
    (кэш / "lords-01.json").write_text(
        json.dumps({"source": "test", "fetched_at_ms": 0, "items": записи},
                   ensure_ascii=False), encoding="utf-8")

    repo, var = tmp_path / "repo", tmp_path / "var"
    база = tmp_path / "base"          # каталога нет — его создаст сборка
    код, отчёт, ошибки = _запустить(repo=repo, staging=база, current=кэш,
                                    cache=кэш, var=var, record=True)
    assert код == СОБРАН, f"снимок не записан: {код} {ошибки[-300:]}"
    return {"кэш": кэш, "repo": repo, "var": var, "tmp": tmp_path}


class TestЗаранееСозданныйКаталогСборки:
    def test_пустой_каталог_не_ломает_быстрый_путь(self, стенд, tmp_path):
        """Конвейер создаёт каталог до вызова — это не повод падать."""
        база = tmp_path / "release"
        (база / "title").mkdir(parents=True)
        (база / "index.html").write_text("<html>главная</html>", encoding="utf-8")

        staging = tmp_path / "staging"
        staging.mkdir()  # ровно то, что делает `mktemp -d` в конвейере

        код, отчёт, ошибки = _запустить(
            repo=стенд["repo"], staging=staging, current=база,
            cache=стенд["кэш"], var=стенд["var"])
        assert "IncrementalError" not in ошибки, (
            "заранее созданный пустой каталог сборки не должен ломать быстрый путь: "
            f"{ошибки[-300:]}")
        assert код != 1, f"падение вместо решения: {ошибки[-300:]}"

    def test_непустой_каталог_отправляет_в_полный_рендер(self, стенд, tmp_path):
        """Чужое содержимое в каталоге сборки — повод пересобрать, а не гадать."""
        база = tmp_path / "release2"
        (база / "title").mkdir(parents=True)
        (база / "index.html").write_text("<html>главная</html>", encoding="utf-8")

        staging = tmp_path / "staging2"
        staging.mkdir()
        (staging / "чужое").write_text("не наше", encoding="utf-8")

        код, отчёт, ошибки = _запустить(
            repo=стенд["repo"], staging=staging, current=база,
            cache=стенд["кэш"], var=стенд["var"])
        assert код == НУЖЕН_ПОЛНЫЙ, f"ожидался полный рендер, получено {код}: {ошибки[-200:]}"
        assert (staging / "чужое").exists(), "чужое содержимое не должно удаляться"
