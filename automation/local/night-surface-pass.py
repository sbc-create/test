#!/usr/bin/env python3
"""Один проход по публичной поверхности: пять мер, один артефакт, один код.

Только чтение публичных страниц и снимков данных. Ничего не публикует, служб
не трогает, за пределы `var/` и `artifacts/` не пишет.

ЗАЧЕМ ОБЁРТКА. Пять ночных мер отвечают на разные вопросы, но запускать их по
отдельности — пять шагов владельца и пять мест, где результат теряется:

* ``robots-closure-consistency`` — совпадает ли режим индексации с замыслом и
  прочтёт ли робот запрет;
* ``mobile-render-probe`` — не разъехалась ли отрисовка на телефоне;
* ``catalog-vs-sitemap-sample`` — не потерялись ли адреса каталога в карте;
* ``inline-css-weight`` — не вырос ли вес пояснений в встроенном стиле;
* ``description-gap-measure`` — куда движется пробел описаний.

КАК ЧИТАЕТСЯ КОД ВОЗВРАТА, и почему «неуспешно» здесь нормально. Меры
отвечают о СОСТОЯНИИ сети, а не о себе: код 1 значит «найдено то, что названо
дефектом», и на 21.10 это ожидаемый ответ. Код 2 значит «мера не измерила» —
вот это и есть повод смотреть на сам проход. Код 0 — всё измерено и чисто.
Поэтому итоговый код: 2, если хоть одна мера НЕ ИЗМЕРИЛА; иначе 1, если хоть
одна нашла дефект; иначе 0.

    python3 automation/local/night-surface-pass.py
    python3 automation/local/night-surface-pass.py --only robots --only mobile
    python3 automation/local/night-surface-pass.py --out var/surface/2026-10-22
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]

#: Имя → (скрипт, аргументы, предел секунд). Пределы названы по измеренной
#: длительности ночных прогонов с запасом вдвое: мобильная отрисовка поднимает
#: настоящий браузер на десять страниц и это самая долгая мера.
МЕРЫ: dict[str, tuple[str, list[str], int]] = {
    "robots": ("robots-closure-consistency.py", ["--json"], 900),
    "mobile": ("mobile-render-probe.py", ["--json"], 900),
    "sitemap": ("catalog-vs-sitemap-sample.py",
                ["1lordserials1.online", "--pages", "20", "--json"], 900),
    "css": ("inline-css-weight.py", ["--json"], 300),
    "descriptions": ("description-gap-measure.py", ["--json"], 300),
    # Мера новой серии против карты появилась 21.10 и сразу нашла 7 работ из
    # 24 на `yummyani.biz`. Предел выше остальных: она читает три части карты
    # по 50 000 адресов и открывает страницы работ по одной.
    "episodes": ("fresh-episode-in-sitemap.py",
                 ["--domain", "yummyani.biz", "--hours", "36", "--json"], 1200),
    # Зависимость обработки изображений проверяется КАЖДЫМ проходом, потому
    # что её отсутствие не видно ни по одному другому признаку: 23.10 правка
    # уменьшения обложек была выпущена и полдня не действовала — Pillow стоял
    # в каталоге пользователя, а служба идёт системным интерпретатором.
    # Проверяется не импорт, а реальное преобразование, и на живой обложке.
    # Редакционные подборки и анонсы против ТЕКУЩЕГО снимка: состав выбран
    # однажды, а каталог меняется каждую ночь. Пропавшая работа, потерянный
    # источник видео, аниме на витрине фильмов, просроченный анонс и анонс,
    # который уже доступен к просмотру, — всё это страница продолжает отдавать
    # с кодом 200, и без отдельной меры их не видно. Мера только измеряет:
    # «добивать» состав случайными карточками запрещено (поручение 27.10).
    "editorial": ("editorial-sets-validate.py", ["--json"], 300),
    "images": ("service-image-support-check.py",
               ["--user", "animedia-icu", "--url",
                "https://animedia.icu/poster/"
                "019fc2ae-8785-7a47-a311-2751785e6b31.webp",
                "--expect-width", "480", "--json"], 300),
}

ЧИСТО, ДЕФЕКТ, НЕ_ИЗМЕРЕНО, СБОЙ = "чисто", "найден дефект", "НЕ ИЗМЕРЕНО", "СБОЙ"


def исход_по_коду(код: int) -> str:
    """Что означает код возврата отдельной меры."""
    if код == 0:
        return ЧИСТО
    if код == 1:
        return ДЕФЕКТ
    if код == 2:
        return НЕ_ИЗМЕРЕНО
    return СБОЙ


def итоговый_код(исходы: dict[str, str]) -> int:
    """Код прохода целиком. Неизмеренное весит больше найденного дефекта."""
    if not исходы:
        return 2
    if any(и in (НЕ_ИЗМЕРЕНО, СБОЙ) for и in исходы.values()):
        return 2
    if any(и == ДЕФЕКТ for и in исходы.values()):
        return 1
    return 0


def запустить(имя: str, каталог: pathlib.Path) -> dict:
    скрипт, аргументы, предел = МЕРЫ[имя]
    путь = КОРЕНЬ / "automation" / "local" / скрипт
    файл = каталог / f"{имя}.json"
    начало = datetime.datetime.now(datetime.timezone.utc)
    try:
        г = subprocess.run([sys.executable, str(путь), *аргументы],
                           capture_output=True, text=True, timeout=предел,
                           cwd=str(КОРЕНЬ))
        код = г.returncode
        вывод = г.stdout or ""
        ошибка = (г.stderr or "")[-400:]
    except subprocess.TimeoutExpired:
        код, вывод, ошибка = 3, "", f"предел {предел} с исчерпан"
    длительность = (datetime.datetime.now(datetime.timezone.utc)
                    - начало).total_seconds()
    if вывод.strip().startswith(("{", "[")):
        файл.write_text(вывод, encoding="utf-8")
        артефакт = str(файл)
    else:
        артефакт = ""
    return {"мера": имя, "скрипт": скрипт, "код": код,
            "исход": исход_по_коду(код), "секунд": round(длительность, 1),
            "артефакт": артефакт, "ошибка": ошибка.strip()[:200]}


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--only", action="append", default=[], choices=sorted(МЕРЫ))
    р.add_argument("--out", default="")
    а = р.parse_args(аргв)

    сегодня = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    каталог = pathlib.Path(а.out) if а.out else (КОРЕНЬ / "var" / "surface"
                                                 / сегодня)
    каталог.mkdir(parents=True, exist_ok=True)

    имена = а.only or list(МЕРЫ)
    строки = [запустить(имя, каталог) for имя in имена]
    исходы = {с["мера"]: с["исход"] for с in строки}
    код = итоговый_код(исходы)

    сводка = {"снято": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "каталог": str(каталог), "итоговый_код": код, "меры": строки}
    (каталог / "сводка.json").write_text(
        json.dumps(сводка, ensure_ascii=False, indent=2), encoding="utf-8")

    for с in строки:
        print(f"{с['мера']:14} {с['исход']:14} код {с['код']}"
              f" {с['секунд']:7.1f} с  {с['артефакт'] or '—'}")
        if с["ошибка"]:
            print(f"{'':14}   {с['ошибка'][:120]}")
    print(f"\nитог прохода: код {код}"
          f" ({'всё измерено и чисто' if код == 0 else 'найдены дефекты' if код == 1 else 'есть НЕ ИЗМЕРЕННОЕ — смотреть на сам проход'})")
    print(f"сводка: {каталог / 'сводка.json'}")
    return код


if __name__ == "__main__":
    sys.exit(main())
