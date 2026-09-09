"""Снимок маршрутов: адрес → устойчивый идентификатор.

Проверяется прежде всего то, чего делать нельзя: выбирать первую запись при
столкновении, подменять функцию адреса, выдавать неполный снимок за полный и
терять исчезнувшие маршруты молча.
"""

from __future__ import annotations

import datetime as dt

import pytest

from factory.site_engine.route_normalizer import NormalizeState, normalize
from factory.site_engine.route_snapshot import (
    Completeness,
    RouteState,
    build,
    lookup,
)

СЕЙЧАС = dt.datetime(2026, 9, 9, tzinfo=dt.timezone.utc)
ПРОФИЛИ = {"lordfilm47.space": "lords-01", "yummyani.org": "yummyani-org"}


def _адрес(name, external_id):
    from factory.lords.live_catalog import slugify
    return f"/title/{slugify(name) or external_id.lower()}/"


def _снимок(записи, **ещё):
    поля = {"site_id": "lords-01", "route_of": _адрес, "observed_at": СЕЙЧАС,
            "producer_sha": "2ccfa102", "source_digest": "abc",
            "generation_reason": "full-rebuild"}
    поля.update(ещё)
    return build(записи, **поля)


# --- нормализация --------------------------------------------------------------------

def test_три_записи_одного_адреса_дают_один_ключ():
    """Считать их тремя значит трижды не найти одну запись."""
    ключи = {normalize(u, profiles=ПРОФИЛИ).route_key for u in (
        "https://lordfilm47.space/title/x/",
        "HTTPS://LordFilm47.Space/title/x",
        "https://lordfilm47.space//title//x/?utm_source=mail")}
    assert ключи == {"/title/x"}


def test_значимая_часть_пути_не_выбрасывается():
    """Убрав номер сезона, мы повысим долю совпадений и начнём приписывать
    сезону сведения о произведении целиком."""
    н = normalize("https://yummyani.org/anime/x/season/2/episode/5",
                  profiles=ПРОФИЛИ)
    assert н.route_key == "/anime/x/season/2/episode/5"
    assert н.route_kind == "episode"
    assert н.parent_key == "/anime/x"


def test_чужой_узел_вне_области():
    н = normalize("https://чужой.test/title/x/", profiles=ПРОФИЛИ)
    assert н.state is NormalizeState.OUT_OF_SCOPE


def test_не_адрес_страницы_отвергается():
    assert normalize("file:///etc/passwd",
                     profiles=ПРОФИЛИ).state is NormalizeState.MALFORMED


def test_профили_приходят_настройкой_а_не_зашиты():
    """Сорок третья витрина добавляется строкой в объявлении."""
    н = normalize("https://новая.test/title/x/",
                  profiles={"новая.test": "site-043"})
    assert н.state is NormalizeState.OK and н.site_id == "site-043"


# --- столкновения ----------------------------------------------------------------------

def test_столкновение_не_разрешается_выбором_первой():
    """Страница окажется приписана произвольной из двух записей, и ошибка
    будет выглядеть обычной страницей."""
    с = _снимок([{"external_id": "w1", "name": "Тишина"},
                 {"external_id": "w2", "name": "Тишина"}])
    assert с.completeness is Completeness.INCOMPLETE
    assert len(с.collisions) == 1
    итог = lookup(с.as_dict(), "/title/tishina")
    assert not итог["found"] and итог["reason"] == "COLLISION"
    assert sorted(итог["candidates"]) == ["w1", "w2"]


def test_снимок_со_столкновениями_объявлен_неполным():
    с = _снимок([{"external_id": "w1", "name": "А"},
                 {"external_id": "w2", "name": "А"}])
    assert с.as_dict()["completeness"] == "INCOMPLETE"


def test_разные_названия_столкновением_не_считаются():
    с = _снимок([{"external_id": "w1", "name": "Тишина"},
                 {"external_id": "w2", "name": "Гроза"}])
    assert с.completeness is Completeness.COMPLETE
    assert lookup(с.as_dict(), "/title/groza")["stableWorkId"] == "w2"


# --- надгробия ---------------------------------------------------------------------------

def test_исчезнувший_маршрут_получает_надгробие():
    """Исчезнувший молча выглядит как никогда не существовавший, и страница,
    которая вчера была, объясняется ошибкой потребителя."""
    первый = _снимок([{"external_id": "w1", "name": "Тишина"},
                      {"external_id": "w2", "name": "Гроза"}]).as_dict()
    второй = _снимок([{"external_id": "w1", "name": "Тишина"}],
                     previous=первый)
    надгробия = [з for з in второй.records if з.state is RouteState.TOMBSTONE]
    assert len(надгробия) == 1 and надгробия[0].route_key == "/title/groza"
    assert lookup(второй.as_dict(), "/title/groza")["reason"] == "ROUTE_REMOVED"


