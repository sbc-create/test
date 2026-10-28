#!/usr/bin/env python3
"""MOD-220 и договор кодов — одной правкой на файл (семейство animedia).

    python3 automation/host/apply-animedia-data-dir-codes.py \
        --repo var/site-repos/animedia-icu --only next_episode_title [--dry-run]

Почему одной правкой, а не двумя проходами
------------------------------------------

Участок один и тот же: адрес данных выводится из ИМЕНИ КАТАЛОГА репозитория, и
тут же, при ненайденном снимке, проверка возвращает 0. Два прохода по одному
участку — два шанса разойтись, а расхождение общего слоя мы уже видели
(MOD-216, MOD-219, MOD-220).

Что правится
------------

1. **Адрес данных.** Порядок становится: окружение → НАСТРОЙКА витрины
   (`_каталог_снимков()` из `checks/_snapshot_dir.py`) → имя каталога
   последним. Имя каталога — не адрес: оно совпадает со каталогом в `/srv`
   случайно, и у семейства lords уже не совпадает
   (`/srv/site-1lordserials1-online`).

2. **Договор кодов, и состояния РАЗВЕДЕНЫ** (`docs/ANALYSIS_ORDER.md`,
   «„Не измерено“ и „случая сегодня нет“ — разные состояния»):

   * «снимка нет, мерить нечем» → код **2** и строка `НЕ ИЗМЕРЕНО: …`. Это
     пропуск, и правило MOD-221 обязано его валить;
   * «снимок есть, а проверяемого случая в нём сегодня нет» → код **0** и
     строка `НЕТ СЛУЧАЯ: …`. Проверка исполнилась на живых данных, и
     утверждать ей нечего; образец раннера
     `ПРОПУЩЕНО|ограничение окружения|НЕ ИЗМЕРЕНО|не измерено` эту строку не
     ловит, поэтому состояние данных не станет пропуском.

   Отдать оба состояния кодом 2 нельзя: после переноса MOD-221 витрина не
   выпустилась бы в любой день, когда в каталоге просто нет недоступных серий
   или свежего расписания. Правило fail-closed превратилось бы в запрет
   выпуска по погоде (возражение линии ячейки, 28.10, принято).

Ворота
------

Три мутации на ВРЕМЕННОЙ копии, все обязательны:

1. снимок лежит по НАСТРОЙКЕ, а имя каталога намеренно не совпадает с `/srv` —
   правленая проверка обязана снимок найти и мерить (иначе правка
   неотличима от случайного попадания имени);
2. снимка нет вовсе — обязан быть код **2**;
3. снимок есть, случая в нём нет — обязан быть код **0** со строкой
   `НЕТ СЛУЧАЯ`, то есть выпуск не падает.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

РЕЗОЛВЕР = "checks/_snapshot_dir.py"
ИСТОЧНИК_РЕЗОЛВЕРА = (pathlib.Path(__file__).resolve().parent
                      / "lords-checks" / "_snapshot_dir.py")

#: Формы адреса данных, измеренные по checks/*.py animedia.icu. У каждой СВОЯ
#: замена: имена переменных и порядок источников у проверок разные, и одна
#: замена на все формы меняла бы смысл.
ФОРМЫ_АДРЕСА = (
    (
        '''ИСТОЧНИК = Path(os.environ.get("SITE_DATA_DIR") or f"/srv/{КОРЕНЬ.name}/data")''',
        '''# Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
ИСТОЧНИК = Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()
                or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''ЖИВЫЕ = Path(os.environ.get("ZONA_FIXTURE_DIR", f"/srv/{КОРЕНЬ.name}/data"))''',
        '''# Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
ЖИВЫЕ = Path(os.environ.get("ZONA_FIXTURE_DIR") or _каталог_снимков()
             or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''    живые = pathlib.Path(f"/srv/{КОРЕНЬ.name}/data")''',
        '''    # Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
    живые = pathlib.Path(_каталог_снимков() or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''    данные_живые = Path(os.environ.get("SITE_DATA_DIR") or f"/srv/{КОРЕНЬ.name}/data")''',
        '''    # Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
    данные_живые = Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()
                   or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''    данные = Path(os.environ.get("SITE_DATA_DIR") or f"/srv/{КОРЕНЬ.name}/data")''',
        '''    # Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
    данные = Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()
             or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''    ДАННЫЕ = Path(os.environ.get("SITE_DATA_DIR") or f"/srv/{КОРЕНЬ.name}/data")''',
        '''    # Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
    ДАННЫЕ = Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()
             or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''ДАННЫЕ = Path(os.environ.get("SITE_DATA_DIR") or f"/srv/{КОРЕНЬ.name}/data")''',
        '''# Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220): со каталогом
# в /srv имя репозитория совпадает случайно.
ДАННЫЕ = Path(os.environ.get("SITE_DATA_DIR") or _каталог_снимков()
              or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''ЖИВЫЕ = Path(os.environ.get("ANIMEDIA_FIXTURE_DIR", f"/srv/{КОРЕНЬ.name}/data"))''',
        '''# Адрес из НАСТРОЙКИ витрины, имя каталога последним (MOD-220).
ЖИВЫЕ = Path(os.environ.get("ANIMEDIA_FIXTURE_DIR") or _каталог_снимков()
             or f"/srv/{КОРЕНЬ.name}/data")''',
    ),
    (
        '''Path(f"/srv/{КОРЕНЬ.name}/data"))''',
        '''Path(_каталог_снимков() or f"/srv/{КОРЕНЬ.name}/data"))''',
    ),
    (
    '''    источник = next((п for п in (Path(f"/srv/{имя_репо}/data"), Path(os.environ.get("SITE_DATA_DIR", "/нет")))
                     if any(п.glob("*-catalog.json"))), None)''',
    '''    # Порядок: окружение, НАСТРОЙКА витрины, имя каталога последним. Имя
    # каталога адресом не является: со каталогом в /srv оно совпадает
    # случайно, и у семейства lords уже не совпадает (MOD-220).
    источник = next((п for п in (Path(os.environ.get("SITE_DATA_DIR", "/нет")),
                                 Path(_каталог_снимков() or "/нет"),
                                 Path(f"/srv/{имя_репо}/data"))
                     if any(п.glob("*-catalog.json"))), None)''',
    ),
)

ВСТАВКА_РЕЗОЛВЕРА = '''

def _каталог_снимков() -> str:
    """Каталог снимков витрины по НАСТРОЙКЕ или пустая строка (MOD-220).

    Один резолвер на все проверки: адрес данных — один факт о витрине, и его
    копии расходятся. `SITE_DATA_DIR` не задаёт никто, а имя каталога
    репозитория адресом не является.
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

