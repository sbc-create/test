#!/usr/bin/env python3
"""MOD-223: девять проверок витрины не находят снимок и потому всегда молчат.

    python3 automation/host/apply-checks-data-dir-patch.py \
        --repo var/site-repos/zonafilm-cc [--check] [--dry-run]

Что измерено
------------

Замер 28.10 (находка владельца общего кода, подтверждена мной): девять
проверок zonafilm.cc берут каталог снимков как
`Path(os.environ.get("SITE_DATA_DIR") or "/nonexistent-site-data")` —
`favicon_color`, `country_fact_links`, `home_novelty_order`, `www_redirect`,
`listing_default_mode_canonical`, `listing_titles_unique`,
`section_breadcrumbs`, `unavailable_episode_noindex`,
`sitemap_index_lastmod`.

`SITE_DATA_DIR` не задаёт никто: ноль совпадений по всем `deploy/*.sh`, по
`factory/` и по `automation/`; `deploy/activate.sh` запускает набор как
`( cd "$RELEASE" && SITE_ROOT= bash checks/run.sh )`. Значит все девять
пропускаются на АКТИВАЦИИ — витрина выпускается, не измерив их, хотя снимки на
площадке лежат рядом.

Это тот же класс, что MOD-220: адрес данных не выводится, а берётся из флага,
которого нет, и отсутствие адреса кончается молчанием, а не отказом.

Что делает инструмент
---------------------

Добавляет в порядок поиска ОДИН шаг — `checks/_snapshot_dir.каталог()`, то
есть тот же резолвер, что у правила MOD-221: окружение → `deployment.data_dir`
настройки с раскрытием `<root>` → каталог по домену. Запасное
`/nonexistent-site-data` остаётся последним: там, где снимков нет (раннер CI),
проверки по-прежнему пропускаются сами.

Почему один резолвер, а не девять копий порядка: адрес данных — один факт о
витрине, и девять его копий разойдутся, как уже разошлись имена подстановки
токенов и имена проводки режима индексации.

Порядок работ: этот инструмент применяется ПЕРЕД правилом MOD-221. Иначе
правило сделает пропуск провалом ровно для этих девяти, и активация начнёт
отказывать — не потому, что витрина плоха, а потому, что проверки не нашли
данных.

Чего инструмент не делает: не меняет сути ни одной проверки, не трогает
снимки, не правит `activate.sh`, не перезаписывает резолвер, если он уже
совпадает.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import shutil
import sys

РЕЗОЛВЕР = "checks/_snapshot_dir.py"
ИСТОЧНИК_РЕЗОЛВЕРА = (pathlib.Path(__file__).resolve().parent
                      / "lords-checks" / "_snapshot_dir.py")

#: Формы, которыми проверки берут каталог данных. Все измерены по checks/*.py
#: zonafilm-cc 28.10; к первой добавились остальные после находки владельца
#: общего кода: запасной путь по ИМЕНИ КАТАЛОГА репозитория — второй источник
#: правды, и `_snapshot_dir.py` прямо говорит, что имя каталога адресом данных
#: не считается. У 1lordserials1-online (каталог site-…) такой путь
#: промахивается; у zonafilm-cc имя совпадает и вреда сегодня нет.
ПАРЫ_ЯКОРЕЙ = (
    ('Path(os.environ.get("SITE_DATA_DIR") or "/nonexistent-site-data")',
     'Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()\n'
     '                   or "/nonexistent-site-data")'),
    ('Path(os.environ.get("SITE_DATA_DIR") or f"/srv/{КОРЕНЬ.name}/data")',
     'Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()\n'
     '                   or f"/srv/{КОРЕНЬ.name}/data")'),
    ('Path(os.environ.get("ZONA_FIXTURE_DIR", f"/srv/{КОРЕНЬ.name}/data"))',
     'Path(os.environ.get("ZONA_FIXTURE_DIR") or _каталог_снимков()\n'
     '                 or f"/srv/{КОРЕНЬ.name}/data")'),
    ('pathlib.Path(f"/srv/{КОРЕНЬ.name}/data")',
     'pathlib.Path(_каталог_снимков() or f"/srv/{КОРЕНЬ.name}/data")'),
)

#: Первый якорь оставлен отдельным именем: по нему инструмент узнаёт файлы,
#: которые правил до расширения.
ЯКОРЬ = ПАРЫ_ЯКОРЕЙ[0][0]
ЗАМЕНА = ПАРЫ_ЯКОРЕЙ[0][1]

#: Вторая стража у части проверок: смотрит прямо на переменную окружения, и
#: найденный адрес её не убеждает. Измерено на sitemap_index_lastmod.py:169.
ЯКОРЬ_СТРАЖИ = 'if not os.environ.get("SITE_DATA_DIR") or not ИСТОЧНИК.is_dir():'
ЗАМЕНА_СТРАЖИ = 'if not ИСТОЧНИК.is_dir():'

ВСТАВКА_ИМПОРТА = '''

def _каталог_снимков() -> str:
    """Каталог снимков витрины или пустая строка (MOD-223).

    Один резолвер на все проверки: адрес данных — один факт о витрине, и
    девять его копий разошлись бы, как уже разошлись имена подстановки токенов
    и имена проводки режима индексации. `SITE_DATA_DIR` не задаёт никто, и без
    этого шага проверка молчала на каждой активации.
    """
    import importlib.util as _иу
    import pathlib as _пл
    путь = _пл.Path(__file__).resolve().parent / "_snapshot_dir.py"
    if not путь.is_file():
        return ""
    спец = _иу.spec_from_file_location("_snapshot_dir", путь)
    if спец is None or спец.loader is None:
        return ""
    модуль = _иу.module_from_spec(спец)
    try:
        спец.loader.exec_module(модуль)
        return модуль.каталог()
    except Exception:  # noqa: BLE001 — резолвер не обязан работать всюду
        return ""
'''


def _место_вставки(текст: str) -> int:
    """Номер строки, после которой можно вставить определение.

    После строки документации модуля И после всех импортов из `__future__`.
    Это третья версия, и каждая правилась по прогону, а не по рассуждению:

    1. «конец блока импортов» указал ВНУТРЬ блока `except`: определение встало
       между `print()` и `sys.exit(2)`, тот стал недостижимым, исполнение
       пошло дальше — `NameError` (unavailable_episode_noindex.py);
    2. «сразу за строкой документации» ломало файлы, где следом идёт
       `from __future__ import annotations`: такой импорт обязан быть первым,
       иначе `SyntaxError: from __future__ imports must occur at the beginning
       of the file` (indexing_live_switch.py, indexing_mode_rules.py);
    3. теперь — после документации и после `__future__`.

    Помощник самодостаточен (свои импорты внутри), поэтому верх файла для него
    безопасен всегда.
    """
    try:
        дерево = ast.parse(текст)
    except SyntaxError:
        return -1
    строка = 0
    for узел in дерево.body:
        if (isinstance(узел, ast.Expr)
                and isinstance(getattr(узел, "value", None), ast.Constant)
                and isinstance(узел.value.value, str)
                and строка == 0):
            строка = getattr(узел, "end_lineno", узел.lineno)
            continue
        if isinstance(узел, ast.ImportFrom) and узел.module == "__future__":
            строка = max(строка, getattr(узел, "end_lineno", узел.lineno))
            continue
        break
    return строка


def _правка_файла(путь: pathlib.Path, писать: bool) -> tuple[bool, str]:
    текст = путь.read_text(encoding="utf-8")
    if "_каталог_снимков()" in текст:
        return False, "уже"
    подошли = [(я, з) for я, з in ПАРЫ_ЯКОРЕЙ if текст.count(я) == 1]
    многие = [я for я, _ in ПАРЫ_ЯКОРЕЙ if текст.count(я) > 1]
    if многие:
        return False, "якорь встречается больше одного раза"
    if not подошли:
        return False, "ни одна известная форма адреса данных не найдена"
    после = _место_вставки(текст)
    if после < 0:
        return False, "файл не разбирается, вставлять нечего"
    новый = текст
    for я, з in подошли:
        новый = новый.replace(я, з, 1)
    # Вторая стража, если она есть: найденный адрес должен её убеждать.
    if ЯКОРЬ_СТРАЖИ in новый:
        новый = новый.replace(ЯКОРЬ_СТРАЖИ, ЗАМЕНА_СТРАЖИ)
    строки = новый.splitlines(keepends=True)
    строки.insert(после, ВСТАВКА_ИМПОРТА.lstrip("\n") + "\n")
    новый = "".join(строки)
    try:
        ast.parse(новый)
    except SyntaxError as сбой:
        return False, f"правка дала бы SyntaxError: {сбой.msg} (строка {сбой.lineno})"
    if писать:
        путь.write_text(новый, encoding="utf-8")
    return True, "правится"


def применить(репо: pathlib.Path, писать: bool) -> tuple[str, str]:
    каталог = репо / "checks"
    if not каталог.is_dir():
        return "refuse", f"нет каталога {каталог}"
    if not ИСТОЧНИК_РЕЗОЛВЕРА.is_file():
        return "refuse", f"нет источника резолвера {ИСТОЧНИК_РЕЗОЛВЕРА}"
    def подходит(f: pathlib.Path) -> bool:
        т = f.read_text(encoding="utf-8", errors="replace")
        if "_каталог_снимков()" in т:
            return True
        # Форма с именем каталога правится только там, где НЕТ шага по
        # настройке: у восьми моих проверок этот путь стоит последним, после
        # окружения, настройки и домена, и он там на месте.
        если_настройка = "deployment" in т or "data_dir" in т
        for я, _ in ПАРЫ_ЯКОРЕЙ:
            if т.count(я) == 1:
                if "КОРЕНЬ.name" in я and если_настройка:
                    continue
                return True
        return False

    цели = sorted(f for f in каталог.glob("*.py") if подходит(f))
    if not цели:
        return "skip", "ни одна проверка не берёт каталог из «/nonexistent-site-data»"

    цель_резолвера = репо / РЕЗОЛВЕР
    резолвер_на_месте = (цель_резолвера.is_file()
                         and цель_резолвера.read_bytes()
                         == ИСТОЧНИК_РЕЗОЛВЕРА.read_bytes())
    правятся = []
    отказы = []
    for f in цели:
        надо, причина = _правка_файла(f, писать=False)
        if надо:
            правятся.append(f.name)
        elif причина != "уже":
            отказы.append(f"{f.name}: {причина}")
    if отказы:
        return "refuse", "; ".join(отказы)
    if not правятся and резолвер_на_месте:
        return "skip", f"все {len(цели)} проверок уже находят каталог"

    if not писать:
        что = ([РЕЗОЛВЕР] if not резолвер_на_месте else []) + правятся
        return "ok", f"будет сделано ({len(правятся)} проверок): " + ", ".join(что)

    if not резолвер_на_месте:
        shutil.copyfile(ИСТОЧНИК_РЕЗОЛВЕРА, цель_резолвера)
    сделано = []
    for f in цели:
        надо, _ = _правка_файла(f, писать=True)
        if надо:
            сделано.append(f.name)
    return "ok", f"исправлено проверок: {len(сделано)} — " + ", ".join(сделано)


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", action="append", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    отказы = правок = 0
    for путь in а.repo:
        репо = pathlib.Path(путь).resolve()
        исход, пояснение = применить(репо, писать=not (а.check or а.dry_run))
        print(f"[{исход:6s}] {репо.name}: {пояснение}")
        if исход == "refuse":
            отказы += 1
        elif исход == "ok":
            правок += 1
    if отказы:
        return 2
    if а.check:
        return 1 if правок else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
