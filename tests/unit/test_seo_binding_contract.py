"""Контракт `seo-route-binding`: обещания производителя и права потребителя.

Проверки делятся надвое, и деление существенно. Проверки производителя
спрашивают «выдаёт ли ядро то, что обещало»; проверки потребителя — «может ли
SEO опереться на выданное, ничего не додумывая». Второй вопрос не следует из
первого: контракт можно выдать безупречно и всё же оставить потребителю
возможность угадать вид произведения из названия.

Числа в пояснениях — с боевого снимка каталога, а не придуманы.
"""
from __future__ import annotations

import json

import pytest

from factory.site_engine import seo_binding as sb
from factory.site_engine.adapters import lords_seo_binding as ad
from factory.site_engine.content_kind import ContentKind

СНИМОК = "2026-09-06T04:45:32+00:00"
ПРОИСХОЖДЕНИЕ = "catalog-cache:test"


def запись(**kwargs):
    основа = {
        "external_id": "01a00000-0000-7000-8000-000000000001",
        "name": "Произведение",
        "type": "tv",
        "is_series": True,
        "tags": [],
        "year": 2026,
        "playback": {"aggregator": "kp", "title_id": "1"},
        "external_ids": {"kp": "1"},
    }
    основа.update(kwargs)
    return основа


def связать(записи):
    return ad.build(записи, site_id="site-01", snapshot_at=СНИМОК,
                    provenance=ПРОИСХОЖДЕНИЕ)


def одна(**kwargs):
    return связать([запись(**kwargs)])[0]


class Профиль:
    def __init__(self, site_id="site-01", host="example.test"):
        self.site_id = site_id
        self.canonical_host = host


# --- производитель: виды произведений ---------------------------------------

@pytest.mark.parametrize("тип,теги,ожидаемый", [
    ("movie", [], ContentKind.MOVIE),
    ("tv", [], ContentKind.SERIES),
    ("tv", ["ona"], ContentKind.ONA),
    ("tv", ["ova"], ContentKind.OVA),
    ("movie", ["special"], ContentKind.SPECIAL),
])
def test_вид_приходит_из_данных_источника(тип, теги, ожидаемый):
    b = одна(type=тип, tags=теги)
    assert b.content_kind is ожидаемый, b.content_kind_provenance
    assert b.content_kind_state is sb.KindState.RESOLVED
    assert b.binding_state is sb.BindingState.BOUND


def test_анимация_не_является_видом():
    """Тег способа исполнения не делает произведение анимационным фильмом."""
    b = одна(type="tv", tags=["cartoon"])
    assert b.content_kind is ContentKind.SERIES
    assert b.is_animation is True
    assert b.schema_type == "TVSeries"


def test_неизвестный_вид_не_становится_фильмом():
    b = одна(type="", tags=[])
    assert b.content_kind is ContentKind.UNKNOWN
    assert b.content_kind_state is sb.KindState.MISSING
    assert b.schema_type == ""
    assert b.binding_state is sb.BindingState.KIND_UNRESOLVED
    assert sb.ReasonCode.KIND_MISSING in b.reason_codes


def test_конфликтный_вид_уходит_в_разбор_с_кодом():
    b = одна(type="movie", tags=["ona"])
    assert b.content_kind_state is sb.KindState.CONFLICTED
    assert b.content_kind is ContentKind.UNKNOWN
    assert b.schema_type == ""
    assert sb.ReasonCode.KIND_CONFLICTED in b.reason_codes


def test_состояние_вида_не_может_нести_вид_при_конфликте():
    with pytest.raises(sb.ContractViolation, match="обязан выглядеть"):
        sb.RouteBinding(
            site_id="s", content_id="c", external_ids={}, route_id="/t/",
            page_type="title", canonical_path="/t/",
            content_kind=ContentKind.MOVIE,
            content_kind_state=sb.KindState.CONFLICTED,
            content_kind_provenance="", playback_state=sb.PlaybackState.UNKNOWN,
            playback_reason_code=sb.ReasonCode.MISSING_PROVIDER_ID,
            playback_observed_at="", content_revision="r",
            binding_state=sb.BindingState.KIND_UNRESOLVED,
            reason_codes=(sb.ReasonCode.KIND_CONFLICTED,),
            provenance="p", snapshot_at=СНИМОК)


