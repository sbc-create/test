#!/usr/bin/env python3
"""Фактическая цепочка выпуска по домену: DNS → nginx/TLS → служба → приложение → репозиторий.

Зачем. «Сайт выпущен» — это не одно состояние, а семь, и отказ на любом звене
выглядит снаружи одинаково: страница не открывается. Прошлые отчёты называли
причиной то звено, на котором остановилась проверка, а не то, которое сломано:
502 объявляли «нет конфигурации nginx», хотя конфигурация была, а не слушал
процесс. Здесь каждое звено измеряется отдельно и печатается своим словом.

Ничего не меняет: только читает. Секретов не касается.
"""

from __future__ import annotations

import argparse
import http.client
import json
import socket
import ssl
import subprocess
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
АНАЛИТИКА = КОРЕНЬ / "config" / "analytics.json"
ОТЧЁТ_TOPVISOR = КОРЕНЬ / "var" / "topvisor" / "check-latest.txt"
NGINX = Path("/etc/nginx")
ЮНИТЫ = Path("/etc/systemd/system")


def _ячейки() -> dict[str, dict]:
    return {c["domain"]: c for c in json.loads(РЕЕСТР.read_text(encoding="utf-8"))["cells"]}


def _счётчики() -> dict[str, object]:
    return {
        з["domain"]: з.get("counter_id")
        for з in json.loads(АНАЛИТИКА.read_text(encoding="utf-8"))["properties"]
    }


def _проекты() -> dict[str, int]:
    import re

    итог: dict[str, int] = {}
    if ОТЧЁТ_TOPVISOR.is_file():
        for строка in ОТЧЁТ_TOPVISOR.read_text(encoding="utf-8").splitlines():
            с = re.match(r"^\s*#(\d+)\s+(\S+)\s+—", строка)
            if с:
                итог.setdefault(с.group(2), int(с.group(1)))
    return итог


def dns(домен: str) -> str:
    try:
        адреса = sorted({и[4][0] for и in socket.getaddrinfo(домен, None, socket.AF_INET)})
    except OSError:
        делегирование = subprocess.run(
            ["dig", "+short", "NS", домен], capture_output=True, text=True, timeout=20
        ).stdout.strip()
        return "НЕТ ДЕЛЕГИРОВАНИЯ" if not делегирование else "нет A (зона есть)"
    return ",".join(адреса)


def http_состояние(домен: str) -> tuple[str, str, str]:
    """HTTP, HTTPS и build-id из заголовка. Три отдельных измерения."""
    итог = {}
    build = ""
    for схема, порт in (("http", 80), ("https", 443)):
        try:
            if схема == "https":
                c = http.client.HTTPSConnection(
                    домен, порт, timeout=8, context=ssl.create_default_context()
                )
            else:
                c = http.client.HTTPConnection(домен, порт, timeout=8)
            c.request("GET", "/", headers={"Host": домен, "User-Agent": "site-factory-chain"})
            r = c.getresponse()
            итог[схема] = str(r.status)
            build = build or r.headers.get("X-Site-Factory-Build-Id", "")
            r.read(1)
            c.close()
        except ssl.SSLCertVerificationError:
            итог[схема] = "чужой сертификат"
        except OSError as e:
            итог[схема] = f"{type(e).__name__}"
    return итог.get("http", "?"), итог.get("https", "?"), build


def слушает(порт: int | None) -> str:
    if not порт:
        return "порт не объявлен"
    s = socket.socket()
    s.settimeout(3)
    try:
        s.connect(("127.0.0.1", порт))
        s.close()
        return f"слушает :{порт}"
    except OSError:
        return f"НЕ СЛУШАЕТ :{порт}"


def конфигурация_nginx(домен: str) -> str:
    """Ищется по server_name, а не по имени файла: файл мог быть назван иначе."""
    найдено = []
    for путь in NGINX.rglob("*.conf"):
        try:
            текст = путь.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for строка in текст.splitlines():
            голая = строка.strip()
            if голая.startswith("server_name") and домен in голая.split():
                найдено.append(путь.name)
                break
    return ",".join(sorted(set(найдено))) or "НЕТ server_name"


