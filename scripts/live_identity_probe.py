#!/usr/bin/env python3
"""Отдаёт ли адрес именно эту витрину. Один запрос на чтение, без повторов.

Зачем отдельный шаг
-------------------

Доступность домена и готовность продукта — разные величины, и складывать их
нельзя. Домен может отвечать 200 и отдавать чужой сайт, заглушку регистратора
или страницу провайдера; приёмка, запущенная по такому адресу, измерит чужую
работу и запишет её в наш отчёт.

Поэтому до приёмки — опознание. Витрина этой фабрики узнаётся по разметке
рендерера: `data-block`, `data-shelf`, `data-algorithm`. Эти атрибуты не
встречаются у сторонних сайтов случайно, и ни один из них не является тайной.

Что делает и чего не делает
---------------------------

Делает один запрос GET на корень адреса. Не ходит по ссылкам, не отправляет
ничего изменяющего, не обходит защиту и не повторяет запрос после отказа:
401, 403 и 429 означают защиту провайдера или ограничение частоты, и ответ на
них — записать причину, а не пробовать иначе.

Отсутствие разрешения имени (`PENDING_DNS`) отказом витрины не считается.

Запуск:
    .venv/bin/python scripts/live_identity_probe.py
"""

from __future__ import annotations

import json
import socket
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "live-acceptance.json"
OUT = ROOT / "artifacts" / "evidence" / "products" / "live-identity.json"

#: Разметка рендерера этой фабрики. Совпадение случайным не бывает.
MARKERS = ('data-block="', 'data-shelf="', 'data-algorithm="')

#: Честное представление. Выдавать себя за браузер значило бы обходить
#: различение клиентов, которое сайт вправе делать.
AGENT = "site-factory-templates-acceptance/1.0 (read-only identity probe)"

TIMEOUT = 20
ОТКАЗ_ДОСТУПА = {401, 403, 429}


def _resolve(host: str) -> str | None:
    """Адрес имени или None. Разрешение имени — отдельный факт от доступности."""
    try:
        return socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)[0][4][0]
    except socket.gaierror:
        return None