# --- производитель: воспроизведение -----------------------------------------

def test_разрешённый_идентификатор_даёт_право_обещать_просмотр():
    b = одна(playback={"aggregator": "mali", "title_id": "9"})
    assert b.playback_state is sb.PlaybackState.PLAYABLE
    assert b.playback_reason_code is sb.ReasonCode.PLAYBACK_OK
    assert b.may_promise_playback is True
    assert b.playback_observed_at == СНИМОК


def test_только_imdb_права_обещать_просмотр_не_даёт():
    """654 записи каталога: идентификатор есть, контракт его запрещает."""
    b = одна(playback=None, external_ids={"imdb": "tt1"})
    assert b.playback_state is sb.PlaybackState.BLOCKED_BY_CONTRACT
    assert b.playback_reason_code is sb.ReasonCode.IDENTIFIER_FORBIDDEN_BY_CONTRACT
    assert b.may_promise_playback is False


def test_отсутствие_идентификаторов_отличается_от_запрещённого():
    """66 записей каталога: идентификаторов нет вовсе. Это другое состояние."""
    b = одна(playback=None, external_ids={})
    assert b.playback_state is sb.PlaybackState.NO_IDENTIFIER
    assert b.playback_reason_code is sb.ReasonCode.MISSING_PROVIDER_ID


def test_разрешённый_идентификатор_без_потока_третье_состояние():
    b = одна(playback=None, external_ids={"kp": "1"})
    assert b.playback_state is sb.PlaybackState.NO_STREAM
    assert b.playback_reason_code is sb.ReasonCode.PROVIDER_NOT_PLAYABLE


def test_playable_без_момента_наблюдения_создать_нельзя():
    with pytest.raises(sb.ContractViolation, match="без момента наблюдения"):
        sb.RouteBinding(
            site_id="s", content_id="c", external_ids={}, route_id="/t/",
            page_type="title", canonical_path="/t/",
            content_kind=ContentKind.MOVIE,
            content_kind_state=sb.KindState.RESOLVED,
            content_kind_provenance="", playback_state=sb.PlaybackState.PLAYABLE,
            playback_reason_code=sb.ReasonCode.PLAYBACK_OK,
            playback_observed_at="", content_revision="r",
            binding_state=sb.BindingState.BOUND,
            reason_codes=(sb.ReasonCode.OK,), provenance="p",
            snapshot_at=СНИМОК)


# --- производитель: оценка ---------------------------------------------------

def test_отсутствие_оценки_не_превращается_в_ноль():
    b = одна(kinopoisk_rating=None, imdb_rating=None)
    assert b.rating_state is sb.RatingState.UNRATED
    assert b.rating_value is None


def test_нечитаемая_оценка_даёт_неизвестность_а_не_ноль():
    b = одна(kinopoisk_rating="—")
    assert b.rating_state is sb.RatingState.UNKNOWN
    assert b.rating_value is None


def test_числовая_оценка_переносится_как_есть():
    b = одна(kinopoisk_rating="6,7")
    assert b.rating_state is sb.RatingState.RATED
    assert b.rating_value == 6.7


def test_оценка_без_состояния_rated_значения_не_несёт():
    with pytest.raises(sb.ContractViolation, match="ноль здесь означал бы"):
        sb.RouteBinding(
            site_id="s", content_id="c", external_ids={}, route_id="/t/",
            page_type="title", canonical_path="/t/",
            content_kind=ContentKind.MOVIE,
            content_kind_state=sb.KindState.RESOLVED,
            content_kind_provenance="", playback_state=sb.PlaybackState.UNKNOWN,
            playback_reason_code=sb.ReasonCode.MISSING_PROVIDER_ID,
            playback_observed_at="", content_revision="r",
            binding_state=sb.BindingState.BOUND,
            reason_codes=(sb.ReasonCode.OK,), provenance="p",
            snapshot_at=СНИМОК, rating_state=sb.RatingState.UNRATED,
            rating_value=0.0)


