"""REQ-RATING-FEED: оценки из действующего договорного фида поставщика.

Владелец разрешил ровно одно: **использовать и показывать оценки, которые уже
приходят в действующем договорном фиде**. Скрапинг IMDb, Кинопоиска и любых
других сайтов, а также подключение новых внешних источников без отдельного
разрешения — запрещены.

Отсюда четыре свойства, и каждое проверяется, а не объявляется.

**Сеть не нужна вовсе.** Значения уже лежат в фиде, который забирает штатное
обновление каталога. Соединитель читает кэш и не ходит наружу — ни на imdb.com,
ни на кинопоиск, ни куда-либо ещё. Проверяется по исходному коду: модуль не
имеет права даже импортировать сетевой клиент.

**Происхождение записано у каждого значения.** Не «оценка 7.6», а «7.6, метрика
imdb, получено из фида поставщика, фид забран тогда-то, правовое основание —
действующий договор». Число без происхождения через месяц неотличимо от
скачанного со стороны.

**Два разных числа не сводятся в одно.** В фиде приходят и `imdb_rating`, и
`kinopoisk_rating`. Они меряют разные совокупности, и выбирать между ними —
решение, которого владелец не принимал. Пока оно не принято, отдаются оба, а
главного значения нет.

**Источник выключается одним полем.** `enabled: false` при действующем
разрешении — это `SOURCE_DISABLED`, а не «нет прав»: разные причины, и путать
их нельзя.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

ЗАПИСИ = [
    {
        "external_id": "01a00000-0000-7000-8000-000000000001",
        "name": "С двумя оценками",
        "type": "movie",
        "year": 2020,
        "imdb_rating": 7.6,
        "kinopoisk_rating": 6.922,
    },
    {
        "external_id": "01a00000-0000-7000-8000-000000000002",
        "name": "Только imdb",
        "type": "movie",
        "year": 2019,
        "imdb_rating": 8,
        "kinopoisk_rating": None,
    },
    {
        "external_id": "01a00000-0000-7000-8000-000000000003",
        "name": "Без оценок",
        "type": "movie",
        "year": 2021,
        "imdb_rating": None,
        "kinopoisk_rating": None,
    },
    {
        "external_id": "01a00000-0000-7000-8000-000000000004",
        "name": "Ещё не вышло",
        "type": "movie",
        "year": 2099,
        "imdb_rating": None,
        "kinopoisk_rating": None,
    },
]

SITE = "js-site"
ТОКЕН = "tok"
H = {"Authorization": f"Bearer {ТОКЕН}"}
ENV = {
    "SITE_ENGINE_CONTROL_TOKENS": f"{ТОКЕН}=read",
    "SITE_ENGINE_CATALOG_DIR": "var/lords/lords/catalog-cache",
}

РАЗРЕШЁННЫЙ_РЕЕСТР = """version: 2
sources:
  - id: provider-feed
    enabled: true
    ttl_seconds: 3600
    rate_limit_per_minute: 0
    provenance:
      delivery: "поля фида каталога"
      legal_basis: "действующий договор с поставщиком контента"
    authorization:
      status: granted
      reason: "разрешение владельца от 2026-09-06"
      document: docs/rights/provider-feed-ratings.md
      granted_at: "2026-09-06"
