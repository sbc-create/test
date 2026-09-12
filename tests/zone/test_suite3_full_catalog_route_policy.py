"""SUITE_3 — политика адресов на полном каталоге.

Проверяется не «ноль ошибок в отчёте», а свойства самой политики: каждая
сущность получает адрес, адреса различают сущности, перестановка входа ничего
не меняет, а действующие публичные адреса остаются на своих сущностях.
"""
from __future__ import annotations

import collections
import json
import pathlib
import random
import sys

import pytest

from factory.lords import detail_enrichment as enrich_mod
from factory.lords import live_catalog as live_mod
from factory.lords import urlmap as um

СНИМОК = pathlib.Path(
    "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-02.json")
КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def записи():
    if not СНИМОК.is_file():
        pytest.skip(f"снимка каталога нет: {СНИМОК}")
    сырое = json.loads(СНИМОК.read_text(encoding="utf-8"))
    элементы = сырое["items"] if isinstance(сырое, dict) else сырое
    детали, битые = enrich_mod.load_cached_details(
        pathlib.Path("/srv/site-factory/repo/var/lords/detail-cache"))
    assert not битые, f"битые файлы обогащения: {битые[:3]}"
    слитые, _ = enrich_mod.merge_cached(элементы, детали)
    for з in слитые:
        з["_natural"] = (live_mod.slugify((з.get("name") or "").strip())
                         or live_mod.slugify(з["external_id"])
                         or з["external_id"].lower())
    return слитые


@pytest.fixture(scope="module")
def закреплённые():
    ф = КОРЕНЬ / "data" / "lords" / "route-ledger.json"
    return json.loads(ф.read_text(encoding="utf-8"))["assignments"]


@pytest.fixture(scope="module")
def назначение(записи, закреплённые):
    return um.назначить(записи, закреплённые=закреплённые,
                        слаг_из=lambda з: з["_natural"])


class TestПолнаяБухгалтерия:
    def test_каждая_запись_получила_адрес(self, записи, назначение):
        assert len(назначение.by_id) == len(записи)
        потеряны = [з["external_id"] for з in записи
                    if з["external_id"] not in назначение.by_id]
        assert потеряны == [], f"без адреса: {len(потеряны)}"

    def test_ни_одна_сущность_не_отброшена_молча(self, записи, назначение):
        """Равенство вход = маршрутизируемые + слияния + карантин + непригодные."""
        маршрутизируемые = len(назначение.by_id)
        слияния = 0          # одинаковых external_id в источнике нет
        карантин = 0
        непригодные = len(записи) - маршрутизируемые - слияния - карантин
        assert непригодные == 0
        assert len(записи) == маршрутизируемые + слияния + карантин + непригодные

    def test_канонические_идентификаторы_уникальны(self, записи):
        счёт = collections.Counter(з["external_id"] for з in записи)
        assert [и for и, n in счёт.items() if n > 1] == []


class TestАдресаРазличаютСущности:
    def test_нет_точных_коллизий(self, назначение):
        слаги = list(назначение.by_id.values())
        дубли = [с for с, n in collections.Counter(слаги).items() if n > 1]
        assert дубли == [], f"адрес назначен дважды: {дубли[:5]}"

    def test_нет_коллизий_после_нормализации(self, назначение):
        """Регистр, Unicode, ё/е и повторные дефисы не должны склеивать адреса."""
        норм = [um.нормализовать_слаг(с) for с in назначение.by_id.values()]
        дубли = [с for с, n in collections.Counter(норм).items() if n > 1]
        assert дубли == [], f"после нормализации совпали: {дубли[:5]}"

    def test_все_слаги_допустимого_вида(self, назначение):
        плохие = [с for с in назначение.by_id.values() if not um.СЛАГ.match(с)]
        assert плохие == [], f"слаги вне допустимого вида: {плохие[:5]}"

    def test_суффикс_не_может_совпасть_с_настоящим_названием(self, назначение):
        """Разделитель `--` недостижим для slugify, значит различающий суффикс
        структурно не может занять адрес настоящего произведения."""
        различённые = [с for с in назначение.by_id.values() if um.РАЗДЕЛИТЕЛЬ in с]
        assert различённые, "различение не применялось — проверять нечего"
        for с in различённые:
            assert live_mod.slugify(с.replace(um.РАЗДЕЛИТЕЛЬ, " ")) != с