# --- производитель: адрес и идентичность ------------------------------------

def test_одинаковые_названия_получают_разные_адреса():
    """Витрина разводит совпадения номером; связь воспроизводит это правило."""
    связи = связать([
        запись(external_id="a-1", name="Одно название"),
        запись(external_id="a-2", name="Одно название"),
    ])
    пути = [b.canonical_path for b in связи]
    assert пути == ["/title/odno-nazvanie/", "/title/odno-nazvanie-2/"]
    assert all(b.binding_state is sb.BindingState.BOUND for b in связи)


def test_смена_адреса_не_рвёт_идентичность():
    """Слаг зависит от порядка; contentId — нет. Идентичность в нём."""
    прямой = связать([запись(external_id="a-1", name="Одно"),
                      запись(external_id="a-2", name="Одно")])
    обратный = связать([запись(external_id="a-2", name="Одно"),
                        запись(external_id="a-1", name="Одно")])
    адреса_прямо = {b.content_id: b.canonical_path for b in прямой}
    адреса_обратно = {b.content_id: b.canonical_path for b in обратный}
    assert адреса_прямо != адреса_обратно, (
        "перестановка обязана менять адреса — иначе правило витрины "
        "воспроизведено неверно")
    assert set(адреса_прямо) == set(адреса_обратно), "идентичность уплыла"
    for b in прямой + обратный:
        assert b.content_revision, "ревизия обязана быть у каждой записи"


def test_неоднозначный_адрес_закрывается_наглухо():
    """Два произведения на один адрес — не повод выбрать одно."""
    связи = связать([
        запись(external_id="a-1", name="Одно"),
        запись(external_id="a-2", name="Одно 2"),
    ])
    assert [b.canonical_path for b in связи] == ["/title/odno/", "/title/odno-2/"]
    коллизия = связать([
        запись(external_id="b-1", name="Одно"),
        запись(external_id="b-2", name="Одно"),
        запись(external_id="b-3", name="Одно 2"),
    ])
    состояния = {b.content_id: b.binding_state for b in коллизия}
    assert состояния["b-2"] is sb.BindingState.ROUTE_COLLISION
    assert состояния["b-3"] is sb.BindingState.ROUTE_COLLISION
    for cid in ("b-2", "b-3"):
        b = next(x for x in коллизия if x.content_id == cid)
        assert sb.ReasonCode.ROUTE_AMBIGUOUS in b.reason_codes


def test_запись_без_ключа_или_названия_не_адресуема():
    без_ключа = связать([запись(external_id="")])[0]
    без_имени = связать([запись(name="")])[0]
    assert без_ключа.binding_state is sb.BindingState.NOT_ADDRESSABLE
    assert без_имени.binding_state is sb.BindingState.NOT_ADDRESSABLE
    assert sb.ReasonCode.MISSING_CONTENT_ID in без_ключа.reason_codes
    assert sb.ReasonCode.MISSING_TITLE in без_имени.reason_codes


def test_иностранное_название_адресуется_ключом():
    """Незнакомая письменность не даёт слага — адрес берётся из ключа."""
    b = одна(external_id="01a00000-0000-7000-8000-00000000000f", name="日本語")
    assert b.canonical_path.startswith("/title/")
    assert b.binding_state is sb.BindingState.BOUND


