"""Рантайм семейства ОТПРАВЛЯЕТ цели, и отправляет их безопасно.

Повод (MOD-38), измеренный 15.10 с двух сторон: в
`automation/host/lords-frontend.py` было ноль вызовов `reachGoal` при
инициализированном теге Метрики, а на странице тайтла живой витрины
`lordserials22.info` уходило двенадцать запросов счётчика без единой цели. По
отчётам за 8–14 октября у тринадцати доменов визиты есть, достижений целей
ноль — при том что девять целей с идентификаторами объявлены в
`config/analytics.json`.

Проверяется ИСПОЛНЕНИЕМ, а не наличием строки: скрипт вынимается из вывода
рантайма и прогоняется в node с подставленными `window`, `document`, `ym` и
адресом страницы. «Скрипт добавлен» доказывало бы только то, что строка есть.

Главное свойство, которое здесь сторожится, — приватность: у вызова цели
РОВНО три аргумента (счётчик, `reachGoal`, имя из закрытого списка). Четвёртый
аргумент Метрики — произвольные данные, и один такой вызов из обработчика
поиска вынес бы поисковую фразу в отчёт. Написать «цель с данными» в этом
контракте нечем.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
РАНТАЙМ = КОРЕНЬ / "automation" / "host" / "lords-frontend.py"

pytestmark = pytest.mark.skipif(shutil.which("node") is None,
                                reason="node на машине нет — исполнить скрипт нечем")


def _функции_тега(счётчик: str = "112010277") -> dict:
    """Только блок тега и целей: рантайм целиком требует каталога витрины."""
    исходник = РАНТАЙМ.read_text(encoding="utf-8")
    начало = исходник.index("СЧЁТЧИК_МЕТРИКИ = ")
    конец = исходник.index("#: Контракт многоисточниковых оценок")
    # Переменная окружения ВОЗВРАЩАЕТСЯ на место. Первая редакция оставляла
    # её выставленной, и соседняя проверка темы, рендерящая страницу в том же
    # процессе, падала — порядок тестов не имеет права решать, есть ли у
    # витрины счётчик.
    было = os.environ.get("LORDS_METRIKA_COUNTER")
    os.environ["LORDS_METRIKA_COUNTER"] = счётчик
    прост: dict = {}
    try:
        exec(compile("import os\n" + исходник[начало:конец], "<тег>", "exec"),
             прост)
    finally:
        if было is None:
            os.environ.pop("LORDS_METRIKA_COUNTER", None)
        else:
            os.environ["LORDS_METRIKA_COUNTER"] = было
    return прост


@pytest.fixture(scope="module")
def блок() -> dict:
    return _функции_тега()


@pytest.fixture(scope="module")
def скрипт(блок) -> str:
    тег = блок["тег_метрики"]()
    куски = [с for с in re.findall(r"<script[^>]*>(.*?)</script>", тег, re.S)
             if "__sfGoal" in с]
    assert куски, "в теге Метрики нет скрипта целей"
    return куски[0]


ПРОБА = """
globalThis.window = globalThis;
const вызовы = [];
globalThis.ym = function(){ вызовы.push(Array.prototype.slice.call(arguments)); };
const слушатели = {};
globalThis.document = {
  addEventListener: (имя, фн) => { (слушатели[имя] = слушатели[имя] || []).push(фн); },
};
globalThis.location = { pathname: "%(путь)s" };
%(скрипт)s
const форма = (роль, действие, класс) => ({ target: {
  getAttribute: (a) => (a === "role" ? роль : действие), className: класс } });
(слушатели.submit||[]).forEach(ф => ф(форма("search", "/search/", "srch")));
(слушатели.submit||[]).forEach(ф => ф(форма(null, "/series/", "filt__form")));
const ссылка = (h) => ({ tagName: "A", getAttribute: () => h,
                         parentNode: globalThis.document });