#: «Снимка нет» → код 2. Строка остаётся «НЕ ИЗМЕРЕНО»: это именно пропуск, и
#: правило MOD-221 обязано его валить. Форм две, потому что часть проверок
#: выходит из модуля (sys.exit), а часть — из main (return).
КОДЫ_НЕТ_СНИМКА = (
    (
        '''    print(f"НЕ ИЗМЕРЕНО: снимка в {ДАННЫЕ} нет — сравнение выполняется на хосте площадки")
    sys.exit(0)''',
        '''    print(f"НЕ ИЗМЕРЕНО: снимка в {ДАННЫЕ} нет — сравнение выполняется на хосте площадки")
    sys.exit(2)''',
    ),
    (
        '''    print(f"НЕ ИЗМЕРЕНО: снимка в {ДАННЫЕ} нет — проверка выполняется на хосте площадки")
    sys.exit(0)''',
        '''    print(f"НЕ ИЗМЕРЕНО: снимка в {ДАННЫЕ} нет — проверка выполняется на хосте площадки")
    sys.exit(2)''',
    ),
    (
    '''        print("НЕ ИЗМЕРЕНО: снимка ячейки нет — проверка выполняется на хосте площадки")
        return 0''',
    '''        print("НЕ ИЗМЕРЕНО: снимка ячейки нет — проверка выполняется на хосте площадки")
        return 2''',
    ),
)

#: «Снимок есть, случая нет» → код 0, но строка ДРУГАЯ: раннер не считает её
#: пропуском, иначе состояние данных запретило бы выпуск.
КОДЫ_НЕТ_СЛУЧАЯ = (
    ('''                print("НЕ ИЗМЕРЕНО: в снимке нет свежего расписания с будущими выходами")''',
     '''                print("НЕТ СЛУЧАЯ: в снимке нет свежего расписания с будущими "
                      "выходами — проверка исполнилась, утверждать нечего")'''),
    ('''        print("НЕ ИЗМЕРЕНО: в снимке нет сезона с недоступными сериями")''',
     '''        print("НЕТ СЛУЧАЯ: в снимке нет сезона с недоступными сериями — "
              "проверка исполнилась, утверждать нечего")'''),
)


def _место_вставки(текст: str) -> int:
    """После строки документации и после всех импортов из `__future__`."""
    try:
        дерево = ast.parse(текст)
    except SyntaxError:
        return -1
    строка = 0
    for узел in дерево.body:
        if (isinstance(узел, ast.Expr)
                and isinstance(getattr(узел, "value", None), ast.Constant)
                and isinstance(узел.value.value, str) and строка == 0):
            строка = getattr(узел, "end_lineno", узел.lineno)
            continue
        if isinstance(узел, ast.ImportFrom) and узел.module == "__future__":
            строка = max(строка, getattr(узел, "end_lineno", узел.lineno))
            continue
        break
    return строка