def test_идентификатор_из_неизвестного_пространства_прав_не_получает():
    b = одна(external_ids={"kp": "1", "какой-то-новый": "9"})
    assert set(b.external_ids) == {"kp"}
    with pytest.raises(sb.ContractViolation, match="пространства имён"):
        sb.RouteBinding(
            site_id="s", content_id="c", external_ids={"выдумка": "1"},
            route_id="/t/", page_type="title", canonical_path="/t/",
            content_kind=ContentKind.MOVIE,
            content_kind_state=sb.KindState.RESOLVED,
            content_kind_provenance="", playback_state=sb.PlaybackState.UNKNOWN,
            playback_reason_code=sb.ReasonCode.MISSING_PROVIDER_ID,
            playback_observed_at="", content_revision="r",
            binding_state=sb.BindingState.BOUND,
            reason_codes=(sb.ReasonCode.OK,), provenance="p", snapshot_at=СНИМОК)


def test_несколько_идентификаторов_переносятся_все():
    b = одна(external_ids={"kp": "1", "imdb": "tt1", "myanimelist": "9"})
    assert set(b.external_ids) == {"kp", "imdb", "myanimelist"}


def test_повторяющийся_внешний_идентификатор_не_объединяет_записи():
    """Два произведения с одним imdb остаются двумя записями."""
    связи = связать([
        запись(external_id="c-1", name="Первое", external_ids={"imdb": "tt1"},
               playback=None),
        запись(external_id="c-2", name="Второе", external_ids={"imdb": "tt1"},
               playback=None),
    ])
    assert len({b.content_id for b in связи}) == 2
    assert len({b.canonical_path for b in связи}) == 2


# --- производитель: свойства выгрузки ---------------------------------------

def test_порядок_записей_не_меняет_отпечаток():
    записи = [запись(external_id=f"d-{i}", name=f"Работа {i}") for i in range(20)]
    прямо = sb.digest(связать(записи))
    обратно = sb.digest(связать(list(reversed(записи))))
    assert прямо == обратно


def test_повторная_выгрузка_идемпотентна():
    записи = [запись(external_id=f"e-{i}", name=f"Работа {i}") for i in range(10)]
    первая = sb.envelope(связать(записи), site_id="site-01",
                         snapshot_at=СНИМОК, provenance=ПРОИСХОЖДЕНИЕ)
    вторая = sb.envelope(связать(записи), site_id="site-01",
                         snapshot_at=СНИМОК, provenance=ПРОИСХОЖДЕНИЕ)
    assert первая == вторая


def test_ревизия_меняется_вместе_с_содержимым_а_не_с_выгрузкой():
    было = одна()
    стало = связать([запись(year=2027)])[0]
    ещё_раз = одна()
    assert было.content_revision == ещё_раз.content_revision
    assert было.content_revision != стало.content_revision


def test_среди_принятых_записей_коллизий_нет():
    связи = связать([запись(external_id=f"f-{i}", name="Одно") for i in range(5)])
    принятые = [b for b in связи if b.binding_state is sb.BindingState.BOUND]
    пути = [b.canonical_path for b in принятые]
    assert len(пути) == len(set(пути)) == 5


def test_версия_объявлена_и_не_является_словом_latest():
    b = одна()
    assert b.schema_version == "seo-route-binding/1.0.0"
    assert b.contract_version == "1.0.0"
    assert "latest" not in json.dumps(b.as_dict())


# --- потребитель -------------------------------------------------------------

def test_потребитель_строит_адрес_из_версионированного_профиля():
    b = одна()
    assert b.canonical_url(Профиль(host="lordfilm47.space")) == \
        f"https://lordfilm47.space{b.canonical_path}"


def test_профиль_чужой_витрины_адрес_построить_не_даёт():
    b = одна()
    with pytest.raises(sb.ContractViolation, match="не соответствует"):
        b.canonical_url(Профиль(site_id="site-99"))


def test_профиль_без_канонического_хоста_адрес_построить_не_даёт():
    b = одна()
    with pytest.raises(sb.ContractViolation, match="канонический хост"):
        b.canonical_url(Профиль(host=""))


def test_потребителю_не_из_чего_угадать_вид():
    """У неустановленного вида нет ни типа разметки, ни разрешения на текст."""
    b = одна(type="", tags=[])
    payload = b.as_dict()
    assert payload["contentKind"] == "UNKNOWN"
    assert payload["schemaType"] == ""
    assert payload["contentKindState"] == "MISSING"
    assert payload["mayPromisePlayback"] is False


