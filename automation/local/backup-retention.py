#!/usr/bin/env python3
"""Срок хранения суточных копий публикатора: план и, по решению владельца, уборка.

Зачем инструмент, а не команда `find -mtime`. Время изменения у этих файлов —
НЕ время копирования: копии делаются `shutil.copy2`, который сохраняет время
исходного файла. Из-за этого `find -mtime` удалил бы не то, а проверка «есть
ли сегодняшняя копия» по времени изменения однажды уже дала у меня ложное
«сегодняшнего бэкапа нет» (копии прогона `daily-20261016T033001Z` лежали на
месте, все 26, со временем 15.10). Надёжный ключ даты — `run_id` в имени
файла, и считает здесь только он.

Что инструмент делает: группирует файлы по дате прогона из имени
(`*.before.daily-YYYYMMDDT…`), оставляет N самых свежих ДАТ и показывает, что
освободится. Чего не делает: не трогает `/srv/backups` (защищённые архивы),
не трогает файлы без `run_id` в имени (происхождение неизвестно — удалять
нечего понятного), не удаляет ничего без `--apply` и отказывается оставить
меньше трёх дат.

Решение о сроке хранения — владельца: это суточные снимки постоянных данных
сайта, и выпуск их только читает (`docs/RUNTIME_DATA_OWNERSHIP.md`).

    python3 automation/local/backup-retention.py --keep-days 7
    python3 automation/local/backup-retention.py --keep-days 7 --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys
from pathlib import Path

КАТАЛОГ = Path("/srv/site-factory/repo/var/lords/publish-backups")
#: Имя копии: `<витрина>-<вид>.json.before.daily-<дата>T<время>Z`.
ОБРАЗЕЦ = re.compile(r"\.before\.daily-(\d{8})T\d{6}Z$")
МИНИМУМ_ДАТ = 3


def собрать(каталог: Path) -> tuple[dict[str, list[Path]], list[Path]]:
    по_дате: dict[str, list[Path]] = collections.defaultdict(list)
    прочие: list[Path] = []
    for ф in sorted(каталог.iterdir()):
        if not ф.is_file():
            continue
        м = ОБРАЗЕЦ.search(ф.name)
        if м:
            по_дате[м.group(1)].append(ф)
        else:
            прочие.append(ф)
    return dict(по_дате), прочие


def объём(файлы: list[Path]) -> int:
    итог = 0
    for ф in файлы:
        try:
            итог += ф.stat().st_size
        except OSError:
            pass
    return итог


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--keep-days", type=int, required=True,
                   help="сколько самых свежих ДАТ прогонов оставить")
    р.add_argument("--apply", action="store_true",
                   help="удалить; без него только план")
    р.add_argument("--dir", default=str(КАТАЛОГ), help="каталог копий")
    опции = р.parse_args(аргв)

    каталог = Path(опции.dir)
    if not каталог.is_dir():
        raise SystemExit(f"каталога нет: {каталог}")
    if опции.keep_days < МИНИМУМ_ДАТ:
        raise SystemExit(f"оставить меньше {МИНИМУМ_ДАТ} дат нельзя: точки "
                         "восстановления нужны не в единственном числе")

    по_дате, прочие = собрать(каталог)
    даты = sorted(по_дате)
    if not даты:
        raise SystemExit(f"в {каталог} нет файлов с датой прогона в имени — "
                         "удалять по дате нечего")
    оставить = даты[-опции.keep_days:]
    удалить = даты[:-опции.keep_days] if len(даты) > опции.keep_days else []

    всего = объём([ф for с in по_дате.values() for ф in с]) + объём(прочие)
    освободится = объём([ф for д in удалить for ф in по_дате[д]])
    print(f"каталог: {каталог}")
    print(f"  всего: {всего / 2**30:.2f} ГиБ; дат прогонов: {len(даты)} "
          f"({даты[0]} → {даты[-1]})")
    print(f"  файлов без даты в имени: {len(прочие)} "
          f"({объём(прочие) / 2**30:.2f} ГиБ) — не трогаются")
    print(f"  оставить дат: {len(оставить)} "
          f"({оставить[0]} → {оставить[-1]})")
    print(f"  удалить дат: {len(удалить)}"
          + (f" ({удалить[0]} → {удалить[-1]})" if удалить else ""))
    print(f"  освободится: {освободится / 2**30:.2f} ГиБ "
          f"({sum(len(по_дате[д]) for д in удалить)} файлов)")
    статистика = os.statvfs(каталог)
    свободно = статистика.f_bavail * статистика.f_frsize
    print(f"  свободно сейчас: {свободно / 2**30:.2f} ГиБ; станет около "
          f"{(свободно + освободится) / 2**30:.2f} ГиБ")

    if not удалить:
        print("удалять нечего: дат не больше, чем просили оставить")
        return 0
    if not опции.apply:
        print("это план; для уборки — тот же вызов с --apply")
        return 0

    удалено = 0
    ошибок = 0
    for д in удалить:
        for ф in по_дате[д]:
            try:
                ф.unlink()
                удалено += 1
            except OSError as сбой:
                ошибок += 1
                print(f"   не удалён {ф.name}: {сбой}", file=sys.stderr)
    статистика = os.statvfs(каталог)
    print(f"удалено файлов: {удалено}; ошибок: {ошибок}; свободно стало "
          f"{статистика.f_bavail * статистика.f_frsize / 2**30:.2f} ГиБ")
    return 0 if ошибок == 0 else 2


if __name__ == "__main__":
    raise SystemExit(главное())
