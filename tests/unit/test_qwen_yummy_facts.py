"""Факты для семейства Yummy: со своей страницы и только проверяемые.

Зачем отдельный источник. Приложение Yummy держит каталог в своей базе, снимка
подробностей у фабрики для него нет и не будет. Пока фактов не было,
`ТРЕБУЕТ_ВОЗМОЖНОСТИ` справедливо не давала операцию `prepare`, а без неё
редактор не мог ни подготовить, ни опубликовать текст — при работающей
доставке и отображении (измерено 2026-10-09: наложение смонтировано у
yummyani.org и yummyani.site, публикация доходит до страницы).

Источник — РАЗМЕТКА СВОЕЙ ЖЕ СТРАНИЦЫ: `application/ld+json` со `@type`
`TVSeries`/`Movie`. Это не внешний сайт: читается домен из реестра, и адрес
назван в `source`, поэтому каждое утверждение текста сверяется там же, где его
увидит посетитель.

Проверки написаны по тому, что может сломаться молча: подхват чужого блока
(`BreadcrumbList` есть на той же странице), потеря страны и года, выдуманные
факты при отсутствии разметки и обзор каталога, которого этим путём нет.
"""

from __future__ import annotations

import json

import pytest

from factory.qwen import editorial, registry

СТРАНИЦА = """<!DOCTYPE html><html><head>
<script type="application/ld+json">{"@context":"https://schema.org",
 "@type":"BreadcrumbList","itemListElement":[{"@type":"ListItem","position":1,
 "name":"Главная"}]}</script>
<script type="application/ld+json">{"@context":"https://schema.org",
 "@type":"TVSeries","name":"009-1","alternateName":"Zero Zero Nine One",
 "url":"https://yummyani.org/anime/009-1","datePublished":"2006-10-04",
 "description":"Шпионка-киборг выполняет задания в мире затяжной войны.",
 "genre":["Аниме","Боевик","Фантастика"],
 "countryOfOrigin":[{"@type":"Country","name":"Япония"}]}</script>
</head><body><main>текст страницы</main></body></html>"""

БЕЗ_РАЗМЕТКИ = """<!DOCTYPE html><html><head>
<script type="application/ld+json">{"@context":"https://schema.org",
 "@type":"BreadcrumbList","itemListElement":[]}</script>
</head><body><main>страница без описания произведения</main></body></html>"""


class Сайт:
    """Запись реестра в объёме, который читают факты."""

    def __init__(self) -> None:
        self.domain = "yummyani.org"
        self.site_id = "yummy-org"
        self.adapter = "yummy"
        self.account = "yummyani-org"


def test_разметка_берётся_о_произведении_а_не_о_навигации():
    разметка = editorial._разметка_страницы(СТРАНИЦА)
    assert разметка.get("@type") == "TVSeries", (
        "на той же странице есть BreadcrumbList — подхват его дал бы факты "
        "о хлебных крошках вместо произведения")
    assert разметка.get("name") == "009-1"


def test_пустая_разметка_не_выдумывается():
    assert editorial._разметка_страницы(БЕЗ_РАЗМЕТКИ) == {}
    assert editorial._разметка_страницы("<html></html>") == {}


def test_факты_со_страницы_переносят_проверяемое(monkeypatch):
    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(registry, "_страница", lambda url, таймаут=15: ("200", СТРАНИЦА))
    итог = editorial._факты_со_страницы(Сайт(), "009-1")
    ф = итог["facts"]
    assert ф["name"] == "009-1"
    assert ф["original_name"] == "Zero Zero Nine One"
    assert ф["year"] == 2006, "год берётся из datePublished, а не выдумывается"
    assert ф["type"] == "tv"
    assert ф["genres"] == ["Аниме", "Боевик", "Фантастика"]
    assert ф["countries"] == ["Япония"], "страна лежит объектом Country, а не строкой"
    assert ф["description"].startswith("Шпионка-киборг")
    # Источник называется адресом страницы: по нему утверждение и сверяется.
    assert итог["source"] == "https://yummyani.org/anime/009-1"
    assert итог["facts"]["description_source"] == итог["source"]
    assert итог["source_kind"] == "page-schema-org"
    # Чего на странице нет — остаётся пустым, а не заполняется похожим.
    assert ф["imdb_rating"] is None and ф["seasons"] is None and ф["id"] is None


def test_страница_без_разметки_это_отказ(monkeypatch):
    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(registry, "_страница",
                        lambda url, таймаут=15: ("200", БЕЗ_РАЗМЕТКИ))
    with pytest.raises(editorial.ОперацияОтклонена, match="нет разметки schema.org"):
        editorial._факты_со_страницы(Сайт(), "009-1")


def test_страница_не_ответила_это_отказ(monkeypatch):
    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(registry, "_страница", lambda url, таймаут=15: ("503", ""))
    with pytest.raises(editorial.ОперацияОтклонена, match="503"):
        editorial._факты_со_страницы(Сайт(), "009-1")


def test_обзора_каталога_этим_путём_нет():
    """Факты читаются со страницы ОДНОГО тайтла — обзор требует снимка."""
    with pytest.raises(editorial.ОперацияОтклонена, match="обзор каталога"):
        editorial._факты_со_страницы(Сайт(), None)


def test_возможность_объявлена_семейству():
    """Без объявления операция `prepare` не предлагается вовсе."""
    умеет = registry.ВОЗМОЖНОСТИ_АДАПТЕРА["yummy"]
    assert "facts" in умеет and "schema.org" in умеет["facts"]
    # А отображение по-прежнему НЕ объявлено семейством: оно проверяется по
    # монтированию в контейнер каждого домена отдельно.
    assert "display" not in умеет


def test_форма_адреса_семейства_не_угадывается():
    """Факты читаются по адресу семейства: /anime/<slug> без слеша на конце."""
    assert registry.ФОРМА_АДРЕСА["yummy"] == "/anime/{slug}"
    разобрано = json.loads(json.dumps(registry.ФОРМА_АДРЕСА))
    assert разобрано["animedia"].endswith("/") and not разобрано["yummy"].endswith("/")