(слушатели.click||[]).forEach(ф => ф({ target: ссылка("/title/x/season-7/episode-4/") }));
(слушатели.click||[]).forEach(ф => ф({ target: ссылка("/title/x/season-7/") }));
(слушатели.click||[]).forEach(ф => ф({ target: ссылка("/catalog/") }));
window.__sfGoalOnce("player_start");
window.__sfGoalOnce("player_ready");
window.__sfGoalOnce("player_start");
window.__sfGoal("нет_такой_цели");
console.log(JSON.stringify({ вызовы, события: Object.keys(слушатели) }));
"""


def прогон(скрипт: str, путь: str, tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    файл = tmp_path / "проба.mjs"
    файл.write_text(ПРОБА % {"путь": путь, "скрипт": скрипт}, encoding="utf-8")
    г = subprocess.run(["node", str(файл)], capture_output=True, text=True,
                       timeout=120)
    assert г.returncode == 0, (г.stderr or "")[:600]
    д = json.loads(г.stdout.strip().splitlines()[-1])
    д["имена"] = [в[2] for в in д["вызовы"] if len(в) > 2]
    return д


def test_цель_страницы_произведения_только_на_её_адресе(скрипт, tmp_path):
    на_тайтле = прогон(скрипт, "/title/kakoy-to-tajtl/", tmp_path / "a")
    на_каталоге = прогон(скрипт, "/catalog/", tmp_path / "b")
    assert "title_view" in на_тайтле["имена"]
    assert "title_view" not in на_каталоге["имена"], (
        "title_view ушёл с каталога — отчёт показал бы просмотры произведений "
        "там, где их не было")


def test_поиск_и_фильтр_отправляются_по_отправке_формы(скрипт, tmp_path):
    д = прогон(скрипт, "/catalog/", tmp_path)
    assert "search" in д["имена"] and "filter_apply" in д["имена"], д["имена"]


def test_сезон_и_серия_по_переходу(скрипт, tmp_path):
    д = прогон(скрипт, "/title/x/", tmp_path)
    assert "episode_select" in д["имена"], д["имена"]
    assert "season_select" in д["имена"], д["имена"]
    # Обычная ссылка каталога цели не даёт: иначе каждое нажатие на сайте
    # считалось бы выбором серии.
    assert д["имена"].count("episode_select") == 1, д["имена"]
    assert д["имена"].count("season_select") == 1, д["имена"]


def test_повтор_цели_в_одной_загрузке_съедается(скрипт, tmp_path):
    д = прогон(скрипт, "/title/x/", tmp_path)
    assert д["имена"].count("player_start") == 1, (
        "один и тот же player_start ушёл дважды — отчёт завысил бы запуски")


def test_имя_вне_закрытого_списка_не_отправляется(скрипт, tmp_path):
    д = прогон(скрипт, "/title/x/", tmp_path)
    assert "нет_такой_цели" not in д["имена"], (
        "опечатка в вызове заводит в кабинете цель-призрак, которой нет в "
        "реестре аналитики")


def test_у_вызова_ровно_три_аргумента(скрипт, tmp_path):
    """Приватность: четвёртым аргументом Метрики уходят произвольные данные."""
    д = прогон(скрипт, "/title/x/", tmp_path)
    assert д["вызовы"], "ни одной цели не ушло — проверять нечего"
    длины = {len(в) for в in д["вызовы"]}
    assert длины == {3}, (
        f"у вызова цели {длины} аргументов вместо трёх — через лишний "
        "аргумент в отчёт попали бы поисковая фраза, текст комментария или "
        "идентификатор издателя")
    assert all(в[1] == "reachGoal" for в in д["вызовы"])


def test_счётчик_берётся_из_окружения_витрины(tmp_path):
    блок = _функции_тега("999000111")
    куски = [с for с in re.findall(
        r"<script[^>]*>(.*?)</script>", блок["тег_метрики"](), re.S)
        if "__sfGoal" in с]
    д = прогон(куски[0], "/title/x/", tmp_path)
    assert {в[0] for в in д["вызовы"]} == {999000111}, (
        "цель ушла в чужой счётчик")


def test_список_целей_совпадает_с_реестром(блок):
    """Имена не придумываются: у каждой цели в реестре есть goal_id."""
    реестр = json.loads((КОРЕНЬ / "config" / "analytics.json"
                         ).read_text(encoding="utf-8"))
    известные = set()
    for з in реестр.get("properties") or []:
        известные |= set(з.get("goals") or [])
    лишние = set(блок["ЦЕЛИ_МЕТРИКИ"]) - известные
    assert not лишние, (
        f"рантайм отправляет цели, которых нет в реестре: {sorted(лишние)}")


def test_comment_submit_не_отправляется_и_причина_названа():
    """Отсутствие цели — решение с причиной, а не пропуск.

    У Yummy `comment_submit` уходит по ПРИЁМУ сервером. Здесь форма
    сообщества уходит обычным POST с переходом, и «отправлено» не равно
    «принято». Отправлять по submit значило бы считать принятыми отклонённые
    комментарии.
    """
    исходник = РАНТАЙМ.read_text(encoding="utf-8")
    блок = _функции_тега()
    assert "comment_submit" not in блок["ЦЕЛИ_МЕТРИКИ"]
    assert "«отправлено» не равно «принято»" in исходник, (
        "причина отсутствия comment_submit не записана рядом со списком")


def test_цели_плеера_уходят_из_единственной_воронки():
    """Иначе отправка разойдётся с состояниями на первой же правке."""
    исходник = РАНТАЙМ.read_text(encoding="utf-8")
    м = re.search(r"function state\(k,t,p\)\{(.{0,900})", исходник, re.S)
    assert м, "воронка состояний плеера изменилась — проверку надо обновить"
    голова = м.group(1)
    assert "player_ready" in голова and "player_error" in голова, голова
    assert "__sfGoalOnce" in голова
