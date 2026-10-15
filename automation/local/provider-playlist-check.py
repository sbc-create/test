#!/usr/bin/env python3
"""Отдаёт ли поставщик дорожку по назначенному номеру: спрашиваем поставщика.

Зачем. Номер в разметке доказывает, что он уехал на страницу. Он НЕ
доказывает, что поставщик по нему что-то отдаёт: витрина с чужим или
отозванным номером выглядит точно так же, а плеер оказывается пустым. Проверка
воспроизведения браузером возможна только на живом домене; до перевода DNS
доступен другой, более прямой ответ — спросить у поставщика плейлист по тому же
номеру и тому же внешнему идентификатору, который витрина поставит в запрос.

Форма запроса взята у `automation/host/nova-player-configure.py::дорожка_есть`,
а не придумана: тот же адрес, те же заголовки `Origin`/`Referer` (поставщик
смотрит на источник), тот же разбор `items`.

Пустой плеер за успех не считается: ответ 200 с нулём элементов — отказ.
Внешний идентификатор берётся из ДОСТАВЛЕННЫХ данных витрины, а не выдумывается.

    python3 automation/local/provider-playlist-check.py --site lords-10 \\
        --data var/k2-data/publish-stage8
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПЛЕЙЛИСТ = "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"
#: Агрегаторы в том порядке, в каком их предпочитает рантайм витрины.
АГРЕГАТОРЫ = ("kp", "imdb", "mdl", "mali")


def учёт(site_id: str) -> tuple[str, str]:
    """Номер из учёта реестра и домен витрины. Номер не печатается наружу."""
    реестр = json.loads((КОРЕНЬ / "config" / "site-cells.json").read_text(encoding="utf-8"))
    ячейка = next((c for c in реестр["cells"] if c["site_id"] == site_id), None)
    if ячейка is None:
        raise SystemExit(f"{site_id}: нет такой ячейки в реестре")
    номер = str((ячейка.get("publisher") or {}).get("publisher_id") or "").strip()
    if not номер:
        raise SystemExit(f"{site_id}: в учёте реестра нет publisher_id — BLOCKED_INPUT")
    return номер, str(ячейка.get("domain") or "")


def внешний_идентификатор(данные: Path, site_id: str) -> tuple[str, str, str]:
    """Первый тайтл с внешним идентификатором: агрегатор, id, слуг."""
    файл = данные / f"{site_id}-details.json"
    if not файл.is_file():
        raise SystemExit(f"{site_id}: нет {файл}")
    детали = json.loads(файл.read_text(encoding="utf-8")).get("details") or {}
    for слаг, запись in детали.items():
        внешние = (запись or {}).get("external_ids") or {}
        for агрегатор in АГРЕГАТОРЫ:
            значение = str(внешние.get(агрегатор) or "").strip()
            if значение:
                return агрегатор, значение, слаг
    raise SystemExit(f"{site_id}: в доставленных данных нет внешних идентификаторов")


def дорожка(номер: str, агрегатор: str, идентификатор: str, домен: str) -> dict:
    url = f"{ПЛЕЙЛИСТ}?pub={номер}&id={идентификатор}&aggr={агрегатор}"
    запрос = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "Origin": f"https://{домен}",
        "x-origin": f"https://{домен}",
        "Referer": f"https://{домен}/",
        "User-Agent": "provider-playlist-check",
    })
    try:
        with urllib.request.urlopen(запрос, timeout=30) as о:
            тело = json.loads(о.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as ош:
        return {"ок": False, "почему": f"provider http={ош.code}"}
    except Exception as ош:  # noqa: BLE001 — сеть и разбор одинаково не доказывают
        return {"ок": False, "почему": f"provider error={type(ош).__name__}"}
    вещи = тело.get("items") or []
    поток = bool(вещи and (вещи[0].get("cvhId") or вещи[0].get("vkId")))
    return {"ок": поток, "элементов": len(вещи),
            "почему": "" if поток else "items есть, но без потока"
            if вещи else "items пуст"}


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", action="append", required=True)
    р.add_argument("--data", required=True)
    а = р.parse_args()

    плохо = 0
    for site_id in а.site:
        номер, домен = учёт(site_id)
        агрегатор, идентификатор, слаг = внешний_идентификатор(Path(а.data), site_id)
        итог = дорожка(номер, агрегатор, идентификатор, домен)
        знак = "v" if итог["ок"] else "x"
        print(f"[{знак}] {site_id:9} {домен:22} aggr={агрегатор} "
              f"элементов={итог.get('элементов', '—')} "
              f"{'дорожка есть' if итог['ок'] else итог['почему']} ({слаг[:28]})")
        if not итог["ок"]:
            плохо += 1
    print(f"итог: без дорожки {плохо} из {len(а.site)}")
    return 0 if плохо == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