def сертификат(домен: str) -> str:
    # Каталог сертификатов закрыт для непривилегированной учётной записи, и
    # `.exists()` там выбрасывает PermissionError, а не возвращает False. Без
    # этой ветки инструмент падал на первом же домене. «Нет сертификата» и «не
    # могу проверить» — разные ответы: первый требует выпуска сертификата,
    # второй — только прав, и путать их значит гнаться за несуществующей
    # проблемой. Ровно эту ошибку пришлось исправлять в двух модулях учётных
    # данных сегодня же.
    корень = Path("/etc/letsencrypt/live") / домен
    try:
        return "есть" if (корень / "fullchain.pem").exists() else "нет"
    except PermissionError:
        return "не проверено (нет прав на /etc/letsencrypt)"


def юнит(ячейка: dict) -> str:
    # Имя юнита и каталоги объявлены в блоке `runtime` реестра. Первая версия
    # искала их в `deployment.serving_unit`, которого у этих ячеек нет, и честно
    # печатала «имя не объявлено» у работающей витрины — то есть искала не там.
    имя = ((ячейка.get("runtime") or {}).get("unit")
           or (ячейка.get("deployment") or {}).get("serving_unit") or "")
    if not имя:
        return "имя не объявлено"
    return f"{имя}: {'файл есть' if (ЮНИТЫ / имя).exists() else 'ФАЙЛА НЕТ'}"


def каталог_ячейки(ячейка: dict) -> str:
    app = (ячейка.get("runtime") or {}).get("app_dir") or ""
    корень = str(Path(app).parent) if app else f"/srv/{ячейка.get('site_id', '')}"
    п = Path(корень)
    if not п.exists():
        return f"НЕТ {корень}"
    ссылка = п / "current"
    выпуски = п / "releases"
    сколько = len(list(выпуски.iterdir())) if выпуски.is_dir() else 0
    цель = ссылка.resolve().name if ссылка.exists() else "нет current"
    return f"{корень}: выпусков {сколько}, current → {цель}"


def репозиторий(ячейка: dict) -> str:
    путь = КОРЕНЬ / ((ячейка.get("repo") or {}).get("path") or "")
    if not (ячейка.get("repo") or {}).get("path"):
        return "путь не объявлен"
    if not (путь / ".git").exists():
        return f"НЕТ рабочей копии {путь.relative_to(КОРЕНЬ)}"
    ветка = subprocess.run(
        ["git", "-C", str(путь), "branch", "--show-current"], capture_output=True, text=True
    ).stdout.strip()
    коммит = subprocess.run(
        ["git", "-C", str(путь), "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    грязь = subprocess.run(
        ["git", "-C", str(путь), "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    return f"{ветка}@{коммит}" + (" (есть незакоммиченное)" if грязь else "")


def main(argv: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    р.add_argument("domains", nargs="+")
    а = р.parse_args(argv)

    ячейки, счётчики, проекты = _ячейки(), _счётчики(), _проекты()
    for домен in а.domains:
        ячейка = ячейки.get(домен)
        h, s, build = http_состояние(домен)
        print(f"\n=== {домен} ===")
        if ячейка is None:
            print("  в реестре ячеек ЗАПИСИ НЕТ")
        else:
            порт = (ячейка.get("runtime") or {}).get("port") or ячейка.get("port")
            print(
                f"  site_id={ячейка.get('site_id')}  шаблон="
                f"{(ячейка.get('template') or {}).get('template_id')}  порт={порт}"
            )
            print(f"  репозиторий : {репозиторий(ячейка)}")
            print(f"  каталог     : {каталог_ячейки(ячейка)}")
            print(f"  юнит        : {юнит(ячейка)}")
            print(f"  приложение  : {слушает(порт)}")
        print(f"  DNS         : {dns(домен)}")
        print(f"  nginx       : {конфигурация_nginx(домен)}   сертификат: {сертификат(домен)}")
        print(f"  HTTP/HTTPS  : {h} / {s}   build-id: {build or 'нет заголовка'}")
        print(
            f"  Метрика     : {счётчики.get(домен, 'нет записи в реестре')}"
            f"   Topvisor: {проекты.get(домен, 'нет в списке аккаунта')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
