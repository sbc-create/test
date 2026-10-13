"""Обход поисковыми роботами по журналам nginx (B026).

Два формата входа:

* ``tsv`` — журнал роботов ``seo_bots`` (поля через табуляцию):
  ``time_iso8601 host server_name remote_addr method request_uri status bytes
  request_time upstream_response_time "user_agent"``;
* ``combined`` — штатный формат nginx без домена; домен задаётся аргументом
  (журналы витрин ``lords-0N.access.log``, где домен даёт имя файла).

Правила измерения:

* робот по User-Agent — только КАНДИДАТ; подлинность Googlebot и YandexBot
  проверяется обратным DNS с прямым подтверждением (официальная процедура обоих
  поисковиков), результат — ``verified`` / ``failed`` / ``unchecked``;
* строки с тестовым маркером ``sf-seo-logtest`` в статистику не идут и
  считаются отдельно;
* отчёт называет период и полноту: первая и последняя строка, число строк, число
  нераспознанных строк, файлы. Нет строк робота — «обращений в журнале нет за
  период», а не «робот не обходил»: журнал мог не писаться.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import socket
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

ТЕСТОВЫЙ_МАРКЕР = "sf-seo-logtest"

#: Семейство робота по User-Agent: порядок важен (первое совпадение).
СЕМЕЙСТВА: tuple[tuple[str, re.Pattern], ...] = (
    ("yandex", re.compile(r"Yandex[A-Za-z]*Bot|YandexImages|YandexMetrika|YandexRenderResources|YandexAccessibility", re.I)),
    ("google", re.compile(r"Googlebot|Google-InspectionTool|Storebot-Google|AdsBot-Google|GoogleOther", re.I)),
    ("bing", re.compile(r"bingbot|BingPreview", re.I)),
    ("mailru", re.compile(r"Mail\.RU_Bot", re.I)),
    ("other_bot", re.compile(r"bot|crawler|spider", re.I)),
)

#: Допустимые суффиксы обратного DNS для проверки подлинности.
ДОМЕНЫ_ПОДЛИННОСТИ = {
    "google": (".googlebot.com", ".google.com", ".googleusercontent.com"),
    "yandex": (".yandex.ru", ".yandex.net", ".yandex.com"),
    "bing": (".search.msn.com",),
}

_COMBINED = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "(?P<method>[A-Z]+) (?P<uri>\S+)[^"]*" '
    r'(?P<status>\d{3}) (?P<bytes>\d+|-) "(?P<ref>[^"]*)" "(?P<ua>[^"]*)"')


def семейство(ua: str) -> str | None:
    for имя, шаблон in СЕМЕЙСТВА:
        if шаблон.search(ua or ""):
            return имя
    return None


def тип_страницы(uri: str) -> str:
    путь = uri.split("#", 1)[0]
    чистый = путь.split("?", 1)[0]
    if чистый == "/robots.txt":
        return "robots"
    if re.search(r"sitemap[^/]*\.xml$", чистый) or чистый.startswith("/sitemap/"):
        return "sitemap"
    if чистый in ("", "/"):
        return "главная"
    if re.search(r"/episode[-/]\d+", чистый):
        return "серия"
    if re.search(r"/season[-/]\d+/?$", чистый):
        return "сезон"
    if чистый.startswith(("/title/", "/anime/")):
        return "тайтл"
    if чистый.startswith(("/genre/", "/genres")) or "genre=" in путь:
        return "жанр"
    if чистый.startswith("/year/") or "year=" in путь:
        return "год"
    if чистый.startswith(("/collection", "/lists")):
        return "подборка"
    if чистый.startswith(("/poster/", "/static/", "/_next/", "/assets/")) or re.search(r"\.(css|js|png|jpe?g|webp|svg|ico|woff2?)$", чистый):
        return "ресурс"
    return "раздел/прочее"


def _открыть(путь: Path):
    return gzip.open(путь, "rt", encoding="utf-8", errors="replace") if путь.suffix == ".gz" \
        else open(путь, encoding="utf-8", errors="replace")


def разобрать_tsv(строка: str) -> dict | None:
    части = строка.rstrip("\n").split("\t")
    if len(части) < 11:
        return None
    try:
        время = dt.datetime.fromisoformat(части[0])
        статус = int(части[6])
    except ValueError:
        return None
    ua = части[10]
    if len(ua) >= 2 and ua[0] == ua[-1] == '"':
        ua = ua[1:-1]
    def число(x):
        try:
            return float(x)
        except ValueError:
            return None
    return {"time": время, "host": части[1].lower(), "ip": части[3], "uri": части[5], "status": статус,
            "request_time": число(части[8]), "ua": ua}


def разобрать_combined(строка: str, домен: str) -> dict | None:
    м = _COMBINED.match(строка)
    if not м:
        return None
    try:
        время = dt.datetime.strptime(м.group("time"), "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        return None
    return {"time": время, "host": домен.lower(), "ip": м.group("ip"), "uri": м.group("uri"),
            "status": int(м.group("status")), "request_time": None, "ua": м.group("ua")}


def проверить_подлинность(ip: str, сем: str,
                          обратный: Callable[[str], str] | None = None,
                          прямой: Callable[[str], list[str]] | None = None) -> str:
    """verified / failed / unchecked — обратный DNS по суффиксу и прямое подтверждение."""
    if сем not in ДОМЕНЫ_ПОДЛИННОСТИ:
        return "unchecked"
    обратный = обратный or (lambda a: socket.gethostbyaddr(a)[0])
    прямой = прямой or (lambda h: socket.gethostbyname_ex(h)[2])
    try:
        имя = обратный(ip).rstrip(".").lower()
    except (OSError, socket.herror, socket.gaierror):
        return "failed"
    if not имя.endswith(ДОМЕНЫ_ПОДЛИННОСТИ[сем]):
        return "failed"
    try:
        адреса = прямой(имя)
    except (OSError, socket.gaierror):
        return "failed"
    return "verified" if ip in адреса else "failed"


def анализ(записи: Iterable[dict], *, проверять_dns: bool = True,
           обратный=None, прямой=None) -> dict[str, Any]:
    итог: dict[str, Any] = {"lines_bot": 0, "lines_test": 0, "lines_other": 0, "first": None, "last": None}
    по_домену: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "requests": 0, "status": Counter(), "types": Counter(), "robots_at": [], "sitemap_at": [],
        "request_time": []})))
    подлинность: dict[tuple[str, str], str] = {}
    for з in записи:
        t = з["time"]
        итог["first"] = t if итог["first"] is None or t < итог["first"] else итог["first"]
        итог["last"] = t if итог["last"] is None or t > итог["last"] else итог["last"]
        if ТЕСТОВЫЙ_МАРКЕР in (з["ua"] or ""):
            итог["lines_test"] += 1
            continue
        сем = семейство(з["ua"])
        if сем is None:
            итог["lines_other"] += 1
            continue
        итог["lines_bot"] += 1
        ключ = (з["ip"], сем)
        if ключ not in подлинность:
            подлинность[ключ] = (проверить_подлинность(з["ip"], сем, обратный, прямой)
                                 if проверять_dns else "unchecked")
        метка = f"{сем}:{подлинность[ключ]}"
        день = t.astimezone(dt.timezone.utc).date().isoformat()
        с = по_домену[з["host"]][день][метка]
        с["requests"] += 1
        с["status"][str(з["status"])] += 1
        тип = тип_страницы(з["uri"])
        с["types"][тип] += 1
        if тип in ("robots", "sitemap"):
            с[f"{тип}_at"].append(t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        if з.get("request_time") is not None:
            с["request_time"].append(з["request_time"])
    домены = {}
    for дом, дни in по_домену.items():
        домены[дом] = {}
        for день, метки in sorted(дни.items()):
            домены[дом][день] = {}
            for метка, с in метки.items():
                времена = sorted(с["request_time"])
                домены[дом][день][метка] = {
                    "requests": с["requests"], "status": dict(с["status"]), "types": dict(с["types"]),
                    "robots_fetches": len(с["robots_at"]), "sitemap_fetches": len(с["sitemap_at"]),
                    "last_sitemap_at": max(с["sitemap_at"]) if с["sitemap_at"] else None,
                    "median_request_time": времена[len(времена) // 2] if времена else None,
                }
    итог["first"] = итог["first"].isoformat() if итог["first"] else None
    итог["last"] = итог["last"].isoformat() if итог["last"] else None
    итог["ips_by_verdict"] = dict(Counter(v for v in подлинность.values()))
    итог["domains"] = домены
    return итог


def читать(файлы: list[Path], формат: str, домен: str | None) -> tuple[list[dict], dict]:
    записи, полнота = [], {"files": [], "lines": 0, "unparsed": 0}
    for f in файлы:
        полнота["files"].append(str(f))
        with _открыть(f) as fh:
            for строка in fh:
                полнота["lines"] += 1
                з = разобрать_tsv(строка) if формат == "tsv" else разобрать_combined(строка, домен or "")
                if з is None:
                    полнота["unparsed"] += 1
                    continue
                записи.append(з)
    return записи, полнота


def main(argv: list[str] | None = None) -> int:
    п = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    п.add_argument("files", nargs="+", type=Path)
    п.add_argument("--format", choices=("tsv", "combined"), required=True)
    п.add_argument("--domain", help="домен для combined-журнала (в формате его нет)")
    п.add_argument("--no-dns", action="store_true", help="не проверять подлинность (все — unchecked)")
    п.add_argument("--out", type=Path)
    а = п.parse_args(argv)
    if а.format == "combined" and not а.domain:
        п.error("--domain обязателен для combined")
    записи, полнота = читать(а.files, а.format, а.domain)
    отчёт = анализ(записи, проверять_dns=not а.no_dns)
    отчёт["completeness"] = полнота
    отчёт["generated_at"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    текст = json.dumps(отчёт, ensure_ascii=False, indent=1)
    if а.out:
        а.out.parent.mkdir(parents=True, exist_ok=True)
        а.out.write_text(текст + "\n", encoding="utf-8")
    else:
        sys.stdout.write(текст + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
