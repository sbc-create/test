"""Паритет с оригиналом: измеренные величины закреплены, чтобы не уплыть.

Числа здесь не выдуманы и не «подобраны красиво» — каждое взято из снимка
оригинала (`animedia-reference-parity-2026-09-20`) и проверено замером после
правки. Тест держит их, потому что правка соседнего правила уводит геометрию
незаметно: шапка на пиксель, карточка на десяток, и через неделю витрина
снова не похожа на оригинал, а отчёт по-прежнему зелёный.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
РАНТАЙМ = ROOT / "automation/host/animedia-frontend.py"
ДОК = ROOT / "artifacts/evidence/animedia-original-parity-01"
ЭТАЛОН = (ROOT / "artifacts/evidence/animedia-reference-parity-2026-09-20"
          / "REFERENCE_MANIFEST.json")


@pytest.fixture(scope="module")
def стиль() -> str:
    return РАНТАЙМ.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def эталон() -> dict:
    return json.loads(ЭТАЛОН.read_text(encoding="utf-8"))["reference"]


@pytest.fixture(scope="module")
def замер() -> dict:
    файл = ДОК / "15-after-cleanup" / "PROBE_after-cleanup_animedia_icu.json"
    assert файл.is_file(), "нет замера после правок оболочки"
    д = json.loads(файл.read_text(encoding="utf-8"))
    return {(c["route"], c["width"]): c for c in д["cells"]}


# --- величины оболочки --------------------------------------------------------

def test_высота_шапки_как_у_оригинала(замер, эталон):
    ожидания = {390: 126, 768: 90, 1440: 90, 1920: 90}
    for ш, эт in ожидания.items():
        о = эталон["home"]["viewports"][
            {390: "390x844", 768: "768x1024", 1440: "1440x900",
             1920: "1920x1080"}[ш]]["metrics"]["header"]["h"]
        assert о == эт, f"эталон изменился: {ш} → {о}"
        наш = замер[("home", ш)]["header"]["h"]
        assert abs(наш - эт) <= 1, f"{ш}: шапка {наш}, у оригинала {эт}"


def test_ширина_рамки_шапки_как_у_оригинала(замер):
    # Оригинал не растягивает шапку на широком экране: 1420 и на 1440, и на 1920.
    assert замер[("home", 1440)]["header"]["w"] == 1420
    assert замер[("home", 1920)]["header"]["w"] == 1420
    # На телефоне и планшете — во всю ширину окна.
    assert замер[("home", 390)]["header"]["w"] == 390
    assert замер[("home", 768)]["header"]["w"] == 768


def test_контейнер_не_растягивается_за_оригиналом(замер):
    assert замер[("home", 1440)]["container"]["width"] == 1340
    assert замер[("home", 1920)]["container"]["width"] == 1340


def test_карточка_каталога_совпала_с_эталоном(замер, эталон):
    # На главной первым измеряется постер карусели: он на ширину рамки уже
    # карточки каталога, и это соответствует оригиналу, где обе величины
    # совпадают с точностью до полей ленты.
    ожидания = {768: (118, 165), 1440: (163, 228), 1920: (163, 228)}
    for ш, (эw, эh) in ожидания.items():
        постеры = [p for p in замер[("home", ш)]["posters"] if 40 < p["w"] < 600]
        assert постеры, f"{ш}: постеров не найдено"
        w, h = постеры[0]["w"], постеры[0]["h"]
        assert abs(w - эw) <= 5 and abs(h - эh) <= 6, f"{ш}: постер {w}x{h}, эталон {эw}x{эh}"
        assert abs(w / h - 5 / 7) < 0.01, f"{ш}: пропорция {w / h:.3f}"


def test_пропорция_постера_пять_к_семи(стиль):
    """5/7 — измеренная пропорция оригинала; 2/3 вытягивало каждую карточку."""
    assert стиль.count("aspect-ratio:5/7") >= 2  # карточка каталога и плитка карусели
    import re as _re
    двойки = _re.findall(r"\.(?:zt__p|ahero \.zt__p)\{[^}]*aspect-ratio:2/3", стиль)
    assert двойки == [], двойки


def test_базовый_кегль_четырнадцать(стиль):
    assert re.search(r"font:14px/1\.5 ui-sans-serif", стиль), "базовый кегль не 14px"


def test_ширина_плитки_карусели_считается_от_окна_прокрутки(стиль):
    """Проценты внутри ленты считаются от ленты, а она шире экрана."""
    assert "container-type:inline-size" in стиль
    assert "calc((100cqw - 198px)/7)" in стиль
    assert "calc((100% - 198px)/7)" not in стиль


# --- первый экран -------------------------------------------------------------

def test_первый_экран_начинается_каруселью(замер):
    """У оригинала первый экран — карусель, а не заголовок с лидом."""
    с = замер[("home", 1440)]["slider"]
    assert с is not None, "карусели на главной нет"
    assert с["box"]["y"] < 200, f"карусель не на первом экране: y={с['box']['y']}"
    assert с["slides"] >= 6
    assert с["unique_hrefs"] >= 6
    assert с["unique_images"] >= 6
    assert с["is_single_image"] is False, "одна картинка каруселью не является"


def test_на_каждой_странице_ровно_один_h1(замер):
    сколько = {}
    for (маршрут, ширина), c in замер.items():
        if c["http"] == 200:
            сколько.setdefault(c["h1_count"], 0)
            сколько[c["h1_count"]] += 1
    assert set(сколько) == {1}, f"распределение H1: {сколько}"


def test_карусель_подписана_своим_источником(стиль):
    """Подписать одну выборку названием другой — выдумать популярность."""
    assert 'data-carousel-source=' in стиль
    assert "источник: str = \"weekly-popular\"" in стиль


# --- требования к слайдеру ----------------------------------------------------

def test_запись_проверки_слайдера_зелёная():
    файл = ДОК / "10-slider" / "SLIDER_CHECK.json"
    assert файл.is_file(), "нет записи проверки слайдера"
    з = json.loads(файл.read_text(encoding="utf-8"))
    assert з["SLIDER_PASS"] is True, з["failures"][:5]
    assert з["failures"] == []
    # Проверка обязана покрывать обе настройки движения на трёх ширинах.
    ключи = {(c["width"], c["motion"]) for c in з["cells"]}
    assert ключи == {(ш, м) for ш in (390, 768, 1440)
                     for м in ("no-preference", "reduce")}
    for c in з["cells"]:
        assert c["slides"] >= 6 and c["unique_ids"] >= 6
        assert c["scroll_after_wrap"] <= 4, "лента не возвращается к началу"
        for к in c["buttons"]:
            assert к["w"] >= 44 and к["h"] >= 44


def test_перескок_в_начало_мгновенный(стиль):
    """Плавная прокрутка через всю ленту спорит с обязательной привязкой."""
    assert "перескок=true" in стиль
    assert "behavior:(перескок||!плавно())?'auto':'smooth'" in стиль


def test_нет_второго_обработчика_листания(стиль):
    """Два обработчика на одном клике дают ленте противоречивые команды."""
    assert стиль.count("data-rl]') ") + стиль.count("closest('[data-rl]')") <= 1
    assert "{СКРИПТ_ЛЕНТ}" not in стиль, "старый обработчик снова подключён"


# --- качество, которое нельзя терять ради похожести ---------------------------

def test_после_правок_нет_переполнения_обрезок_и_битых_изображений(замер):
    for (маршрут, ширина), c in замер.items():
        assert c["overflow_px"] <= 1, f"{маршрут}@{ширина}: переполнение {c['overflow_px']}"
        assert c["clipped_required"] == [], f"{маршрут}@{ширина}: обрезка"
        assert c["broken_images"] == 0, f"{маршрут}@{ширина}: битые изображения"
        assert c["player_instances"] <= 1, f"{маршрут}@{ширина}: плееров {c['player_instances']}"
        assert c["http"] == c["expected_http"], f"{маршрут}@{ширина}: код {c['http']}"


def test_индексация_не_менялась(замер):
    for (маршрут, ширина), c in замер.items():
        if c["http"] == 200:
            assert c["robots"] and "noindex" in c["robots"], f"{маршрут}@{ширина}"