def test_метаданные_без_видео_не_обещают_просмотра():
    b = одна(playback=None, external_ids={"imdb": "tt1"})
    payload = b.as_dict()
    assert payload["mayPromisePlayback"] is False
    assert payload["playbackReasonCode"] == "IDENTIFIER_FORBIDDEN_BY_CONTRACT"
    assert payload["schemaType"], "вид известен — разметка выпускается"


def test_каждая_запись_несёт_код_причины():
    для_проверки = [одна(), одна(type="", tags=[]), одна(playback=None,
                                                          external_ids={})]
    for b in для_проверки:
        assert b.reason_codes
        assert all(isinstance(c, sb.ReasonCode) for c in b.reason_codes)


def test_запись_без_кода_причины_создать_нельзя():
    with pytest.raises(sb.ContractViolation, match="без кода причины"):
        sb.RouteBinding(
            site_id="s", content_id="c", external_ids={}, route_id="/t/",
            page_type="title", canonical_path="/t/",
            content_kind=ContentKind.MOVIE,
            content_kind_state=sb.KindState.RESOLVED,
            content_kind_provenance="", playback_state=sb.PlaybackState.UNKNOWN,
            playback_reason_code=sb.ReasonCode.MISSING_PROVIDER_ID,
            playback_observed_at="", content_revision="r",
            binding_state=sb.BindingState.BOUND, reason_codes=(),
            provenance="p", snapshot_at=СНИМОК)


def test_секретов_в_контракте_нет():
    """Контракт отвечает «можно ли обещать», а не «где лежит файл»."""
    payload = json.dumps(одна().as_dict(), ensure_ascii=False).lower()
    for запрещённое in ("token", "secret", "password", "m3u8", "http://",
                        "aggregator", "title_id"):
        assert запрещённое not in payload, запрещённое


# --- масштаб -----------------------------------------------------------------

@pytest.mark.parametrize("витрин", [3, 43, 50])
def test_контракт_масштабируется_на_витрины(витрин):
    """Добавление витрины — вызов адаптера, а не правка кода."""
    выгрузки = []
    for i in range(витрин):
        связи = связать([запись(external_id=f"{i}-1", name=f"Работа {i}")])
        связи = [__import__("dataclasses").replace(b, site_id=f"site-{i:03d}")
                 for b in связи]
        выгрузки.append(sb.envelope(связи, site_id=f"site-{i:03d}",
                                    snapshot_at=СНИМОК,
                                    provenance=ПРОИСХОЖДЕНИЕ))
    assert len(выгрузки) == витрин
    assert len({в["siteId"] for в in выгрузки}) == витрин
    for в in выгрузки:
        assert в["byBindingState"] == {"BOUND": 1}


def test_в_ядре_контракта_нет_имён_витрин():
    """Ядро описывает форму; про конкретные витрины знает адаптер.

    Смотрится код без пояснений — той же функцией, которой это делает гейт
    границ. Правило запрещает ядру **вести себя** по-разному для разных
    витрин, а не упоминать их в объяснении, откуда взялось правило адресации:
    объяснение без имени модуля перестало бы быть объяснением.
    """
    import inspect

    from factory.site_engine.boundaries import code_without_prose

    код = code_without_prose(inspect.getsource(sb)).lower()
    for имя in ("lords", "yummy", "lordfilm", "lordserial", "dle"):
        assert имя not in код, f"имя витрины в поведении ядра: {имя}"


def test_конфликт_типа_и_тега_не_разрешается_молча():
    """Тип поставщика «сериал» и тег «спецвыпуск» — разные группы."""
    b = одна(type="tv", tags=["special"])
    assert b.content_kind_state is sb.KindState.CONFLICTED
    assert b.content_kind is ContentKind.UNKNOWN
    assert sb.ReasonCode.KIND_CONFLICTED in b.reason_codes
