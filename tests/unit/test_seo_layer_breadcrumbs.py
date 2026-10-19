"""REQ-SEO-BREADCRUMB-TRUTH: звено крошек без известного имени не объявляется.

`BreadcrumbList` — обещание поисковику о пути, который видит человек. Общий
слой `automation/host/seo_layer.py` строил цепочку из сегментов адреса и при
отсутствии имени подставлял сам сегмент (`titles.get(ч, ч)`).

Измерено 19.10 приёмкой `automation/local/breadcrumb-acceptance.py` по 33
витринам: у восьми (lords-10…lords-17, партия K2 на общих профилях) разметка
объявляла звенья `['Главная', 'title', 'korolevstvo-dzirote']`, тогда как на
странице видно «lordfilm.group » Фильмы » Королевство Дзиротё». То есть
поисковику объявлялись звено-префикс маршрута `title` и slug, которых на
странице нет. У lords-01…lords-05, Zona и Yummy цепочка верная — там её строит
сам шаблон витрины, и общий слой её не добавляет.

Правило, которое закрепляют эти проверки: лучше не объявить крошки вовсе, чем
объявить звено, имени которого мы не знаем. Сегмент адреса именем не является.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/host/seo_layer.py"
_спец = importlib.util.spec_from_file_location("seo_layer_breadcrumbs", _путь)
СЛОЙ = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(СЛОЙ)

ХОСТ = "lordfilm-proverka.test"
ИМЕНА = {"title": "Фильмы", "korolevstvo-dzirote": "Королевство Дзиротё"}


def крошки_из(разметка: str) -> list[dict]:
    for блок in re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                           разметка, re.S):
        узел = json.loads(блок)
        if узел.get("@type") == "BreadcrumbList":
            return узел["itemListElement"]
    return []


def test_известные_имена_дают_полную_цепочку():
    """Отрицательный контроль: исправная витрина теряет крошки — это регресс."""
    р = СЛОЙ.схема(ХОСТ, "/title/korolevstvo-dzirote/", "Lordfilm", крошки=ИМЕНА)
    звенья = крошки_из(р)
    assert [з["name"] for з in звенья] == ["Главная", "Фильмы",
                                           "Королевство Дзиротё"]
    assert [з["position"] for з in звенья] == [1, 2, 3]


def test_сегмент_без_имени_крошек_не_даёт():
    """Ровно случай восьми витрин: имён нет — объявлять нечего."""
    р = СЛОЙ.схема(ХОСТ, "/title/korolevstvo-dzirote/", "Lordfilm", крошки={})
    assert крошки_из(р) == []
    assert "BreadcrumbList" not in р


def test_частично_известные_имена_крошек_не_дают():
    """Неполная цепочка — такое же ложное обещание, как и целиком неверная."""
    р = СЛОЙ.схема(ХОСТ, "/title/korolevstvo-dzirote/", "Lordfilm",
                   крошки={"title": "Фильмы"})
    assert крошки_из(р) == []


def test_slug_не_превращается_в_имя_звена():
    """Проверка на сам текст: slug не должен попасть в name ни при каких именах."""
    р = СЛОЙ.схема(ХОСТ, "/title/korolevstvo-dzirote/", "Lordfilm", крошки={})
    assert "korolevstvo-dzirote" not in [з.get("name") for з in крошки_из(р)]


def test_главная_без_сегментов_крошек_не_объявляет():
    """Отрицательный контроль: на главной цепочки из одного звена не бывает."""
    р = СЛОЙ.схема(ХОСТ, "/", "Lordfilm", крошки=ИМЕНА)
    assert крошки_из(р) == []


def test_остальная_разметка_не_страдает():
    """WebSite обязан остаться: правка касается только крошек."""
    р = СЛОЙ.схема(ХОСТ, "/title/korolevstvo-dzirote/", "Lordfilm", крошки={})
    типы = {json.loads(б).get("@type") for б in re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', р, re.S)}
    assert "WebSite" in типы


def test_своя_цепочка_витрины_не_дублируется():
    """Если шаблон объявил крошки сам, общий слой их не добавляет."""
    р = СЛОЙ.схема(ХОСТ, "/title/korolevstvo-dzirote/", "Lordfilm",
                   крошки=ИМЕНА, кроме={"BreadcrumbList"})
    assert крошки_из(р) == []


def test_цепочка_по_известным_именам_для_раздела():
    р = СЛОЙ.схема(ХОСТ, "/catalog/", "Lordfilm", крошки={"catalog": "Каталог"})
    assert [з["name"] for з in крошки_из(р)] == ["Главная", "Каталог"]
