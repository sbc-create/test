"""Мутационные проверки: каждый гейт обязан падать на испорченной странице.

## Зачем

Гейт, который никогда не срабатывал, не отличим от гейта, который не работает.
Ровно это и случилось однажды: измеритель искал карточки по чужим селекторам,
находил пустое множество, и пятьдесят шаблонов получали «сто из ста» за
проверки, которые не могли упасть.

Поэтому здесь каждая проверка предъявляется дважды: на здоровой странице она
молчит, на намеренно испорченной — срабатывает. Порча вносится в разметку и
стили готовой страницы, то есть ровно туда, где дефект и живёт.

Тесты требуют Chromium: без браузера измерять нечего, и пропуск честно
отмечается, а не выдаётся за успех.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
ЯДРО = КОРЕНЬ / "factory" / "templates" / "lords" / "shared"
ПАКЕТ = КОРЕНЬ / "factory" / "templates" / "lords" / "T001-forest-cinema-stage"

playwright = pytest.importorskip("playwright.sync_api",
                                 reason="без Chromium измерять нечего")


def _загрузить(имя: str, файл: pathlib.Path):
    spec = importlib.util.spec_from_file_location(имя, файл)
    модуль = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(модуль)
    return модуль


score = _загрузить("lords_score", ЯДРО / "score.py")
render = _загрузить("lords_render", ЯДРО / "render.py")


@pytest.fixture(scope="module")
def фикстура() -> dict:
    сырая = json.loads((ЯДРО / "test-fixtures" / "catalog.json").read_text(encoding="utf-8"))
    копия = copy.deepcopy(сырая)
    # Постеры убираются намеренно: их адреса ведут на внешний хост, которого в
    # разрешённом периметре нет, и каждая картинка считалась бы битой. Тогда
    # «битое изображение» перестало бы быть находкой.
    for запись in копия["items"]:
        запись["poster"] = None
        запись["poster_local"] = None
    return копия


@pytest.fixture(scope="module")
def браузер():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        б = pw.chromium.launch(args=["--disable-dev-shm-usage"])
        yield б
        б.close()


@pytest.fixture(scope="module")
def измеритель():
    return score._измеритель()


def измерить_текст(браузер, измеритель, html: str, tmp: pathlib.Path,
                   ширина: int = 1440) -> dict:
    файл = tmp / "page.html"
    файл.write_text(html, encoding="utf-8")
    контекст = браузер.new_context(viewport={"width": ширина, "height": 900})
    стр = контекст.new_page()
    try:
        стр.goto(файл.resolve().as_uri(), wait_until="load", timeout=45000)
        стр.wait_for_timeout(150)
        запись = {"route": "home", "viewport": ширина}
        запись.update(стр.evaluate(измеритель.ИЗМЕРЕНИЕ))
        запись["a11y"] = стр.evaluate(score.ДОСТУПНОСТЬ)
        return запись
    finally:
        стр.close()
        контекст.close()


def свод(запись: dict) -> dict:
    манифест = json.loads((ПАКЕТ / "template.json").read_text(encoding="utf-8"))
    return score.оценить(манифест, [запись], [], 0)["measured"]


def испортить(html: str, стиль: str = "", вставка: str = "") -> str:
    если_стиль = html.replace("</style>", стиль + "</style>", 1) if стиль else html
    return (если_стиль.replace('<main class="wrap" id="main" role="main">',
                               '<main class="wrap" id="main" role="main">' + вставка, 1)
            if вставка else если_стиль)


@pytest.fixture(scope="module")
def здоровая(фикстура) -> str:
    return render.отрисовать(ПАКЕТ, фикстура, ЯДРО, "home")


@pytest.fixture(scope="module")
def каталог(фикстура) -> str:
    return render.отрисовать(ПАКЕТ, фикстура, ЯДРО, "catalog")


# --- здоровая страница молчит ------------------------------------------------

def test_healthy_page_is_clean(браузер, измеритель, здоровая, tmp_path):
    м = свод(измерить_текст(браузер, измеритель, здоровая, tmp_path))
    for ключ in ("HORIZONTAL_OVERFLOW_COUNT", "CLIPPED_REQUIRED_TEXT_COUNT",
                 "BROKEN_IMAGE_COUNT", "POSTER_ASPECT_RATIO_VIOLATIONS",
                 "OVERLAP_COUNT", "LOW_CONTRAST_COUNT", "SMALL_TOUCH_TARGET_COUNT",
                 "DEAD_CONTROL_COUNT", "HEADING_ORDER_SKIPS",
                 "HEAVY_FRAMES_BEFORE_ACTION", "UNLABELLED_CONTROL_COUNT"):
        assert м[ключ] == 0, f"здоровая страница дала {ключ}={м[ключ]}"
    assert м["PAGES_WITHOUT_SINGLE_H1"] == 0
    assert м["PAGES_WITHOUT_LANDMARKS"] == 0


# --- каждый гейт падает на своей порче ---------------------------------------

def test_overflow_gate_catches_wide_element(браузер, измеритель, здоровая, tmp_path):
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, ".k{min-width:2400px}"), tmp_path))
    assert м["HORIZONTAL_OVERFLOW_COUNT"] > 0


def test_clipped_text_gate_catches_squeezed_date(браузер, измеритель, здоровая, tmp_path):
    """Обязательная дата — строгая величина: её обрезка должна ловиться всегда.

    Именно этот дефект и наблюдался на живой витрине: дата помещалась в 26 px
    при нужных семидесяти.
    """
    порча = ".k__d{max-width:14px;overflow:hidden;display:block;white-space:nowrap}"
    м = свод(измерить_текст(браузер, измеритель, испортить(здоровая, порча), tmp_path))
    assert м["CLIPPED_REQUIRED_TEXT_COUNT"] > 0


def test_broken_image_gate_catches_missing_file(браузер, измеритель, здоровая, tmp_path):
    вставка = '<img src="нет-такого-файла.png" width="100" height="150" alt="">'
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, вставка=вставка), tmp_path))
    assert м["BROKEN_IMAGE_COUNT"] > 0


def test_poster_ratio_gate_catches_squashed_frame(браузер, измеритель, фикстура, tmp_path):
    """Раздавленный постер ловится только там, где постер есть.

    На странице без изображений эта проверка не может сработать в принципе —
    и молчала бы, создавая впечатление годности. Поэтому здесь кладётся
    настоящий файл 2:3.
    """
    from PIL import Image
    Image.new("RGB", (200, 300), (40, 80, 60)).save(tmp_path / "poster.png")
    с_постером = copy.deepcopy(фикстура)
    for запись in с_постером["items"]:
        запись["poster_local"] = "poster.png"
    html = render.отрисовать(ПАКЕТ, с_постером, ЯДРО, "home")
    здоровые = свод(измерить_текст(браузер, измеритель, html, tmp_path))
    assert здоровые["POSTER_ASPECT_RATIO_VIOLATIONS"] == 0, "здоровая рамка не годна"
    порча = ".k--poster .k__p{aspect-ratio:auto;height:24px}.k__img{height:24px}"
    м = свод(измерить_текст(браузер, измеритель, испортить(html, порча), tmp_path))
    assert м["POSTER_ASPECT_RATIO_VIOLATIONS"] > 0


def test_contrast_gate_catches_dim_text(браузер, измеритель, здоровая, tmp_path):
    порча = ".sec__t,.k__t{color:#101815}"
    м = свод(измерить_текст(браузер, измеритель, испортить(здоровая, порча), tmp_path))
    assert м["LOW_CONTRAST_COUNT"] > 0


def test_touch_target_gate_catches_tiny_control(браузер, измеритель, здоровая, tmp_path):
    порча = ".hd__l{min-height:12px;height:12px;padding:0 2px}"
    м = свод(измерить_текст(браузер, измеритель, испортить(здоровая, порча), tmp_path))
    assert м["SMALL_TOUCH_TARGET_COUNT"] > 0


def test_dead_control_gate_catches_button_without_behaviour(
        браузер, измеритель, здоровая, tmp_path):
    вставка = ('<button class="fake" style="min-width:60px;min-height:44px">'
               'Показать ещё</button>')
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, вставка=вставка), tmp_path))
    assert м["DEAD_CONTROL_COUNT"] > 0, "нарисованная кнопка без поведения не поймана"


def test_form_button_is_not_reported_as_dead(браузер, измеритель, здоровая, tmp_path):
    """Кнопка отправки внутри формы — живая, и ложно обвинять её нельзя."""
    вставка = ('<form action="/search/"><button type="submit" '
               'style="min-width:60px;min-height:44px">Найти</button></form>')
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, вставка=вставка), tmp_path))
    assert м["DEAD_CONTROL_COUNT"] == 0


def test_unlabelled_control_gate_catches_empty_button(
        браузер, измеритель, здоровая, tmp_path):
    вставка = '<button data-lx-play></button>'
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, вставка=вставка), tmp_path))
    assert м["UNLABELLED_CONTROL_COUNT"] > 0


def test_heading_order_gate_catches_skip(браузер, измеритель, здоровая, tmp_path):
    порченая = здоровая.replace('<h2 class="sec__t"', '<h4 class="sec__t"', 1) \
                        .replace("</h2>", "</h4>", 1)
    м = свод(измерить_текст(браузер, измеритель, порченая, tmp_path))
    assert м["HEADING_ORDER_SKIPS"] > 0


def test_single_h1_gate_catches_second_h1(браузер, измеритель, здоровая, tmp_path):
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, вставка="<h1>Второй</h1>"), tmp_path))
    assert м["PAGES_WITHOUT_SINGLE_H1"] > 0


def test_heavy_frame_gate_catches_autoloaded_player(
        браузер, измеритель, здоровая, tmp_path):
    вставка = '<iframe title="плеер" src="about:blank" width="320" height="180"></iframe>'
    м = свод(измерить_текст(браузер, измеритель,
                            испортить(здоровая, вставка=вставка), tmp_path))
    assert м["HEAVY_FRAMES_BEFORE_ACTION"] > 0


def test_landmark_gate_catches_missing_main(браузер, измеритель, здоровая, tmp_path):
    порченая = здоровая.replace('<main class="wrap" id="main" role="main">',
                                '<div class="wrap" id="main">').replace("</main>", "</div>")
    м = свод(измерить_текст(браузер, измеритель, порченая, tmp_path))
    assert м["PAGES_WITHOUT_LANDMARKS"] > 0


def test_overlap_gate_catches_stacked_cards(браузер, измеритель, здоровая, tmp_path):
    порча = ".g{display:block;position:relative}.k{position:absolute;top:0;left:0;" \
            "width:320px;height:300px}"
    м = свод(измерить_текст(браузер, измеритель, испортить(здоровая, порча), tmp_path))
    assert м["OVERLAP_COUNT"] > 0


# --- проверки действием тоже обязаны падать ----------------------------------

def _действия(браузер, html: str, tmp: pathlib.Path, маршрут: str) -> list[dict]:
    файл = tmp / "page.html"
    файл.write_text(html, encoding="utf-8")
    контекст = браузер.new_context(viewport={"width": 1440, "height": 900})
    стр = контекст.new_page()
    try:
        стр.goto(файл.resolve().as_uri(), wait_until="load", timeout=45000)
        стр.wait_for_timeout(150)
        return score.проверить_действия(стр, маршрут)
    finally:
        стр.close()
        контекст.close()


def test_filter_check_passes_on_healthy_catalog(браузер, каталог, tmp_path):
    провалы = [п for п in _действия(браузер, каталог, tmp_path, "catalog") if not п["ok"]]
    assert not провалы, провалы


def test_filter_check_fails_when_javascript_is_removed(браузер, каталог, tmp_path):
    """Без ядра интерактивности фильтр — нарисованные кнопки. Это обязано падать."""
    без_скрипта = каталог[:каталог.rindex("<script>")] + "</body></html>"
    провалы = [п for п in _действия(браузер, без_скрипта, tmp_path, "catalog")
               if not п["ok"]]
    имена = {п["check"] for п in провалы}
    assert провалы, "мёртвые фильтры не пойманы"
    assert any("сокращает выдачу" in и for и in имена), имена


def test_rail_check_fails_when_arrows_do_nothing(браузер, фикстура, tmp_path):
    """Стрелка, нарисованная в разметке и ничего не делающая, обязана падать."""
    страница = render.отрисовать(ПАКЕТ, фикстура, ЯДРО, "title_movie")
    if 'data-lx="rail"' not in страница:
        pytest.skip("у этого пакета на странице тайтла нет полосы")
    без_скрипта = страница[:страница.rindex("<script>")]
    мёртвые = без_скрипта.replace(
        '<div class="rail__nav" data-lx-nav hidden></div>',
        '<div class="rail__nav" data-lx-nav>'
        '<button class="rail__b" type="button" aria-label="Прокрутить назад">‹</button>'
        '<button class="rail__b" type="button" aria-label="Прокрутить вперёд">›</button>'
        '</div>') + "</body></html>"
    провалы = [п for п in _действия(браузер, мёртвые, tmp_path, "title-movie")
               if not п["ok"]]
    assert провалы, "нарисованные стрелки без поведения не пойманы"
