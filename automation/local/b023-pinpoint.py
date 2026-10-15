#!/usr/bin/env python3
"""B023: где именно отказывает доступ к `api.webmaster.yandex.net:443`.

Задание владельца: «установи точное место отказа… формулировки „откройте
доступ“ без установленной причины недостаточно». Поэтому проверяется не
«работает/не работает», а РАЗНИЦА между соседними случаями:

* тот же адрес на другом порту — отличает фильтр по порту от фильтра по адресу;
* другой адрес в ТОЙ ЖЕ подсети /24 — отличает отказ службы от отказа
  маршрута к префиксу;
* адрес другой подсети того же владельца (Метрика) — показывает, что сеть до
  Яндекса в целом работает;
* те же адреса из второго узла у другого провайдера — отличает нашу
  конфигурацию от внешней.

Соединение проверяется на уровне TCP (`socket.connect`), а не curl: нужен
именно момент установления, без TLS и HTTP.

Ничего не меняет. Адреса берутся из DNS, список хостов — из
`inventory/network-allowlist.yaml`, то есть из разрешённого задания.

    python3 automation/local/b023-pinpoint.py
"""
from __future__ import annotations

import json
import socket
import subprocess
import time
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ТАЙМАУТ = 6.0

ХОСТЫ = [
    "api.webmaster.yandex.net",
    "api-metrika.yandex.net",
    "yandex.ru",
    "ya.ru",
    "passport.yandex.ru",
]


def адреса(хост: str) -> list[str]:
    try:
        сведения = socket.getaddrinfo(хост, None, socket.AF_INET)
    except OSError:
        return []
    return sorted({с[4][0] for с in сведения})


def соединение(адрес: str, порт: int) -> tuple[bool, float, str]:
    с = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    с.settimeout(ТАЙМАУТ)
    т0 = time.monotonic()
    try:
        с.connect((адрес, порт))
        return True, time.monotonic() - т0, ""
    except Exception as сбой:  # noqa: BLE001 — нужен сам факт и его имя
        return False, time.monotonic() - т0, type(сбой).__name__
    finally:
        с.close()


def главное() -> int:
    карта: dict[str, list[str]] = {х: адреса(х) for х in ХОСТЫ}
    print("DNS:")
    for х, а in карта.items():
        print(f"  {х:30s} {', '.join(а) or 'не разрешается'}")

    цель = карта.get("api.webmaster.yandex.net") or []
    if not цель:
        print("\nимя не разрешается — дальше мерить нечего")
        return 2
    ip = цель[0]
    сеть = ".".join(ip.split(".")[:3])
    print(f"\nцель: {ip} (подсеть {сеть}.0/24)")

    print("\n1. тот же адрес, разные порты:")
    for порт in (443, 80, 22):
        ок, сек, беда = соединение(ip, порт)
        print(f"   {ip}:{порт:<4} {'установлено' if ок else 'отказ':12s} "
              f"{сек:.2f} с {беда}")

    print(f"\n2. другие адреса ТОЙ ЖЕ подсети {сеть}.0/24 "
          "(из DNS соседних имён):")
    соседи = sorted({а for х, сп in карта.items() for а in сп
                     if а.startswith(сеть + ".") and а != ip})
    if not соседи:
        print("   соседних адресов этой подсети в DNS проверяемых имён нет — "
              "НЕ ИЗМЕРЕНО")
    for а in соседи:
        ок, сек, беда = соединение(а, 443)
        print(f"   {а}:443 {'установлено' if ок else 'отказ':12s} "
              f"{сек:.2f} с {беда}")

    print("\n3. адреса других подсетей того же владельца:")
    for х, сп in карта.items():
        for а in сп:
            if а.startswith(сеть + "."):
                continue
            ок, сек, беда = соединение(а, 443)
            print(f"   {х:26s} {а:16s} "
                  f"{'установлено' if ок else 'отказ':12s} {сек:.2f} с {беда}")

    print("\n4. тот же замер со ВТОРОГО узла (другой провайдер):")
    инв = КОРЕНЬ / "var" / "ansible" / "hosts.yml"
    if not инв.is_file():
        print("   инвентаря ansible нет — НЕ ИЗМЕРЕНО")
        return 0
    код = (
        "import socket,time\n"
        f"for a,p in (('{ip}',443),('{ip}',80),"
        "('87.250.251.47',443)):\n"
        "    s=socket.socket(); s.settimeout(6); t=time.monotonic()\n"
        "    try:\n"
        "        s.connect((a,p)); print(a,p,'установлено','%.2f'%(time.monotonic()-t))\n"
        "    except Exception as e:\n"
        "        print(a,p,'отказ',type(e).__name__,'%.2f'%(time.monotonic()-t))\n"
        "    finally:\n"
        "        s.close()\n")
    г = subprocess.run(
        ["ansible", "-i", str(инв), "k2-zomro-01", "-m", "raw",
         "-a", f"python3 -c {json.dumps(код)}"],
        capture_output=True, text=True, timeout=180)
    for с in (г.stdout or "").splitlines():
        if с.strip() and not с.startswith("[WARNING]"):
            print("   " + с.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
