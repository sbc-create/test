"""Доставка целей кладёт ТОЛЬКО недостающие куски и не угадывает якоря.

Зачем проверка. Инструмент правит рантайм витрин, у которых поверх шаблона
лежат собственные правки (например нажимаемая цель по WCAG 2.5.8 — решение
D212а). Две его ошибки дороги по-разному:

* положить файл шаблона целиком — стереть правку витрины и привезти заодно
  всё, что менялось в шаблоне по другим поводам;
* отказаться целиком из-за одного отсутствующего якоря — лишить витрину даже
  целей посещения, которые от плеера не зависят. Измерено по рабочим копиям
  15.10: у `lordfilm47.space` и `lordserials22.info` все три якоря на месте, у
  `zonafilm12.site` только якорь тега (свой блок плеера), у `animedia.icu`
  ни одного (свой рантайм).

И отдельно: вставка, попавшая ВНУТРЬ строкового литерала, ломает файл. Так и
вышло с первой редакцией якоря, обрывавшейся до закрывающей кавычки; инструмент
это поймал и вернул копию. Здесь закреплено и то, что он так делает.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
ИНСТРУМЕНТ = КОРЕНЬ / "automation" / "local" / "deliver-metrika-goals.py"

ТЕГ = '''
def тег_метрики() -> str:
    if not СЧЁТЧИК_МЕТРИКИ.isdigit():
        return ""
    н = СЧЁТЧИК_МЕТРИКИ
    return (
        f'<script data-metrika-counter="{н}">'
        "</script>"
        f'<noscript><div><img src="https://mc.yandex.ru/watch/{н}" '
        'style="position:absolute;left:-9999px" alt=""></div></noscript>'
    )
'''

ПЛЕЕР = """
СКРИПТ_ПЛЕЕРА_КЛИЕНТ = \"\"\"
(function(){
 function state(k,t,p){
  if(отказ&&k==='ok') return;
  /* Hard failures hide the component. */
  var hard=(k==='error');
 }
 function remount(c){
  var n=document.createElement('video-player');
  host.appendChild(n);
  bind(n, ++token);
 }
})();
\"\"\"
"""


@pytest.fixture(scope="module")
def инструмент():
    спец = importlib.util.spec_from_file_location("_доставка", ИНСТРУМЕНТ)
    м = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = м
    спец.loader.exec_module(м)
    return м


@pytest.fixture(scope="module")
def куски(инструмент):
    return инструмент.куски_шаблона()


def test_куски_берутся_из_шаблона_а_не_переписаны(куски):
    """Второй копии того же кода существовать не должно."""
    assert "ЦЕЛИ_МЕТРИКИ" in куски["объявления"]
    assert "reachGoal" in куски["объявления"]
    assert "__sfGoalOnce" in куски["воронка"]
    assert "player_start" in куски["элемент"]
    # Проверяется КОД, а не пояснение: слово reachGoal в примечании к замку
    # уместно и даже нужно — там объясняется, чего в рантайме не было. Своей
    # копией был бы вызов: токен в кавычках внутри куска JS.
    import re as _re

    текст_инструмента = ИНСТРУМЕНТ.read_text(encoding="utf-8")
    вызовы = _re.findall(r"""['"]reachGoal['"]""", текст_инструмента)
    assert not вызовы, (
        "инструмент несёт свою копию кода отправки — она разойдётся с "
        "шаблоном на первой же правке")
    assert _re.search(r"\bym\s*\(", текст_инструмента) is None


def test_все_три_вставки_когда_якоря_на_месте(инструмент, куски):
    было = ТЕГ + ПЛЕЕР
    стало, шаги = инструмент.правка(было, куски)
    assert "цели_метрики(н)" in стало
    assert "ЦЕЛИ_МЕТРИКИ" in стало
    assert "player_ready" in стало and "player_error" in стало
    assert "player_start" in стало
    assert not [ш for ш in шаги if ш.startswith("[")], шаги


def test_без_плеера_цели_посещения_всё_равно_доставляются(инструмент, куски):
    """`zonafilm12.site`: свой блок плеера, но визиты и поиск считать надо."""
    стало, шаги = инструмент.правка(ТЕГ, куски)
    assert "цели_метрики(н)" in стало and "ЦЕЛИ_МЕТРИКИ" in стало
    предупреждения = [ш for ш in шаги if ш.startswith("[!]")]
    assert len(предупреждения) == 2, шаги
    assert "player_ready" not in стало.split("ЦЕЛИ_МЕТРИКИ")[0]


def test_без_тега_не_доставляется_ничего(инструмент, куски):
    """Точка отправки объявляется рядом с тегом: без неё вставки мертвы."""
    стало, шаги = инструмент.правка(ПЛЕЕР, куски)
    assert стало == ПЛЕЕР, "правка пошла без точки отправки"
    assert шаги and шаги[0].startswith("[x]"), шаги


def test_повторный_запуск_ничего_не_меняет(инструмент, куски):
    стало, _ = инструмент.правка(ТЕГ + ПЛЕЕР, куски)
    снова, шаги = инструмент.правка(стало, куски)
    assert снова == стало
    assert шаги == ["уже есть: цели в этой копии доставлены"]


def test_результат_разбирается_как_python(инструмент, куски):
    """Вставка внутрь строкового литерала ломает файл — это уже случалось."""
    import ast

    стало, _ = инструмент.правка(ТЕГ + ПЛЕЕР, куски)
    ast.parse("СЧЁТЧИК_МЕТРИКИ = '1'\n" + стало)


def test_замок_обновляется_и_прежнее_примечание_живёт(инструмент, tmp_path):
    import hashlib
    import json

    проект = tmp_path / "витрина"
    (проект / "src").mkdir(parents=True)
    файл = проект / "src" / "lords-frontend.py"
    файл.write_text("print('рантайм')\n", encoding="utf-8")
    (проект / "pins.lock.json").write_text(json.dumps({
        "files": {"lords-frontend.py": {
            "sha256": "0" * 64, "bytes": 1,
            "verified_against": "правка ячейки поверх git",
            "note": "Прежняя правка витрины: нажимаемая цель по WCAG 2.5.8.",
        }}}, ensure_ascii=False), encoding="utf-8")

    инструмент.закрепить(проект, файл)
    з = json.loads((проект / "pins.lock.json").read_text(encoding="utf-8"))
    запись = з["files"]["lords-frontend.py"]
    assert запись["sha256"] == hashlib.sha256(файл.read_bytes()).hexdigest()
    assert запись["bytes"] == файл.stat().st_size
    assert "WCAG" in запись["note"], (
        "прежнее примечание стёрто — потеряно объяснение правки витрины")
    assert "MOD-38" in запись["note"]


def test_чужая_рабочая_копия_не_правится_молча():
    """`--repo` существует для линии витрины, а не для обхода изоляции."""
    текст = ИНСТРУМЕНТ.read_text(encoding="utf-8")
    assert "--repo" in текст
    assert "чужую рабочую копию эта сессия не правит" in текст
