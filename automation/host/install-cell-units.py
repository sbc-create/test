#!/usr/bin/env python3
"""Юниты ячеек по реестру: ставит недостающие, не трогает существующие.

    sudo python3 automation/host/install-cell-units.py [--dry-run]

Зачем отдельный сценарий, а не «поставьте пакет». Пакет обновляет КОД
исполнителя; юниты — это описание служб, и их состав меняется каждый раз,
когда витрина переезжает в свою ячейку. Для zona-01 и трёх Lords они стоят
давно, для трёх Yummy поставлены 26.09, для zonafilm.cc не поставлены вовсе —
и без файла службы исполнитель не может ни прогреть кандидата, ни повысить
его: он ЗАПУСКАЕТ службу по имени из реестра.

Почему именно по реестру. Выписывать имена руками — значит однажды забыть
одно и получить выпуск, который «прошёл успешно», ничего не переключив: такое
уже было, когда в реестре у Yummy стоял юнит монолита, и повышение
перезапускало бы монолитную службу с ExecStart в общем дереве. Снаружи это
неотличимо от настоящего выпуска.

Чего сценарий НЕ делает: не включает и не запускает службы. Запуск кандидата и
повышение — работа исполнителя; запуск отсюда поднял бы витрину до того, как в
её хранилище что-либо положено. И не переписывает уже стоящий файл, если он
совпадает: повторный прогон обязан быть тихим.
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
КОРЕНЬ_САЙТОВ = Path("/srv")

ШАБЛОН = """[Unit]
Description={домен} ({учётка}), выделенная ячейка
After=network-online.target

[Service]
Type=simple
User={учётка}
Group={учётка}
WorkingDirectory=/srv/{учётка}/{каталог}
ExecStart=/usr/bin/python3 /srv/{учётка}/{каталог}/run.py --port {порт} --data-dir /srv/{учётка}/data
Restart=on-failure
RestartSec=2
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
# Хранилище открыто на запись целиком, а не отдельными файлами: рядом с базой
# появляются -wal и -shm, а рядом с правками редактора — временный файл замены.
ReadWritePaths=/srv/{учётка}/data
ProtectKernelTunables=true
RestrictSUIDSGID=true

[Install]
WantedBy=multi-user.target
"""


def ячейки() -> list[dict]:
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    итог = []
    for c in данные.get("cells") or []:
        р = c.get("runtime") or {}
        unit, учётка, порт = р.get("unit"), р.get("account"), р.get("port")
        if not (unit and учётка and порт):
            continue
        # Юнит монолита не создаётся: он принадлежит прежней установке, и файл
        # с таким именем там уже есть. Признак — он же стоит в previous_unit
        # какой-нибудь ячейки, либо ячейка ещё не описана своей службой.
        итог.append({"site_id": c["site_id"], "domain": c.get("domain") or c["site_id"],
                     "unit": unit, "account": учётка, "port": int(порт)})
    return итог


def написать(путь: Path, тело: str, сухой: bool) -> str:
    # Существующий файл НЕ переписывается, даже если отличается. Он чья-то
    # работающая конфигурация: у zona-01 и трёх Lords юниты стоят с переноса,
    # и подгонять их под мой шаблон значило бы менять чужие службы ради
    # единообразия. Сценарий закрывает ровно одну дыру — отсутствие файла.
    if путь.exists():
        return "уже есть, не трогаю"
    if сухой:
        return "поставил бы"
    путь.write_text(тело, encoding="utf-8")
    путь.chmod(0o644)
    return "записан"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--dry-run", action="store_true")
    a = р.parse_args()
    if not a.dry_run and os.geteuid() != 0:
        print("нужен root", file=sys.stderr)
        return 2

    изменено = 0
    for я in ячейки():
        основной = ЮНИТЫ / я["unit"]
        кандидат = ЮНИТЫ / я["unit"].replace(".service", "-candidate.service")
        тело_о = ШАБЛОН.format(домен=я["domain"], учётка=я["account"],
                               каталог="current", порт=я["port"])
        тело_к = ШАБЛОН.format(домен=я["domain"], учётка=я["account"],
                               каталог="candidate", порт=я["port"] + 1000)
        и_о = написать(основной, тело_о, a.dry_run)
        и_к = написать(кандидат, тело_к, a.dry_run)
        изменено += (и_о == "записан") + (и_к == "записан")
        print(f"{я['site_id']:12} {я['domain']:22} порт {я['port']}/{я['port'] + 1000}")
        print(f"   {основной.name}: {и_о}")
        print(f"   {кандидат.name}: {и_к}")

    if a.dry_run:
        print("\nсухой прогон завершён: существующие файлы не трогались")
        return 0
    if изменено:
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        print(f"\nперечитано; изменено файлов: {изменено}")
    else:
        print("\nвсё уже на месте, ничего не менялось")
    print("Ни одна служба не включена и не запущена: это делает исполнитель.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
