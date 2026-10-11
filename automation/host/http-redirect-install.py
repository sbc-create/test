#!/usr/bin/env python3
"""Перенаправление http → https в блоках `:80` названных доменов. Root.

Повод. Девять доменов сети отдают `200` по http: animedia.icu, animedia.space,
an1meg0.site, lordserials22.info, zonafilm.cc, zonafilm.space, zonafilm12.site,
yummyani7.site, yummyani7.info. Это два адреса одной страницы — дубль для
поиска. У остальных восьми перенаправление уже стоит, и правка повторяет именно
их образец (`lords-01`): в блоке `:80` тело `location /` заменяется на
`return 308 https://$host$request_uri;`.

Чего правка НЕ делает:

* **не трогает путь ACME.** `location ^~ /.well-known/acme-challenge/` остаётся
  как есть и проверяется до изменения: «перенаправлять всё подряд» сломало бы
  продление сертификата. Если пути ACME в блоке нет — отказ, а не правка;
* не трогает блоки `:443`, прочие `location`, TLS, upstream и заголовки;
* не трогает домены, которые уже перенаправляют;
* ничего не пишет без `--apply`.

Откат (`--rollback`) возвращает файлы из копий, снятых этой же правкой.

    python3 automation/host/http-redirect-install.py --dry-run
    sudo python3 automation/host/http-redirect-install.py --apply
    sudo python3 automation/host/http-redirect-install.py --rollback
"""
from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

NGINX = Path("/etc/nginx")
МЕТКА = "http-redirect"
ЗАМЕНА = "            return 308 https://$host$request_uri;"
ПУТЬ_ACME = "/.well-known/acme-challenge/"
ДОМЕНЫ = ("animedia.icu", "animedia.space", "an1meg0.site",
          "lordserials22.info", "zonafilm.cc", "zonafilm.space",
          "zonafilm12.site", "yummyani7.site", "yummyani7.info")


def блоки_сервера(текст: str) -> list[tuple[int, int]]:
    """Границы каждого `server { … }` — по счёту фигурных скобок."""
    итог = []
    for м in re.finditer(r"\bserver\s*\{", текст):
        глубина, i = 0, м.start()
        while i < len(текст):
            if текст[i] == "{":
                глубина += 1
            elif текст[i] == "}":
                глубина -= 1
                if глубина == 0:
                    итог.append((м.start(), i + 1))
                    break
            i += 1
    return итог


def найти_блок(текст: str, домен: str) -> tuple[int, int] | None:
    """Блок, который слушает :80 и обслуживает этот домен."""
    for начало, конец in блоки_сервера(текст):
        блок = текст[начало:конец]
        if not re.search(r"listen\s+(\[::\]:)?80\b", блок):
            continue
        имена = re.search(r"server_name\s+([^;]+);", блок)
        if имена and домен in имена.group(1).split():
            return начало, конец
    return None


def правка(текст: str, домен: str) -> tuple[str, str]:
    """Новый текст файла и причина отказа (одно из двух непусто)."""
    место = найти_блок(текст, домен)
    if not место:
        return "", f"в файле нет блока :80 для {домен}"
    начало, конец = место
    блок = текст[начало:конец]
    if "return 308 https://" in блок:
        return "", "перенаправление уже стоит"
    if ПУТЬ_ACME not in блок:
        return "", (f"в блоке :80 нет {ПУТЬ_ACME} — перенаправление сломало бы "
                    "продление сертификата")
    # Заменяется ТЕЛО `location /`, а не весь блок: остальные location
    # (healthz, ACME) остаются как есть.
    м = re.search(r"(\n(\s*)location\s+/\s*\{)(.*?)(\n\2\})", блок, re.S)
    if not м:
        return "", "в блоке :80 не нашёлся location / с телом"
    # Отступ берётся у самого `location`, чтобы файл остался ровным.
    замена = f"\n{м.group(2)}    {ЗАМЕНА.strip()}"
    новый_блок = блок[:м.start(3)] + замена + блок[м.end(3):]
    return текст[:начало] + новый_блок + текст[конец:], ""


def файлы_домена(домен: str) -> list[Path]:
    итог = []
    for путь in sorted(NGINX.rglob("*.conf")):
        if ".bak" in путь.name or f".before-{МЕТКА}" in путь.name:
            continue
        try:
            текст = путь.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if найти_блок(текст, домен):
            итог.append(путь)
    return итог


def главное(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="перенаправление http → https")
    р.add_argument("--domain", action="append",
                   help="домен; по умолчанию все девять без перенаправления")
    р.add_argument("--apply", action="store_true")
    р.add_argument("--rollback", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args(аргв)
    домены = tuple(а.domain) if а.domain else ДОМЕНЫ
    меняем = а.apply or а.rollback
    if меняем and os.geteuid() != 0:
        print("нужен root: правятся файлы в /etc/nginx", file=sys.stderr)
        return 2

    if а.rollback:
        возвращено = 0
        for путь in sorted(NGINX.rglob(f"*.before-{МЕТКА}.*")):
            цель = Path(str(путь).split(f".before-{МЕТКА}.")[0])
            shutil.copyfile(путь, цель)
            print(f"   возвращено {цель} из {путь.name}")
            возвращено += 1
        if not возвращено:
            print("копий этой правки не найдено — откатывать нечего")
            return 0
        if subprocess.run(["nginx", "-t"]).returncode != 0:
            print("nginx -t не прошёл ПОСЛЕ откат — разбирать руками",
                  file=sys.stderr)
            return 1
        subprocess.run(["systemctl", "reload", "nginx"], check=False)
        print(f"откат выполнен: файлов {возвращено}")
        return 0

    метка_времени = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    изменённые: list[tuple[Path, str, str]] = []
    отказы: list[tuple[str, str]] = []
    for домен in домены:
        файлы = файлы_домена(домен)
        if not файлы:
            отказы.append((домен, "файла с блоком :80 не нашлось"))
            continue
        for путь in файлы:
            было = путь.read_text(encoding="utf-8")
            стало, причина = правка(было, домен)
            if причина:
                отказы.append((f"{домен} ({путь.name})", причина))
                continue
            изменённые.append((путь, было, стало))
            print(f"=== {домен}: {путь}")
            for с in difflib.unified_diff(
                    было.splitlines(), стало.splitlines(),
                    "до", "после", lineterm="", n=2):
                if с.startswith(("+", "-", "@")):
                    print("   ", с)

    for имя, причина in отказы:
        print(f"   [отказ] {имя}: {причина}")

    if not а.apply:
        print(f"\nизменилось бы файлов: {len(изменённые)}, отказов: {len(отказы)}")
        print("это план; для исполнения — sudo … --apply")
        return 0 if изменённые else 1

    копии = []
    for путь, было, стало in изменённые:
        копия = Path(f"{путь}.before-{МЕТКА}.{метка_времени}")
        shutil.copyfile(путь, копия)
        копии.append((путь, копия))
        путь.write_text(стало, encoding="utf-8")
        print(f"   правлено {путь} (копия {копия.name})")
    если_сломалось = subprocess.run(["nginx", "-t"])
    if если_сломалось.returncode != 0:
        print("nginx -t НЕ прошёл — возвращаю файлы", file=sys.stderr)
        for путь, копия in копии:
            shutil.copyfile(копия, путь)
        return 1
    subprocess.run(["systemctl", "reload", "nginx"], check=True)
    print(f"\nправлено файлов: {len(изменённые)}; nginx проверен и перезагружен")
    print("проверить: python3 automation/local/http-redirect-audit.py")
    print(f"откат: sudo python3 {Path(__file__).name} --rollback")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
