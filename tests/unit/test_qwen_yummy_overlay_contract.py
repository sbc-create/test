"""Накладка Yummy пишется в составе ПРИЛОЖЕНИЯ, иначе не пишется вовсе.

Откуда это требование. Приложение витрины читает `title-overlays.json` своей
схемой (`src/modules/editorial/title-overlay.ts`: `fileSchema`/`itemSchema`) и
при неудаче разбора МОЛЧА берёт `title-overlays.last-good.json`. То есть одна
неполная запись не «не работает сама» — она возвращает посетителю ПРЕЖНИЕ
тексты всех записей сайта, и операция при этом отвечает «опубликовано».

Измерено 2026-10-09 на yummyani.site: публикация 07:13:52Z записала запись в
нашем составе (`slug`, `title_id`, `body`, `provenance`), у неё `title_id`,
`canonical_path`, `content_id`, `content_type`, `published_at` и
`methodology_version` были `null`. Страница отдавала текст от 30 сентября:
уникальный кусок нового текста на ней отсутствовал, уникальный кусок прежнего —
присутствовал. Остальные три записи были полны и сходились по цифре.

Поэтому проверки держат три утверждения:

* состав записи для Yummy дополняется до схемы приложения, и `title_id`
  берётся из хранилища, а не выдумывается;
* файл, который приложение отвергло бы, не записывается — операция отказывает
  громко и до записи;
* семейства с НАШИМ читателем эта застава не касается: состав там задаём мы.
"""

from __future__ import annotations

import json

import pytest

from factory.qwen import editorial, registry


class СайтYummy:
    domain = "yummyani.site"
    site_id = "yummy-site"
    adapter = "yummy"
    account = "yummyani-site"


class СайтAnimeGo:
    domain = "an1meg0.site"
    site_id = "animego-04"
    adapter = "animego"
    account = "an1meg0-site"


ТЕЛО = "Текст о произведении длиной, которой хватает для разбора и цифры."


def _запись(**поля):
    итог = {"slug": "009-1", "title_id": None, "body": ТЕЛО,
            "provenance": {"author": "cell/wt-portable-site-cell-01"}}
    итог.update(поля)
    return итог


def test_состав_для_yummy_дополняется_до_схемы_приложения(monkeypatch):
    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    текущее = {"items": [{"slug": "009-1", "title_id": "01927e18-0e9e-7319-91b5-b8dd8be5a6a9"}]}
    полная = editorial._дополнить_под_приложение(СайтYummy(), _запись(), текущее)
    for поле in editorial.ПОЛЯ_ПРИЛОЖЕНИЯ_YUMMY:
        assert isinstance(полная.get(поле), str) and полная[поле].strip(), поле
    assert полная["title_id"] == "01927e18-0e9e-7319-91b5-b8dd8be5a6a9", (
        "идентификатор берётся из хранилища, а не выдумывается")
    assert полная["canonical_path"] == "/anime/009-1", (
        "адрес строится формой семейства: у Yummy это /anime/<slug> без слеша")
    assert полная["content_digest"] == editorial.отпечаток(ТЕЛО)
    assert полная["content_type"] == "TITLE_DESCRIPTION"
    assert полная["methodology_version"] == "SEO_CONTENT_METHODOLOGY_V1"
    # Провенанс не теряется: он наш и нужен журналу.
    assert полная["provenance"]["author"] == "cell/wt-portable-site-cell-01"