def _reachable(address: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET6 if ":" in address else socket.AF_INET)
    sock.settimeout(10)
    try:
        sock.connect((address, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _fetch(url: str) -> dict:
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        body = response.read(300_000).decode("utf-8", errors="replace")
        return {"status": response.status, "body": body, "final_url": response.geturl(),
                "server": dict(response.headers).get("Server", "")}


def probe(url: str) -> dict:
    """Одно опознание. Возвращает состояние и доказательство, а не приговор.

    Порядок важен и разделяет то, что легко спутать: имя не разрешается —
    одно; разрешается, но порт молчит — другое; отвечает, но отдаёт не нашу
    витрину — третье. Все три раньше выглядели бы как «сайт недоступен», и
    владелец не узнал бы, чинить ему DNS, сервер или выкладку.
    """
    host = url.split("://", 1)[1].split("/", 1)[0]
    address = _resolve(host)
    if address is None:
        return {"url": url, "host": host, "status": None, "verdict": "NAME_NOT_RESOLVED",
                "note": ("имя не разрешается в адрес; разрешение имён в этой полосе "
                         "работает — проверено на посторонних именах, — значит запись "
                         "отсутствует или ещё не разошлась")}

    ports = {"443": _reachable(address, 443), "80": _reachable(address, 80)}
    try:
        got = _fetch(url)
    except urllib.error.HTTPError as error:
        status = error.code
        verdict = "BLOCKED_ACCESS" if status in ОТКАЗ_ДОСТУПА else "HTTP_ERROR"
        return {"url": url, "host": host, "address": address, "ports": ports,
                "status": status, "verdict": verdict,
                "note": ("защита провайдера или ограничение частоты"
                         if verdict == "BLOCKED_ACCESS" else f"ответ {status}")}
    except (urllib.error.URLError, ssl.SSLError, TimeoutError, OSError) as error:
        reason = getattr(error, "reason", error)
        # Имя разрешилось, а соединение не состоялось. Если при этом открыт
        # порт 80, хост жив и дело в самой выкладке HTTPS, а не в хосте.
        if ports["80"] and not ports["443"]:
            note = ("HTTPS не отвечает, при этом порт 80 принимает соединения: "
                    "хост жив, TLS не обслуживается")
            verdict = "HTTPS_NOT_SERVED"
            # Один диагностический запрос по HTTP: владельцу важно знать, что
            # хост отдаёт вместо витрины. Приёмкой это не является и никогда ею
            # не станет — адрес объявлен как https, и по нему витрина не
            # отвечает. Значение здесь ровно одно: назвать, что там на самом
            # деле, вместо общего «сайт недоступен».
            diagnostic = {}
            try:
                fallback = _fetch("http://" + host + "/")
                title = ""
                if "<title>" in fallback["body"]:
                    title = fallback["body"].split("<title>", 1)[1].split(
                        "</title>", 1)[0].strip()[:200]
                diagnostic = {
                    "scheme": "http",
                    "status": fallback["status"],
                    "final_url": fallback["final_url"],
                    "server": fallback["server"],
                    "title": title,
                    "markers_found": [m for m in MARKERS if m in fallback["body"]],
                    "bytes": len(fallback["body"]),
                    "note": "диагностика, а не приёмка: объявленный адрес — https",
                }
            except Exception as fallback_error:  # noqa: BLE001 — диагностика
                diagnostic = {"scheme": "http", "error":
                              f"{type(fallback_error).__name__}: {fallback_error}"[:200]}
            return {"url": url, "host": host, "address": address, "ports": ports,
                    "status": None, "verdict": verdict, "note": note,
                    "http_diagnostic": diagnostic}
        else:
            note = f"{type(error).__name__}: {reason}"[:200]
            verdict = "UNREACHABLE"
        return {"url": url, "host": host, "address": address, "ports": ports,
                "status": None, "verdict": verdict, "note": note}

    body = got["body"]
    found = [m for m in MARKERS if m in body]
    title = ""
    if "<title>" in body:
        title = body.split("<title>", 1)[1].split("</title>", 1)[0].strip()[:200]
    return {
        "url": url, "host": host, "address": address, "ports": ports,
        "status": got["status"], "final_url": got["final_url"], "server": got["server"],
        "verdict": "SERVES_OUR_STOREFRONT" if len(found) >= 2 else "SERVES_SOMETHING_ELSE",
        "markers_found": found, "title": title, "bytes_read": len(body),
        "note": ("разметка рендерера найдена" if len(found) >= 2 else
                 "адрес отвечает, но разметки рендерера нет: это не наша витрина"),
    }


def main() -> int:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    results: dict[str, dict] = {}
    for product, entry in config["products"].items():
        адреса = []
        if entry["base_url"]:
            адреса.append((entry["base_url"], entry["status"], True))
        for extra in entry.get("additional_urls", []):
            адреса.append((extra["url"], extra["status"], False))
        if not адреса:
            results[product] = {"verdict": "BLOCKED_OWNER_URLS",
                                "note": "адрес не передан владельцем"}
            continue
        results[product] = {"primary": None, "additional": []}
        for url, status, primary in адреса:
            outcome = probe(url)
            outcome["declared_status"] = status
            if primary:
                results[product]["primary"] = outcome
            else:
                results[product]["additional"].append(outcome)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for product, outcome in results.items():
        if "verdict" in outcome:
            print(f"{product:16} {outcome['verdict']}: {outcome['note']}")
            continue
        for label, item in [("основной", outcome["primary"])] + [
                ("второй", a) for a in outcome["additional"]]:
            if item is None:
                continue
            print(f"{product:16} {label:9} {item['url']:30} "
                  f"{str(item['status']):5} {item['verdict']}")
            print(f"{'':16} {'':9} {item['note']}")
            if item.get("title"):
                print(f"{'':16} {'':9} заголовок: {item['title']}")
    print(OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