def test_вернувшийся_маршрут_снова_живой():
    первый = _снимок([{"external_id": "w1", "name": "Тишина"}]).as_dict()
    второй = _снимок([], previous=первый).as_dict()
    третий = _снимок([{"external_id": "w1", "name": "Тишина"}],
                     previous=второй).as_dict()
    assert lookup(третий, "/title/tishina")["found"]


def test_дата_создания_переживает_пересборку():
    первый = _снимок([{"external_id": "w1", "name": "Тишина"}]).as_dict()
    позже = _снимок([{"external_id": "w1", "name": "Тишина"}],
                    previous=первый,
                    observed_at=СЕЙЧАС + dt.timedelta(days=1)).as_dict()
    з = [x for x in позже["records"] if x["routeKey"] == "/title/tishina"][0]
    assert з["createdAt"] == СЕЙЧАС.isoformat()
    assert з["updatedAt"] != з["createdAt"]


# --- детерминированность ---------------------------------------------------------------------

def test_снимок_детерминирован():
    записи = [{"external_id": f"w{n}", "name": f"Имя {n}"} for n in range(20)]
    a = _снимок(записи).as_dict()
    b = _снимок(list(reversed(записи))).as_dict()
    assert a["digest"] == b["digest"]
    assert [з["routeKey"] for з in a["records"]] == sorted(
        з["routeKey"] for з in a["records"])


def test_отпечаток_не_зависит_от_времени_сборки():
    записи = [{"external_id": "w1", "name": "Тишина"}]
    a = _снимок(записи).as_dict()
    b = _снимок(записи, observed_at=СЕЙЧАС + dt.timedelta(days=5)).as_dict()
    assert a["digest"] == b["digest"] and a["observedAt"] != b["observedAt"]


# --- отказ и причины ---------------------------------------------------------------------------

def test_запись_без_идентификатора_отклоняется_с_причиной():
    с = _снимок([{"external_id": "", "name": "Без ключа"}])
    assert len(с.rejected) == 1 and с.rejected[0]["reason"]
    assert с.completeness is Completeness.INCOMPLETE


def test_отсутствие_ключа_несёт_причину():
    """«Не нашлось» без причины неотличимо от «мы не искали»."""
    с = _снимок([{"external_id": "w1", "name": "Тишина"}]).as_dict()
    итог = lookup(с, "/title/чего-нет")
    assert not итог["found"] and итог["reason"] == "NOT_IN_SNAPSHOT"
    assert итог["detail"]


def test_снимок_несёт_производителя_и_отпечаток_источника():
    т = _снимок([{"external_id": "w1", "name": "Т"}]).as_dict()
    for поле in ("producerSha", "sourceDigest", "observationId", "observedAt",
                 "compatibilityRange", "generationReason"):
        assert т[поле], поле


def test_адрес_строится_переданной_функцией_а_не_подменяется():
    """Снимок обязан строиться той же функцией, какой витрина строит адреса."""
    вызовов = []

    def своя(name, external_id):
        вызовов.append(name)
        return f"/title/{external_id}/"

    _снимок([{"external_id": "w1", "name": "Тишина"}], route_of=своя)
    assert вызовов == ["Тишина"]


# --- масштаб -----------------------------------------------------------------------------

@pytest.mark.parametrize("витрин", [3, 43, 50, 51])
def test_число_витрин_кода_не_требует(витрин):
    """Профиль добавляется строкой в объявлении, а не правкой модуля."""
    профили = {f"site-{n:03d}.test": f"site-{n:03d}" for n in range(витрин)}
    ключи = set()
    for n in range(витрин):
        н = normalize(f"https://site-{n:03d}.test/title/x/", profiles=профили)
        assert н.state is NormalizeState.OK
        assert н.site_id == f"site-{n:03d}"
        ключи.add((н.site_id, н.route_key))
    assert len(ключи) == витрин, "витрины не смешались"


def test_одинаковый_путь_на_разных_доменах_не_смешивается():
    """Иначе страница одной витрины получила бы сведения другой."""
    профили = {"a.test": "site-a", "b.test": "site-b"}
    a = normalize("https://a.test/title/x/", profiles=профили)
    b = normalize("https://b.test/title/x/", profiles=профили)
    assert a.route_key == b.route_key
    assert a.site_id != b.site_id, "ключ общий, витрина — нет"


def test_домен_без_маршрутов_даёт_причину_а_не_пустоту():
    с = _снимок([]).as_dict()
    итог = lookup(с, "/title/x")
    assert not итог["found"] and итог["reason"] == "NOT_IN_SNAPSHOT"


def test_снимки_разных_витрин_не_пересекаются():
    """Изоляция витрин: маршрут одной не находится в снимке другой."""
    a = _снимок([{"external_id": "w1", "name": "Тишина"}],
                site_id="lords-01").as_dict()
    b = _снимок([{"external_id": "w9", "name": "Гроза"}],
                site_id="lords-02").as_dict()
    assert lookup(a, "/title/groza")["found"] is False
    assert lookup(b, "/title/tishina")["found"] is False
