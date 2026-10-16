#!/usr/bin/env python3
"""Готовность восьми витрин K2 к трафику — по публичному имени, а не по узлу.

Зачем. Код партии собран и сверен на узле, но трафик физически невозможен,
пока публичное имя не ведёт на свой контур с правильным сертификатом. SEO и
эта линия назвали РАЗНЫЕ симптомы (421 и «сертификат не на домен, HTTP 404»),
поэтому замер один и тот же для всех восьми и печатает причину дословно.

Проверяется по каждому домену:

  A-запись        куда ведёт имя (dig, без догадок)
  TLS             чьё имя в сертификате и до какого числа
  HTTPS главная   код и чем представился сервер (заголовки витрины)
  HTTP главная    код без TLS
  каталог         код /catalog/ или /serialy/ — есть ли что индексировать

Инструмент НИЧЕГО не меняет: ни DNS, ни сертификаты, ни nginx, ни режим
индексации. Это измерение для отчёта владельцу.

    python3 automation/local/k2-readiness.py
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ПАРТИЯ_K2 = "k2-zomro-01"


def домены_партии() -> list[str]:
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    итог = []
    for я in д["cells"]:
        if ПАРТИЯ_K2 in json.dumps(я, ensure_ascii=False):
            итог.append(я["domain"])
    return sorted(set(итог))


def команда(аргв: list[str], таймаут: int = 25) -> str:
    try:
        г = subprocess.run(аргв, capture_output=True, text=True, timeout=таймаут)
        return (г.stdout or "") + (г.stderr or "")
    except subprocess.TimeoutExpired:
        return "ТАЙМАУТ"


def адрес(домен: str) -> str:
    вывод = команда(["dig", "+short", "A", домен], 20).strip().splitlines()
    адреса = [с for с in вывод if re.fullmatch(r"[0-9.]+", с.strip())]
    return ",".join(адреса) or "нет A-записи"


def сертификат(домен: str) -> str:
    вывод = команда(
        ["curl", "-sv", "-o", "/dev/null", "--max-time", "15", f"https://{домен}/"], 30)
    кому = re.search(r"subject: .*?CN=([^\s;]+)", вывод)
    до = re.search(r"expire date: ([^\n]+)", вывод)
    ошибка = re.search(r"(SSL certificate problem[^\n]*|SSL_ERROR[^\n]*|"
                       r"schannel[^\n]*|unable to get local issuer[^\n]*)", вывод)
    части = []
    if кому:
        части.append(f"CN={кому.group(1)}")
    if до:
        части.append(f"до {до.group(1).strip()[:20]}")
    if ошибка:
        части.append(ошибка.group(1)[:60])
    return "; ".join(части) or "сертификат не прочитан"


def код(url: str, таймаут: int = 20) -> tuple[int, str]:
    г = subprocess.run(
        ["curl", "-sk", "-o", "/dev/null", "-D", "-", "-w", "\n%{http_code}",
         "--max-time", str(таймаут), url],
        capture_output=True, text=True, timeout=таймаут + 15)
    весь = г.stdout or ""
    части = весь.rsplit("\n", 1)
    к = int(части[-1]) if части[-1].strip().isdigit() else 0
    м = re.search(r"(?im)^x-site-factory-template:\s*(.+)$", части[0])
    return к, (м.group(1).strip() if м else "")


def по_домену(домен: str) -> dict:
    к_https, шаблон = код(f"https://{домен}/")
    к_http, _ = код(f"http://{домен}/")
    к_каталог, _ = код(f"https://{домен}/serialy/")
    if к_каталог in (0, 404):
        к2, _ = код(f"https://{домен}/catalog/")
        if к2 not in (0, 404):
            к_каталог = к2
    return {
        "домен": домен,
        "адрес": адрес(домен),
        "tls": сертификат(домен),
        "https": к_https,
        "http": к_http,
        "шаблон": шаблон,
        "каталог": к_каталог,
    }


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--domain", action="append", default=[])
    опции = р.parse_args(аргв)

    домены = опции.domain or домены_партии()
    print(f"витрин партии {ПАРТИЯ_K2}: {len(домены)}\n")
    with ThreadPoolExecutor(4) as ex:
        итоги = list(ex.map(по_домену, домены))

    print(f"{'домен':22s} {'A-запись':18s} {'https':>5s} {'http':>5s} "
          f"{'каталог':>7s} {'шаблон витрины':22s} сертификат")
    готовы = 0
    for и in sorted(итоги, key=lambda x: x["домен"]):
        print(f"{и['домен']:22s} {и['адрес'][:18]:18s} {и['https']:5d} "
              f"{и['http']:5d} {и['каталог']:7d} {(и['шаблон'] or '—')[:22]:22s} "
              f"{и['tls'][:70]}")
        if и["https"] == 200 and и["каталог"] == 200 and "CN=" in и["tls"] \
                and и["домен"] in и["tls"]:
            готовы += 1
    print(f"\nготовы принимать трафик: {готовы} из {len(итоги)}")
    print("измерение не меняет ни DNS, ни TLS, ни nginx, ни режим индексации")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