def _правка(путь: pathlib.Path) -> tuple[bool, str]:
    текст = путь.read_text(encoding="utf-8")
    if "_каталог_снимков()" in текст:
        return False, "уже"
    подошли = [(я, з) for я, з in ФОРМЫ_АДРЕСА if текст.count(я) == 1]
    if not подошли:
        return False, "формы адреса известного вида нет"
    якорь, замена = подошли[0]
    новый = текст.replace(якорь, замена, 1)
    сделано_кодов = 0
    for я, з in КОДЫ_НЕТ_СНИМКА:
        if новый.count(я) == 1:
            новый = новый.replace(я, з, 1)
            сделано_кодов += 1
    for я, з in КОДЫ_НЕТ_СЛУЧАЯ:
        if новый.count(я) == 1:
            новый = новый.replace(я, з, 1)
            сделано_кодов += 1
    место = _место_вставки(новый)
    if место < 0:
        return False, "файл не разбирается"
    строки = новый.splitlines(keepends=True)
    строки.insert(место, ВСТАВКА_РЕЗОЛВЕРА.lstrip("\n"))
    новый = "".join(строки)
    try:
        ast.parse(новый)
    except SyntaxError as сбой:
        return False, f"правка дала бы SyntaxError: {сбой.msg} (строка {сбой.lineno})"
    путь.write_text(новый, encoding="utf-8")
    return True, f"правлено (участков кода: {сделано_кодов})"


def _погасить_сирот() -> None:
    """Снять свои осиротевшие стенды ПЕРЕД подъёмом нового.

    Сирота переживает `finally` по определению: когда родитель умирает раньше
    (timeout, kill, конец хода), `finally` не исполняется вообще. Измерено
    28.10: стенд прожил 409 минут с ppid 1 и держал 598 МиБ, из-за чего шлюз
    фонового редактора трижды не запустился. Поэтому уборка — перед подъёмом.
    """
    import importlib.util as _иу
    путь = pathlib.Path(__file__).resolve().parent / "_orphan_stands.py"
    if not путь.is_file():
        return
    спец = _иу.spec_from_file_location("_orphan_stands", путь)
    if спец is None or спец.loader is None:
        return
    модуль = _иу.module_from_spec(спец)
    try:
        спец.loader.exec_module(модуль)
        модуль.погасить(pathlib.Path("/home/claude/wt-nova-publish-memory-02"))
    except Exception:  # noqa: BLE001 — уборка не обязана мешать прогону
        return


def _прогон(корень: pathlib.Path, имя: str, среда: dict) -> tuple[int, str]:
    _погасить_сирот()
    готово = subprocess.run(  # noqa: S603
        [sys.executable, f"checks/{имя}.py"], cwd=корень,
        capture_output=True, text=True, timeout=900,
        env={**os.environ, **среда, "PYTHONDONTWRITEBYTECODE": "1"})
    вывод = ((готово.stdout or "") + (готово.stderr or "")).strip()
    хвост = вывод.splitlines()[-1][:160] if вывод else "без вывода"
    return готово.returncode, хвост


def _зависит_от_снимка(копия: pathlib.Path, имя: str) -> bool:
    """Зависит ли предмет проверки от снимка — измеряется, а не угадывается.

    Проверка запускается БЕЗ снимка ДО правки. Если она при этом проходит молча
    (код 0 и ни «НЕ ИЗМЕРЕНО», ни «НЕТ СЛУЧАЯ» в выводе), значит её предмет
    снимка не требует: она закрепляет правила, а не данные. Требовать от такой
    кода 2 — ложное требование моих же ворот.

    Измерено 28.10 на zonafilm.cc/checks/indexing_mode_rules.py: без снимка
    «все случаи пройдены», код 0. Ворота отказывали ей по мутации 2, хотя
    отказывать было нечему.
    """
    код, хвост = _прогон(копия, имя, {"SITE_DATA_DIR": "/nonexistent-probe-dir"})
    молча = "НЕ ИЗМЕРЕНО" not in хвост and "НЕТ СЛУЧАЯ" not in хвост
    return not (код == 0 and молча)


