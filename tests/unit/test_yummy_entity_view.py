"""Готовность шаблона Yummy принять контентный контракт.

Проверяется не «файл существует», а поведение компонентов на данных того
контура, который придёт: полная карточка, рекомендации, внутренняя оценка и
шесть независимых лент рисуются на фикстуре целиком, а на пустом контракте
исчезают, не оставляя ни подписей, ни нулей, ни пустых рамок.

Живых данных для этих поверхностей сегодня нет — их готовит Архитектор.
Именно поэтому фикстура обязательна: иначе «компонент готов» осталось бы
утверждением без единого прогона.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ХОСТ = КОРЕНЬ / "automation" / "host"
sys.path.insert(0, str(КОРЕНЬ / "tests" / "fixtures" / "yummy"))

import contract_fixture as ФИКСТУРА  # noqa: E402


def _модуль(имя: str):
    if имя in sys.modules and hasattr(sys.modules[имя], "__file__"):
        return sys.modules[имя]
    путь = ХОСТ / f"{имя}.py"
    спец = importlib.util.spec_from_loader(
        имя, importlib.machinery.SourceFileLoader(имя, str(путь)))
    м = importlib.util.module_from_spec(спец)
    sys.modules[имя] = м
    спец.loader.exec_module(м)
    return м


СТРАНИЦЫ = _модуль("yummy_pages")
ВИД = _модуль("yummy_entity")
СВЯЗЬ = _модуль("yummy_contract")

ХВОСТ_UUID = re.compile(
    r"--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
ПОЛНЫЕ_КАППЫ = {"personal_rating": True}


@pytest.fixture()
def база():
    соед = ФИКСТУРА.база()
    yield соед
    соед.close()


@pytest.fixture()
def полная(база):
    return СВЯЗЬ.сущность(база, entity_id=ФИКСТУРА.ГЛАВНЫЙ)


class TestСовместимость:
    """Контракт принимается осознанно, а не по факту наличия таблиц."""

    @pytest.mark.parametrize("к", ["yummy-read-model/1.0.0", "yummy-read-model/1.1.0",
                                   "yummy-read-model/1.9.3"])
    def test_мажор_1_принимается(self, к):
        assert ВИД.совместим(к)

    @pytest.mark.parametrize("к", ["yummy-read-model/2.0.0", "other/1.0.0", "", None,
                                   "yummy-read-model"])
    def test_чужое_отвергается(self, к):
        assert not ВИД.совместим(к)

    def test_версия_контура_читается_а_не_угадывается(self, база):
        assert СВЯЗЬ.версия_контракта(база) == "yummy-read-model/1.1.0"

    def test_без_объявления_базовая_версия(self):
        соед = sqlite3.connect(":memory:")
        соед.executescript("CREATE TABLE entity (entity_id TEXT)")
        assert СВЯЗЬ.версия_контракта(соед) == "yummy-read-model/1.0.0"


class TestПолнаяКарточка:
    """Все объявленные владельцем поля выводятся, когда контур их отдаёт."""

    ОЖИДАЕМЫЕ = {
        "оригинальное название": "Fixture: Complete Entity",
        "альтернативные": "フィクスチャ",
        "описание": "Синтетическое описание",
        "тип": "Сериал",
        "статус": "Выходит",
        "год": "2024",
        "даты показа": "2025-04-05",
        "страна": "Япония",
        "студия": "Fixture Studio",
        "жанры": "фантастика",
        "режиссёр": "Фикстура Режиссёров",
        "актёры": "Фикстура Актёрова",
        "возраст": "16+",
        "длительность": "24 мин",
        "сезоны": "Сезонов",
        "серии": "8 из 24",
        "озвучки": "Fixture Dub Two",
    }

    def test_поля_выводятся(self, полная):
        разметка = ВИД.карточка_тайтла(полная, ПОЛНЫЕ_КАППЫ)
        нет = [имя for имя, кусок in self.ОЖИДАЕМЫЕ.items() if кусок not in разметка]
        assert not нет, f"полная карточка не показывает: {нет}"

    def test_постер_и_фон(self, полная):
        разметка = ВИД.карточка_тайтла(полная, ПОЛНЫЕ_КАППЫ)
        assert "/poster/fixture-0001.webp" in разметка
        assert "/backdrop/fixture-0001.webp" in разметка

    def test_отсутствующее_поле_скрывается_поодиночке(self, база):
        """Убрали студию — исчезла только она, соседние строки на месте."""
        база.execute("DELETE FROM entity_studio")
        база.commit()
        разметка = ВИД.карточка_тайтла(
            СВЯЗЬ.сущность(база, entity_id=ФИКСТУРА.ГЛАВНЫЙ), ПОЛНЫЕ_КАППЫ)
        assert "Студия" not in разметка
        assert "Япония" in разметка and "фантастика" in разметка

    def test_ни_пустых_подписей_ни_нулей(self, база):
        """Голая сущность: только название — и ни одной подписи без значения."""
        база.executescript(
            "DELETE FROM external_rating; DELETE FROM entity_genre;"
            "DELETE FROM entity_studio; DELETE FROM entity_country;"
            "DELETE FROM entity_dub; DELETE FROM entity_person;"
            "DELETE FROM entity_title; DELETE FROM recommendation;")
        база.execute(
            "UPDATE entity SET description=NULL, backdrop_path=NULL, age_rating=NULL,"
            " duration_minutes=NULL, seasons=0, episodes_total=0, episodes_released=0,"
            " aired_from=NULL, aired_to=NULL, year=NULL, airing_status='UNCONFIRMED',"
            " title_original=NULL, kind='UNKNOWN' WHERE entity_id=?",
            (ФИКСТУРА.ГЛАВНЫЙ,))
        база.commit()
        разметка = ВИД.карточка_тайтла(
            СВЯЗЬ.сущность(база, entity_id=ФИКСТУРА.ГЛАВНЫЙ), ПОЛНЫЕ_КАППЫ)
        for подпись in ("Студия", "Жанры", "Серий", "Сезонов", "Возраст",
                        "Длительность", "Страна", "Озвучки", "Статус", "Год"):
            assert подпись not in разметка, f"подпись «{подпись}» без значения"
        assert ">0<" not in разметка and ">0.0<" not in разметка

    def test_нечего_показать_нет_блока(self):
        assert ВИД.карточка_тайтла({}) == ""
        assert ВИД.карточка_тайтла({"entity_id": "x"}) == ""

    def test_канонический_адрес_без_uuid(self, база):
        база.execute(
            "UPDATE entity SET canonical_path=? WHERE entity_id=?",
            ("/anime/fixture-0001--0192f0aa-1111-2222-3333-444455556666",
             ФИКСТУРА.ГЛАВНЫЙ))
        база.commit()
        разметка = ВИД.карточка_тайтла(
            СВЯЗЬ.сущность(база, entity_id=ФИКСТУРА.ГЛАВНЫЙ), ПОЛНЫЕ_КАППЫ)
        assert not ХВОСТ_UUID.search(разметка)
        assert 'data-canonical="/anime/fixture-0001"' in разметка


class TestРейтинги:
    """Провайдеры не сводятся в одно число и подписаны каждый своим именем."""

    def test_каждый_провайдер_подписан(self, полная):
        разметка = ВИД.рейтинги(полная["ratings"])
        for имя in ("IMDb", "Кинопоиск", "Shikimori", "AniList"):
            assert имя in разметка
        assert "8.2" in разметка and "/10" in разметка

    def test_чужая_шкала_не_приводится_к_десятке(self, полная):
        """AniList отдаёт 84 из 100 — и показывается именно так."""
        разметка = ВИД.рейтинги(полная["ratings"])
        assert "84.0<small>/100" in разметка

    def test_голоса_показаны_где_есть_и_молчат_где_нет(self, полная):
        разметка = ВИД.рейтинги(полная["ratings"])
        assert "15 321" in разметка
        # У Shikimori голосов нет: ноль вместо них не печатается.
        шикимори = разметка[разметка.index("Shikimori"):]
        кусок = шикимори[:шикимори.index("</li>")]
        assert "sf-rt__v" not in кусок

    def test_absent_не_показывается(self, полная):
        assert "Kitsu" not in ВИД.рейтинги(полная["ratings"])

    def test_пусто_значит_нет_блока(self):
        assert ВИД.рейтинги([]) == ""
        assert ВИД.рейтинги([{"provider": "imdb", "value": None, "scale": 10}]) == ""


class TestРекомендации:
    """Только `recommendations[]` контракта; подбор на месте запрещён."""

    def test_шесть_карточек_рисуются(self, полная):
        разметка = ВИД.рекомендации(полная["recommendations"])
        assert разметка.count('class="sf-rc"') == ВИД.МИНИМУМ_РЕКОМЕНДАЦИЙ == 6

    def test_поля_карточки_рекомендации(self, полная):
        разметка = ВИД.рекомендации(полная["recommendations"])
        assert "/anime/fixture-rec-1" in разметка          # canonical_path
        assert "/poster/fixture-rec-1.webp" in разметка    # poster
        assert "Фикстура рекомендация 1" in разметка       # title
        assert "2021" in разметка and "Фильм" in разметка  # year/type
        assert "IMDb" in разметка                          # provider-labelled rating
        assert "совпадение по жанру и студии" in разметка  # reason
        assert "fixture" in разметка                       # source

    def test_пустой_массив_скрывает_секцию(self):
        assert ВИД.рекомендации([]) == ""
        assert "Похожее" not in ВИД.карточка_тайтла(
            {"entity_id": "x", "title": "Т", "recommendations": []})

    def test_без_канонического_адреса_не_публикуется(self):
        assert ВИД.рекомендации([{"entity_id": "x", "title": "Т",
                                  "canonical_path": ""}]) == ""

    def test_шаблон_не_подбирает_сам(self, база):
        """Связей нет — секции нет, хотя каталог полон похожих записей."""
        база.execute("DELETE FROM recommendation")
        база.commit()
        с = СВЯЗЬ.сущность(база, entity_id=ФИКСТУРА.ГЛАВНЫЙ)
        assert с["recommendations"] == []
        assert "Похожее" not in ВИД.карточка_тайтла(с, ПОЛНЫЕ_КАППЫ)


class TestЛичнаяОценка:
    """Компонент за флагом; сохранение не имитируется."""

    def test_без_флага_компонента_нет(self, полная):
        assert ВИД.личная_оценка({"state": "нет"}, {}) == ""
        assert "sf-pr" not in ВИД.карточка_тайтла(полная, {})

    @pytest.mark.parametrize("вид", list(ВИД.СОСТОЯНИЯ_ОЦЕНКИ))
    def test_каждое_состояние_рисуется(self, вид):
        разметка = ВИД.личная_оценка(
            {"state": вид, "value": 8, "scale": 10, "votes": 1200, "average": 7.6},
            ПОЛНЫЕ_КАППЫ)
        assert разметка and f'data-state="{вид}"' in разметка

    def test_шкала_и_голоса(self):
        разметка = ВИД.личная_оценка(
            {"state": "нет", "scale": 10, "votes": 1200, "average": 7.6}, ПОЛНЫЕ_КАППЫ)
        assert разметка.count('class="sf-pr__b"') == 10
        assert "1 200" in разметка and "7.6" in разметка

    def test_выбранная_оценка_отмечена(self):
        разметка = ВИД.личная_оценка({"state": "оценено", "value": 8}, ПОЛНЫЕ_КАППЫ)
        assert 'value="8" aria-pressed="true"' in разметка
        assert "Убрать оценку" in разметка

    def test_ошибка_и_недоступность_говорят_о_несохранении(self):
        ош = ВИД.личная_оценка({"state": "ошибка"}, ПОЛНЫЕ_КАППЫ)
        assert 'role="alert"' in ош and "не сохранена" in ош
        нед = ВИД.личная_оценка({"state": "недоступен"}, ПОЛНЫЕ_КАППЫ)
        assert "Сохранение не выполнялось" in нед
        assert "sf-pr__b" not in нед, "недоступный backend не даёт кликать по шкале"

    def test_сохранение_не_имитируется(self):
        """В разметке компонента нет ни хранилища, ни «сохранено» без API.

        Проверяется выдача, а не текст модуля: слово в комментарии ничего не
        сохраняет, а вот скрипт в разметке — сохраняет.
        """
        для_всех = "".join(
            ВИД.личная_оценка({"state": в, "value": 8}, ПОЛНЫЕ_КАППЫ)
            for в in ВИД.СОСТОЯНИЯ_ОЦЕНКИ)
        for запрет in ("localStorage", "sessionStorage", "document.cookie",
                       "<script", "Сохранено", "сохранено"):
            assert запрет not in для_всех, f"компонент имитирует сохранение: {запрет}"

    def test_без_api_состояние_недоступен(self):
        соед = sqlite3.connect(":memory:")
        соед.executescript("CREATE TABLE entity (entity_id TEXT)")
        assert СВЯЗЬ.личная(соед, "x")["state"] == "недоступен"

    def test_ноль_голосов_не_печатается(self, база):
        состояние = СВЯЗЬ.личная(база, ФИКСТУРА.ГЛАВНЫЙ)
        assert "votes" not in состояние and "average" not in состояние
        разметка = ВИД.личная_оценка(состояние, ПОЛНЫЕ_КАППЫ)
        assert "sf-pr__sum" not in разметка


class TestЛенты:
    """Шесть поверхностей, шесть источников, ноль общих сущностей."""

    ВСЕ = ("new_episodes", "ongoing", "trending", "news", "announcements", "schedule")

    def test_объявлены_все_шесть(self):
        assert set(ВИД.ПОВЕРХНОСТИ) == set(self.ВСЕ)

    #: Время фиксируется: раздел «Расписание» показывает будущее, и тест,
    #: зависящий от календаря, однажды позеленеет или покраснеет сам по себе.
    СЕЙЧАС = "2026-09-10T12:00:00+00:00"

    def test_каждая_наполняется_своим_запросом(self, база):
        свод = СВЯЗЬ.ленты(база, сейчас=self.СЕЙЧАС)
        assert len(свод["new_episodes"]) == 4
        assert len(свод["ongoing"]) == 4
        assert len(свод["schedule"]) == 4
        assert len(свод["news"]) == 3
        assert len(свод["announcements"]) == 2

    def test_ни_одна_секция_не_повторяет_другую(self, база):
        """Общий каталог под разными заголовками обязан падать здесь."""
        свод = СВЯЗЬ.ленты(база, сейчас=self.СЕЙЧАС)
        assert ВИД.совпадения(свод) == []

    def test_детектор_ловит_нарезку_одного_массива(self, база):
        """Обратная проверка: если подсунуть один массив дважды — падает."""
        один = СВЯЗЬ.новые_серии(база)
        совпало = ВИД.совпадения({"new_episodes": один, "trending": один})
        assert совпало and совпало[0][2] == 1.0

    def test_пустой_массив_убирает_секцию_целиком(self):
        for п in self.ВСЕ:
            разметка = ВИД.лента(п, [])
            assert разметка == "", f"поверхность {п} оставила разметку при пустом массиве"
            имя = ВИД.ПОВЕРХНОСТИ[п][0]
            assert имя not in разметка

    def test_наполненная_секция_рисуется(self, база):
        свод = СВЯЗЬ.ленты(база, сейчас=self.СЕЙЧАС)
        разметка = ВИД.лента("new_episodes", свод["new_episodes"])
        assert 'data-surface="new_episodes"' in разметка
        assert "Новые серии" in разметка
        assert разметка.count('class="sf-rc"') == 4
        assert "Сезон 1, серия 1" in разметка

    def test_онгоинг_только_подтверждённый(self, база):
        """Догадка «серий меньше заявленного» онгоингом не считается."""
        база.execute("UPDATE entity SET airing_status='UNCONFIRMED'")
        база.commit()
        assert СВЯЗЬ.сейчас_выходит(база) == []

    def test_расписание_не_показывает_прошлое(self, база):
        assert СВЯЗЬ.расписание(база, сейчас="2026-12-01T00:00:00+00:00") == []

    def test_протухшая_новость_скрыта_но_не_удалена(self, база):
        поздно = "2026-09-20T00:00:00+00:00"
        assert СВЯЗЬ.посты(база, "news", сейчас=поздно) == []
        осталось = база.execute(
            "SELECT COUNT(*) FROM editorial_post WHERE type='news'").fetchone()[0]
        assert осталось == 3

    def test_черновик_не_публикуется(self, база):
        база.execute("UPDATE editorial_post SET status='draft'")
        база.commit()
        assert СВЯЗЬ.посты(база, "news") == []

    def test_пост_без_адреса_не_рисуется(self):
        assert ВИД.пост({"title": "Т", "canonical_path": None}) == ""

    def test_пост_рисуется_с_источником_и_датой(self, база):
        разметка = ВИД.пост(СВЯЗЬ.посты(база, "news")[0])
        assert "fixture" in разметка and "2026-09-10" in разметка


class TestРежимДополнения:
    """Витрина рисует карточку сама — представление её не удваивает."""

    def test_поля_витрины_не_дублируются(self, полная):
        разметка = ВИД.карточка_тайтла(
            полная, ПОЛНЫЕ_КАППЫ,
            пропустить=ВИД.РИСУЕТ_ВИТРИНА + ("poster", "title", "description",
                                             "ratings"))
        # Сверяется тело карточки. Рекомендации — отдельная секция, и оценка
        # провайдера в них обязана быть: это требование к рекомендациям, а не
        # дубль карточки.
        тело = разметка.split('<section class="sf-recs"')[0]
        for кусок in ("Fixture Studio", "фантастика", "Япония", "16+", "24 мин",
                      "Fixture Dub Two", "IMDb", "Синтетическое описание"):
            assert кусок not in тело, f"дубль поля витрины: {кусок}"

    def test_недостающее_витрине_остаётся(self, полная):
        разметка = ВИД.карточка_тайтла(
            полная, ПОЛНЫЕ_КАППЫ,
            пропустить=ВИД.РИСУЕТ_ВИТРИНА + ("poster", "title", "description",
                                             "ratings"))
        assert "Сезонов" in разметка          # витрина сезоны не показывает
        assert "sf-recs" in разметка          # рекомендаций у неё нет
        assert "sf-pr" in разметка            # внутренней оценки тоже

    def test_нечего_дополнить_нет_блока(self, полная):
        """Всё, что есть, уже нарисовано витриной — блок не появляется."""
        голая = dict(полная, seasons=None, backdrop=None, recommendations=[],
                     personal={})
        разметка = ВИД.карточка_тайтла(
            голая, {}, пропустить=ВИД.РИСУЕТ_ВИТРИНА + (
                "poster", "title", "description", "ratings"))
        assert разметка == ""


class TestВарианты:
    """Три домена различаются не только цветом."""

    @pytest.fixture(scope="class")
    def варианты(self):
        return _модуль("yummy_variants").ВАРИАНТЫ

    def test_три_профиля(self, варианты):
        assert set(варианты) == {"yummyani.biz", "yummyani.org", "yummyani.site"}

    @pytest.mark.parametrize("поле", ["h1", "лид", "title", "description",
                                       "плотность", "первый_экран"])
    def test_поле_уникально_у_каждого(self, варианты, поле):
        значения = [в[поле] for в in варианты.values()]
        assert len(set(значения)) == 3, f"«{поле}» совпадает у разных доменов"

    def test_приоритет_навигации_различен(self, варианты):
        первые = [в["нав_порядок"][0] for в in варианты.values()]
        assert len(set(первые)) == 3

    def test_порядок_поверхностей_различен(self, варианты):
        порядки = [tuple(в["поверхности"]) for в in варианты.values()]
        assert len(set(порядки)) == 3

    def test_навигация_покрывает_все_маршруты(self, варианты):
        нужные = {"/new/", "/top/", "/collections/", "/schedule/"}
        for домен, в in варианты.items():
            assert set(в["нав_порядок"]) == нужные, домен

    def test_общий_контракт_адресов_один(self, варианты):
        """Различается подача, а не адреса: canonical у всех один."""
        for в in варианты.values():
            assert "canonical" not in в and "домен" not in в


class TestЗаголовокСтраницы:
    """Оболочка берётся у каталога — вместе с его <title>, и это дефект.

    Раздел «Расписание выходов» уходил наружу под заголовком «Каталог с
    редакционной навигацией»: во вкладке одно, в H1 другое. Здесь закрепляется,
    что страница объявляет себя сама.
    """

    ОБОЛОЧКА = {
        "head": ('<head><title>Каталог с редакционной навигацией</title>'
                 '<meta name="description" content="чужое описание">'
                 '<meta property="og:title" content="чужой og"></head>'),
        "header": "<header></header>", "footer": "<footer></footer>"}

    def собрать(self, заголовок="Расписание выходов", лид="Что выходит и что заявлено."):
        return СТРАНИЦЫ.собрать(
            self.ОБОЛОЧКА, заголовок, лид, "",
            вариант={"title": "Новые серии и расписание аниме",
                     "акцент": "#4dd0a0"}).decode("utf-8")

    def test_титул_страницы_а_не_оболочки(self):
        html_ = self.собрать()
        assert "<title>Расписание выходов · YummyAnime</title>" in html_
        assert "Каталог с редакционной навигацией" not in html_

    def test_h1_и_титул_об_одной_странице(self):
        html_ = self.собрать()
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html_, re.S).group(1)
        титул = re.search(r"<title>(.*?)</title>", html_, re.S).group(1)
        assert h1.strip() in титул

    def test_описание_и_og_свои(self):
        html_ = self.собрать()
        assert html_.count('name="description"') == 1
        assert "чужое описание" not in html_ and "чужой og" not in html_
        assert 'og:title" content="Расписание выходов"' in html_
        assert 'og:site_name" content="Новые серии и расписание аниме"' in html_


class TestПервыйЭкран:
    """Композиция первого экрана различает витрины, а не только цвет."""

    def экран(self, домен):
        в = _модуль("yummy_variants").ВАРИАНТЫ[домен]
        return СТРАНИЦЫ.первый_экран(в, активный="/new")

    def test_каталожная_открывается_поиском(self):
        э = self.экран("yummyani.site")
        assert 'action="/search"' in э and 'name="q"' in э
        assert "sf-tabs" in э

    def test_событийная_открывается_рядом_разделов(self):
        э = self.экран("yummyani.org")
        assert "sf-tabs" in э and "sf-find" not in э

    def test_редакционная_открывается_лидом(self):
        assert self.экран("yummyani.biz") == ""

    def test_три_композиции_различны(self):
        экраны = [self.экран(д) for д in
                  ("yummyani.biz", "yummyani.org", "yummyani.site")]
        assert len(set(экраны)) == 3

    def test_ссылки_только_существующих_маршрутов(self):
        for домен in ("yummyani.org", "yummyani.site"):
            адреса = re.findall(r'<a href="([^"]+)"', self.экран(домен))
            assert set(адреса) <= {"/new/", "/top/", "/collections/", "/schedule/"}

    def test_текущий_раздел_отмечен(self):
        assert 'href="/new/" aria-current="page"' in self.экран("yummyani.org")

    def test_порядок_разделов_из_профиля(self):
        первый = {д: re.findall(r'<a href="([^"]+)"', self.экран(д))[0]
                  for д in ("yummyani.org", "yummyani.site")}
        assert первый["yummyani.org"] == "/schedule/"
        assert первый["yummyani.site"] == "/top/"


class TestГраница:
    """Фикстура не должна протечь в рантайм."""

    def test_рантайм_не_знает_про_фикстуру(self):
        for имя in ("yummy_entity.py", "yummy_contract.py", "yummy_pages.py",
                    "yummy-frontend.py", "yummy_variants.py"):
            текст = (ХОСТ / имя).read_text(encoding="utf-8")
            assert "contract_fixture" not in текст
            assert ФИКСТУРА.МЕТКА not in текст
