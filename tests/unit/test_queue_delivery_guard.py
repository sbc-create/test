"""Задание на описание не выдаётся и не заводится там, где доставки нет.

Измерено 2026-10-09 по живой очереди: шесть заданий на описание, закреплённых
арендами, стоят у ячеек семейства `animego` (два на an1mego.site, четыре на
animeg0.site), у которого в реестре объявлена только возможность `facts`.
Текст для них написать можно, положить его некуда. За сутки до этого очередь
выдала 203 задания и получила 45 результатов.

Критерий заставы не придуман здесь заново: это тот же
`registry.ТРЕБУЕТ_ВОЗМОЖНОСТИ["publish"]` (доставка И отображение), которым
пользуется сама публикация. Поэтому тесты проверяют и то, что застава НЕ
мешает площадкам, где публикация работает: у семейства `lords` доставка идёт
механизмом `editorial-queue` в `editorial-overrides.json`, и отказывать ему
было бы неверно.
"""

from __future__ import annotations

import pytest

from factory.qwen import queue_bridge as qb


def test_критерий_взят_из_реестра_а_не_переписан():
    from factory.qwen import registry

    assert registry.ТРЕБУЕТ_ВОЗМОЖНОСТИ["publish"] == ("deliver", "display")


def test_животное_семейство_без_доставки_отвергается(monkeypatch):
    """Площадка, у которой объявлены только факты, задания не получает."""
    monkeypatch.setattr(qb, "доставка_описаний",
                        lambda site: (False, f"{site}: доставки нет"))
    вызовы = []
    monkeypatch.setattr(qb, "_вызвать", lambda з, **к: вызовы.append(з) or {})
    итог = qb.взять(site="an1mego.site", owner="editor/ночь/run-1", limit=3)
    assert итог["claimed"] == 0
    assert итог["tasks"] == []
    assert "доставки нет" in итог["blocked_reason"]
    # Самое важное: очередь даже не спрашивается — аренда не создаётся.
    assert вызовы == []


def test_площадка_с_доставкой_работает_как_прежде(monkeypatch):
    monkeypatch.setattr(qb, "доставка_описаний", lambda site: (True, ""))
    monkeypatch.setattr(qb, "_вызвать",
                        lambda з, **к: {"tasks": [{"task_id": "a1"}]})
    итог = qb.взять(site="animedia.icu", owner="editor/ночь/run-1")
    assert итог["claimed"] == 1
    assert "blocked_reason" not in итог


def test_запрос_новостей_заставой_не_задевается(monkeypatch):
    """Застава про описания. Новость доставляется другим путём."""
    monkeypatch.setattr(qb, "доставка_описаний",
                        lambda site: (False, "описаний нет"))
    monkeypatch.setattr(qb, "_вызвать",
                        lambda з, **к: {"tasks": [{"task_id": "n1"}]})
    итог = qb.взять(site="an1mego.site", owner="editor/ночь/run-1",
                    content_types=("NEWS",))
    assert итог["claimed"] == 1, итог


def test_регистрация_невыполнимого_задания_отклоняется(monkeypatch):
    monkeypatch.setattr(qb, "доставка_описаний",
                        lambda site: (False, f"{site}: доставки нет"))
    вызовы = []
    monkeypatch.setattr(qb, "_вызвать", lambda з, **к: вызовы.append(з) or {})
    with pytest.raises(qb.ОчередьОтклонила, match="доставки нет"):
        qb.завести(site="animeg0.site",
                   canonical_url="https://animeg0.site/title/пример/",
                   headline="Пример")
    assert вызовы == []


def test_регистрация_новости_заставой_не_задевается(monkeypatch):
    monkeypatch.setattr(qb, "доставка_описаний",
                        lambda site: (False, "описаний нет"))
    monkeypatch.setattr(qb, "_вызвать", lambda з, **к: {"created": True})
    итог = qb.завести(site="an1mego.site",
                      canonical_url="https://an1mego.site/posts/пример",
                      headline="Пример", content_type="NEWS")
    assert итог["created"] is True


def test_нечитаемый_реестр_заставой_не_становится(monkeypatch):
    """Отказ реестра не обязан останавливать редакционную работу.

    Застава существует, чтобы не тратить работу впустую, а не чтобы добавить
    ещё одну причину, по которой очередь молчит. Поэтому неразобранная запись
    реестра пропускает задание и называет это в причине.
    """
    import factory.qwen.editorial as ред

    monkeypatch.setattr(ред, "_сайт",
                        lambda *а, **к: (_ for _ in ()).throw(RuntimeError("нет записи")))
    можно, причина = qb.доставка_описаний("незнакомая.test")
    assert можно is True
    assert "не разобрана" in причина
