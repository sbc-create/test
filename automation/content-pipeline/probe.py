#!/usr/bin/env python3
"""Внешняя проба публичных витрин по HTTPS.

Проверка базы и проверка петли доказывают разное. База говорит, что запись
сохранена; петля — что её отдаёт локальный процесс. Ни то, ни другое не
говорит, что запись видна снаружи: между процессом и посетителем стоят nginx,
сертификат, кэш и DNS, и любое из этих звеньев способно отдать вчерашнее.

Поэтому здесь запрашивается публичный адрес целиком, и сверяется то, что
обещано опубликованным каталогом: голова ленты обязана быть на главной.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
ДОМЕНЫ = {
    "lords-01": "lordfilm47.space", "lords-02": "lordserial33.biz",
    "lords-03": "1lordserials1.online", "animedia-01": "animedia.icu",
    "animedia-02": "animedia.space", "zona-01": "zonafilm.space",
}
АГЕНТ = "site-factory-content-probe/1.0"


def достать(url: str) -> tuple[int, str, str]:
    зпр = urllib.request.Request(url, headers={"User-Agent": АГЕНТ})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(зпр, timeout=25, context=ctx) as о:
            return о.status, о.read().decode("utf-8", "replace"), ""
    except Exception as ош:  # noqa: BLE001
        return 0, "", f"{type(ош).__name__}: {ош}"


def main() -> int:
    итоги, плохих = [], 0
    for витрина, домен in sorted(ДОМЕНЫ.items()):
        путь = ФРОНТ / f"{витрина}-catalog.json"
        if not путь.exists():
            continue
        д = json.loads(путь.read_text(encoding="utf-8"))
        ожидается = next((з["slug"] for з in д["items"] if з.get("poster")), "")
        код, тело, ошибка = достать(f"https://{домен}/")
        ссылок = тело.count('href="/title/')
        виден = bool(ожидается) and f'href="/title/{ожидается}/' in тело
        ок = код == 200 and ссылок >= 12 and виден
        плохих += 0 if ок else 1
        итоги.append({"site": витрина, "domain": домен, "http": код,
                      "bytes": len(тело), "titleLinks": ссылок,
                      "expected": ожидается, "expectedVisible": виден,
                      "revision": д.get("revision"), "error": ошибка,
                      "ok": ок})
        знак = "OK " if ок else "СБОЙ"
        print(f"  {знак} {домен:<24} HTTP {код} · {len(тело):>6} байт · "
              f"ссылок {ссылок:>3} · {ожидается[:24]} "
              f"{'виден' if виден else 'НЕ ВИДЕН'}{(' · ' + ошибка) if ошибка else ''}")
    Path("/srv/site-factory/content-pipeline/state/public-probe.json").write_text(
        json.dumps({"results": итоги, "failed": плохих}, ensure_ascii=False,
                   indent=1), encoding="utf-8")
    print(f"\nвитрин проверено: {len(итоги)}, неуспешных: {плохих}")
    return 1 if плохих else 0


if __name__ == "__main__":
    sys.exit(main())