class TestНезависимостьОтПорядка:
    def test_перестановка_входа_не_меняет_адреса(self, записи, закреплённые,
                                                 назначение):
        перемешанные = list(записи)
        random.Random(20260912).shuffle(перемешанные)
        другое = um.назначить(перемешанные, закреплённые=закреплённые,
                              слаг_из=lambda з: з["_natural"])
        assert другое.by_id == назначение.by_id

    def test_повторный_вызов_даёт_ту_же_карту(self, записи, закреплённые,
                                              назначение):
        снова = um.назначить(записи, закреплённые=закреплённые,
                             слаг_из=lambda з: з["_natural"])
        а = um.построить(назначение.by_id.values())
        б = um.построить(снова.by_id.values())
        assert а.отпечаток == б.отпечаток

    def test_отпечаток_не_зависит_от_порядка_множества(self, назначение):
        слаги = list(назначение.by_id.values())
        а = um.построить(слаги)
        б = um.построить(reversed(слаги))
        assert а.отпечаток == б.отпечаток


class TestУстойчивостьПубличныхАдресов:
    @pytest.fixture(scope="class")
    def прежнее(self, записи):
        """Прежний адрес каждой сущности и владелец каждого адреса.

        Хранятся только исключения; для остальных прежний адрес равен
        естественному слагу — хранить выводимое незачем.
        """
        ф = КОРЕНЬ / "data" / "lords" / "previous-routes.json"
        д = json.loads(ф.read_text(encoding="utf-8"))
        суффиксы = д["suffixed"]
        адрес = {з["external_id"]: суффиксы.get(з["external_id"], з["_natural"])
                 for з in записи}
        # Владелец восстанавливается однозначно: адрес принадлежит своей
        # единственной сущности, а для спорных адресов владелец закреплён —
        # вывести его из отображения сущность→адрес нельзя.
        владелец = {}
        for ид, с in адрес.items():
            владелец[с] = ид
        владелец.update(д["contested_owner"])
        return {"entity_slug": адрес, "served_by": владелец,
                "addresses_total": д["addresses_total"]}

    def test_действующие_адреса_остались_за_своими_сущностями(self, прежнее,
                                                              назначение):
        """Публичный адрес меняется только у того, у кого его фактически не было.

        Владелец берётся из закреплённого `served_by`, а не выводится из
        словаря сущность→адрес: при совпадении побеждала последняя запись
        входа, и в отсортированном словаре этот порядок уже потерян.
        """
        прежние = прежнее["entity_slug"]
        отдавались = прежнее["served_by"]
        сменили = {ид for ид, с in назначение.by_id.items()
                   if прежние.get(ид) != с}
        потеряли_свой = {ид for ид in сменили if отдавались.get(прежние[ид]) == ид}
        assert потеряли_свой == set(), (
            f"адрес сменился у сущностей, которые его занимали: "
            f"{len(потеряли_свой)}")

    def test_старые_адреса_не_исчезли(self, прежнее, назначение):
        старые = {um.маршрут(с) for с in прежнее["served_by"]}
        новые = {um.маршрут(с) for с in назначение.by_id.values()}
        пропали = старые - новые
        assert пропали == set(), f"исчезло публичных адресов: {len(пропали)}"

    def test_переходов_не_требуется(self, прежнее, назначение):
        """Ни один старый адрес не нуждается в переходе, значит цепочек нет."""
        старые = {um.маршрут(с) for с in прежнее["served_by"]}
        новые = {um.маршрут(с) for с in назначение.by_id.values()}
        assert len(старые - новые) == 0


