#!/usr/bin/env python3
"""Штатный сборщик недельного снимка для ячейки: служба, таймер и путь.

    sudo python3 automation/host/install-popular-weekly.py --site zona-03 [--dry-run]

Зачем это отдельный сценарий. Витрина снимок только ЧИТАЕТ: контракт
POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT запрещает считать его на запросе, а сам
модуль `popular_weekly.py` прямо пишет, что таймер не заводит и расписание —
работа владельца. Пока расписания нет, полка «Высокие оценки недели» пуста, и
подложить файл руками означало бы доказать не работу обновлений, а свою
способность положить файл.

Три юнита, а не один:

    <учётка>-popular-weekly.service   сборка из каталога ячейки в её же данные
    <учётка>-popular-weekly.timer     раз в сутки, Persistent — догоняет простой
    <учётка>-popular-weekly.path      сразу после КАЖДОЙ доставки каталога

`.path` здесь не роскошь: без него первый снимок нового домена появился бы
только в следующие 04:20, а проверка «обновления доходят» ждала бы сутки. С
ним снимок пересобирается по факту изменения каталога. Лишних публикаций это
не даёт: модуль сам ограничивает себя одной публикацией в неделю
(POPULAR_MAX_PUBLICATIONS_PER_WEEK=1), и повторный запуск с тем же составом
завершается успехом, ничего не меняя.

Существующие файлы не перезаписываются: у zonafilm.space юниты настроены
вручную и подгонять их под шаблон ради единообразия нельзя.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parent.parent.parent
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ЮНИТЫ = Path(os.environ.get("SITE_UNIT_DIR", "/etc/systemd/system"))

СЛУЖБА = """# Недельный снимок «популярного» для {домен} ({site_id}).
#
# Витрина снимок только читает (POPULAR_REFRESH_MODE=WEEKLY_SNAPSHOT), поэтому
# собирать его обязан планировщик. Код берётся через `current`, а не через
# `app`: выпуск переводит на новый релиз именно ссылку `current`, а `app` —
# копия первоначального переноса, она отстаёт.
[Unit]
Description=Недельный снимок популярного, {домен}
After=network-online.target
# Снимок строится ИЗ каталога: без него собирать нечего. Условие, а не отказ —
# задание помечается пропущенным, и таймер не копит ошибки.
ConditionPathExists=/srv/{учётка}/data/{site_id}-catalog.json
ConditionPathExists=/srv/{учётка}/current/src/popular_weekly.py

[Service]
Type=oneshot
User={учётка}
Group={учётка}
WorkingDirectory=/srv/{учётка}/current
Environment=PYTHONPATH=/srv/{учётка}/current/src
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/usr/bin/python3 /srv/{учётка}/current/src/popular_weekly.py \\
    --catalog /srv/{учётка}/data/{site_id}-catalog.json \\
    --out /srv/{учётка}/data/{site_id}-popular-weekly.json

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/{учётка}/data
ProtectKernelTunables=true
RestrictSUIDSGID=true
"""

ТАЙМЕР = """# Расписание недельного снимка {домен}. Раз в сутки, а не раз в неделю:
# неделю закрывает сам модуль (POPULAR_MAX_PUBLICATIONS_PER_WEEK=1), а суточный
# запуск гарантирует появление снимка и после доставки каталога, и после
# простоя, не дожидаясь следующего понедельника.
[Unit]
Description=Недельный снимок популярного, {домен}

[Timer]
OnCalendar=*-*-* 04:{минута}:00
# Пропущенный запуск догоняется: иначе полка пустовала бы до следующих суток.
Persistent=true
RandomizedDelaySec=600
Unit={учётка}-popular-weekly.service

[Install]
WantedBy=timers.target
"""

ПУТЬ = """# Пересборка снимка сразу после доставки каталога {домен}.
#
# Без этого юнита первый снимок нового домена появился бы только в следующие
# 04:xx, и «обновления доходят» приходилось бы ждать сутки. Лишних публикаций
# не будет: модуль ограничивает себя одной публикацией в неделю.
[Unit]
Description=Каталог {домен} изменился — пересобрать недельный снимок

[Path]
PathChanged=/srv/{учётка}/data/{site_id}-catalog.json
Unit={учётка}-popular-weekly.service

[Install]
WantedBy=multi-user.target
"""


def ячейка(site_id: str) -> dict:
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    for c in данные.get("cells") or []:
        if c["site_id"] == site_id:
            return c
    raise SystemExit(f"в реестре нет ячейки {site_id}")


def написать(путь: Path, тело: str, сухой: bool) -> str:
    if путь.exists():
        return "уже есть, не трогаю"
    if сухой:
        return "поставил бы"
    путь.write_text(тело, encoding="utf-8")
    путь.chmod(0o644)
    return "записан"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--site", required=True)
    р.add_argument("--dry-run", action="store_true")
    a = р.parse_args()
    if not a.dry_run and os.geteuid() != 0:
        print("нужен root", file=sys.stderr)
        return 2

    я = ячейка(a.site)
    рв = я.get("runtime") or {}
    учётка = рв.get("account")
    if not учётка:
        raise SystemExit(f"у {a.site} в реестре нет runtime.account")
    домен = я.get("domain") or a.site
    # Минуты разводятся по site_id, чтобы сборщики разных витрин не сходились
    # в одну минуту: каждый читает свой каталог целиком.
    минута = f"{20 + (sum(map(ord, a.site)) % 30):02d}"
    поля = {"домен": домен, "учётка": учётка, "site_id": a.site, "минута": минута}

    состав = (
        (ЮНИТЫ / f"{учётка}-popular-weekly.service", СЛУЖБА.format(**поля)),
        (ЮНИТЫ / f"{учётка}-popular-weekly.timer", ТАЙМЕР.format(**поля)),
        (ЮНИТЫ / f"{учётка}-popular-weekly.path", ПУТЬ.format(**поля)),
    )
    изменено = 0
    print(f"{a.site}  {домен}  учётка {учётка}  сборка в 04:{минута}")
    for путь, тело in состав:
        исход = написать(путь, тело, a.dry_run)
        изменено += исход == "записан"
        print(f"   {путь.name}: {исход}")

    if a.dry_run:
        таймер = f"{учётка}-popular-weekly.timer"
        путь_ю = f"{учётка}-popular-weekly.path"
        print(f"   [сухой прогон] systemctl enable --now {таймер} {путь_ю}")
        print("\nсухой прогон завершён: существующие файлы не трогались")
        return 0
    if изменено:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
    # Включение здесь, а не отдельным шагом: юнит, который лежит и не включён,
    # выглядит установленным и не работает. Именно так полка была пуста.
    subprocess.run(["systemctl", "enable", "--now",
                    f"{учётка}-popular-weekly.timer",
                    f"{учётка}-popular-weekly.path"], check=True)
    print(f"\nвключено. Пока в /srv/{учётка}/current нет выпуска, задание будет")
    print("помечаться пропущенным — это условие, а не ошибка. После первого")
    print("выпуска снимок соберётся по изменению каталога, без ожидания суток.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
