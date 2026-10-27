"""Главная называет сайт, а не подборку; визитки Animedia измеримы.

Повод измеренный, 27.10, после активации редакционной полки на выложенных
витринах:

* `zonafilm.space` отдавала единственный H1 «Сериалы, которые стоит
  посмотреть», `zonafilm12.site` — «Сериалы на вечер: выбор редакции».
  H1 главной давала панель героя, а с полкой герой не рисуется вовсе. Для
  сравнения `zonafilm.cc`, где полки ещё нет: «Zona — фильмы и сериалы
  онлайн». Главная перестала называть предмет сайта — это признак темы
  страницы, а не оформление.
* в рантайме Animedia `data-block-key` встречался трижды, и два раза — в самом
  скрипте целей: ключ стоял ТОЛЬКО у редакционной полки. Визитки подборок на
  главной и в хабе не измерялись ни показом, ни переходом, хотя эффект
  оценивается именно по показам блоков и переходам из них.

Проверяется разметка, которую отдаёт шаблон, и отказ инструмента на чужом
рантайме. Живой результат проверяется отдельно — `automation/local/home-acceptance.py`.
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import tempfile
import textwrap

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "host" / "apply-home-h1-patch.py"
ЗОНА = (
    КОРЕНЬ / "var" / "site-repos" / "zonafilm-space" / "src" / "lords-frontend.py",
    КОРЕНЬ / "var" / "site-repos" / "zonafilm12-site" / "src" / "lords-frontend.py",
)
АНИМЕДИА = КОРЕНЬ / "var" / "site-repos" / "animedia-icu" / "src" / "animedia-frontend.py"
АНИМЕДИА_SPACE = (КОРЕНЬ / "var" / "site-repos" / "animedia-space" / "src"
                  / "animedia-frontend.py")
АНИМЕГО = tuple(
    КОРЕНЬ / "var" / "site-repos" / р / "src" / "animego-frontend.py"
    for р in ("an1mego-site", "animeg0-site", "an1meg0-site"))
КАНОН = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"


def _методы(путь: pathlib.Path, имя: str) -> list:
    """Все одноимённые методы рантайма — их несколько: у каждой линии свой.

    Имя `главная` объявлено пять раз (база Lords, переработанное оформление
    Lords, Zona, Animedia, обработчик 1.1). Брать первое попавшееся нельзя:
    проверка молчала бы о том методе, который витрина действительно отдаёт.
    """
    текст = путь.read_text(encoding="utf-8")
    строки = текст.splitlines()
    найдено = ["\n".join(строки[у.lineno - 1:у.end_lineno])
               for у in ast.walk(ast.parse(текст))
               if isinstance(у, (ast.FunctionDef, ast.AsyncFunctionDef))
               and у.name == имя]
    assert найдено, f"в {путь} нет метода {имя}"
    return найдено


def _метод(путь: pathlib.Path, имя: str, содержит: str = "") -> str:
    """Один метод: либо единственный, либо тот, в котором есть признак линии."""
    найдено = _методы(путь, имя)
    if содержит:
        найдено = [т for т in найдено if содержит in т]
        assert найдено, f"в {путь} нет метода {имя} с признаком «{содержит}»"
    return найдено[0]


# --- Zona: заголовок первого уровня принадлежит странице, не полке ----------

@pytest.mark.parametrize("путь", ЗОНА, ids=lambda п: п.parts[-3])
def test_полка_не_несёт_h1(путь):
    полка = _метод(путь, "_полка_главной")
    assert "<h1" not in полка, (
        "заголовок полки занимал H1 страницы: главная называлась подборкой")


@pytest.mark.parametrize("путь", ЗОНА, ids=lambda п: п.parts[-3])
def test_подпись_полки_осталась_связана(путь):
    """Опускание до H2 не должно рвать `aria-labelledby`: id сохраняется."""
    полка = _метод(путь, "_полка_главной")
    assert 'aria-labelledby="zr1-h"' in полка
    assert '<h2 id="zr1-h">' in полка


@pytest.mark.parametrize("путь", ЗОНА, ids=lambda п: п.parts[-3])
def test_h1_главной_стоит_первым_и_берёт_поле_настроек(путь):
    главная = _метод(путь, "главная", 'блоки["rail1"]')
    assert 'куски.insert(0, f\'<h1 class="vh">' in главная, (
        "у главной с полкой не осталось заголовка первого уровня")
    # Текст не придумывается в коде страницы: он лежит полем настроек
    # семейства, и строку назвала линия SEO. Литерала в этом месте быть не
    # должно — иначе наименование уедет из её области в механизм.
    место = главная.index("куски.insert(0,")
    вставка = главная[место:место + 220]
    assert 'self.се["h1 главной"]' in вставка, вставка
    assert "Фильмы, сериалы" not in вставка, вставка


@pytest.mark.parametrize("путь", ЗОНА, ids=lambda п: п.parts[-3])
def test_h1_появляется_только_с_полкой(путь):
    """Без полки H1 даёт герой: два заголовка первого уровня — тоже дефект.

    Условие проверяется по дереву, а не по соседним строкам: вставка обязана
    стоять ВНУТРИ ветки `if полка_html`, иначе на витрине без редакционной
    полки на главной оказалось бы два H1 — скрытый и заголовок героя.
    """
    главная = _метод(путь, "главная", 'блоки["rail1"]')
    дерево = ast.parse(textwrap.dedent(главная))
    ветки = [у for у in ast.walk(дерево)
             if isinstance(у, ast.If) and isinstance(у.test, ast.Name)
             and у.test.id == "полка_html"]
    assert ветки, "ветки `if полка_html` в главной нет вовсе"
    внутри = any("куски.insert(0," in ast.unparse(в) for в in ветки)
    assert внутри, "вставка H1 не ограничена наличием полки"


# --- Animedia: визитки подборок измеримы ------------------------------------

def test_визитки_animedia_несут_ключ_блока():
    сетка = _метод(АНИМЕДИА, "_сетка_коллекций")
    assert 'data-block-key="card:{html.escape(к["key"])}"' in сетка, (
        "визитки подборок не измерялись: наблюдателю доставалась одна полка")


def test_ключ_блока_совпадает_с_ключом_подборки():
    """Разбивка берётся из просмотров `/collection/<key>/` — ключи обязаны совпасть."""
    сетка = _метод(АНИМЕДИА, "_сетка_коллекций")
    assert сетка.count('к["key"]') >= 2, сетка
    assert 'data-collection-key="{html.escape(к["key"])}"' in сетка


def test_ключ_в_цель_не_уходит():
    """Ключ остаётся в разметке: третьего аргумента у точки отправки нет."""
    текст = АНИМЕДИА.read_text(encoding="utf-8")
    assert "__sfGoal(name)" in текст or "function __sfGoal" in текст or \
        "window.__sfGoal" in текст
    assert "g('block_click')" in текст


# --- инструмент: отказ, повтор, вердикт -------------------------------------

def _запуск(аргументы: list) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ИНСТРУМЕНТ), *аргументы],
                          capture_output=True, text=True)


@pytest.mark.parametrize("путь", (*ЗОНА, АНИМЕДИА), ids=lambda п: п.parts[-3])
def test_check_зелёный_на_приведённых(путь):
    р = _запуск(["--check", str(путь)])
    assert р.returncode == 0, р.stdout + р.stderr
    assert "ок" in р.stdout


def test_канон_не_этой_линии():
    """Редакционной полки в каноне нет — опускать там нечего, и это не провал."""
    р = _запуск(["--check", str(КАНОН)])
    assert р.returncode == 0, р.stdout + р.stderr
    assert "не этой линии" in р.stdout


def test_повтор_ничего_не_меняет():
    with tempfile.TemporaryDirectory() as каталог:
        копия = pathlib.Path(каталог) / "runtime.py"
        копия.write_text(ЗОНА[0].read_text(encoding="utf-8"), encoding="utf-8")
        до = копия.read_text(encoding="utf-8")
        р = _запуск([str(копия)])
        assert р.returncode == 0, р.stdout + р.stderr
        assert "пропущено (уже стоит)" in р.stdout
        assert копия.read_text(encoding="utf-8") == до


def test_отказ_на_чужом_файле():
    with tempfile.TemporaryDirectory() as каталог:
        чужой = pathlib.Path(каталог) / "runtime.py"
        чужой.write_text("print('ни полки, ни сетки визиток')\n", encoding="utf-8")
        р = _запуск([str(чужой)])
        assert р.returncode != 0
        assert "ОТКАЗ" in (р.stdout + р.stderr)


def test_отказ_когда_якорь_разошёлся():
    """Якорь исчез — инструмент отказывается ДО записи, а не пишет наугад."""
    with tempfile.TemporaryDirectory() as каталог:
        битый = pathlib.Path(каталог) / "runtime.py"
        текст = АНИМЕДИА.read_text(encoding="utf-8")
        текст = текст.replace('data-block-key="card:{html.escape(к["key"])}" ', "")
        текст = текст.replace('f\'href="{html.escape(к["path"])}">\'',
                              'f\'href="{html.escape(к["ПУТЬ"])}">\'')
        битый.write_text(текст, encoding="utf-8")
        до = битый.read_text(encoding="utf-8")
        р = _запуск([str(битый)])
        assert р.returncode != 0, р.stdout
        assert "ОТКАЗ" in (р.stdout + р.stderr)
        assert битый.read_text(encoding="utf-8") == до


# --- строка заголовка: решение линии SEO, проверяемые свойства --------------

@pytest.mark.parametrize("путь", ЗОНА, ids=lambda п: п.parts[-3])
def test_строка_заголовка_названа_и_перечисляет_все_виды(путь):
    """Свойства строки проверяемы, а не стилистичны.

    Линия SEO 27.10 назвала «Фильмы, сериалы и мультфильмы онлайн» и
    обосновала: в каталоге три значения `kind` — Фильм, Сериал, Мультфильм, и
    вариант «фильмы и сериалы» (как на zonafilm.cc) опускал бы третий вид.
    """
    текст = путь.read_text(encoding="utf-8")
    assert '"h1 главной": "Фильмы, сериалы и мультфильмы онлайн",' in текст
    строка = "Фильмы, сериалы и мультфильмы онлайн"
    for вид in ("Фильм", "сериал", "мультфильм"):
        assert вид.lower()[:6] in строка.lower(), вид
    # Ни одного общего слова с заголовком страницы: он собирается как
    # «<имя> — кинопортал», и повтор сделал бы H1 пересказом <title>.
    assert "кинопортал" not in строка.lower()
    assert "Zona" not in строка


@pytest.mark.parametrize("путь", ЗОНА, ids=lambda п: п.parts[-3])
def test_заголовок_главной_не_лид(путь):
    """Лид остаётся на своём месте — его использует герой без слайдов."""
    текст = путь.read_text(encoding="utf-8")
    assert '"лид": "Кинопортал: что смотреть и где это найти",' in текст
    assert текст.count('"h1 главной":') == 1


# --- Animedia: H1 главной не повторяет заголовок страницы ------------------

def test_h1_главной_animedia_берёт_своё_поле():
    """H1 брался из `title_home` — того же значения, что уходит в <title> и в
    подпись SEO-блока. Главная повторяла сама себя побайтно: измерено 27.10 на
    animedia.icu и animedia.space. Поле `h1` в настройках домена при этом
    объявлялось и НЕ использовалось ни разу."""
    главная = _метод(АНИМЕДИА, "главная", 'class="vh"')
    assert 'домен["h1"]' in главная, главная[:400]
    assert 'class="vh">{html.escape(домен["title_home"])}' not in главная


@pytest.mark.parametrize("домен", ("animedia.space", "animedia.icu"))
def test_h1_настроек_домена_не_равен_заголовку(домен):
    """Свойство, а не текст: H1 и <title> не совпадают ни на одной витрине."""
    текст = АНИМЕДИА.read_text(encoding="utf-8")
    import ast as _ast
    дерево = _ast.parse(текст)
    таблица = next(
        у.value for у in _ast.walk(дерево)
        if isinstance(у, _ast.Assign)
        and any(getattr(ц, "id", "") == "АНИМЕДИА_ДОМЕНЫ" for ц in у.targets))
    настройки = {}
    for ключ, значение in zip(таблица.keys, таблица.values):
        if getattr(ключ, "value", None) == домен:
            настройки = {к.value: getattr(з, "value", None)
                         for к, з in zip(значение.keys, значение.values)}
    assert настройки, домен
    assert настройки["h1"], домен
    assert настройки["h1"] != настройки["title_home"], настройки["h1"]
    # Строку назвала линия SEO: разделение каталога по `type` — movie и tv.
    assert настройки["h1"] == "Аниме-сериалы и фильмы онлайн", настройки["h1"]
    # «Дунхуа» в H1 не называется: это один жанр из 55.
    assert "дунхуа" not in настройки["h1"].lower()


def test_заголовок_страницы_animedia_остался_брендовым():
    """`title_home` не трогался: он работает заголовком и подписью SEO-блока."""
    текст = АНИМЕДИА.read_text(encoding="utf-8")
    assert '"title_home": "Animedia ICU — сериалы, фильмы и дунхуа",' in текст
    assert '"title_home": "Animedia Space — новое в каталоге и популярное аниме",' in текст


# --- AnimeGo: заголовок страницы перестал зависеть от календаря ------------

@pytest.mark.parametrize("путь", АНИМЕГО, ids=lambda п: п.parts[-3])
def test_animego_подпись_сезонной_ленты_не_h1(путь):
    """H1 выдавала сезонная лента, и он МЕНЯЛСЯ четыре раза в год: зимой
    страница называлась бы «Аниме зимнего сезона». Класс сохраняется —
    композиция первого экрана не меняется, меняется уровень заголовка."""
    главная = _метод(путь, "главная", "ag-h1")
    assert '<h1 class="ag-h1">' not in главная, главная[:300]
    assert '<h2 class="ag-h1">Аниме {сезон} сезона</h2>' in главная


@pytest.mark.parametrize("путь", АНИМЕГО, ids=lambda п: п.parts[-3])
def test_animego_h1_постоянный_и_первый(путь):
    главная = _метод(путь, "главная", "ag-h1")
    # Заголовок стоит ПЕРВЫМ в содержимом: он открывает сборку тела, а не
    # приписывается после сезонной ленты.
    assert ('тело = (f\'<h1 class="vh">{html.escape(АНИМЕГО_H1_ГЛАВНОЙ)}</h1>\''
            in главная), главная[главная.find("тело = ("):][:200]


@pytest.mark.parametrize("путь", АНИМЕГО, ids=lambda п: п.parts[-3])
def test_animego_строка_заголовка_названа_и_без_чисел(путь):
    """Строку назвала линия SEO по измеренной навигации витрины: онгоинги,
    жанровые фильтры, годы выпуска. Чисел в ней нет сознательно — в навигации
    рядом стоят «ТОП-98» и «ТОП-250», и они расходятся между собой."""
    текст = путь.read_text(encoding="utf-8")
    assert ('АНИМЕГО_H1_ГЛАВНОЙ = "Каталог аниме: онгоинги, жанры и годы выпуска"'
            in текст)
    строка = "Каталог аниме: онгоинги, жанры и годы выпуска"
    assert not any(с.isdigit() for с in строка), строка
    # Заголовок страницы собирается как «<имя> — аниме онлайн»: повторяется
    # только «аниме», и для аниме-витрины это предмет, а не дублирование.
    assert "онлайн" not in строка.lower()
    # Сезон в постоянную строку попасть не может.
    for сезон in ("зимн", "весен", "летн", "осен"):
        assert сезон not in строка.lower(), сезон


def test_animego_отличима_от_animedia():
    """Рантайм AnimeGo унаследовал таблицу настроек Animedia целиком; по одному
    этому признаку он был бы принят за неё, и правка тронула бы код, который
    эта витрина на главной не отдаёт."""
    import importlib.util
    спец = importlib.util.spec_from_file_location("инструмент", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    for путь in АНИМЕГО:
        имя, _ = м.линия(путь.read_text(encoding="utf-8"))
        assert имя == "animego", (путь, имя)
    имя, _ = м.линия(АНИМЕДИА.read_text(encoding="utf-8"))
    assert имя == "animedia", имя
    # И наоборот: таблица Animedia в рантайме AnimeGo есть, значит различение
    # держится не на её отсутствии.
    assert "АНИМЕДИА_ДОМЕНЫ" in АНИМЕГО[0].read_text(encoding="utf-8")


@pytest.mark.parametrize("путь", АНИМЕГО, ids=lambda п: п.parts[-3])
def test_animego_check_зелёный(путь):
    р = _запуск(["--check", str(путь)])
    assert р.returncode == 0, р.stdout + р.stderr
    assert "ок" in р.stdout


@pytest.mark.parametrize("путь", АНИМЕГО, ids=lambda п: п.parts[-3])
def test_animego_сезонная_лента_несёт_ключ_блока(путь):
    """Признак дефекта становится независимым от ТЕКСТА: «H1 внутри блока,
    который является лентой» проверяется структурой, а не совпадением строк.
    Без ключа обход заголовков по парку этот случай пропускал — и пропустил
    27.10, пока его не нашла линия SEO глазами."""
    главная = _метод(путь, "главная", "ag-h1")
    assert 'data-block-key="rail:season"' in главная
    # Ключ стоит на блоке, ВНУТРИ которого и подпись, и карточки: иначе
    # `closest` от карточки до него не дойдёт, а наблюдателю нечего мерить.
    место_ключа = главная.index('data-block-key="rail:season"')
    место_подписи = главная.index('class="ag-h1">Аниме {сезон} сезона</h2>')
    assert место_ключа < место_подписи, главная[место_ключа:место_подписи + 80]
    assert "</section>" in главная[место_подписи:]


@pytest.mark.parametrize("путь", АНИМЕГО, ids=lambda п: п.parts[-3])
def test_animego_целей_блока_здесь_нет_и_это_не_скрыто(путь):
    """Ключ блока сам по себе ничего не отправляет. В этом рантайме слоя
    отправки целей нет вовсе — значит обещать `block_view`/`block_click` по
    AnimeGo нельзя, пока он не перенесён. Тест стоит, чтобы это не забылось
    и не превратилось в «цели есть, раз ключ есть»."""
    текст = путь.read_text(encoding="utf-8")
    # Ищем ИМЯ ЦЕЛИ как строку кода, а не слово в тексте: собственный
    # комментарий о том, что целей здесь нет, иначе считался бы целью.
    объявлена = '"block_view"' in текст or "'block_view'" in текст
    есть_слой = "ЦЕЛИ_МЕТРИКИ" in текст or "__sfGoal" in текст
    if есть_слой:
        # Слой перенесли — тогда цель обязана быть в закрытом списке.
        assert объявлена, "слой целей есть, а показа блока в нём нет"
    else:
        assert not объявлена, (
            "цель объявлена без точки отправки — она молчала бы при исправном коде")


# --- Animedia Space: та же болезнь, своя разметка визиток -----------------

def test_animedia_space_отличима_от_icu():
    """Таблица настроек домена у витрин одна, а сетку визиток Space собирает
    своим выражением ключа. Если бы линия определялась только по таблице,
    инструмент правил бы у Space разметку, которой там нет."""
    import importlib.util
    спец = importlib.util.spec_from_file_location("инструмент", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    имя, _ = м.линия(АНИМЕДИА_SPACE.read_text(encoding="utf-8"))
    assert имя == "animedia-space", имя
    имя, _ = м.линия(АНИМЕДИА.read_text(encoding="utf-8"))
    assert имя == "animedia", имя


def test_animedia_space_h1_берёт_своё_поле():
    главная = _метод(АНИМЕДИА_SPACE, "главная", 'class="vh"')
    assert 'домен["h1"]' in главная, главная[:300]
    assert 'class="vh">{html.escape(домен["title_home"])}' not in главная


def test_animedia_space_визитки_несут_ключ_блока():
    текст = АНИМЕДИА_SPACE.read_text(encoding="utf-8")
    assert 'data-block-key="card:{html.escape(str(к.get("key") or ""))}"' in текст


@pytest.mark.parametrize("домен", ("animedia.space", "animedia.icu"))
def test_animedia_space_строка_та_же(домен):
    """Строка одна на обе витрины: их каталоги по измерению одинаковы, и
    расходиться H1 не из чего (решение линии SEO 27.10)."""
    текст = АНИМЕДИА_SPACE.read_text(encoding="utf-8")
    assert текст.count('"h1": "Аниме-сериалы и фильмы онлайн",') == 2, домен
