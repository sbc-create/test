"""Накладка описания пишется только НА СУЩЕСТВУЮЩУЮ карточку каталога.

Почему этот тест существует
---------------------------

Измерено 2026-10-05 на yummyani.org: НОВОСТЬ о радиоэфире была записана
операцией накладки описаний 26-й записью в `title-overlays.json`, адрес
`/anime/100kano-radio-57` ответил 404, и запись пришлось снимать.

Проверки качества тогда не сработали и не могли: у семейства Yummy источника
фактов нет вовсе, `умеет_факты` ложно, `title_id` остаётся `None` — то есть
слаг не сверялся НИ С ЧЕМ. Путь записи при этом обходит черновик: операция
публикации принимает тело прямо (`тело=...`), и проверка существования
карточки не выполнялась нигде.

Единственный измеримый признак существования карточки у такого семейства —
ответ её страницы. Спросить его нужно ДО записи: подтверждение спрашивает то
же самое, но уже после, и запись к тому моменту уже в файле.
"""
from __future__ import annotations

import pytest

from factory.qwen import editorial, registry


def _сайт() -> registry.Сайт:
    return registry.Сайт(site_id="y", domain="y.example", adapter="yummy",
                         public_http="200", published_release="deadbeef")


def test_карточки_нет_запись_отклоняется(monkeypatch):
    monkeypatch.setattr(registry, "_страница", lambda url, таймаут=15: ("404", ""))
    with pytest.raises(editorial.ОперацияОтклонена) as ош:
        editorial._требовать_карточку(_сайт(), "100kano-radio-57")
    текст = str(ош.value)
    assert "404" in текст
    assert "/anime/100kano-radio-57" in текст
    # Отказ обязан назвать ВЕРНУЮ операцию: иначе редактор снова возьмёт эту.
    assert "posts-publish" in текст
    assert "/posts/100kano-radio-57" in текст


def test_карточка_есть_запись_не_мешают(monkeypatch):
    monkeypatch.setattr(registry, "_страница", lambda url, таймаут=15: ("200", ""))
    editorial._требовать_карточку(_сайт(), "nastoyashchaya-kartochka")


@pytest.mark.parametrize("код", ["404", "500", "000", ""])
def test_неизмеримость_тоже_отказ(monkeypatch, код):
    """Публиковать описание страницы, которую нельзя увидеть, незачем:
    подтверждение всё равно не состоится, а запись останется."""
    monkeypatch.setattr(registry, "_страница", lambda url, таймаут=15: (код, ""))
    with pytest.raises(editorial.ОперацияОтклонена):
        editorial._требовать_карточку(_сайт(), "lyuboy-slag")


def test_проверка_идёт_до_записи(monkeypatch):
    """Порядок важнее самой проверки: отказ после записи записи не отменяет."""
    monkeypatch.setattr(editorial, "_сайт",
                        lambda site, опрашивать_сеть=False: _сайт())
    monkeypatch.setattr(editorial, "_требует", lambda *_а, **_и: None)
    monkeypatch.setattr(registry, "_страница", lambda url, таймаут=15: ("404", ""))

    def не_должно_случиться(*_а, **_и):
        raise AssertionError("доставка вызвана при отсутствующей карточке")

    monkeypatch.setattr(editorial, "_доставить", не_должно_случиться)
    monkeypatch.setattr(editorial, "_записать_атомарно", не_должно_случиться)
    monkeypatch.setattr(editorial, "_дописать_историю", не_должно_случиться)

    with pytest.raises(editorial.ОперацияОтклонена) as ош:
        editorial.публиковать("y.example", "100kano-radio-57",
                              author="Редакция", тело="Текст новости.")
    assert "карточки" in str(ош.value)


def test_форма_адреса_карточки_берётся_у_семейства(monkeypatch):
    """Зашитый `/title/` не нашёл бы карточку у Yummy: там `/anime/<slug>`."""
    снято: list[str] = []

    def запомнить(url, таймаут=15):
        снято.append(url)
        return ("200", "")

    monkeypatch.setattr(registry, "_страница", запомнить)
    editorial._требовать_карточку(_сайт(), "slag")
    assert снято == ["https://y.example/anime/slag"], снято
