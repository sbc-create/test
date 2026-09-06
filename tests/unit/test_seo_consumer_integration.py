"""Настоящий потребитель SEO против настоящего контракта ядра.

Проверки в `test_seo_binding_contract` спрашивают, выдаёт ли ядро обещанное.
Эти — спрашивают другое: **принимает ли выданное тот самый код SEO, который
написан и запушен**, без единой правки на его стороне.

Разница не формальная. Контракт можно выдать безупречно и всё же не совпасть
с потребителем по имени поля, по написанию состояния или по тому, сколько
кандидатов он требует при конфликте. Такое расхождение не ловится ничем,
кроме запуска настоящего кода.

**Проверка идёт через границу процесса.** Измерено при первой же попытке:
ядро работает на Python 3.10.12, потребитель — на 3.11.16 и пользуется
`enum.StrEnum`, которого в 3.10 нет. Ввезти потребителя в интерпретатор ядра
невозможно, и это к лучшему: контракт пересекает границу процесса в виде
JSON — ровно так, как он пересекает её в работе. Проверка ввозом чужого
модуля доказала бы совместимость объектов в одной памяти, а не совместимость
контракта.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from factory.site_engine.adapters import lords_seo_binding as ad
from factory.site_engine.seo_binding import BindingState

#: Коммит потребителя, против которого доказывается совместимость. Не
#: `latest` и не «ветка»: совместимость доказывается против названного
#: состояния кода.
SEO_CONSUMER_SHA = "99e12ba7588693b17229046bd6a747675be7bbc9"

SEO_TREE = Path("/home/claude/wt-seo-quality-21")
SEO_PYTHON = Path("/home/claude/work-seo/seo-engine/.venv/bin/python")
ПРОБА = Path(__file__).with_name("consumer_probe_seo.py")
СНИМОК = "2026-09-06T04:45:32+00:00"


def _потребитель_доступен() -> Path:
    if not (SEO_TREE / "seo_engine").is_dir():
        pytest.skip(f"дерева потребителя нет: {SEO_TREE}")
    if not SEO_PYTHON.exists():
        pytest.skip(f"интерпретатора потребителя нет: {SEO_PYTHON}")
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SEO_TREE,
                             capture_output=True, text=True,
                             check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as error:  # pragma: no cover
        pytest.skip(f"состояние дерева потребителя не читается: {error}")
    if sha != SEO_CONSUMER_SHA:
        pytest.skip(
            f"дерево потребителя на {sha[:12]}, а совместимость доказывается "
            f"против {SEO_CONSUMER_SHA[:12]}")
    return SEO_TREE


def запись(**kwargs):
    основа = {
        "external_id": "01a00000-0000-7000-8000-000000000001",
        "name": "Произведение", "type": "tv", "is_series": True,
        "tags": [], "year": 2026,
        "playback": {"aggregator": "kp", "title_id": "1"},
        "external_ids": {"kp": "1"},
    }
    основа.update(kwargs)
    return основа


def связь(**kwargs):
    return ad.build([запись(**kwargs)], site_id="site-01", snapshot_at=СНИМОК,
                    provenance="catalog-cache:test")[0]


def случай(имя: str, b, *, ожидание: dict) -> dict:
    """Одна запись для пробы потребителя."""
    return {
        "case": имя,
        "domain": "lordfilm47.space",
        "profileVersion": "lords-01/1.0.0",
        "canonicalPath": b.canonical_path or "/title/x/",
        "contentIdentity": b.as_identity_payload(),
        "playbackReasonCode": ("OK" if b.playback_reason_code.value == "PLAYBACK_OK"
                               else b.playback_reason_code.value),
        "playbackObservedAt": b.playback_observed_at,
        "externalIds": sorted(b.external_ids),
        "expect": ожидание,
    }


#: Набор случаев. Каждый — сочетание вида, состояния воспроизведения и
#: ожидаемого решения о странице.
def _случаи() -> list[dict]:
    return [
        случай("играющий сериал", связь(type="tv"), ожидание={
            "contentKind": "SERIES", "identityStatus": "RESOLVED",
            "schemaType": "TVSeries", "mayPromisePlayback": True,
            "eligibility": "INDEXABLE_WITH_PLAYBACK"}),
        случай("играющий фильм", связь(type="movie"), ожидание={
            "contentKind": "MOVIE", "identityStatus": "RESOLVED",
            "schemaType": "Movie", "mayPromisePlayback": True,
            "eligibility": "INDEXABLE_WITH_PLAYBACK"}),
        случай("ONA", связь(type="tv", tags=["ona"]), ожидание={
            "contentKind": "ONA", "identityStatus": "RESOLVED",
            "schemaType": "TVSeries", "mayPromisePlayback": True,
            "eligibility": "INDEXABLE_WITH_PLAYBACK"}),
        случай("OVA", связь(type="tv", tags=["ova"]), ожидание={
            "contentKind": "OVA", "identityStatus": "RESOLVED",
            "schemaType": "TVSeries", "mayPromisePlayback": True,
            "eligibility": "INDEXABLE_WITH_PLAYBACK"}),
        случай("спецвыпуск", связь(type="movie", tags=["special"]), ожидание={
            "contentKind": "SPECIAL", "identityStatus": "RESOLVED",
            "schemaType": "TVSpecial", "mayPromisePlayback": True,
            "eligibility": "INDEXABLE_WITH_PLAYBACK"}),
        случай("анимационный сериал",
               связь(type="tv", tags=["cartoon"]), ожидание={
                   "contentKind": "SERIES", "identityStatus": "RESOLVED",
                   "schemaType": "TVSeries", "mayPromisePlayback": True,
                   "eligibility": "INDEXABLE_WITH_PLAYBACK"}),
        случай("вид не установлен", связь(type="", tags=[]), ожидание={
            "contentKind": "UNKNOWN", "identityStatus": "MISSING",
            "schemaType": "", "mayPromisePlayback": True,
            "eligibility": "HOLD_FOR_KIND_REVIEW"}),
        случай("конфликт вида", связь(type="movie", tags=["ona"]), ожидание={
            "contentKind": "UNKNOWN", "identityStatus": "CONFLICTED",
            "schemaType": "", "mayPromisePlayback": True,
            "eligibility": "HOLD_FOR_KIND_REVIEW"}),
        случай("только imdb",
               связь(playback=None, external_ids={"imdb": "tt1"}), ожидание={
                   "contentKind": "SERIES", "identityStatus": "RESOLVED",
                   "schemaType": "TVSeries", "mayPromisePlayback": False,
                   "eligibility": "INDEXABLE_METADATA_ONLY"}),
        случай("идентификаторов нет",
               связь(playback=None, external_ids={}), ожидание={
                   "contentKind": "SERIES", "identityStatus": "RESOLVED",
                   "schemaType": "TVSeries", "mayPromisePlayback": False,
                   "eligibility": "INDEXABLE_METADATA_ONLY"}),
    ]


@pytest.fixture(scope="module")
def итог_пробы(tmp_path_factory):
    """Один запуск пробы потребителя на весь модуль."""
    дерево = _потребитель_доступен()
    файл = tmp_path_factory.mktemp("contract") / "cases.json"
    файл.write_text(json.dumps(_случаи(), ensure_ascii=False), "utf-8")
    прогон = subprocess.run(
        [str(SEO_PYTHON), str(ПРОБА), str(файл)],
        cwd=str(дерево), capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(дерево),
             "HOME": str(Path.home())})
    if прогон.returncode not in (0, 1):  # pragma: no cover
        pytest.fail(f"проба потребителя не запустилась: {прогон.stderr[-800:]}")
    строка = (прогон.stdout or "").strip().splitlines()
    if not строка:  # pragma: no cover
        pytest.fail(f"проба ничего не напечатала: {прогон.stderr[-800:]}")
    return json.loads(строка[-1])


def test_потребитель_принимает_контракт_целиком(итог_пробы):
    assert итог_пробы["passed"] is True, итог_пробы["failures"]


def test_все_случаи_действительно_проверены(итог_пробы):
    """Пустой набор проверок прошёл бы «успешно», ничего не проверив."""
    assert len(итог_пробы["checks"]) == len(_случаи()) * 5


@pytest.mark.parametrize("имя", [с["case"] for с in _случаи()])
def test_случай_принят_потребителем(итог_пробы, имя):
    свои = [c for c in итог_пробы["checks"] if c["name"].startswith(имя + ":")]
    assert свои, f"случай {имя} не проверялся"
    провалы = [c for c in свои if not c["passed"]]
    assert not провалы, провалы


def test_совместимость_у_потребителя_предварительная(итог_пробы):
    """Пока матрица не подтвердила контракт, потребитель обязан это видеть."""
    assert итог_пробы["consumerCompatibility"] == "PROVISIONAL"


def test_потребитель_и_производитель_на_разных_интерпретаторах():
    """Расхождение измерено и зафиксировано, а не обойдено молча."""
    _потребитель_доступен()
    свой = f"{sys.version_info.major}.{sys.version_info.minor}"
    чужой = subprocess.run([str(SEO_PYTHON), "-c",
                            "import sys;print(f'{sys.version_info.major}."
                            "{sys.version_info.minor}')"],
                           capture_output=True, text=True).stdout.strip()
    assert свой != чужой, (
        "интерпретаторы совпали — проверку через границу процесса можно "
        "упростить, но сначала это надо подтвердить измерением")


def test_неоднозначный_адрес_до_потребителя_не_доходит():
    """Запись с коллизией маршрута не объявляется связанной."""
    связи = ad.build([запись(external_id="a-1", name="Одно"),
                      запись(external_id="a-2", name="Одно"),
                      запись(external_id="a-3", name="Одно 2")],
                     site_id="site-01", snapshot_at=СНИМОК,
                     provenance="catalog-cache:test")
    коллизии = [b for b in связи
                if b.binding_state is BindingState.ROUTE_COLLISION]
    assert коллизии, "коллизия не обнаружена"
    assert all(b.binding_state is not BindingState.BOUND for b in коллизии)
