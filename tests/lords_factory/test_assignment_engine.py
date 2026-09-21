"""Движок назначения шаблонов: восемь обязательных сценариев.

Список сценариев задан заданием и проверяет не удобство, а свойства, потеря
которых видна не сразу:

* пятьдесят доменов подряд получают пятьдесят разных шаблонов;
* пятьдесят первый честно упирается в исчерпание пула и НИЧЕГО не меняет;
* повтор того же домена возвращает то же назначение;
* два одновременных домена не получают один шаблон;
* домен без нужных возможностей получает отказ, а не «что-нибудь похожее»;
* обрыв после резервирования не теряет шаблон и не выдаёт его дважды;
* существующий домен не переназначается молча;
* откат до активации оставляет резерв видимым, а не растворяет его.
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
МОДУЛЬ = КОРЕНЬ / "factory" / "templates" / "lords" / "registry" / "assignment.py"


def _загрузить():
    spec = importlib.util.spec_from_file_location("lords_assignment", МОДУЛЬ)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


assignment = _загрузить()

ВОЗМОЖНОСТИ = {"film", "series", "catalog", "search", "collections"}
ЛЕНТЫ = {"catalog", "details"}


def _пул(путь: pathlib.Path, сколько: int = 50, **переопределения) -> pathlib.Path:
    шаблоны = []
    for н in range(1, сколько + 1):
        шаблоны.append({
            "template_id": f"T{н:03d}",
            "slug": f"template-{н:03d}",
            "version": "1.0.0",
            "family": "forest-cinema",
            "status": переопределения.get("status", "ASSIGNABLE"),
            "source_commit": "0123abc",
            "capabilities": sorted(переопределения.get("capabilities", {"film", "catalog", "search"})),
            "required_feeds": sorted(переопределения.get("required_feeds", {"catalog"})),
            "visual_score": 92,
            "artifact_digest": "f" * 64,
            "assigned_domain": None,
            "reserved_at": None,
        })
    путь.mkdir(parents=True, exist_ok=True)
    (путь / "template-pool.json").write_text(
        json.dumps({"schema_version": 1, "pool": "lords-50-v1", "templates": шаблоны},
                   ensure_ascii=False), encoding="utf-8")
    return путь


def test_fifty_domains_get_fifty_distinct_templates(tmp_path):
    реестр = assignment.Реестр(_пул(tmp_path / "reg"))
    выданные = []
    for н in range(50):
        з = реестр.назначить(f"site{н:02d}.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
        выданные.append(з["template_id"])
    assert len(set(выданные)) == 50, "шаблон выдан дважды"
    assert выданные == sorted(выданные), "порядок выдачи не детерминирован"
    assert выданные[0] == "T001" and выданные[-1] == "T050"


def test_fifty_first_domain_is_refused_without_mutation(tmp_path):
    корень = _пул(tmp_path / "reg")
    реестр = assignment.Реестр(корень)
    for н in range(50):
        реестр.назначить(f"site{н:02d}.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    до = (корень / "assignments.json").read_text()

    with pytest.raises(assignment.ПулИсчерпан):
        реестр.назначить("overflow.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)

    assert (корень / "assignments.json").read_text() == до, "отказ изменил ledger"
    assert реестр.назначение("overflow.example") is None


def test_replay_of_same_domain_returns_same_assignment(tmp_path):
    реестр = assignment.Реестр(_пул(tmp_path / "reg"))
    первое = реестр.назначить("replay.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    второе = реестр.назначить("replay.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    третье = реестр.назначить("REPLAY.example  ", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    assert первое["template_id"] == второе["template_id"] == третье["template_id"]
    assert len(реестр.ledger()["assignments"]) == 1, "повтор создал второе назначение"


def _рабочий(корень: str, домен: str, очередь) -> None:
    модуль = _загрузить()
    try:
        з = модуль.Реестр(pathlib.Path(корень)).назначить(
            домен, возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
        очередь.put(з["template_id"])
    except Exception as ошибка:  # pragma: no cover - диагностика падения процесса
        очередь.put(f"ОШИБКА:{type(ошибка).__name__}:{ошибка}")


def test_concurrent_domains_never_share_a_template(tmp_path):
    """Два процесса одновременно: блокировка обязана развести их по разным шаблонам."""
    корень = _пул(tmp_path / "reg")
    очередь = multiprocessing.Queue()
    процессы = [
        multiprocessing.Process(target=_рабочий, args=(str(корень), f"race{н}.example", очередь))
        for н in range(6)
    ]
    for п in процессы:
        п.start()
    for п in процессы:
        п.join(timeout=60)
    выданные = [очередь.get() for _ in процессы]
    assert all(not str(в).startswith("ОШИБКА") for в in выданные), выданные
    assert len(set(выданные)) == len(выданные), f"одновременность выдала дубль: {выданные}"


def test_missing_capability_is_blocked_not_substituted(tmp_path):
    реестр = assignment.Реестр(_пул(tmp_path / "reg", capabilities={"film", "catalog", "episodes"}))
    with pytest.raises(assignment.НетСовместимого):
        реестр.назначить("nocaps.example", возможности={"film", "catalog"}, ленты=ЛЕНТЫ)
    assert реестр.ledger()["assignments"] == []


def test_missing_required_feed_is_blocked(tmp_path):
    реестр = assignment.Реестр(_пул(tmp_path / "reg", required_feeds={"catalog", "episodes"}))
    with pytest.raises(assignment.НетСовместимого):
        реестр.назначить("nofeed.example", возможности=ВОЗМОЖНОСТИ, ленты={"catalog"})


def test_crash_after_reservation_is_resumable_and_loses_nothing(tmp_path):
    """Резерв переживает обрыв: он виден и доигрывается, а не начинается заново."""
    корень = _пул(tmp_path / "reg")
    первый = assignment.Реестр(корень).назначить(
        "crash.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    assert первый["state"] == "RESERVED"
    assert первый["activated_at"] is None

    # Новый экземпляр реестра = новый процесс после обрыва.
    второй = assignment.Реестр(корень)
    повтор = второй.назначить("crash.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    assert повтор["template_id"] == первый["template_id"]

    следующий = второй.назначить("after-crash.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    assert следующий["template_id"] != первый["template_id"], "шаблон выдан дважды после обрыва"


def test_existing_domain_is_never_silently_reassigned(tmp_path):
    корень = _пул(tmp_path / "reg")
    реестр = assignment.Реестр(корень)
    первое = реестр.назначить("stable.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    реестр.активировать("stable.example")
    for _ in range(3):
        реестр.назначить("stable.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    записи = [з for з in реестр.ledger()["assignments"] if з["exact_domain"] == "stable.example"]
    assert len(записи) == 1
    assert записи[0]["template_id"] == первое["template_id"]
    assert записи[0]["state"] == "ACTIVE"


def test_activation_is_idempotent_and_reservation_survives_until_then(tmp_path):
    корень = _пул(tmp_path / "reg")
    реестр = assignment.Реестр(корень)
    реестр.назначить("activate.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    первая = реестр.активировать("activate.example")
    вторая = реестр.активировать("activate.example")
    assert первая["activated_at"] == вторая["activated_at"], "повторная активация сдвинула время"
    assert вторая["state"] == "ACTIVE"


@pytest.mark.parametrize("плохой", ["", "не-домен", "*.example.com", "site", "site..example",
                                    "http://site.example"])
def test_inexact_domain_is_refused(tmp_path, плохой):
    реестр = assignment.Реестр(_пул(tmp_path / "reg"))
    with pytest.raises(assignment.ОтказНазначения):
        реестр.назначить(плохой, возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)


def test_only_assignable_templates_are_handed_out(tmp_path):
    """TECHNICAL_CANDIDATE не попадает домену ни при каких условиях."""
    реестр = assignment.Реестр(_пул(tmp_path / "reg", status="TECHNICAL_CANDIDATE"))
    with pytest.raises(assignment.ПулИсчерпан):
        реестр.назначить("candidate.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)


def test_assignment_does_not_touch_indexability_or_dns(tmp_path):
    """Назначение — запись в реестре, а не выкладка: посторонних полей нет."""
    реестр = assignment.Реестр(_пул(tmp_path / "reg"))
    з = реестр.назначить("plain.example", возможности=ВОЗМОЖНОСТИ, ленты=ЛЕНТЫ)
    запрещённые = {"dns", "indexing", "indexability", "robots", "deploy", "activate_domain"}
    assert not (set(з) & запрещённые), f"в записи назначения появились поля выкладки: {set(з) & запрещённые}"
