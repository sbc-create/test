"""Выделенный сайт не публикуется общим путём — ни одним из них.

Правило задания: «поправить модуль на таком-то домене» обязано вести ровно в
один репозиторий. Пока у домена остаётся второй источник изменений, ответ на
этот вопрос зависит от того, кто выложил последним, — а это не ответ.

Проверяется поведение, а не наличие кода: конвейер и сборка запускаются и
обязаны отказать, CLI обязан вернуть свой код возврата, а хостовые сценарии —
спросить реестр раньше, чем сделают первую запись.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(КОРЕНЬ))

from factory import build as build_mod  # noqa: E402
from factory import pipeline  # noqa: E402
from factory.cell import registry  # noqa: E402
from factory.errors import FAILURE_STATES, NON_RETRYABLE, SiteExtracted  # noqa: E402

ВЫДЕЛЕННЫЙ = "lords-01"
НЕ_ВЫДЕЛЕННЫЙ = "lords-02"


@pytest.fixture()
def реестр(tmp_path: Path) -> Path:
    """Свой реестр: тест не должен зависеть от того, что уже перенесено."""
    путь = tmp_path / "site-cells.json"
    путь.write_text(json.dumps({
        "schema_version": 1,
        "cells": [
            {"site_id": ВЫДЕЛЕННЫЙ, "domain": "lordfilm47.space",
             "template": {"template_id": "lords-nova"},
             "repo": {"remote": "https://github.com/sbc-create/site-lordfilm47-space"}},
            {"site_id": НЕ_ВЫДЕЛЕННЫЙ, "domain": "lordserial33.biz",
             "template": {"template_id": "lords-nova"}, "repo": {}},
            {"site_id": "moved-to-monorepo", "domain": "example.test",
             "template": {"template_id": "lords-nova"},
             "repo": {"remote": "https://github.com/sbc-create/site-factory"}},
        ],
    }, ensure_ascii=False), encoding="utf-8")
    return путь


def test_выделенным_считается_только_сайт_со_своим_репозиторием(реестр):
    выделенные = registry.extracted_sites(реестр)
    assert ВЫДЕЛЕННЫЙ in выделенные
    assert НЕ_ВЫДЕЛЕННЫЙ not in выделенные
    # Монорепозиторий — не собственный репозиторий: иначе достаточно было бы
    # записать любой remote, чтобы объявить сайт выделенным.
    assert "moved-to-monorepo" not in выделенные


def test_отказ_называет_репозиторий(реестр):
    with pytest.raises(registry.SiteAlreadyExtracted) as ош:
        registry.require_not_extracted(ВЫДЕЛЕННЫЙ, action="выкладка", path=реестр)
    # Отказ без адреса заставляет искать репозиторий вручную — и, значит,
    # угадывать. Адрес обязан быть в самом сообщении.
    assert "site-lordfilm47-space" in str(ош.value)


def test_невыделенный_сайт_проходит(реестр):
    registry.require_not_extracted(НЕ_ВЫДЕЛЕННЫЙ, action="выкладка", path=реестр)


def test_статус_зарегистрирован_и_не_ретраится():
    assert "BLOCKED_SITE_EXTRACTED" in FAILURE_STATES
    # Повтор ничего не изменит: выделение — не временная ошибка среды.
    assert "BLOCKED_SITE_EXTRACTED" in NON_RETRYABLE
    схема = json.loads((КОРЕНЬ / "schemas" / "job-result.schema.json")
                       .read_text(encoding="utf-8"))
    assert "BLOCKED_SITE_EXTRACTED" in json.dumps(схема)


def test_конвейер_отказывает_и_ничего_не_пишет(tmp_path):
    """Отказ обязан наступить раньше, чем появится задание."""
    до = {p: p.stat().st_mtime_ns for p in (КОРЕНЬ / "var").rglob("*") if p.is_file()}
    with pytest.raises(SiteExtracted) as ош:
        pipeline.run_job(ВЫДЕЛЕННЫЙ, environment="production")
    assert ош.value.status == "BLOCKED_SITE_EXTRACTED"
    assert ош.value.blocks_stage == "RECEIVED"
    после = {p: p.stat().st_mtime_ns for p in (КОРЕНЬ / "var").rglob("*") if p.is_file()}
    assert до == после, "отказ оставил следы в var/"


def test_сборка_отказывает():
    """Артефакт выделенного сайта не изготавливается здесь.

    Отказ именно на сборке, а не только на выкладке: собранный пакет можно
    поставить и руками, и тогда запрет на выкладку уже ничего не решает.
    """
    with pytest.raises(SiteExtracted) as ош:
        build_mod.build(ВЫДЕЛЕННЫЙ)
    assert ош.value.status == "BLOCKED_SITE_EXTRACTED"
    assert ош.value.blocks_stage == "BUILDING"


def _cli(*аргументы: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "factory", "cell", "extracted", *аргументы],
                          cwd=str(КОРЕНЬ), capture_output=True, text=True)


def test_cli_возвращает_код_отказа():
    """Имена сайтов берутся из текущего реестра, а не зашиваются.

    Первая версия теста называла `lords-02` как невыделенный — и позеленела
    ровно до того часа, когда `lords-02` перенесли. Тест, привязанный к стадии
    переноса, начинает падать на собственном прогрессе, и это не находка, а шум.
    """
    перечень = json.loads(_cli().stdout)
    выделенные = sorted(перечень["extracted"])
    assert выделенные, "в реестре нет ни одного выделенного сайта — проверять нечего"

    отказ = _cli("--modules", выделенные[0])
    assert отказ.returncode == 3
    assert "BLOCKED_SITE_EXTRACTED" in отказ.stderr

    все_ячейки = json.loads(subprocess.run(
        [sys.executable, "-m", "factory", "cell", "registry"],
        cwd=str(КОРЕНЬ), capture_output=True, text=True).stdout)
    свободные = [c["site_id"] for c in все_ячейки["cells"]
                 if c["site_id"] not in перечень["extracted"]]
    assert свободные, "все сайты выделены — нечем проверить пропуск"
    пропуск = _cli("--modules", свободные[0])
    assert пропуск.returncode == 0, пропуск.stderr


#: Первая запись каждого сценария: до неё обязан стоять вопрос к реестру.
ПЕРВАЯ_МУТАЦИЯ = {
    "automation/host/finalize-public-sites.sh": r"^WORKDIR=\"\$\(mktemp",
    "automation/host/lords-staging-apply.sh": r"^ROLLBACK_READY=1",
}


@pytest.mark.parametrize("сценарий,мутация", sorted(ПЕРВАЯ_МУТАЦИЯ.items()))
def test_хостовой_сценарий_спрашивает_реестр_до_первой_записи(сценарий, мутация):
    """Порядок важнее наличия: проверка после первой записи бесполезна.

    Сценарий, тронувший часть контура и остановленный на середине, оставляет
    состояние, которого нет ни в одном отчёте, — поэтому вопрос задаётся до
    любой мутации, а не перед той операцией, что касается витрин.
    """
    строки = (КОРЕНЬ / сценарий).read_text(encoding="utf-8").splitlines()
    охрана = next((i for i, s in enumerate(строки) if "cell extracted" in s), None)
    первая = next((i for i, s in enumerate(строки) if re.match(мутация, s)), None)
    assert охрана is not None, f"{сценарий}: реестр не спрашивается вовсе"
    assert первая is not None, f"{сценарий}: не нашёл первую мутацию {мутация!r}"
    assert охрана < первая, f"{сценарий}: проверка стоит после первой записи"