def test_без_известного_идентификатора_операция_отказывает(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(registry, "путь_доставки",
                        lambda s: str(tmp_path / "title-overlays.json"))
    # Поиск приложения — третий источник; здесь он ничего не знает. В сеть
    # тест не выходит: опрос подменён.
    monkeypatch.setattr(editorial, "_title_id_из_поиска", lambda s, slug: "")
    # Четвёртый источник — сама карточка; на стенде её тоже нет. Без этой
    # заглушки тест ушёл бы в сеть за страницей живой витрины.
    monkeypatch.setattr(editorial, "_title_id_со_страницы", lambda s, slug: "")
    with pytest.raises(editorial.ОперацияОтклонена, match="title_id"):
        editorial._дополнить_под_приложение(СайтYummy(), _запись(slug="новый-слаг"),
                                            {"items": []})


def test_идентификатор_первой_записи_берётся_из_поиска_приложения(monkeypatch):
    """Первой записи сайта в хранилище нет по определению — и это не отказ.

    Измерено 2026-10-09 на yummyani.org (ни одного материала): приложение
    отдаёт идентификатор поставщика своим же поиском, страница тайтла его не
    печатает. Тождество проверяется ссылкой: совпадения по названию
    недостаточно, названия в сети повторяются.
    """
    страницы = {"https://yummyani.org/anime/ры": '<meta property="og:title" content="Рыцарь | YummyAnime">'}
    поиски = {"Рыцарь": {"items": [
        {"slug": "019ef9d9-822b-7eda-a819-5f46d5a28050", "href": "/anime/ры"},
        {"slug": "00000000-0000-0000-0000-000000000000", "href": "/anime/другой"}]}}

    class СайтOrg(СайтYummy):
        domain = "yummyani.org"

    def подставной(адрес, *_а, **_к):
        import json as _json
        import urllib.parse as _p
        части = _p.urlsplit(адрес)
        if части.path.startswith("/api/search"):
            запрос = _p.parse_qs(части.query)["q"][0]
            тело = _json.dumps(поиски.get(запрос, {"items": []})).encode()
        else:
            тело = страницы[f"https://{части.netloc}{части.path}"].encode()

        class Ответ:
            def read(self): return тело
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return Ответ()

    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(editorial.urllib.request, "urlopen",
                        lambda запрос, **кв: подставной(запрос.full_url))
    assert (editorial._title_id_из_поиска(СайтOrg(), "ры")
            == "019ef9d9-822b-7eda-a819-5f46d5a28050")


def test_поиск_не_принимает_совпадение_с_чужим_адресом(monkeypatch):
    """Приписать текст другому произведению хуже, чем не опубликовать."""
    class СайтOrg(СайтYummy):
        domain = "yummyani.org"

    def подставной(адрес):
        import json as _json
        import urllib.parse as _p
        части = _p.urlsplit(адрес)
        if части.path.startswith("/api/search"):
            тело = _json.dumps({"items": [
                {"slug": "019f0000-0000-0000-0000-000000000001",
                 "href": "/anime/sovsem-drugoe"}]}).encode()
        else:
            тело = ('<meta property="og:title" content="Название | YummyAnime">'
                    .encode("utf-8"))

        class Ответ:
            def read(self): return тело
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return Ответ()

    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(editorial.urllib.request, "urlopen",
                        lambda запрос, **кв: подставной(запрос.full_url))
    assert editorial._title_id_из_поиска(СайтOrg(), "наш-слаг") == ""


def test_идентификатор_берётся_и_из_last_good(monkeypatch, tmp_path):
    """Приложение держит last-good рядом, и это наш же проверяемый источник."""
    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(registry, "путь_доставки",
                        lambda s: str(tmp_path / "title-overlays.json"))
    (tmp_path / "title-overlays.last-good.json").write_text(json.dumps(
        {"items": [{"slug": "джоджо", "title_id": "019d0533-fa56-7950-8236-4c2c9903689d"}]}),
        encoding="utf-8")
    полная = editorial._дополнить_под_приложение(
        СайтYummy(), _запись(slug="джоджо"), {"items": []})
    assert полная["title_id"] == "019d0533-fa56-7950-8236-4c2c9903689d"


def test_наш_читатель_застава_не_трогает():
    """У AnimeGo состав задаём мы: дополнять и проверять чужую схему незачем."""
    запись = _запись(title_id="019fa7c1-700c-77c6-a9e4-13b223a032dc")
    assert editorial._дополнить_под_приложение(СайтAnimeGo(), запись, {"items": []}) == запись
    # И проверка файла молчит — она включается только там, где схему диктует
    # приложение витрины.
    editorial._отказать_если_приложение_отвергнет(СайтAnimeGo(), "поколение", [запись])


def test_неполная_запись_не_записывается(monkeypatch):
    """Ровно тот случай, что случился 07:13:52Z: ОТКАЗ вместо «опубликовано»."""
    запись = _запись()           # title_id = None и ни одного поля приложения
    with pytest.raises(editorial.ОперацияОтклонена) as ош:
        editorial._отказать_если_приложение_отвергнет(СайтYummy(), "поколение", [запись])
    текст = str(ош.value)
    assert "last-good" in текст, "отказ обязан называть цену: вернутся прежние тексты"
    assert "title_id" in текст


def test_проверка_файла_повторяет_схему_приложения():
    полный = {
        "schema_version": 1, "site": "yummyani.site",
        "generated_at": "2026-10-09T13:00:00Z", "generation_id": "g1",
        "items": [{
            "title_id": "01927e18-0e9e-7319-91b5-b8dd8be5a6a9", "slug": "009-1",
            "canonical_path": "/anime/009-1", "content_id": "editorial-009-1-abc",
            "content_type": "TITLE_DESCRIPTION", "body": ТЕЛО,
            "content_digest": editorial.отпечаток(ТЕЛО),
            "published_at": "2026-10-09T13:00:00Z",
            "methodology_version": "SEO_CONTENT_METHODOLOGY_V1",
        }],
    }
    assert editorial.проверить_накладку_приложения(полный, "yummyani.site") == []
    # Чужой сайт в файле — приложение отвергает весь файл, и проверка тоже.
    чужой = {**полный, "site": "yummyani.org"}
    assert any("не совпадает" in б
               for б in editorial.проверить_накладку_приложения(чужой, "yummyani.site"))
    # Цифра, не сходящаяся с телом: приложение ПРОПУСТИТ запись молча.
    кривая = json.loads(json.dumps(полный))
    кривая["items"][0]["content_digest"] = "0" * 64
    беды = editorial.проверить_накладку_приложения(кривая, "yummyani.site")
    assert any("не сходится" in б for б in беды), беды
    # Версия схемы — литерал: приложение сверяет её точным значением.
    иная = {**полный, "schema_version": 2}
    assert any("schema_version" in б
               for б in editorial.проверить_накладку_приложения(иная, "yummyani.site"))


def test_состав_полей_взят_из_схемы_приложения():
    """Перечень не живёт своей жизнью: он назван тем же, чем проверяется."""
    assert set(editorial.ПОЛЯ_ПРИЛОЖЕНИЯ_YUMMY) == {
        "title_id", "slug", "canonical_path", "content_id", "content_type",
        "body", "content_digest", "published_at", "methodology_version"}

def test_идентификатор_читается_с_самой_карточки(monkeypatch):
    """Поток страницы печатает пару `slug`/`publicSlug` — это и есть ответ.

    Измерено 2026-10-09 на `yummyani.site/anime/holst`: в разметке ответа
    стоит `{"slug":"01a11d26-…","publicSlug":"holst"}`, и это тот самый
    идентификатор, по которому карточка запрашивает свой тред комментариев.
    Прежнее измерение «страница идентификатор не печатает» касалось JSON-LD и
    мета-тегов и для них остаётся верным.

    Почему источник стоит ПЕРЕД поиском: пара напечатана рядом с нашим
    публичным слагом, поэтому ошибиться произведением нельзя. Поиск отвечает
    по названию, и совпадение приходится сверять ссылкой.
    """
    class СайтSite(СайтYummy):
        domain = "yummyani.site"

    страницы = {
        # Порядок полей встречается оба; выражение принимает любой.
        "holst": '["$","$L21",null,{"title":{"slug":"01a11d26-8d48-7890-850f-bca5f4926e42","publicSlug":"holst","name":"Холст"}}]',
        "obratno": '{"publicSlug":"obratno","slug":"01a11d26-8d48-7890-850f-bca5f49200aa"}',
        # Чужая пара в потоке (блок рекомендаций) не должна приниматься за свою.
        "nash": '{"slug":"01a11d26-0000-0000-0000-000000000001","publicSlug":"chuzhoy"}',
    }

    def подставной(адрес):
        слаг = адрес.rsplit("/", 1)[-1]
        тело = страницы[слаг].encode("utf-8")

        class Ответ:
            def read(self): return тело
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return Ответ()

    monkeypatch.setattr(registry, "адрес_тайтла",
                        lambda s, slug: f"https://{s.domain}/anime/{slug}")
    monkeypatch.setattr(editorial.urllib.request, "urlopen",
                        lambda запрос, **кв: подставной(запрос.full_url))
    assert (editorial._title_id_со_страницы(СайтSite(), "holst")
            == "01a11d26-8d48-7890-850f-bca5f4926e42")
    assert (editorial._title_id_со_страницы(СайтSite(), "obratno")
            == "01a11d26-8d48-7890-850f-bca5f49200aa")
    assert editorial._title_id_со_страницы(СайтSite(), "nash") == "", (
        "пара чужого слага принята за свою — так приписывают текст другому "
        "произведению")


def test_страница_опрашивается_раньше_поиска(monkeypatch, tmp_path):
    """Порядок источников закреплён: карточка, потом поиск."""
    monkeypatch.setattr(registry, "путь_доставки",
                        lambda s: str(tmp_path / "title-overlays.json"))
    звонки = []
    monkeypatch.setattr(editorial, "_title_id_со_страницы",
                        lambda s, slug: звонки.append("страница") or "со-страницы")
    monkeypatch.setattr(editorial, "_title_id_из_поиска",
                        lambda s, slug: звонки.append("поиск") or "из-поиска")
    assert editorial._известный_title_id(СайтYummy(), "слаг", {"items": []}) == "со-страницы"
    assert звонки == ["страница"], "поиск вызван, хотя страница уже ответила"
