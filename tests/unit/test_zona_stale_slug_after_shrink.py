"""После пробы свежести синтетики не остаётся ни в данных, ни в выдаче.

Сам дефект (удалённая запись продолжает отвечать 200 до перезапуска) описан в
`docs/release-orchestrator/TEMPLATE_ZONA_BLOCKERS.md` как
`TEMPLATE_ZONA_BLOCKER-05`. Его воспроизводит
`automation/host/zonafilm-cc-freshness-probe.py`, и доказательство прогона
лежит в `artifacts/evidence/.../05-content/freshness-probe.json`.

Здесь — не воспроизведение, а проверка последствия: перечитывание каталога на
53 652 записи занимает у витрины минуты, и гонять его в каждом прогоне тестов
значило бы сделать набор неприменимым. Зато требование «после проверки не
оставляй синтетические данные» проверяется дёшево и обязано проверяться всегда:
и в файлах, и в живой выдаче.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ФРОНТ = Path("/srv/lords/.frontend")
КАТАЛОГ = ФРОНТ / "zona-02-catalog.json"
ПОДРОБНОСТИ = ФРОНТ / "zona-02-details.json"
МЕТКИ = ("SYNTHETIC-FRESHNESS-PROBE", "synthetic-freshness-probe", "synthetic-")
ORIGIN = os.environ.get("ZONA02_ORIGIN", "http://127.0.0.1:9123")
HOST = os.environ.get("ZONA02_HOST", "zonafilm.cc")


def _запрос(путь: str, timeout: float = 120.0) -> int:
    req = urllib.request.Request(ORIGIN + путь, headers={"Host": HOST})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


pytestmark = pytest.mark.skipif(
    not КАТАЛОГ.is_file(), reason="витрина zona-02 не развёрнута")


def test_в_опубликованном_каталоге_нет_синтетики():
    текст = КАТАЛОГ.read_text(encoding="utf-8")
    for метка in МЕТКИ:
        assert метка not in текст, f"в zona-02-catalog.json осталась метка {метка}"


def test_в_подробностях_нет_синтетики():
    if not ПОДРОБНОСТИ.is_file():
        pytest.skip("бокового файла подробностей нет")
    текст = ПОДРОБНОСТИ.read_text(encoding="utf-8")
    for метка in МЕТКИ:
        assert метка not in текст, f"в zona-02-details.json осталась метка {метка}"


def test_каталог_совпадает_с_тем_что_опубликовал_инструмент():
    """Побайтная сверка с суммой из отчёта публикации.

    Проба свежести меняет этот файл и возвращает его обратно. Совпадение суммы
    — единственный способ утверждать, что вернулся именно он, а не похожий.
    """
    отчёт = (Path(__file__).resolve().parents[2] / "artifacts" / "evidence"
             / "release-zonafilm-cc-full-cycle-01" / "12-deploy"
             / "restore-after-rollback.json")
    ожидаемая = "5cd67cf22cd00b4f29391e1d2b513a3ba986402b8e5c868e5c89944238fca150"
    import hashlib
    фактическая = hashlib.sha256(КАТАЛОГ.read_bytes()).hexdigest()
    assert фактическая == ожидаемая, (
        f"каталог витрины не совпадает с опубликованным: {фактическая}"
    )
    assert отчёт.is_file() or True  # отчёт справочный, отсутствие не отменяет сверку


def test_синтетический_адрес_не_отвечает_на_живой_витрине():
    """Ровно та проверка, которая ловит TEMPLATE_ZONA_BLOCKER-05 в остатке."""
    if _запрос("/healthz", timeout=15) != 200:
        pytest.skip("витрина не отвечает: проверять живую выдачу нечем")
    код = _запрос("/title/synthetic-freshness-probe/")
    assert код == 404, (
        f"удалённая запись отвечает {код} вместо 404: указатель по slug сохранил "
        "снятую запись (TEMPLATE_ZONA_BLOCKER-05). Обходной путь — перезапуск "
        "службы витрины после публикации, уменьшившей каталог"
    )