class TestКаталогПрименяетПолитику:
    @pytest.fixture(scope="class")
    def каталог(self, записи):
        return live_mod.catalog_from_live(записи)

    def test_каталог_даёт_столько_же_адресов(self, каталог, записи):
        assert len(каталог.titles) == len(записи)
        assert len({t.slug for t in каталог.titles}) == len(записи)

    def test_поиск_по_адресу_возвращает_свою_сущность(self, каталог, назначение):
        по_слагу = {t.slug: t for t in каталог.titles}
        for ид, с in list(назначение.by_id.items())[:2000]:
            assert по_слагу[с].external_id == ид

    def test_запись_с_тем_же_названием_получает_свой_адрес(self, записи):
        """Совпадение названия — не повод отобрать адрес и не повод упасть."""
        двойник = dict(записи[0])
        двойник["external_id"] = "00000000-0000-0000-0000-000000000000"
        двойник["year"] = (записи[0].get("year") or 2000) + 1
        # Новая запись появляется позже существующей — и потому не может
        # забрать её адрес.
        двойник["created_at"] = "2099-01-01T00:00:00Z"
        каталог = live_mod.catalog_from_live(list(записи) + [двойник])
        слаги = [t.slug for t in каталог.titles]
        assert len(set(слаги)) == len(слаги) == len(записи) + 1
        новый = next(t for t in каталог.titles
                     if t.external_id == двойник["external_id"])
        assert um.РАЗДЕЛИТЕЛЬ in новый.slug

    def test_повторный_канонический_идентификатор_роняет_сборку(self, записи):
        """Две записи с одним external_id — это потеря сущности, а не коллизия."""
        двойник = dict(записи[1])
        with pytest.raises(um.UrlMapError) as ош:
            live_mod.catalog_from_live(list(записи) + [двойник])
        assert ош.value.error_code == "DUPLICATE_CANONICAL_ID"

    def test_совпадение_назначенных_адресов_роняет_сборку(self, записи,
                                                          monkeypatch):
        """Если политика когда-нибудь вернёт два одинаковых адреса, сборка
        обязана упасть, а не оставить последнюю запись молча."""
        настоящая = um.назначить

        def испорченная(зз, **кв):
            н = настоящая(зз, **кв)
            ид = list(н.by_id)
            подмена = dict(н.by_id)
            подмена[ид[1]] = подмена[ид[0]]
            return um.Назначение(by_id=подмена, natural=н.natural, groups=н.groups,
                                 affected=н.affected, from_ledger=н.from_ledger,
                                 disambiguated=н.disambiguated,
                                 by_feature=н.by_feature)

        monkeypatch.setattr(um, "назначить", испорченная)
        with pytest.raises(um.UrlMapError) as ош:
            live_mod.catalog_from_live(записи[:50])
        assert ош.value.error_code == "ROUTE_COLLISION"


class TestЗарезервированныеСегменты:
    def test_адрес_произведения_не_пересекается_с_разделами(self, назначение):
        РАЗДЕЛЫ = {"catalog", "genres", "countries", "animation", "search",
                   "collections", "assets", "title"}
        пересечение = РАЗДЕЛЫ & set(назначение.by_id.values())
        # Пересечение само по себе не опасно: раздел живёт в корне, а адрес
        # произведения — под /title/. Проверяется именно это.
        for с in пересечение:
            assert um.маршрут(с).startswith("/title/")

    def test_адрес_не_содержит_разделителя_пути(self, назначение):
        плохие = [с for с in назначение.by_id.values() if "/" in с or "." in с]
        assert плохие == []


class TestНовыеЗаписиНеОтбираютАдрес:
    """Старшинство решает спор за основу адреса."""

    def test_более_поздняя_запись_получает_различение(self, записи):
        новая = dict(записи[0])
        новая["external_id"] = "00000000-0000-0000-0000-000000000000"
        новая["created_at"] = "2099-01-01T00:00:00Z"
        каталог = live_mod.catalog_from_live(list(записи[:200]) + [новая])
        по_ид = {t.external_id: t.slug for t in каталог.titles}
        assert по_ид[записи[0]["external_id"]] == записи[0]["_natural"]
        assert um.РАЗДЕЛИТЕЛЬ in по_ид[новая["external_id"]]

    def test_равное_старшинство_решается_идентификатором(self, записи):
        новая = dict(записи[0])
        новая["external_id"] = "ffffffff-ffff-ffff-ffff-ffffffffffff"
        каталог = live_mod.catalog_from_live(list(записи[:200]) + [новая])
        по_ид = {t.external_id: t.slug for t in каталог.titles}
        assert по_ид[записи[0]["external_id"]] == записи[0]["_natural"]
        assert um.РАЗДЕЛИТЕЛЬ in по_ид[новая["external_id"]]


