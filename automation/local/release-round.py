#!/usr/bin/env python3
"""Один круг выпуска по ячейке: прогон, замок, коммит, отправка. Без выкладки.

    python3 automation/local/release-round.py --repo var/site-repos/<проект> \\
        --message-file <файл с текстом коммита> [--reason "что изменилось"] [--dry-run]

Что делает по порядку и почему именно так:

1. пересчитывает замок версий, если содержимое файлов разошлось с ним. Причина
   расхождения ЗАПИСЫВАЕТСЯ в замок: «обновите контрольную сумму» без причины —
   это и есть обход проверки;
2. гоняет `checks/run.sh` ячейки. Ярус живой отдачи включается, когда каталог
   данных площадки читается: без него часть проверок пропускается, и об этом
   сказано вслух;
3. при зелёном прогоне коммитит и отправляет ветку. ВЫКЛАДКУ НЕ ДЕЛАЕТ: её
   подаёт `python3 -m factory cell trigger` после зелёного CI, и смешивать эти
   два шага нельзя — CI идёт минуты, а выкладка требует его результата.

Красный прогон останавливает круг: ни коммита, ни отправки. Инструмент печатает
последние строки прогона, чтобы причина была видна без второго запуска.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]


def выполнить(команда: list[str], где: pathlib.Path, среда: dict | None = None,
              таймаут: int = 2400) -> tuple[int, str]:
    г = subprocess.run(команда, cwd=str(где), capture_output=True, text=True,
                       env=среда, timeout=таймаут)
    return г.returncode, (г.stdout or "") + (г.stderr or "")


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--repo", required=True)
    р.add_argument("--message-file", required=True)
    р.add_argument("--reason", default="")
    р.add_argument("--data", default="", help="каталог данных площадки для живого яруса")
    р.add_argument("--no-push", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    о = р.parse_args(argv[1:])

    репо = pathlib.Path(о.repo)
    if not репо.is_absolute():
        репо = КОРЕНЬ / репо
    if not (репо / ".git").is_dir():
        print(f"не репозиторий сайта: {репо}", file=sys.stderr)
        return 2
    cfg = json.loads((репо / "config" / "site.json").read_text(encoding="utf-8"))
    домен = cfg["domain"]
    аккаунт = домен.replace(".", "-")
    данные = pathlib.Path(о.data) if о.data else pathlib.Path("/srv") / аккаунт / "data"

    print(f"=== {репо.name} ({домен})")
    код, вывод = выполнить(
        ["git", "-C", str(репо), "status", "--porcelain"], КОРЕНЬ)
    if not вывод.strip():
        print("   изменений нет — круг не нужен")
        return 0
    print("   изменения: " + ", ".join(
        с[3:] for с in вывод.strip().split("\n")[:8]))

    if о.reason:
        код, вывод = выполнить(
            [sys.executable, "automation/local/refresh-pins-lock.py",
             "--repo", str(репо), "--reason", о.reason], КОРЕНЬ)
        print("   замок: " + (вывод.strip().split("\n")[-1] if вывод.strip()
                              else f"код {код}"))

    среда = dict(os.environ)
    if данные.is_dir() and os.access(данные, os.R_OK):
        среда["SITEMAP_CHECK_DATA"] = str(данные)
        print(f"   живой ярус включён: {данные}")
    else:
        print(f"   живой ярус выключен: {данные} не читается")

    код, вывод = выполнить(["bash", "checks/run.sh"], репо, среда)
    строки = [с for с in вывод.strip().split("\n") if с.strip()]
    провалы = [с for с in строки if "FAIL" in с]
    print(f"   прогон: проверок {len(строки)}, провалов {len(провалы)}, код {код}")
    for с in провалы[:6]:
        print("      " + с.strip())
    if код != 0:
        print("   круг остановлен: красный прогон, коммита нет")
        return 1

    if о.dry_run:
        print("   сухой прогон: коммита и отправки нет")
        return 0

    выполнить(["git", "-C", str(репо), "add", "-A"], КОРЕНЬ)
    сообщение = pathlib.Path(о.message_file).read_text(encoding="utf-8")
    г = subprocess.run(["git", "-C", str(репо), "commit", "-q", "-F", "-"],
                       input=сообщение, capture_output=True, text=True)
    if г.returncode != 0:
        print("   коммит не создан: " + (г.stdout + г.stderr).strip()[:200])
        return 1
    код, вывод = выполнить(["git", "-C", str(репо), "log", "--oneline", "-1"], КОРЕНЬ)
    print("   коммит: " + вывод.strip())

    if о.no_push:
        print("   отправка пропущена по просьбе")
        return 0
    код, ветка = выполнить(
        ["git", "-C", str(репо), "rev-parse", "--abbrev-ref", "HEAD"], КОРЕНЬ)
    ветка = ветка.strip()
    код, вывод = выполнить(["git", "-C", str(репо), "push", "-q", "origin", ветка],
                           КОРЕНЬ)
    print(f"   отправлено: {ветка}" if код == 0
          else f"   отправка не удалась: {вывод.strip()[:200]}")
    return 0 if код == 0 else 1


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
