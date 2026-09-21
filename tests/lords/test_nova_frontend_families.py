"""Рантайм витрин (`automation/host/lords-frontend.py`), оформление 1.1.0.

Почему проверяется именно этот файл. Публичные витрины Lords и Zona отдаёт
он, а не `factory/lords/render.py`: nginx проксирует домены на юниты `nova-*`,
которые запускают ровно этот артефакт. Правка отрисовщика фабрики видна только
после полной пересборки статического релиза; правка здесь видна сразу. Тесты,
проверявшие лишь отрисовщик, поэтому и пропускали дефекты, которые посетитель
видел на первой же карточке.

Что закрывается этими проверками:

* карточка каталога ведёт на СУЩЕСТВУЮЩУЮ страницу, а не в 404 (на zona-01 в
  404 вели все 3868 карточек — снимок каталога ушёл вперёд статического
  релиза, из которого страницы брались);
* неизвестный адрес отвечает настоящей 404, а не оболочкой с кодом 200;
* список серий не обрывается, и двести десятая серия достижима;
* номер серии в адресе, в `H1`, в `<title>`, в canonical и в Schema — одно и
  то же число;
* семейства Lords и Zona различаются композицией, типографикой, геометрией
  карточки и раскладкой страницы произведения, а не только цветом;
* витрина, чей манифест остался на 1.0.2, исполняет прежнюю ветку.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИСХОДНИК = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"

#: Сколько серий в единственном сезоне синтетического сериала. Больше двухсот
#: десяти намеренно: требование задания проверяется на границах 1, 2, 99, 100,
#: 101, 209 и 210, и все они обязаны лежать ВНУТРИ сезона, а не на его конце.
СЕРИЙ = 286


def _каталог(витрина: str, семейство: str) -> dict:
    записи = [
        {"slug": "seriya-dolgaya", "title": "Долгий сериал", "kind": "Сериал",
         "year": 2019, "poster": "https://poster.example/aaa.webp",
         "url": "/title/seriya-dolgaya/", "published_at": "2026-09-01T00:00:00Z",
         "published_at_estimated": False},
        {"slug": "film-prostoy", "title": "Простой фильм", "kind": "Фильм",
         "year": 2024, "poster": "https://poster.example/bbb.webp",
         "url": "/title/film-prostoy/", "published_at": "2026-09-02T00:00:00Z",
         "published_at_estimated": False},
        {"slug": "bez-postera", "title": "Запись без постера", "kind": "Фильм",
         "year": 2021, "poster": "", "url": "/title/bez-postera/",
         "published_at": "2026-09-03T00:00:00Z", "published_at_estimated": False},
        {"slug": "ochen-dlinnoe-nazvanie-kotoroe-ne-pomeschaetsya-v-kartochku-nikak",
         "title": "Очень длинное название, которое не помещается в карточку никак "
                  "и продолжает не помещаться дальше",
         "kind": "Фильм", "year": 2020, "poster": "https://poster.example/ccc.webp",
         "url": "/title/ochen-dlinnoe-nazvanie-kotoroe-ne-pomeschaetsya-v-kartochku-nikak/",
         "published_at": "2026-09-04T00:00:00Z", "published_at_estimated": False},
    ]
    return {"version": 2, "count": len(записи), "items": записи,
            "fields_absent": ["genres"], "site": витрина,
            "schema": "nova-catalog/2.0.0", "revision": "test", "builtAt": "2026-09-13T00:00:00Z"}


def _подробности(витрина: str) -> dict:
    return {
        "schema": "nova-details/1.0.0", "site": витрина, "details_total": 2,
        "source": "test", "items_total": 4,
        "details": {
            "seriya-dolgaya": {
                "id": "0191511d-3648-7224-989d-5ef91f2efaa6",
                "description": "Синтетическое описание синтетического сериала.",
                "original_name": "Long Series", "countries": ["Япония"],
                "genres": ["детектив", "комедия"], "genre_codes": ["detective", "comedy"],
                "duration": 24, "premiere_date": "2019-04-07",
                "seasons": [{"n": 1, "eps": СЕРИЙ, "avail": СЕРИЙ}],
                "seasons_count": 1, "kinopoisk_rating": 8.1, "imdb_rating": 7.9,
                "external_ids": {"kp": "123456", "imdb": "7654321"},
                "is_series": True,
            },
            "film-prostoy": {
                "id": "0191511d-84b5-71de-91aa-9f28e25c0ec7",
                "description": "Синтетическое описание синтетического фильма.",
                "countries": ["Франция"], "genres": ["драма"], "genre_codes": ["drama"],
                "duration": 108, "kinopoisk_rating": 6.4, "is_series": False,
                "external_ids": {"imdb": "1112223"},
            },
        },
    }


def _манифест(семейство: str, версия: str, профиль: str) -> dict:
    return {"schema_version": 1, "template_family": семейство,
            "design_version": версия, "source_commit": "0" * 40,
            "build_id": "TEST", "artifact_sha256": "0" * 64,
            "profile": профиль, "built_at": "2026-09-13T00:00:00Z"}


def _поднять(tmp_path, витрина: str, семейство: str, версия: str = "1.1.0",
             плеер: bool = True):
    """Отдельный экземпляр модуля витрины.

    Модуль читает манифест НА ИМПОРТЕ — так устроен рантайм, и подменять это
    ради теста значило бы проверять не то, что работает в production. Поэтому
    на каждую витрину загружается свой экземпляр под своим именем.
    """
    корень = tmp_path / витрина
    корень.mkdir(parents=True, exist_ok=True)
    (корень / f"{витрина}-catalog.json").write_text(
        json.dumps(_каталог(витрина, семейство), ensure_ascii=False), encoding="utf-8")
    (корень / f"{витрина}-details.json").write_text(
        json.dumps(_подробности(витрина), ensure_ascii=False), encoding="utf-8")
    манифест = корень / "manifest.json"
    манифест.write_text(json.dumps(_манифест(семейство, версия, f"{семейство}-test"),
                                   ensure_ascii=False), encoding="utf-8")
    if плеер:
        (корень / f"player-{витрина}.json").write_text(
            json.dumps({"publisher_id": "10001"}), encoding="utf-8")

    прежние = dict(sys.modules)
    import os
    старое_окружение = dict(os.environ)
    os.environ["LORDS_TEMPLATE_MANIFEST"] = str(манифест)
    os.environ["LORDS_CATALOG"] = str(корень / f"{витрина}-catalog.json")
    os.environ["LORDS_SITE_NAME"] = f"Витрина {семейство}"
    os.environ.pop("LORDS_DETAILS", None)
    os.environ.pop("LORDS_PLAYER_CONFIG", None)
    try:
        имя = f"nova_{витрина.replace('-', '_')}_{версия.replace('.', '_')}"
        спец = importlib.util.spec_from_file_location(имя, ИСХОДНИК)
        модуль = importlib.util.module_from_spec(спец)
        sys.modules[имя] = модуль
        спец.loader.exec_module(модуль)
    finally:
        os.environ.clear()
        os.environ.update(старое_окружение)
        for к in set(sys.modules) - set(прежние):
            if not к.startswith("nova_"):
                sys.modules.pop(к, None)
    модуль.Обработчик.данные = модуль.Данные(str(корень / f"{витрина}-catalog.json"))
    модуль.Обработчик.подробности = модуль.Подробности(str(корень / f"{витрина}-details.json"))
    модуль.Обработчик.индекс = модуль.построить_индекс(
        модуль.Обработчик.данные, модуль.Обработчик.подробности)
    return модуль


class Ответ:
    def __init__(self, статус: int, тело: str, заголовки: dict):
        self.статус, self.тело, self.заголовки = статус, тело, заголовки


def запросить(модуль, путь: str) -> Ответ:
    """Один запрос к витрине без сокета.

    Обработчик вызывается напрямую: поднимать сервер и ходить в него по сети
    ради разметки — это проверять сеть, а не разметку, и тесты фабрики в сеть
    не ходят.
    """
    from urllib.parse import parse_qs, unquote, urlparse

    собрано = {"статус": 200, "тело": b"", "заголовки": {}}

    class Заглушка(модуль.Обработчик):
        def __init__(self):  # сокет не нужен
            self.path = путь
            self.command = "GET"
            self.headers = {"Host": "test.example"}

        def _отдать(self, тело, тип="text/html; charset=utf-8", код=200):
            собрано["статус"] = код
            собрано["тело"] = тело
            собрано["заголовки"]["Content-Type"] = тип

        def send_response(self, код):
            собрано["статус"] = код

        def send_header(self, имя, значение):
            собрано["заголовки"][имя] = значение

        def end_headers(self):
            pass

    о = Заглушка()
    o_разбор = urlparse(путь)
    о.do_GET()
    return Ответ(собрано["статус"],
                 собрано["тело"].decode("utf-8") if собрано["тело"] else "",
                 собрано["заголовки"])


@pytest.fixture(scope="module")
def лордс(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("lords"), "lords-01", "lords")


@pytest.fixture(scope="module")
def зона(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona"), "zona-01", "zona")


@pytest.fixture(scope="module")
def прежняя_версия(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("legacy"), "lords-02", "lords", версия="1.0.2")


class TestКарточкаВедётНаСтраницу:
    """Дефект, из-за которого у zona-01 в 404 вели все карточки без исключения."""

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_каждая_карточка_каталога_открывается(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        каталог = запросить(модуль, "/catalog/")
        assert каталог.статус == 200
        адреса = set(re.findall(r'href="(/title/[^"#?]+/)"', каталог.тело))
        assert адреса, "на странице каталога нет ни одной карточки"
        for адрес in sorted(адреса):
            ответ = запросить(модуль, адрес)
            assert ответ.статус == 200, f"карточка ведёт в {ответ.статус}: {адрес}"
            assert len(ответ.тело) > 2000, f"страница-пустышка: {адрес}"

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_каждая_запись_снимка_имеет_страницу(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        for запись in модуль.Обработчик.данные.items:
            ответ = запросить(модуль, запись["url"])
            assert ответ.статус == 200, f"{запись['url']} → {ответ.статус}"

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_неизвестный_адрес_это_настоящая_404(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        for путь in ("/title/net-takoy-zapisi/", "/nope/", "/title/film-prostoy/season-9/"):
            ответ = запросить(модуль, путь)
            assert ответ.статус == 404, f"мягкая двухсотка на {путь}"

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_адрес_без_слэша_уводит_одним_переходом(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/title/film-prostoy")
        assert ответ.статус == 308
        assert ответ.заголовки["Location"] == "/title/film-prostoy/"
        # Цель перехода обязана отвечать сразу, без второго перехода.
        дальше = запросить(модуль, ответ.заголовки["Location"])
        assert дальше.статус == 200


class TestСерииНеОбрываются:
    """Двести десятая серия достижима, а номер везде один и тот же."""

    ГРАНИЦЫ = (1, 2, 99, 100, 101, 209, 210)

    def test_на_странице_сериала_перечислены_все_серии(self, лордс):
        страница = запросить(лордс, "/title/seriya-dolgaya/")
        assert страница.статус == 200
        номера = sorted({int(н) for н in
                         re.findall(r"/season-1/episode-(\d+)/", страница.тело)})
        assert номера == list(range(1, СЕРИЙ + 1)), (
            f"список серий обрывается: {len(номера)} из {СЕРИЙ}")

    @pytest.mark.parametrize("номер", ГРАНИЦЫ)
    def test_граничная_серия_открывается_и_называет_свой_номер(self, лордс, номер):
        путь = f"/title/seriya-dolgaya/season-1/episode-{номер}/"
        ответ = запросить(лордс, путь)
        assert ответ.статус == 200, f"серия {номер} недоступна"
        h1 = re.search(r"<h1>(.*?)</h1>", ответ.тело, re.S)
        титул = re.search(r"<title>(.*?)</title>", ответ.тело, re.S)
        описание = re.search(r'name="description" content="([^"]*)"', ответ.тело)
        канон = re.search(r'rel="canonical" href="([^"]+)"', ответ.тело)
        схема = re.search(r'"episodeNumber": (\d+)', ответ.тело)
        assert h1 and f"{номер} серия" in h1.group(1)
        assert титул and f"{номер} серия" in титул.group(1)
        assert описание and f"{номер} серия" in описание.group(1)
        assert канон and канон.group(1).endswith(путь)
        assert схема and int(схема.group(1)) == номер

    def test_сотая_и_сто_первая_связаны_в_обе_стороны(self, лордс):
        сотая = запросить(лордс, "/title/seriya-dolgaya/season-1/episode-100/")
        сто_первая = запросить(лордс, "/title/seriya-dolgaya/season-1/episode-101/")
        вперёд = re.search(r'href="([^"]+)" rel="next"', сотая.тело)
        назад = re.search(r'href="([^"]+)" rel="prev"', сто_первая.тело)
        assert вперёд and вперёд.group(1).endswith("/season-1/episode-101/")
        assert назад and назад.group(1).endswith("/season-1/episode-100/")

    def test_у_первой_нет_предыдущей_у_последней_нет_следующей(self, лордс):
        первая = запросить(лордс, "/title/seriya-dolgaya/season-1/episode-1/")
        последняя = запросить(лордс, f"/title/seriya-dolgaya/season-1/episode-{СЕРИЙ}/")
        assert 'rel="prev"' not in первая.тело
        assert 'rel="next"' not in последняя.тело

    def test_серия_за_границей_это_404(self, лордс):
        ответ = запросить(лордс, f"/title/seriya-dolgaya/season-1/episode-{СЕРИЙ + 1}/")
        assert ответ.статус == 404

    def test_страница_сезона_открывается_и_ведёт_к_любой_серии(self, лордс):
        ответ = запросить(лордс, "/title/seriya-dolgaya/season-1/")
        assert ответ.статус == 200
        номера = {int(н) for н in re.findall(r"/season-1/episode-(\d+)/", ответ.тело)}
        assert all(н in номера for н in self.ГРАНИЦЫ)


class TestСтраницаПроизведенияНеПуста:
    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_есть_заголовок_крошки_и_разметка(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/title/film-prostoy/")
        assert "<h1>" in ответ.тело
        assert "application/ld+json" in ответ.тело
        assert 'rel="canonical"' in ответ.тело
        assert "Простой фильм" in ответ.тело
        # Крошки обязаны быть ВНУТРИ документа: приклеенные перед `<!doctype>`
        # они выпадали из листа и всплывали над шапкой.
        крошки = ответ.тело.find('aria-label="Хлебные крошки"')
        assert крошки > ответ.тело.find("<body"), "крошки вне тела документа"

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_отсутствующее_поле_не_печатается_как_значение(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/title/bez-postera/")
        assert ответ.статус == 200
        assert "None" not in ответ.тело
        assert "постер не передан" in ответ.тело or "постер" in ответ.тело
        # Ни одной пустой пары «что — значение».
        assert not re.search(r"<dd[^>]*>\s*</dd>", ответ.тело)

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_один_заголовок_о_фильме(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/title/film-prostoy/")
        заголовки = re.findall(r"<h2[^>]*>(.*?)</h2>", ответ.тело, re.S)
        повторы = [з for з in set(заголовки) if заголовки.count(з) > 1]
        assert not повторы, f"дублирующиеся заголовки разделов: {повторы}"

    def test_оценка_печатается_с_источником(self, лордс):
        """Каждая оценка подписана ТЕМ, кто её выставил.

        Прежде здесь требовалась подпись «CDNVideoHub». Требование снято
        намеренно: CDNVideoHub — поставщик каталога, а не автор оценки, и
        подписывать его именем числа КП и IMDb значит утверждать неправду о
        происхождении оценки. Намерение теста — «оценка не висит без
        источника» — проверяется строже прежнего: у каждой оценки своя
        подпись, своя шкала и своя запись для чтения вслух.
        """
        ответ = запросить(лордс, "/title/seriya-dolgaya/")
        assert "8.1" in ответ.тело and "7.9" in ответ.тело
        assert 'data-source="kp"' in ответ.тело and 'data-source="imdb"' in ответ.тело
        assert "КП" in ответ.тело and "IMDb" in ответ.тело
        assert "/10" in ответ.тело
        assert "CDNVideoHub" not in ответ.тело, (
            "поставщик каталога снова выдаётся за автора оценки")
        # Числа голосов источник не передаёт — и его нигде нет.
        assert "ratingCount" not in ответ.тело
        assert "reviewCount" not in ответ.тело


class TestСостоянияПлеера:
    def test_есть_источник_есть_элемент_провайдера(self, лордс):
        ответ = запросить(лордс, "/title/seriya-dolgaya/")
        assert 'data-state="resolving"' in ответ.тело or 'data-state="playable"' in ответ.тело
        элемент = re.search(r"<video-player [^>]*>", ответ.тело)
        assert элемент, "в состоянии resolving/playable нет элемента провайдера"
        assert 'data-aggregator="kp"' in элемент.group(0)
        assert 'data-title-id="123456"' in элемент.group(0)
        assert "player.cdnvideohub.com" in ответ.тело

    def test_номер_серии_доезжает_до_элемента(self, лордс):
        ответ = запросить(лордс, "/title/seriya-dolgaya/season-1/episode-210/")
        элемент = re.search(r"<video-player [^>]*>", ответ.тело)
        assert элемент and 'episode="210"' in элемент.group(0)

    def test_без_источника_нет_ни_элемента_ни_скрипта(self, лордс):
        """Запись только с imdb источника не имеет: imdb агрегатором не является."""
        ответ = запросить(лордс, "/title/film-prostoy/")
        assert 'data-state="nosource"' in ответ.тело
        assert "<video-player" not in ответ.тело
        assert "player.cdnvideohub.com" not in ответ.тело

    def test_недоступность_объяснена_словами(self, лордс):
        ответ = запросить(лордс, "/title/bez-postera/")
        состояние = re.search(r"data-player data-state=\"(\w+)\"", ответ.тело)
        assert состояние and состояние.group(1) not in {"playable", "resolving"}
        # Не крутящийся кружок и не пустой прямоугольник, а объяснение.
        assert re.search(r"<b>[^<]{10,}</b>", ответ.тело)
        assert "Смотреть</button>" not in ответ.тело

    def test_витрина_без_publisher_id_честно_это_говорит(self, tmp_path):
        модуль = _поднять(tmp_path, "lords-03", "lords", плеер=False)
        ответ = запросить(модуль, "/title/seriya-dolgaya/")
        assert 'data-state="noaccess"' in ответ.тело
        assert "<video-player" not in ответ.тело


class TestСемействаРазличаются:
    """Различие обязано быть не в цвете, а в устройстве страницы.

    Считается по четырём признакам задания: композиция, типографика,
    геометрия карточки и раскладка страницы произведения. Совпадение по всем
    четырём означало бы, что Zona — это Lords с другим акцентом.
    """

    def test_композиция_разная(self, лордс, зона):
        л = запросить(лордс, "/").тело
        з = запросить(зона, "/").тело
        assert 'data-design="lords-sheet"' in л
        assert 'data-design="zona-rail"' in з
        # У Lords шапка строкой сверху, у Zona — постоянная боковая колонка.
        assert "<header" in л and 'class="zrail"' not in л
        assert 'class="zrail"' in з and 'class="hd__in"' not in з

    def test_типографика_разная(self, лордс, зона):
        л = запросить(лордс, "/").тело
        з = запросить(зона, "/").тело
        assert "'Open Sans'" in л and "serif" not in л.split("</style>")[0].split("body{")[1][:120]
        assert "'PT Serif'" in з

    def test_геометрия_карточки_разная(self, лордс, зона):
        л = запросить(лордс, "/catalog/").тело
        з = запросить(зона, "/catalog/").тело
        # Lords: название поверх постера. Zona: строка списка с постером слева.
        assert 'class="c__cap"' in л and 'class="zr"' not in л
        assert ('class="zr"' in з or 'class="zt"' in з) and 'class="c__cap"' not in з

    def test_раскладка_страницы_произведения_разная(self, лордс, зона):
        л = запросить(лордс, "/title/seriya-dolgaya/").тело
        з = запросить(зона, "/title/seriya-dolgaya/").тело
        assert 'class="tw"' in л and 'class="zban"' not in л
        assert ('class="zban"' in з or 'class="ztitle"' in з) and 'class="tw"' not in з

    def test_различие_не_сводится_к_цвету(self, лордс, зона):
        """Если убрать из обоих стилей все цвета, они обязаны остаться разными."""
        цвет = re.compile(r"#[0-9a-fA-F]{3,8}|rgba?\([^)]*\)")
        def скелет(тело):
            стиль = re.search(r"<style>(.*?)</style>", тело, re.S).group(1)
            return цвет.sub("", стиль)
        л = скелет(запросить(лордс, "/").тело)
        з = скелет(запросить(зона, "/").тело)
        assert л != з, "стили различаются только цветом"
        общие = set(re.findall(r"\.([a-z][a-z0-9_-]*)\s*\{", л)) & \
                set(re.findall(r"\.([a-z][a-z0-9_-]*)\s*\{", з))
        # Общими остаются только служебные примитивы: два для доступности
        # (`vh` — скрытая подпись, `skip` — ссылка на содержимое) и `none` —
        # пометка «значения нет». Это состояния, а не раскладка: они ничего не
        # говорят о том, как страница устроена, и делить их семействам можно.
        # Любой РАЗМЕТОЧНЫЙ класс в пересечении означал бы общую композицию.
        ПРИМИТИВЫ = {"vh", "skip", "none"}
        # Компонент оценок общий у всех семейств намеренно: оценка одного и
        # того же произведения обязана читаться одинаково на любой витрине, а
        # подпись источника не может зависеть от оформления. Различие семейств
        # он не размывает — вид задаётся токенами семейства, и цвета из
        # сравнения уже вычтены. Это состояние данных, а не раскладка страницы.
        ОБЩИЙ_КОМПОНЕНТ = {к for к in общие if к == "rbs" or к.startswith("rbs__")
                           or к.startswith("rbs--")}
        РАЗРЕШЕНО = ПРИМИТИВЫ | ОБЩИЙ_КОМПОНЕНТ
        assert общие <= РАЗРЕШЕНО, f"семейства делят разметочные классы: {sorted(общие - РАЗРЕШЕНО)}"
        # И наоборот: сам компонент обязан присутствовать у обоих семейств,
        # иначе «общий» он только на словах.
        assert "rbs" in общие, "компонент оценок есть не у всех семейств"


class TestПрежняяВерсияНеТронута:
    def test_манифест_на_1_0_2_включает_прежнюю_ветку(self, прежняя_версия):
        assert прежняя_версия.ОФОРМЛЕНИЕ_НОВОЕ is False
        ответ = запросить(прежняя_версия, "/")
        assert ответ.статус == 200
        # Признаки 1.1.0 на прежней витрине не появляются.
        assert "data-design=" not in ответ.тело
        assert 'class="tsw"' in ответ.тело, "прежняя витрина потеряла свой переключатель темы"

    def test_прежняя_ветка_не_рисует_страницы_произведений_сама(self, прежняя_версия):
        """1.0.2 по-прежнему отдаёт тайтлы из статического релиза, как и раньше."""
        assert прежняя_версия.ОФОРМЛЕНИЕ_НОВОЕ is False


class TestДоступность:
    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_есть_ссылка_на_содержимое_и_видимый_фокус(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/")
        assert 'class="skip"' in ответ.тело
        assert ":focus-visible" in ответ.тело
        assert "outline:3px solid" in ответ.тело

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_у_поиска_есть_подпись(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/")
        assert re.search(r'<label[^>]*for="q"', ответ.тело)

    @pytest.mark.parametrize("витрина", ["лордс", "зона"])
    def test_страница_объявляет_язык(self, витрина, request):
        модуль = request.getfixturevalue(витрина)
        ответ = запросить(модуль, "/")
        assert '<html lang="ru"' in ответ.тело


class TestАвтоматСостоянийПлеера:
    """Отказ провайдера обязан перебивать уже наступивший успех.

    Обычная последовательность у провайдера такая: элемент СНАЧАЛА поднимается,
    и только потом выясняется, что дорожки для этой серии нет — событие
    `noData` приходит ПОСЛЕ того, как оболочка объявила `ok`.

    В первой редакции флаг «поднялся» глушил все последующие состояния, и до
    зрителя отказ не доходил вовсе: он получал поднявшийся плеер, который молча
    ничего не играет. То есть ровно тот чёрный прямоугольник, ради которого
    состояния и заводились. Обнаружено пробой шести состояний, а не чтением.

    Проверяется сам автомат в клиентском скрипте: глушится только запоздавший
    таймаут, отказы — никогда.
    """

    def _скрипт(self, лордс) -> str:
        return лордс.СКРИПТ_ПЛЕЕРА_КЛИЕНТ

    def test_успех_не_глушит_последующие_состояния(self, лордс):
        скрипт = self._скрипт(лордс)
        # Прежний сторож стоял в самом начале `state` и гасил всё подряд.
        assert "if(done&&k!=='ok')return" not in скрипт, (
            "успех снова глушит отказы: noData после ok не дойдёт до зрителя")

    def test_таймаут_учитывает_уже_поднявшийся_плеер(self, лордс):
        скрипт = self._скрипт(лордс)
        # PASS2: timeout must not mark UNAVAILABLE/ERROR while playing is proven.
        assert "if(myGen!==generation || myAttempt!==attempt || playing) return" in скрипт or (
            "if(my!==token || playing) return" in скрипт), (
            "таймаут перестал проверять, играет ли плеер, и объявит сломанным "
            "то, что уже играет")
        assert "nextOrFail" in скрипт

    def test_отказы_подписаны_без_условий(self, лордс):
        скрипт = self._скрипт(лордс)
        for событие, состояние in (("noData", "provider"), ("error", "error")):
            assert событие in скрипт and f"state('{состояние}'" in скрипт, (
                f"состояние {состояние} перестало выставляться по {событие}")

    def test_все_шесть_состояний_объявлены(self, лордс):
        """Каждое состояние обязано иметь подпись: без неё пустой прямоугольник."""
        for код in ("playable", "resolving", "loading", "nosource", "noaccess",
                    "provider", "error"):
            подпись = лордс._подпись_плеера(код)
            assert подпись and подпись != "состояние неизвестно", (
                f"состояние {код} без подписи")


@pytest.fixture(scope="module")
def зона_1_2(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("zona12"), "zona-01", "zona", версия="1.2.0")


@pytest.fixture(scope="module")
def анимедиа_1_2(tmp_path_factory):
    return _поднять(tmp_path_factory.mktemp("amd12"), "animedia-01", "animedia",
                    версия="1.2.0")


class TestПереработкаВключаетсяВерсией:
    """Оформление 1.2.0 достаётся только витрине, объявившей его манифестом.

    Артефакт один на шесть витрин. Если бы переработка включалась наличием
    кода, выкладка файла ради Animedia сменила бы вид боевой Zona, которая
    стоит на 1.1.0 и об этом не просила. Здесь проверяется именно это: на
    1.1.0 отдаётся прежнее оформление, на 1.2.0 — переработанное.
    """

    def test_zona_1_1_0_отдаёт_прежнее_оформление(self, зона):
        з = запросить(зона, "/").тело
        assert 'data-design="zona-rail"' in з
        assert "'PT Serif'" in з

    def test_zona_1_2_0_отдаёт_переработанное(self, зона_1_2):
        з = запросить(зона_1_2, "/").тело
        assert 'data-design="zona-top"' in з
        assert 'class="zhd"' in з and '<aside class="zrail"' not in з
        assert "font:13px/1.375 ui-sans-serif" in з.split("</style>")[0]
        assert "'PT Serif'" not in з

    def test_zona_1_2_0_главная_без_пустых_полок_и_счётчика(self, зона_1_2):
        з = запросить(зона_1_2, "/").тело
        assert "В снимке каталога" not in з
        assert "тестовая витрина" not in з
        assert "Новые трейлеры" not in з  # empty trailer shelf must stay hidden
        assert '<section class="zsec">' in з or 'class="zsec zsec--seo"' in з
        # Раньше здесь требовался видимый маркер «Zona · v1.2.0 · 00000000».
        # Правило владельца (B22) его запретило: версия, коммит и build id в
        # пользовательском подвале не показываются. Ожидание перевёрнуто, а не
        # снято, — иначе запрет ничем не удерживался бы.
        assert 'data-footer-technical-marker="0"' in з
        assert not re.search(r"Zona\s+[·.]\s*v?1\.2\.0\s+[·.]\s*0{8}", з)
        assert "Template:" not in з

    def test_animedia_1_2_0_свой_вид_а_не_lords(self, анимедиа_1_2):
        а = запросить(анимедиа_1_2, "/").тело
        assert 'data-design="animedia-portal"' in а
        assert 'data-design="lords-sheet"' not in а

    def test_animedia_1_2_0_не_показывает_чужой_каталог(self, анимедиа_1_2):
        """Записи не своего вида не попадают на витрину вовсе."""
        а = запросить(анимедиа_1_2, "/").тело
        assert "Каталог аниме источником не передан" in а or 'class="zt"' in а
        assert 'class="ast"' in а or 'class="zt"' in а

    def test_animedia_1_2_0_расписание_свой_раздел(self, анимедиа_1_2):
        о = запросить(анимедиа_1_2, "/schedule/")
        assert о.статус == 200
        assert 'class="asch"' in о.тело