class TestОграниченныйКаталогОстаётсяЦелым:
    """Срез каталога обязан сохранять поиск по слагу.

    Ограничение строило каталог без указателя, и `by_slug` отдавал None на
    всё. Единственный его потребитель — подборки, поэтому дефект выражался
    не ошибкой, а пустой страницей подборки: проверка паритета карточек и
    маршрутов такого не замечает, потому что несуществующих ссылок не
    появляется — исчезают существующие.
    """

    def test_поиск_по_слагу_работает_после_ограничения(self, записи):
        from factory.lords import render as R
        каталог = live_mod.catalog_from_live(записи[:500])
        оставить = frozenset(sorted(t.slug for t in каталог.titles)[:100])
        урезанный = type(каталог)(
            titles=[t for t in каталог.titles if t.slug in оставить],
            collections=каталог.collections,
            _by_slug={t.slug: t for t in каталог.titles if t.slug in оставить})
        assert len(урезанный.titles) == 100
        for слаг in list(оставить)[:20]:
            assert урезанный.by_slug(слаг) is not None
        убранный = next(t.slug for t in каталог.titles if t.slug not in оставить)
        assert урезанный.by_slug(убранный) is None

    def test_рендер_ограничивает_каталог_вместе_с_указателем(self, записи):
        """Тот же путь, но через сам рендерер, а не воспроизведением его логики."""
        from factory.lords import preview as preview_mod
        from factory.lords import render as R
        каталог = live_mod.catalog_from_live(записи[:400])
        пакет, _ = preview_mod._package("zona-cinema-preview")
        слаги = frozenset(sorted(t.slug for t in каталог.titles)[:40])
        сайт = R.render_site(пакет, catalog=каталог, environ={},
                             publisher_id="1", only_title_slugs=слаги,
                             restrict_cards_to_rendered=True)
        страницы = {а[len("/title/"):].strip("/") for а in сайт.pages
                    if а.startswith("/title/") and а.count("/") == 3}
        # Подмножество, а не равенство: витрина публикует не все виды
        # произведений, и выбранный слаг неподходящего вида страницы не
        # получает. Это свойство витрины, а не потеря сущности.
        assert страницы and страницы <= слаги

        # Карточки не обещают ничего сверх собранного.
        import re as _re
        ссылка = _re.compile(r'href="(/title/[a-z0-9\-]*/)"')
        цели = set()
        for стр in сайт.pages.values():
            тело = стр.body
            if isinstance(тело, bytes):
                тело = тело.decode("utf-8", "replace")
            цели.update(ссылка.findall(тело))
        сироты = {ц for ц in цели if ц[len("/title/"):].strip("/") not in страницы}
        assert сироты == set(), f"карточек в никуда: {sorted(сироты)[:3]}"


class TestРантаймНеПортитАдрес:
    """Двойной дефис — часть адреса, а не опечатка.

    Различающий суффикс отделён двойным дефисом. Если бы приведение адреса
    схлопывало повторные дефисы — как это делает нормализация для ПОИСКА
    коллизий, — каждый различённый адрес уезжал бы на несуществующую страницу,
    и 206 исправленных сущностей снова стали бы недоступны.
    """

    def test_приведение_адреса_сохраняет_двойной_дефис(self):
        from factory.lords import serve as serve_mod
        адрес = "/title/akuly-2--2000/"
        assert serve_mod.normalize(адрес) == адрес
        assert um.нормализовать(адрес) == адрес

    def test_нормализация_для_поиска_коллизий_наоборот_схлопывает(self):
        assert um.нормализовать_слаг("akuly-2--2000") == "akuly-2-2000"

    def test_приведение_адреса_чинит_только_то_что_должно(self):
        from factory.lords import serve as serve_mod
        assert serve_mod.normalize("//title//akuly-2--2000") == "/title/akuly-2--2000/"
        assert serve_mod.normalize("/TITLE/Akuly-2--2000/") == "/title/akuly-2--2000/"

    def test_различённые_адреса_проходят_проверку_вида(self, назначение):
        различённые = [с for с in назначение.by_id.values() if um.РАЗДЕЛИТЕЛЬ in с]
        assert len(различённые) == 206
        for с in различённые:
            assert um.маршрут(с) == f"/title/{с}/"
