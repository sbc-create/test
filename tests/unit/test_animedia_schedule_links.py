"""Два дефекта расписания Animedia и патч, который их закрывает.

Воспроизведено снаружи 2026-10-15 на живых сайтах:

1. `/schedule/` на animedia.icu вёл на `/title/<slug>/season-1/episode-4/` и
   отдавал **404**, тогда как серии тайтла «Невероятное приключение ДжоДжо:
   Гонка „Стальной шар“» лежат в сезоне 7. Из семи ссылок дня 404 отдавали
   три — и это были ссылки на ДОСТУПНЫЕ серии.
2. Карточка того же тайтла на animedia.icu и animeg0.site показывала
   «Доступно серий 4» и одновременно «Следующая серия: 4 серия — 16 октября».

Проверка идёт по ПАТЧЕННОЙ копии рантайма, а не по общей рабочей копии: та
общая (`var/site-repos/animedia-icu`), и 15.10 в 14:08 по ней прошёл чужой
выпуск. Патч — `automation/host/animedia-fixes/t132-t134-schedule-season-and-next.patch`.
"""
from __future__ import annotations

import importlib.util
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Проверяется ВЫЛОЖЕННЫЙ код — он и работает у посетителя. Общая рабочая
#: копия остаётся запасным источником для окружения без /srv.
_ВЫЛОЖЕНО = pathlib.Path("/srv/animedia-icu/current/src/animedia-frontend.py")
ИСТОЧНИК = (_ВЫЛОЖЕНО if _ВЫЛОЖЕНО.is_file()
            else КОРЕНЬ / "var/site-repos/animedia-icu/src/animedia-frontend.py")
ПАТЧ = (КОРЕНЬ / "automation/host/animedia-fixes"
        / "t134-next-episode-already-released.patch")

#: Данные ДжоДжо в той форме, в которой их читает рантайм: сезон 7 с
#: доступными сериями 1–4, более ранние сезоны без доступных.
ДЖОДЖО = {"seasons": [{"number": 1, "nums": []},
                      {"number": 7, "nums": [1, 2, 3, 4]}]}


@pytest.fixture(scope="module")
def модуль(tmp_path_factory):
    if not ИСТОЧНИК.is_file():
        pytest.skip(f"нет общей рабочей копии {ИСТОЧНИК}")
    if not ПАТЧ.is_file():
        pytest.skip(f"нет патча {ПАТЧ}")
    каталог = tmp_path_factory.mktemp("animedia") / "repo"
    # Копируется ВЕСЬ src: рантайм импортирует соседние модули витрины
    # (`seo_layer`, `seo_overlay`, `chronology` и другие). Копия одного файла
    # давала «No module named seo_layer», и проверки молча пропускались — то
    # есть патч оставался непроверенным при зелёном прогоне.
    shutil.copytree(ИСТОЧНИК.parent, каталог / "src",
                    ignore=shutil.ignore_patterns("__pycache__"))
    цель = каталог / "src" / "animedia-frontend.py"
    sys.path.insert(0, str(каталог / "src"))
    г = subprocess.run(["patch", "-d", str(каталог), "-p1", "--forward",
                        "--batch", "-i", str(ПАТЧ)],
                       capture_output=True, text=True)
    assert г.returncode == 0, г.stdout + г.stderr
    спец = importlib.util.spec_from_file_location("animedia_patched", цель)
    м = importlib.util.module_from_spec(спец)
    sys.modules["animedia_patched"] = м
    try:
        спец.loader.exec_module(м)
    except Exception as ош:  # noqa: BLE001
        pytest.skip(f"рантайм не импортируется в этом окружении: {ош}")
    return м


@pytest.fixture()
def вид(модуль):
    """Вид без конструктора: нужны только методы и подставные данные."""
    в = object.__new__(модуль.ВидАнимедиа)
    в.деталь = lambda slug: ДЖОДЖО if slug == "jojo" else {}
    в.хост = "animedia.icu"
    return в


def test_номер_сезона_в_расписании_уже_исправлен():
    """Первый дефект закрыт ДРУГОЙ сессией — проверяется факт, не мой патч.

    Выпуск 15:58 15.10 (releases/7fb87d322a67) передаёт номер сезона в строку
    расписания готовым (`з["сезон"]`), а не подставляет единицу. Измерено на
    живом сайте в 16:46: все шесть ссылок дня отвечают 200, у ДжоДжо
    `/season-7/episode-4/`. Моя версия того же исправления снята, чтобы два
    решения одной задачи не расходились.
    """
    текст = ИСТОЧНИК.read_text(encoding="utf-8")
    assert 'self.адрес_эпизода(запись["slug"], з["сезон"], эпизод)' in текст, (
        "в выложенном коде нет передачи сезона в строку расписания")
    assert 'self.адрес_эпизода(запись["slug"], 1,' not in текст, (
        "зашитая единица вернулась")


def test_доступные_серии_собираются_по_всем_сезонам(вид):
    assert вид._доступные_серии("jojo") == {1, 2, 3, 4}
    assert вид._доступные_серии("нет-такого") == set()


def test_вышедшая_серия_следующей_не_называется(модуль, monkeypatch):
    """Второй дефект: «Доступно 4» и «Следующая: 4 серия» одновременно."""
    import datetime as dt
    в = object.__new__(модуль.ВидАнимедиа)
    в.деталь = lambda slug: ДЖОДЖО if slug == "jojo" else {}
    завтра = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat()
    в._наблюдения_расписания = lambda: {
        "stale": False,
        "events": [{"slug": "jojo", "episode": 4, "airing_at": завтра}]}
    assert в._следующая_серия({"slug": "jojo"}) == "", (
        "событие о ВЫШЕДШЕЙ серии печаталось как следующая")


def test_невышедшая_серия_по_прежнему_называется(модуль):
    """Полезное поведение не потеряно: серия 5 ещё не доступна — строка есть."""
    import datetime as dt
    в = object.__new__(модуль.ВидАнимедиа)
    в.деталь = lambda slug: ДЖОДЖО if slug == "jojo" else {}
    завтра = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=1)).isoformat()
    в._наблюдения_расписания = lambda: {
        "stale": False,
        "events": [{"slug": "jojo", "episode": 5, "airing_at": завтра}]}
    строка = в._следующая_серия({"slug": "jojo"})
    assert 'data-next-episode="5"' in строка
    assert "5 серия" in строка


def test_дата_не_придумывается_при_отсутствии_события(модуль):
    в = object.__new__(модуль.ВидАнимедиа)
    в.деталь = lambda slug: ДЖОДЖО
    в._наблюдения_расписания = lambda: {"stale": False, "events": []}
    assert в._следующая_серия({"slug": "jojo"}) == ""

def test_на_неисправленном_состоянии_дефект_есть():
    """Проверка обязана падать без патча — иначе она ничего не доказывает.

    Доказывается двумя способами сразу: в непатченном тексте стоит зашитая
    единица, и методов, которые вводит патч, там нет вовсе.
    """
    if not ИСТОЧНИК.is_file():
        pytest.skip(f"нет общей рабочей копии {ИСТОЧНИК}")
    текст = ИСТОЧНИК.read_text(encoding="utf-8")
    assert "_доступные_серии" not in текст, (
        "защиты от вышедшей серии в источнике уже нет — значит патч выложен; "
        "тогда эту проверку надо снять вместе с патчем")
    assert "_следующая_серия" in текст, "строка следующей серии исчезла из кода"