"""


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    from factory.paths import PATHS

    monkeypatch.setattr(PATHS, "root", tmp_path)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config" / "rating-sources.yaml").write_text(
        РАЗРЕШЁННЫЙ_РЕЕСТР, encoding="utf-8"
    )
    профили = tmp_path / "config" / "site-profiles"
    профили.mkdir(parents=True, exist_ok=True)
    (профили / f"{SITE}.json").write_text(
        json.dumps({"site_id": SITE, "domains": ["js.test"]}, ensure_ascii=False),
        encoding="utf-8",
    )
    кэш = tmp_path / "var" / "lords" / "lords" / "catalog-cache"
    кэш.mkdir(parents=True)
    (кэш / f"{SITE}.json").write_text(
        json.dumps(
            {"fetched_at_ms": 1788669932935, "source": "live-incremental", "items": ЗАПИСИ},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for под in ("var/state", "var/audit", "var/locks"):
        (tmp_path / под).mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestБезСети:
    def test_модуль_не_умеет_ходить_наружу(self):
        """Запрет проверяется по исходному коду, а не по намерению.

        Соединитель, способный сделать запрос, однажды его сделает — при
        отладке, в спешке, «временно». Модуль, не импортирующий сетевой
        клиент, этого не может.
        """
        текст = (REPO / "factory" / "site_engine" / "rating_feed.py").read_text(encoding="utf-8")
        for запретное in ("urllib", "requests", "http.client", "httpx", "socket"):
            assert запретное not in текст, f"сетевой клиент в слое оценок: {запретное}"

    def test_имена_чужих_сайтов_не_встречаются_как_адреса(self):
        текст = (REPO / "factory" / "site_engine" / "rating_feed.py").read_text(encoding="utf-8")
        for адрес in ("imdb.com", "kinopoisk.ru", "https://"):
            assert адрес not in текст, f"адрес внешнего сайта в слое оценок: {адрес}"


class TestЗначения:
    def test_обе_метрики_отданы_с_происхождением(self, sandbox):
        from factory.site_engine import rating_feed

        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        строка = next(с for с in итог["items"] if с["externalId"] == ЗАПИСИ[0]["external_id"])
        метрики = {м["metric"]: м for м in строка["values"]}
        assert set(метрики) == {"imdb", "kinopoisk"}
        assert метрики["imdb"]["value"] == 7.6
        assert метрики["kinopoisk"]["value"] == 6.922
        for м in метрики.values():
            assert м["source"] == "provider-feed"
            assert м["legalBasis"] == "действующий договор с поставщиком контента"
            assert м["feedFetchedAt"], "без отметки фида значение неотличимо от скачанного"

    def test_два_числа_не_сводятся_в_одно(self, sandbox):
        from factory.site_engine import rating_feed

        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        строка = next(с for с in итог["items"] if с["externalId"] == ЗАПИСИ[0]["external_id"])
        assert строка["primary"] is None
        assert строка["primaryReason"] == "MULTIPLE_METRICS_NOT_RECONCILED"

    def test_единственная_метрика_становится_главной(self, sandbox):
        from factory.site_engine import rating_feed

        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        строка = next(с for с in итог["items"] if с["externalId"] == ЗАПИСИ[1]["external_id"])
        assert строка["primary"]["metric"] == "imdb"
        assert строка["primary"]["value"] == 8.0

    def test_отсутствие_оценки_не_ноль(self, sandbox):
        from factory.site_engine import rating_feed

        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        строка = next(с for с in итог["items"] if с["externalId"] == ЗАПИСИ[2]["external_id"])
        assert строка["state"] == "NO_RATING_IN_FEED"
        assert строка["values"] == []
        assert строка["primary"] is None

    def test_невышедшее_не_считается_пробелом(self, sandbox):
        from factory.site_engine import rating_feed

        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        строка = next(с for с in итог["items"] if с["externalId"] == ЗАПИСИ[3]["external_id"])
        assert строка["state"] == "NOT_RELEASED"

    def test_охват_считается_от_подходящих_а_не_от_всех(self, sandbox):
        from factory.site_engine import rating_feed

        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        assert итог["total"] == 4
        assert итог["eligible"] == 3, "невышедшее из знаменателя исключено"
        assert итог["withRating"] == 2
        assert итог["coverage"] == pytest.approx(2 / 3, rel=1e-3)


class TestВыключение:
    def test_выключенный_источник_отличим_от_неразрешённого(self, sandbox):
        from factory.site_engine import rating_feed

        (sandbox / "config" / "rating-sources.yaml").write_text(
            РАЗРЕШЁННЫЙ_РЕЕСТР.replace("enabled: true", "enabled: false"), encoding="utf-8"
        )
        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        assert итог["state"] == "SOURCE_DISABLED"
        assert итог["items"] == []
        assert "разрешён" in итог["reason"].lower()

    def test_без_разрешения_значения_не_отдаются(self, sandbox):
        from factory.site_engine import rating_feed

        (sandbox / "config" / "rating-sources.yaml").write_text(
            РАЗРЕШЁННЫЙ_РЕЕСТР.replace("enabled: true", "enabled: false").replace(
                "status: granted", "status: revoked"
            ),
            encoding="utf-8",
        )
        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        assert итог["state"] == "SOURCE_NOT_AUTHORIZED"
        assert итог["items"] == []


class TestПоследнееХорошее:
    def test_нечитаемый_фид_отдаёт_последнее_известное(self, sandbox):
        from factory.site_engine import rating_feed

        rating_feed.ratings(sandbox, SITE, env=ENV, remember=True)
        (sandbox / "var" / "lords" / "lords" / "catalog-cache" / f"{SITE}.json").unlink()
        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        assert итог["state"] == "LAST_KNOWN_GOOD"
        assert итог["withRating"] == 2
        assert итог["stale"] in (False, True)

    def test_без_памяти_нечитаемый_фид_это_отказ(self, sandbox):
        from factory.site_engine import rating_feed

        (sandbox / "var" / "lords" / "lords" / "catalog-cache" / f"{SITE}.json").unlink()
        итог = rating_feed.ratings(sandbox, SITE, env=ENV)
        assert итог["state"] == "FEED_UNREADABLE"
        assert итог["items"] == []


class TestРеестрПослеРазрешения:
    def test_фид_разрешён_в_поставке(self):
        from factory.site_engine import rating_sources

        решение = rating_sources.resolve(REPO)
        assert решение.authorized == ("provider-feed",)

    def test_скрапинг_остальных_запрещён_явно(self):
        from factory.site_engine import rating_sources

        решение = rating_sources.resolve(REPO)
        по_имени = {и["id"]: и for и in решение.known}
        for имя in ("imdb", "kinopoisk"):
            assert по_имени[имя]["authorization"]["status"] != "granted"
            причина = по_имени[имя]["authorization"]["reason"].lower()
            assert "запрещ" in причина, f"{имя}: запрет владельца не записан"

    def test_правовое_основание_задокументировано(self):
        документ = REPO / "docs" / "rights" / "provider-feed-ratings.md"
        assert документ.is_file()
        текст = документ.read_text(encoding="utf-8")
        assert "действующий договор" in текст
        assert "2026-09-06" in текст
        assert "скрапинг" in текст.lower()


class TestМаршрут:
    def test_оценки_видны_через_api(self, sandbox):
        from factory.site_engine.api.control import ControlApi

        ответ = ControlApi(root=sandbox, env=ENV).handle(
            "GET", f"/api/v1/ratings/{SITE}", headers=H
        )
        assert ответ.status == 200
        assert ответ.body["source"] == "provider-feed"
        assert ответ.body["withRating"] == 2

    def test_страницы_не_пересекаются(self, sandbox):
        from factory.site_engine.api.control import ControlApi

        api = ControlApi(root=sandbox, env=ENV)
        первая = api.handle("GET", f"/api/v1/ratings/{SITE}", headers=H, body={"limit": 2}).body
        вторая = api.handle(
            "GET", f"/api/v1/ratings/{SITE}", headers=H, body={"limit": 2, "offset": 2}
        ).body
        ключи = lambda т: {с["externalId"] for с in т["items"]}  # noqa: E731
        assert not (ключи(первая) & ключи(вторая))


class TestКарточкаКаталога:
    """Оценка на карточке обязана подчиняться реестру, а не показываться всегда.

    До разрешения владельца карточка отдавала `kinopoisk_rating` и
    `imdb_rating` прямо из записи фида — без происхождения и без проверки, есть
    ли право их показывать. Если бы владелец ответил «нет», числа продолжали бы
    отображаться.
    """

    def test_карточка_отдаёт_оценки_с_происхождением(self, sandbox):
        from factory.site_engine.api import content_browse

        карточка = content_browse.карточка(
            sandbox, site_id=SITE, external_id=ЗАПИСИ[0]["external_id"], env=ENV
        )
        оценки = карточка["ratings"]
        assert оценки["state"] == "AVAILABLE"
        метрики = {м["metric"]: м for м in оценки["values"]}
        assert метрики["imdb"]["value"] == 7.6
        assert метрики["imdb"]["legalBasis"] == "действующий договор с поставщиком контента"
        assert метрики["imdb"]["feedFetchedAt"], (
            "без отметки фида происхождение неполно: неизвестно, какого числа его забрали"
        )
        assert оценки["primary"] is None, "две метрики не сводятся в одну"

    def test_при_отозванном_разрешении_чисел_нет(self, sandbox):
        from factory.site_engine.api import content_browse

        (sandbox / "config" / "rating-sources.yaml").write_text(
            РАЗРЕШЁННЫЙ_РЕЕСТР.replace("enabled: true", "enabled: false").replace(
                "status: granted", "status: revoked"
            ),
            encoding="utf-8",
        )
        карточка = content_browse.карточка(
            sandbox, site_id=SITE, external_id=ЗАПИСИ[0]["external_id"], env=ENV
        )
        оценки = карточка["ratings"]
        assert оценки["state"] == "SOURCE_NOT_AUTHORIZED"
        assert оценки["values"] == []
        # Ни одного числа: отозванное разрешение обязано убирать значения, а не
        # только подпись под ними.
        import json as _json

        assert "7.6" not in _json.dumps(оценки, ensure_ascii=False)

    def test_экран_карточки_показывает_происхождение(self, sandbox):
        from factory.site_engine.admin import ui

        html = ui.content_item(
            {
                "siteId": SITE,
                "externalId": ЗАПИСИ[0]["external_id"],
                "title": "С двумя оценками",
                "ratings": {
                    "state": "AVAILABLE",
                    "primary": None,
                    "primaryReason": "MULTIPLE_METRICS_NOT_RECONCILED",
                    "values": [
                        {
                            "metric": "imdb",
                            "value": 7.6,
                            "scale": "0-10",
                            "source": "provider-feed",
                            "legalBasis": "действующий договор с поставщиком контента",
                            "feedFetchedAt": "2026-09-06T04:45:32Z",
                        }
                    ],
                },
            },
            flash=None,
            session_label="т",
            csrf="c",
        )
        assert "7.6" in html
        assert "provider-feed" in html
        assert "договор" in html

