"""Проверки окружения журнала, которые верны в любом клоне репозитория.

Отдельным файлом, потому что эти проверки касаются не журнала, а того, что он
ничего вокруг себя не испортил. Смешивать их с функциональными тестами значит
потерять различие между «журнал работает» и «журнал ничего не сломал».

Что отсюда ушло и куда
----------------------

Часть прежних проверок утверждала о ЖИВОМ флоте, а не о коде: каноническая
резервная копия в `/srv/site-factory`, перепись реестра (13 сайтов, 9
production), три синтетические записи и `registry_version=32`, ответы публичных
доменов, отсутствие осиротевших процессов и единственность слушателя на
`127.0.0.1:8790`. В CI ничего этого нет — там падало десять проверок, ни одна
из которых не сообщала о журнале ничего.

Они не удалены и не ослаблены: они переехали в host-контур `bin/host-attest`
(`host_attestation/checks.py`) и стали обязательными проверками свидетельства,
без которого production-выкат не выпускается. Соответствие:

    test_27  → ledger.backup
    test_31  → registry.synthetic_records
    test_32  → fleet.public_domains
    test_36  → systemd.no_orphan_processes
    test_37  → systemd.listeners
    перепись → fleet.census, registry.version

`test_28` проверял, что прогон по эфемерной базе не изменил базовую линию
реестра, и делал это запуском скрипта `n_plus_one_isolated.py`, лежащего вне
репозитория. Скрипт воспроизвести нельзя, а проверяемое им свойство —
«базовая линия реестра не изменилась» — измеряется на хосте проверками
`fleet.census` и `registry.synthetic_records`, причём непосредственно, а не по
выводу постороннего процесса.

Здесь остались проверки, не зависящие от машины: восстановление публикации
после перерыва, отсутствие записи в публичные сайты, отсутствие обращений к
внешним провайдерам и отсутствие секретов в данных прогона. Журнал и лента —
эфемерные, их поднимает `tests/audit/conftest.py`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

import pytest

from factory.site_engine.audit import ledger_store as store

#: Журнал прогона. Приходит из обвязки, а не из рабочего контура машины:
#: умолчания здесь намеренно нет — набор, который при отсутствии обвязки молча
#: уходит в канонический журнал, пишет в историю системы.
ЖУРНАЛ = os.environ["AUDIT_LEDGER_DB"]
#: Корень доказательств прогона. Тот же, что объявлен службе.
ДОКАЗАТЕЛЬСТВА = Path(os.environ["AUDIT_EVIDENCE_DIR"])

ДОМЕНЫ = ["yummyani.org", "yummyani.site", "yummyani.biz"]
#: Исходный код журнала — в репозитории; сканировать рабочий каталог данных
#: бессмысленно, там больше нет ни одного модуля.
ИСХОДНИКИ = [Path(__file__).resolve().parent,
             Path(__file__).resolve().parents[2] / "factory/site_engine/audit"]


# 23
def test_23_перерыв_ленты_не_теряет_событий(tmp_path, monkeypatch):
    """Публикация падает после записи в ленту, но до отметки.

    Такое падение обязано дать повтор, а не потерю: повтор потребитель
    отсеет по event_id, потерю не заметит никто.
    """
    from factory.site_engine.audit import ledger_publisher as lp
    копия = tmp_path / "l.sqlite3"
    shutil.copyfile(ЖУРНАЛ, копия)
    лента = tmp_path / "feed.jsonl"
    c = store.открыть(копия)
    for i in range(3):
        store.append(c, {"event_type": "test.outage.v1", "phase": "OBSERVED",
                         "result": "SUCCESS", "scope": "FLEET",
                         "correlation_id": f"out-{i}",
                         "idempotency_key": f"outage-{i}", "summary": "перерыв"},
                     producer_service="architect", actor_id="service:architect",
                     actor_type="SERVICE", authority="OBSERVE")
    ждали = c.execute("SELECT count(*) c FROM ledger_outbox "
                      "WHERE published_at IS NULL").fetchone()["c"]
    c.close()
    monkeypatch.setattr(lp, "ЖУРНАЛ", str(копия))
    monkeypatch.setattr(lp, "ЛЕНТА", лента)

    настоящий = store.сейчас
    вызовов = {"n": 0}

    def падать(*a, **k):
        вызовов["n"] += 1
        if вызовов["n"] == 2:      # запись в ленту прошла, отметка — нет
            raise RuntimeError("перерыв публикации")
        return настоящий(*a, **k)

    monkeypatch.setattr(store, "сейчас", падать)
    with pytest.raises(RuntimeError):
        lp.опубликовать()
    monkeypatch.setattr(store, "сейчас", настоящий)
    итог = lp.опубликовать()          # восстановление
    assert итог["backlog"] == 0
    строки = [json.loads(s) for s in лента.read_text(encoding="utf-8").splitlines()]
    ушедшие = {s["event_id"] for s in строки}
    assert len(ушедшие) == ждали, "после восстановления часть событий не дошла"
    assert len(строки) >= ждали, "доставка не at-least-once"


# 33
def test_33_публичных_записей_не_производилось():
    # Единственный способ этого прогона изменить публичный сайт — послать в
    # него не-GET. Ни один тест такого запроса не содержит.
    подозрительные = []
    for f in [x for к in ИСХОДНИКИ for x in к.rglob("*.py")]:
        т = f.read_text(encoding="utf-8", errors="replace")
        for домен in ДОМЕНЫ:
            for м in ("POST", "PUT", "PATCH", "DELETE"):
                if домен in т and f'method="{м}"' in т:
                    подозрительные.append(f"{f.name}:{домен}:{м}")
    assert not подозрительные, подозрительные


# 34
def test_34_внешние_провайдеры_не_вызывались():
    внешние = ("api.kitsu.io", "graphql.anilist.co", "api.simkl.com",
               "shikimori.one", "api-metrika.yandex", "topvisor.com")
    свой = Path(__file__).resolve()
    найдено = [f"{f.name}:{h}" for f in [x for к in ИСХОДНИКИ for x in к.rglob("*.py")]
               if f.resolve() != свой          # список хостов лежит здесь же
               for h in внешние
               if h in f.read_text(encoding="utf-8", errors="replace")]
    assert not найдено, найдено


# 35
def test_35_секретов_не_раскрыто():
    """Токены не должны попадать ни в журнал, ни в ленту, ни в манифесты.

    Проверяются два разных риска: секрет, записанный в событие, и секрет,
    просочившийся в ленту или лог при публикации. Цели — данные ПРОГОНА: его
    журнал и его каталог доказательств. Канонические ленту и манифесты хоста
    просматривает та же по смыслу проверка host-контура
    (`ledger.secrets_not_exposed`) — там, где они существуют.

    Утечка ищется по живым токенам прогона, а не по выдуманному образцу:
    обвязка выдаёт службе настоящие для неё значения, и если хоть одно из них
    окажется в данных, найдено будет именно оно.
    """
    опасно = re.compile(
        r"(?i)(bearer\s+[A-Za-z0-9._-]{16,}|(?:token|secret|password|api[_-]?key)"
        r"\s*[=:]\s*[\'\"]?[A-Za-z0-9._-]{16,})")
    живые_токены = [v for k, v in os.environ.items()
                    if k.startswith("AUDIT_TOKEN_") and v]
    assert живые_токены, "у прогона нет токенов — искать было бы нечего"

    цели = sorted(ДОКАЗАТЕЛЬСТВА.rglob("*")) if ДОКАЗАТЕЛЬСТВА.is_dir() else []
    утечки = []
    for f in цели:
        if not f.is_file():
            continue
        т = f.read_text(encoding="utf-8", errors="replace")
        if опасно.search(т):
            утечки.append(f"{f.name}: образец секрета")
        утечки += [f"{f.name}: живой токен" for t in живые_токены if t in т]

    c = sqlite3.connect(f"file:{ЖУРНАЛ}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    текст = json.dumps([dict(r) for r in c.execute("SELECT * FROM ledger_event")],
                       ensure_ascii=False)
    c.close()
    if опасно.search(текст):
        утечки.append("ledger_event: образец секрета")
    утечки += ["ledger_event: живой токен" for t in живые_токены if t in текст]
    assert not утечки, утечки