def _мутации(копия: pathlib.Path, имя: str, данные: pathlib.Path,
             зависит: bool = True) -> list[str]:
    беды: list[str] = []
    настройка = копия / "config" / "site.json"
    cfg = json.loads(настройка.read_text(encoding="utf-8"))
    развёртка = dict(cfg.get("deployment") or {})
    развёртка["data_dir"] = str(данные)
    cfg["deployment"] = развёртка
    настройка.write_text(json.dumps(cfg, ensure_ascii=False, indent=1),
                         encoding="utf-8")

    # 1. Снимок по настройке, имя каталога копии («repo») с /srv не совпадает.
    код, хвост = _прогон(копия, имя, {"SITE_DATA_DIR": ""})
    if код not in (0, 1):
        беды.append(f"мутация 1 (снимок по настройке): код {код} — {хвост}")
    elif "НЕ ИЗМЕРЕНО" in хвост:
        беды.append(f"мутация 1: проверка снимок НЕ нашла — {хвост}")

    # 2. Снимка нет вовсе: код обязан быть 2 — но только если предмет проверки
    #    от снимка ЗАВИСИТ. У статической проверки требовать этого нельзя.
    if not зависит:
        беды.append("ПОМЕТКА: предмет проверки от снимка не зависит — мутация "
                    "«снимка нет» к ней не применяется")
        return [б for б in беды if not б.startswith("ПОМЕТКА")]
    cfg["deployment"]["data_dir"] = "/nonexistent-snapshot-dir"
    настройка.write_text(json.dumps(cfg, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    код, хвост = _прогон(копия, имя, {"SITE_DATA_DIR": "/nonexistent-env-dir"})
    if код != 2:
        беды.append(f"мутация 2 (снимка нет): код {код}, ожидался 2 — {хвост}")

    # 3. Снимок есть, случая в нём нет: код 0 и строка «НЕТ СЛУЧАЯ».
    пусто = копия.parent / "snapshot-empty"
    пусто.mkdir(parents=True, exist_ok=True)
    for ф in данные.glob("*-catalog.json"):
        shutil.copyfile(ф, пусто / ф.name)
    for ф in данные.glob("*-details.json"):
        shutil.copyfile(ф, пусто / ф.name)
    cfg["deployment"]["data_dir"] = str(пусто)
    настройка.write_text(json.dumps(cfg, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    код, хвост = _прогон(копия, имя, {"SITE_DATA_DIR": ""})
    if код != 0:
        беды.append(f"мутация 3 (случая нет): код {код}, ожидался 0 — {хвост}")
    elif "НЕТ СЛУЧАЯ" not in хвост and "НЕ ИЗМЕРЕНО" in хвост:
        беды.append(f"мутация 3: состояние данных названо пропуском — {хвост}")
    return беды


def применить(репо: pathlib.Path, имя: str, писать: bool) -> tuple[str, str]:
    цель = репо / "checks" / f"{имя}.py"
    if not цель.is_file():
        return "refuse", f"нет {цель}"
    if not ИСТОЧНИК_РЕЗОЛВЕРА.is_file():
        return "refuse", f"нет источника резолвера {ИСТОЧНИК_РЕЗОЛВЕРА}"
    данные = pathlib.Path(f"/srv/{репо.name}/data")
    if not данные.is_dir():
        return "refuse", f"НЕ ИЗМЕРЕНО: снимка витрины нет ({данные})"
    врем = pathlib.Path(tempfile.mkdtemp(prefix="mod220-codes-"))
    try:
        копия = врем / "repo"
        shutil.copytree(репо, копия, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".git",
                                                      "var", "artifacts"))
        (копия / "checks" / "_snapshot_dir.py").write_bytes(
            ИСТОЧНИК_РЕЗОЛВЕРА.read_bytes())
        зависит = _зависит_от_снимка(копия, имя)
        сделано, причина = _правка(копия / "checks" / f"{имя}.py")
        if not сделано:
            return ("skip", причина) if причина == "уже" else ("refuse", причина)
        беды = _мутации(копия, имя, данные, зависит)
        if беды:
            return "refuse", "мутации не прошли: " + "; ".join(беды)
    finally:
        shutil.rmtree(врем, ignore_errors=True)
    if not писать:
        return "ok", f"три мутации пройдены на копии ({причина}); запись не велась"
    (репо / "checks" / "_snapshot_dir.py").write_bytes(
        ИСТОЧНИК_РЕЗОЛВЕРА.read_bytes())
    сделано, причина2 = _правка(репо / "checks" / f"{имя}.py")
    if not сделано:
        return "refuse", f"правка витрины не прошла: {причина2}"
    код, хвост = _прогон(репо, имя, {})
    if код not in (0, 2):
        return "refuse", (f"доставлено, но прогон в витрине дал код {код}: "
                          f"{хвост} — откатите правку")
    return "ok", f"доставлено; три мутации пройдены; прогон в витрине: код {код}"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--only", required=True, help="имя проверки без .py")
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(репо, а.only,
                                 писать=not (а.check or а.dry_run))
    print(f"[{исход:6s}] {репо.name}/{а.only}: {пояснение}")
    return 2 if исход == "refuse" else 0


if __name__ == "__main__":
    sys.exit(main())
