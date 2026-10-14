#!/usr/bin/env python3
"""Порядок полок главной — измерением разметки, а не чтением кода.

Зачем нужен отдельный инструмент. Без publisher_id ни одна запись каталога не
`playable`, полки главной пустые, и порядок полок в браузере не наблюдаем
вовсе: проверить его осмотром нельзя, а оставить непроверенным нельзя тем
более — в день появления номера сериальный домен открылся бы полкой «Фильмы».

Как измеряется. Рантайм импортируется в ЭТОТ процесс, и ворота плеера
подменяются в памяти на время рендера одной страницы: `состояние_плеера`
возвращает `playable`. Это измерительная оснастка, и границы у неё жёсткие:

  * номер издателя НЕ выдумывается и НЕ записывается никуда — ни в конфигурацию
    ячейки, ни в данные, ни в окружение развёрнутой витрины; подменяется только
    функция в памяти процесса проверки;
  * проверка ничего не публикует и не отправляет: она печатает порядок
    заголовков полок и сверяет его с направлением витрины;
  * «готово к запуску» из её успеха НЕ следует: доступ к плееру остаётся
    закрытым, и состояние `noaccess` на страницах — настоящее.

Что проверяется: первая полка главной принадлежит направлению витрины
(сериальной — «Сериалы», фильмовой — «Фильмы»), и полка чужого направления
стоит последней.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import pathlib
import shutil
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
#: Чего ждём от направления: (первая полка, последняя полка).
ОЖИДАНИЕ = {
    "lords-serials": ("Сериалы", "Фильмы"),
    "lords-films": ("Фильмы", "Сериалы"),
}


def загрузить_рантайм(проект: Path, конфиг: dict, данные: Path):
    """Импортировать витрину как модуль, не запуская сервер."""
    for имя, шаблон in (конфиг.get("environment") or {}).items():
        os.environ[имя] = (str(шаблон).replace("<data>", str(данные))
                           .replace("<app>", str(проект)))
    os.environ["SITE_CONTACT_EMAIL"] = str(конфиг.get("contact_email") or "")
    os.environ["LORDS_INDEXING_SITE"] = str(конфиг.get("domain") or "")
    os.environ["LORDS_INDEXING_RELEASE_PERMITS_OPEN"] = "false"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.path.insert(0, str(проект / "src"))
    путь = проект / "src" / конфиг["entrypoint"]
    спец = importlib.util.spec_from_file_location("витрина_под_измерением", путь)
    модуль = importlib.util.module_from_spec(спец)
    sys.modules["витрина_под_измерением"] = модуль
    спец.loader.exec_module(модуль)
    return модуль


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True)
    р.add_argument("--data", required=True)
    # Своя копия проекта нужна для сравнения ДО и ПОСЛЕ правки: порядок полок
    # иначе приходится принимать по чтению кода, а не по измерению.
    р.add_argument("--project", default=None)
    р.add_argument("--expect-first", default=None,
                   help="какой полке положено быть первой (для сравнения версий)")
    а = р.parse_args()

    проект = pathlib.Path(а.project) if а.project else (
        КОРЕНЬ / "var" / "new-sites" / а.site)
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    врем = Path(tempfile.mkdtemp(prefix=f"shelf-{а.site}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in Path(а.data).glob(f"{а.site}-*.json"):
        shutil.copy(ф, данные / ф.name)

    try:
        м = загрузить_рантайм(проект, конфиг, данные)
        профиль = getattr(м, "ПРОФИЛЬ", None)
        # Подмена ворот плеера — ТОЛЬКО в этом процессе и только на рендер.
        # Номер издателя не придумывается: подменяется функция, а не значение в
        # конфигурации.
        # Данные собираются теми же вызовами, что и при запуске сервера
        # (`main()` рантайма), но сервер не поднимается: нужна одна страница.
        каталог = м.Данные(м.КАТАЛОГ_ФАЙЛ)
        подробности = м.Подробности(м.ПОДРОБНОСТИ_ФАЙЛ)
        индекс = м.построить_индекс(каталог, подробности)
        описание = м.СЕМЕЙСТВА_1_1.get(м.СЕМЕЙСТВО) or м.СЕМЕЙСТВА_1_1["lords"]
        класс = м.ВИДЫ_1_1.get(описание["вид"], м.ВидЛордс)
        вид = класс(описание, каталог, подробности, индекс, м.ИМЯ_ВИТРИНЫ)
        вид.хост = str(конфиг.get("domain") or "")
        вид.запрос = {}

        исходная = м.состояние_плеера
        # Ворота плеера возвращают кортеж (код, …) — подмена обязана держать
        # ту же форму, иначе проверка упадёт не на том, что мерит.
        проба = исходная({})
        м.состояние_плеера = (
            (lambda *а_, **к_: ("playable",) + tuple(проба[1:]))
            if isinstance(проба, tuple) else (lambda *а_, **к_: "playable"))
        try:
            html_ = вид.главная()
        finally:
            м.состояние_плеера = исходная

        заголовки = [re.sub(r"<[^>]+>", "", з).strip()
                     for з in re.findall(r"<h2[^>]*>(.*?)</h2>", html_, re.S)]
        заголовки = [з for з in заголовки if з]
        ожидание = ОЖИДАНИЕ.get(профиль)
        if а.expect_first:
            ожидание = (а.expect_first, ожидание[1] if ожидание else "")
        итог = {"site": а.site, "domain": конфиг.get("domain"), "профиль": профиль,
                "полки": заголовки, "ожидание": ожидание}
        if ожидание:
            первая, последняя = ожидание
            свои = [з for з in заголовки if з in (первая, последняя)]
            итог["своя полка первой"] = bool(свои) and свои[0] == первая
            итог["чужая полка последней"] = bool(свои) and свои[-1] == последняя
        print(json.dumps(итог, ensure_ascii=False, indent=2))
        выход = КОРЕНЬ / "var" / "k2-data" / "audit" / а.site
        выход.mkdir(parents=True, exist_ok=True)
        (выход / "shelf-order.json").write_text(
            json.dumps(итог, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if ожидание and not (итог.get("своя полка первой")
                             and итог.get("чужая полка последней")):
            return 3
        return 0
    finally:
        shutil.rmtree(врем, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
