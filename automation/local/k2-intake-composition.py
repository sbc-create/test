#!/usr/bin/env python3
"""Состав ленты «Недавние поступления» в рантайме КАЖДОЙ витрины партии.

Зачем отдельно от теста шаблона. Проверка шаблона
(`tests/unit/test_lords_intake_rail_follows_profile.py`) доказывает поведение
шаблона фабрики. Витрины держат свои копии рантайма в
`var/new-sites/<site>/src/lords-frontend.py`, и у них бывает более ранний
вариант того же файла — измерено 2026-10-17: подпись полки оценок там
встречалась четырежды против одного раза в шаблоне. Поэтому состав ленты
проверяется на файле каждой витрины: иначе «исправлено» означало бы
«исправлено в одном месте из девяти».

Каталог синтетический и одинаковый для всех: фильмы и сериалы ЧЕРЕДУЮТСЯ.
Если сложить сначала все фильмы, первые двадцать восемь кандидатов окажутся
фильмами сами собой, и отбор по направлению ничего бы не доказал.

Запуск:  k2-intake-composition.py [site_id ...]
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
САЙТЫ_КОРЕНЬ = КОРЕНЬ / "var" / "new-sites"
sys.path.insert(0, str(КОРЕНЬ / "tests" / "unit"))


def наполнение(H, фильмов: int, сериалов: int):
    записи, детали = [], []
    ф = с = 0
    while ф < фильмов or с < сериалов:
        if ф < фильмов:
            записи.append(H.запись(f"film-{ф:03d}", title=f"Фильм {ф}",
                                   kind="Фильм", year=2020 + ф % 6))
            детали.append(H.подробность(f"film-{ф:03d}", type_="movie",
                                        genres=("Драма",)))
            ф += 1
        if с < сериалов:
            записи.append(H.запись(f"serial-{с:03d}", title=f"Сериал {с}",
                                   kind="Сериал", year=2020 + с % 6))
            детали.append(H.подробность(f"serial-{с:03d}", type_="tv",
                                        genres=("Драма",)))
            с += 1
    return записи, детали


def лента(html: str) -> list[str]:
    н = html.find('data-shelf="intake"')
    if н < 0:
        return []
    return re.findall(r'href="/title/([^/"]+)/"',
                      html[н:html.find("</section>", н)])


def профиль(сайт: str) -> str:
    м = САЙТЫ_КОРЕНЬ / сайт / "config" / "template-manifest.json"
    if not м.is_file():
        return ""
    return json.loads(м.read_text(encoding="utf-8")).get("profile") or ""


def главная(аргв: list[str]) -> int:
    import lords_runtime_harness as H
    from _pytest.monkeypatch import MonkeyPatch

    цели = аргв or [f"lords-{н}" for н in range(10, 18)]
    плохо = 0
    for сайт in цели:
        ядро = САЙТЫ_КОРЕНЬ / сайт / "src" / "lords-frontend.py"
        проф = профиль(сайт)
        if not ядро.is_file() or not проф:
            print(f"[x] {сайт}: рантайма или манифеста нет")
            плохо += 1
            continue
        H.ЯДРО = ядро
        mp = MonkeyPatch()
        try:
            with tempfile.TemporaryDirectory() as кат:
                стенд = H.Стенд(pathlib.Path(кат), профиль=проф)
                записи, детали = наполнение(H, 40, 40)
                стенд.записать_каталог(записи)
                стенд.записать_подробности(детали)
                стенд.записать_плеер()
                модуль = H.загрузить(стенд, mp)
                try:
                    слуги = лента(H.вид(модуль).главная())
                    состав: dict[str, int] = {}
                    for с in слуги:
                        к = "фильм" if с.startswith("film-") else "сериал"
                        состав[к] = состав.get(к, 0) + 1
                    ожидание = {"lords-films": "фильм",
                                "lords-serials": "сериал"}.get(проф)
                    ладно = (not ожидание) or (set(состав) == {ожидание})
                    плохо += not ладно
                    метка = " " if ладно else "✗"
                    print(f"{метка} {сайт} ({проф}, дизайн {модуль.ДИЗАЙН_ID}): "
                          f"карточек {len(слуги)}, состав {состав}")
                finally:
                    H.выгрузить(модуль)
        finally:
            mp.undo()
    print(f"\nвитрин с чужим составом ленты: {плохо} из {len(цели)}")
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
