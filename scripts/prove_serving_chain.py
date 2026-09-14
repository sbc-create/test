#!/usr/bin/env python3
"""Кто на самом деле отдаёт публичный домен: цепочка от имени до файла.

Имя юнита НЕ выводится из имени сайта. Совпадение `lords-01` → `lords-01.service`
выглядит очевидным и неверно: `lords-01.service` слушает 9101 и публично не
проксируется вовсе, а домен обслуживает `lords-nova-01.service` на 9110. Ровно на
этом допущении предыдущие кандидаты и оказались невидимыми.

Поэтому цепочка строится по фактам и только по ним:

    домен  → server_name в конфиге nginx
           → proxy_pass в его location /
           → порт
           → юнит, чей ExecStart слушает этот порт
           → исполняемый файл из ExecStart и его отпечаток
           → манифест из Environment юнита
           → то, что домен объявляет о себе в заголовках ответа

Последнее звено замыкает круг: если заголовки живого ответа не совпали с
манифестом, который читает найденный юнит, значит найден не тот юнит.

Скрипт только читает. Ни одной записи, кроме отчёта.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

NGINX = (Path("/etc/nginx/lords"), Path("/etc/nginx/sites-enabled"), Path("/etc/nginx/conf.d"))
SERVER_NAME = re.compile(r"server_name\s+([^;]+);")
PROXY = re.compile(r"location\s+/\s*\{[^}]*?proxy_pass\s+http://127\.0\.0\.1:(\d+)", re.S)
EXEC = re.compile(r"^ExecStart=(.*)$", re.M)
ENVLINE = re.compile(r"^Environment=([A-Z_]+)=(.*)$", re.M)
PORTARG = re.compile(r"--port\s+(\d+)|LORDS_PORT=(\d+)")


def конфиги() -> list[Path]:
    найдено = []
    for каталог in NGINX:
        if каталог.is_dir():
            найдено += [p for p in sorted(каталог.glob("*.conf")) if ".bak" not in p.name]
            найдено += [p for p in sorted(каталог.iterdir())
                        if p.is_file() and p.suffix == "" and ".bak" not in p.name]
    return найдено


def конфиг_домена(домен: str):
    """Файл, который объявляет этот домен, и порт его основного location."""
    for путь in конфиги():
        try:
            текст = путь.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        имена = {и for кусок in SERVER_NAME.findall(текст) for и in кусок.split()}
        if домен not in имена:
            continue
        порты = PROXY.findall(текст)
        if порты:
            return путь, int(порты[-1])
    return None, None


def юниты() -> dict:
    """Все юниты с их ExecStart и окружением. Читается через systemctl show,
    а не разбором каталога: drop-in может переопределить и то, и другое."""
    вывод = subprocess.run(["systemctl", "list-units", "--type=service", "--all",
                            "--no-legend", "--plain"],
                           capture_output=True, text=True, timeout=60).stdout
    найденные = {}
    for строка in вывод.splitlines():
        имя = строка.split()[0] if строка.split() else ""
        if not имя.endswith(".service"):
            continue
        показ = subprocess.run(
            ["systemctl", "cat", имя], capture_output=True, text=True, timeout=30).stdout
        if not показ:
            continue
        найденные[имя] = показ
    return найденные


def юнит_на_порту(порт: int, все: dict):
    подходящие = []
    for имя, текст in все.items():
        совпало = EXEC.search(текст)
        if not совпало:
            continue
        строка = совпало.group(1)
        окружение = dict(ENVLINE.findall(текст))
        порты = set()
        for a, b in PORTARG.findall(строка + "\n" + "\n".join(
                f"{k}={v}" for k, v in окружение.items())):
            порты.add(int(a or b))
        if порт in порты:
            подходящие.append((имя, строка, окружение))
    return подходящие


#: Единственный исполняемый файл, который юнит витрины имеет право запускать.
#: Он общий на весь парк; версию оформления выбирает манифест витрины.
ОБЩИЙ_АРТЕФАКТ = "/srv/lords/.frontend/lords-frontend.py"


def отпечаток(путь: Path) -> str:
    try:
        return hashlib.sha256(путь.read_bytes()).hexdigest()
    except OSError:
        return ""


def объявление(домен: str) -> dict:
    адрес = f"https://{домен}/__template_version"
    try:
        запрос = urllib.request.Request(адрес, headers={"User-Agent": "chain-prover"})
        with urllib.request.urlopen(запрос, timeout=30) as ответ:
            тело = json.loads(ответ.read().decode("utf-8", "replace"))
            заголовки = {
                "artifact": ответ.headers.get("X-Site-Factory-Artifact-Sha256", ""),
                "version": ответ.headers.get("X-Site-Factory-Template-Version", ""),
                "build": ответ.headers.get("X-Site-Factory-Build-Id", ""),
            }
            return {"ok": True, "body": тело, "headers": заголовки}
    except Exception as ош:  # noqa: BLE001
        return {"ok": False, "error": str(ош)[:140]}


def замыкание(цепь: dict) -> tuple[bool, list]:
    """Замкнулся ли круг «домен → nginx → порт → юнит → файл → манифест → ответ».

    Чего здесь больше нет и почему. Прежде одним из условий стояло
    `executable_sha256 == manifest.artifact_sha256`, то есть отпечаток ФАЙЛА
    сверялся с отпечатком РЕЛИЗА. В парке исполняемый файл ОДИН на все витрины,
    а манифест — свой у каждой, и ветку отрисовки выбирает именно манифест. Как
    только соседняя витрина выкачена вперёд, общий файл законно принадлежит
    другой сборке, чем объявляет эта витрина, и условие обращалось в MISMATCH на
    полностью исправной цепочке. Отпечаток файла остаётся в отчёте уликой, но
    выводом о релизе не является, а расхождение названо отдельным полем.

    Взамен условий стало больше, а не меньше: сверяются все три объявленных поля
    вместо двух, и добавлены путь исполняемого файла и активность юнита.
    Невыполненные условия перечисляются поимённо: провал обязан быть назван.
    """
    манифест = цепь.get("manifest") or {}
    заголовки = (цепь.get("served") or {}).get("headers") or {}

    def совпало(отданное, объявленное) -> bool:
        """Пустое не равно пустому: отсутствие значения — не доказательство."""
        return bool(отданное) and отданное == объявленное

    условия = {
        "домен ответил": bool((цепь.get("served") or {}).get("ok")),
        "отданный артефакт = манифест юнита":
            совпало(заголовки.get("artifact"), манифест.get("artifact_sha256")),
        "отданная сборка = манифест юнита":
            совпало(заголовки.get("build"), манифест.get("build_id")),
        "отданная версия = манифест юнита":
            совпало(заголовки.get("version"), манифест.get("design_version")),
        "юнит исполняет общий артефакт парка":
            цепь.get("executable") == ОБЩИЙ_АРТЕФАКТ,
        "юнит активен":
            (цепь.get("unit_state") or {}).get("ActiveState") == "active",
    }
    невыполненные = sorted(и for и, ок in условия.items() if not ок)
    return (not невыполненные), невыполненные


def цепочка(домен: str, все_юниты: dict) -> dict:
    итог = {"domain": домен}
    конфиг, порт = конфиг_домена(домен)
    итог["nginx_config"] = str(конфиг) if конфиг else ""
    итог["upstream_port"] = порт
    if порт is None:
        итог["verdict"] = "NO_UPSTREAM"
        return итог
    кандидаты = юнит_на_порту(порт, все_юниты)
    итог["units_listening_on_port"] = [и for и, _, _ in кандидаты]
    if len(кандидаты) != 1:
        итог["verdict"] = "AMBIGUOUS_UNIT" if кандидаты else "NO_UNIT"
        return итог
    имя, execstart, окружение = кандидаты[0]
    итог["unit"] = имя
    итог["exec_start"] = execstart
    # Исполняемый файл — последний аргумент .py в ExecStart, а не первый токен:
    # первым идёт интерпретатор.
    файлы = [т for т in execstart.split() if т.endswith(".py")]
    исполняемый = Path(файлы[-1]) if файлы else None
    итог["executable"] = str(исполняемый) if исполняемый else ""
    итог["executable_sha256"] = отпечаток(исполняемый) if исполняемый else ""
    # Юнит вправе НЕ задавать манифест: рантайм тогда читает свой умолчательный
    # путь. `lords-nova-01.service` именно такой, и это единственный такой юнит
    # во всём парке — проверено перебором. Считать «манифеста нет» значило бы
    # объявить цепочку недоказанной там, где она доказуема.
    манифест = окружение.get("LORDS_TEMPLATE_MANIFEST", "")
    if not манифест and исполняемый and исполняемый.is_file():
        умолчание = re.search(
            r'LORDS_TEMPLATE_MANIFEST["\']?\s*,\s*\n?\s*["\']([^"\']+)["\']',
            исполняемый.read_text(encoding="utf-8", errors="replace"))
        if умолчание:
            манифест = умолчание.group(1)
            итог["manifest_from"] = "умолчание рантайма (юнит его не задаёт)"
    итог["manifest_path"] = манифест
    if манифест and Path(манифест).is_file():
        итог["manifest"] = json.loads(Path(манифест).read_text(encoding="utf-8"))
        итог["manifest_sha256"] = отпечаток(Path(манифест))
    итог["catalog_path"] = окружение.get("LORDS_CATALOG", "")
    итог["site_name"] = окружение.get("LORDS_SITE_NAME", "")
    состояние = subprocess.run(
        ["systemctl", "show", имя, "-p", "MainPID,ActiveState,NRestarts,FragmentPath"],
        capture_output=True, text=True, timeout=30).stdout
    итог["unit_state"] = dict(
        с.split("=", 1) for с in состояние.strip().splitlines() if "=" in с)
    живое = объявление(домен)
    итог["served"] = живое
    # Замыкание круга: живой ответ обязан совпасть с манифестом, который читает
    # найденный юнит, ПО ВСЕМ трём объявленным полям, а сам юнит — исполнять
    # ожидаемый файл и быть активным.
    #
    # Чего здесь больше нет и почему. Прежде последним условием стояло
    # `executable_sha256 == manifest.artifact_sha256`, то есть отпечаток ФАЙЛА
    # сверялся с отпечатком РЕЛИЗА. В парке исполняемый файл ОДИН на все
    # витрины, а манифест — свой у каждой, и версию оформления выбирает именно
    # манифест. Как только соседняя витрина выкачена вперёд, общий файл
    # законно принадлежит другой сборке, чем объявляет эта витрина, и условие
    # обращалось в MISMATCH на полностью исправной цепочке. Отпечаток файла
    # остаётся в отчёте как улика, но выводом о релизе не является: их
    # расхождение названо отдельным полем, а не спрятано.
    итог["executable_is_manifest_build"] = (
        итог["executable_sha256"] == (итог.get("manifest") or {}).get("artifact_sha256"))
    итог["shared_executable_note"] = (
        "" if итог["executable_is_manifest_build"] else
        "общий файл парка принадлежит другой сборке, чем объявляет манифест этой "
        "витрины; версию оформления выбирает манифест")
    итог["closes_loop"], итог["unmet"] = замыкание(итог)
    итог["verdict"] = "PROVEN" if итог["closes_loop"] else "MISMATCH"
    return итог


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domain", action="append", required=True)
    р.add_argument("--out", required=True)
    арг = р.parse_args(argv)
    все = юниты()
    отчёт = {
        "taken_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "units_scanned": len(все),
        "chains": [цепочка(д, все) for д in арг.domain],
    }
    Path(арг.out).write_text(json.dumps(отчёт, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
    for ц in отчёт["chains"]:
        print(f"{ц['verdict']:<14} {ц['domain']}")
        print(f"   nginx    {ц.get('nginx_config','—')}  → 127.0.0.1:{ц.get('upstream_port')}")
        print(f"   unit     {ц.get('unit','—')}  (PID {ц.get('unit_state',{}).get('MainPID','?')}, "
              f"перезапусков {ц.get('unit_state',{}).get('NRestarts','?')})")
        print(f"   файл     {ц.get('executable','—')}")
        print(f"            sha256 {(ц.get('executable_sha256') or '—')[:16]}"
              + ("" if ц.get("executable_is_manifest_build")
                 else "  (общий файл парка — сборка другой витрины)"))
        м = ц.get("manifest") or {}
        print(f"   манифест {ц.get('manifest_path','—')}")
        print(f"            версия {м.get('design_version','—')} build {м.get('build_id','—')}")
        print(f"   отдаёт   версия {(ц.get('served',{}).get('headers') or {}).get('version','—')} "
              f"артефакт {((ц.get('served',{}).get('headers') or {}).get('artifact') or '—')[:16]}")
    print(f"\nотчёт: {арг.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
