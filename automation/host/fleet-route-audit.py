#!/usr/bin/env python3
"""Проверка доступности содержимого флота: один домен — один сайт, только чтение.

Что делает. Обходит живые витрины через loopback с правильным заголовком
`Host` — ровно так, как в них ходит nginx, — собирает внутренние ссылки из
ОТРИСОВАННОГО DOM и проверяет каждую. Ничего не меняет: ни файла, ни
манифеста, ни индексации.

Что считается дефектом:

* `valid_content_404` — на страницу ведёт внутренняя ссылка, а страница
  отвечает 404. Это и есть «ошибочный 404»;
* `fake_200` — заведомо несуществующий адрес отвечает 200 либо переходом на
  200. Такой ответ прячет отсутствие страницы;
* `wrong_tenant` — canonical на странице домена указывает на чужой домен;
* `error` — витрина не ответила вовсе.

Что дефектом НЕ считается: честный 404 на адрес, которого действительно нет,
и переход `/путь/` → `/путь` там, где это канонический вид маршрута.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor

ФЛОТ = {
    "lordfilm47.space": (9110, "lords-01", "lords"),
    "lordserial33.biz": (9111, "lords-02", "lords"),
    "1lordserials1.online": (9112, "lords-03", "lords"),
    "yummyani.biz": (9130, "yummy-biz", "yummy"),
    "yummyani.org": (9131, "yummy-org", "yummy"),
    "yummyani.site": (9132, "yummy-site", "yummy"),
    "animedia.icu": (9121, "animedia-01", "animedia"),
    "animedia.space": (9122, "animedia-02", "animedia"),
    "zonafilm.space": (9120, "zona-01", "zona"),
    "zonafilm.cc": (9123, "zona-02", "zona"),
}

#: Несуществующий адрес: проверка честности 404. Суффикс постоянный, чтобы
#: два прогона сравнивались между собой.
НЕСУЩЕСТВУЮЩИЙ = ["/takogo-adresa-tochno-net-9f3a/",
                  "/title/takogo-tajtla-tochno-net-9f3a/",
                  "/catalog/takogo-razdela-net-9f3a/"]

#: Что не ходим: файлы, внешние схемы и бесконечные параметры сортировки.
ПРОПУСК = re.compile(r"^(#|mailto:|tel:|javascript:|data:)|\.(?:png|jpe?g|webp|svg|ico|css|js|xml|txt)(?:$|\?)", re.I)


class Клиент:
    """HTTP без автоматических переходов: цепочка переходов нужна целиком."""

    def __init__(self, домен: str, порт: int, таймаут: float = 30.0):
        self.домен, self.порт, self.таймаут = домен, порт, таймаут

        class БезПерехода(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *а, **кв):
                return None

        self.opener = urllib.request.build_opener(БезПерехода)

    def взять(self, путь: str, переходов: int = 5):
        цепь, текущий = [], путь
        for _ in range(переходов + 1):
            адрес = f"http://127.0.0.1:{self.порт}{urllib.parse.quote(текущий, safe='/?&=%:+,')}"
            req = urllib.request.Request(
                адрес, headers={"Host": self.домен, "User-Agent": "fleet-route-audit"})
            try:
                with self.opener.open(req, timeout=self.таймаут) as r:
                    цепь.append((текущий, r.status))
                    return цепь, r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                цепь.append((текущий, e.code))
                if e.code in (301, 302, 303, 307, 308):
                    место = e.headers.get("Location") or ""
                    if not место:
                        return цепь, e.code, ""
                    разбор = urllib.parse.urlsplit(место)
                    текущий = разбор.path + (("?" + разбор.query) if разбор.query else "")
                    continue
                тело = ""
                try:
                    тело = e.read().decode("utf-8", "replace")
                except Exception:
                    pass
                return цепь, e.code, тело
            except Exception as ош:
                цепь.append((текущий, 0))
                return цепь, 0, f"{ош!r}"
        return цепь, -1, ""


def ссылки(тело: str, домен: str) -> list[str]:
    """Внутренние адреса из отрисованного DOM."""
    найдено = []
    for href in re.findall(r'<a\b[^>]*href="([^"]+)"', тело):
        href = href.strip()
        if not href or ПРОПУСК.search(href):
            continue
        разбор = urllib.parse.urlsplit(href)
        if разбор.netloc and домен not in разбор.netloc:
            continue
        путь = разбор.path or "/"
        if not путь.startswith("/"):
            continue
        найдено.append(путь + (("?" + разбор.query) if разбор.query else ""))
    return найдено


def обойти(домен: str, порт: int, семейство: str, предел: int, глубина: int) -> dict:
    к = Клиент(домен, порт)
    очередь = deque((п, 0) for п in ("/", "/catalog/", "/catalog", "/search/?q=a"))
    видели, итог = set(), {
        "domain": домен, "port": порт, "family": семейство,
        "checked": 0, "ok": 0, "pages": {}, "defects": [],
        "valid_content_404": 0, "broken_internal_links": 0,
        "fake_200_for_missing_page": 0, "wrong_tenant_routes": 0, "errors": 0,
    }
    источник: dict[str, str] = {}
    while очередь and итог["checked"] < предел:
        путь, уровень = очередь.popleft()
        ключ = путь.rstrip("/") or "/"
        if ключ in видели:
            continue
        видели.add(ключ)
        цепь, код, тело = к.взять(путь)
        итог["checked"] += 1
        запись = {"status": код, "chain": [c for c in цепь],
                  "from": источник.get(ключ, "seed")}
        if код == 200:
            итог["ok"] += 1
            m = re.search(r'<link rel="canonical" href="([^"]*)"', тело)
            if m:
                host = urllib.parse.urlsplit(m.group(1)).netloc
                запись["canonical_host"] = host
                if host and host.replace("www.", "") != домен:
                    итог["wrong_tenant_routes"] += 1
                    итог["defects"].append({"type": "wrong_tenant", "url": путь,
                                            "canonical": m.group(1)})
            запись["h1"] = len(re.findall(r"<h1\b", тело))
            if уровень < глубина:
                for с in ссылки(тело, домен)[:400]:
                    к2 = с.rstrip("/") or "/"
                    if к2 not in видели:
                        источник.setdefault(к2, путь)
                        очередь.append((с, уровень + 1))
        elif код == 404:
            if запись["from"] != "seed":
                итог["valid_content_404"] += 1
                итог["broken_internal_links"] += 1
                итог["defects"].append({"type": "valid_content_404", "url": путь,
                                        "from": запись["from"]})
        elif код in (0, -1) or код >= 500:
            итог["errors"] += 1
            итог["defects"].append({"type": "error", "url": путь, "status": код,
                                    "body": тело[:120]})
        итог["pages"][путь] = запись

    for путь in НЕСУЩЕСТВУЮЩИЙ:
        цепь, код, тело = к.взять(путь)
        итог["pages"][путь] = {"status": код, "chain": цепь, "from": "probe-missing"}
        if код == 200:
            итог["fake_200_for_missing_page"] += 1
            итог["defects"].append({"type": "fake_200", "url": путь, "chain": цепь})
    return итог


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--domains", default="")
    р.add_argument("--max-urls", type=int, default=140)
    р.add_argument("--depth", type=int, default=2)
    р.add_argument("--out", default="")
    р.add_argument("--workers", type=int, default=5)
    а = р.parse_args()

    выбор = [d.strip() for d in а.domains.split(",") if d.strip()] or list(ФЛОТ)

    def один(домен):
        порт, сайт, семейство = ФЛОТ[домен]
        итог = обойти(домен, порт, семейство, а.max_urls, а.depth)
        итог["site"] = сайт
        print(f"{домен:22} проверено={итог['checked']:4} ok={итог['ok']:4} "
              f"404-по-ссылке={итог['valid_content_404']:3} "
              f"фальшивых-200={итог['fake_200_for_missing_page']} "
              f"чужой-tenant={итог['wrong_tenant_routes']} ошибок={итог['errors']}",
              flush=True)
        return итог

    # Домены независимы друг от друга: по витрине на поток. Последовательный
    # обход десяти витрин по сто адресов занимает десятки минут, и это время
    # уходит на ожидание, а не на проверку.
    with ThreadPoolExecutor(max_workers=а.workers) as пул:
        итоги = list(пул.map(один, выбор))
    свод = {
        "sites": итоги,
        "VALID_CONTENT_404": sum(и["valid_content_404"] for и in итоги),
        "BROKEN_INTERNAL_LINKS": sum(и["broken_internal_links"] for и in итоги),
        "WRONG_TENANT_ROUTES": sum(и["wrong_tenant_routes"] for и in итоги),
        "FAKE_200_FOR_MISSING_PAGE": sum(и["fake_200_for_missing_page"] for и in итоги),
        "ERRORS": sum(и["errors"] for и in итоги),
    }
    if а.out:
        import pathlib
        pathlib.Path(а.out).write_text(json.dumps(свод, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(json.dumps({k: v for k, v in свод.items() if k != "sites"},
                     ensure_ascii=False))
    плохо = (свод["VALID_CONTENT_404"] + свод["FAKE_200_FOR_MISSING_PAGE"]
             + свод["WRONG_TENANT_ROUTES"] + свод["ERRORS"])
    return 0 if плохо == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
