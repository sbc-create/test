#!/usr/bin/env python3
"""Сколько витрина отвечает публично: TTFB, полное время, вес. Только чтение.

Что это НЕ измеряет: показатели Core Web Vitals (LCP, INP, CLS). Для них нужен
браузер у настоящих посетителей или ключ CrUX/PageSpeed, которого у сессии нет
(B027). Здесь измеряется то, что доступно без ключа и за что отвечает наш
сервер: время до первого байта, полное время ответа и вес переданного.

Почему несколько повторов. Первый запрос к витрине после сброса памятки стоит
дороже остальных — измерено 06.10 на zonafilm.cc (504 на первом, 0.08–0.5 с на
следующих). Поэтому каждый адрес опрашивается `--repeat` раз, и печатается
первый замер ОТДЕЛЬНО от медианы остальных: смешивать их нельзя.

Адреса берутся из выгрузки кабинета (верх страниц входа из поиска) или из
`--url`. Третий исход обязателен: адрес не ответил — «не измерено» с причиной.

    python3 automation/local/public-speed-probe.py --domain animedia.icu --top 5
    python3 automation/local/public-speed-probe.py --url https://x.test/ --repeat 4 --json

Коды: 0 — все измеренные в пределах порогов; 1 — есть превышения;
2 — не измерено ничего.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import statistics
import subprocess
import sys

ВЫГРУЗКА = pathlib.Path(
    "/home/claude/wt-portable-site-cell-01/var/analytics/cabinet-latest.json")
ПОРОГ_TTFB_С = 1.5
ПОРОГ_ВЕС_МБ = 3.0


def страницы_спроса(выгрузка: pathlib.Path, домен: str, верх: int) -> tuple[list[str], str]:
    try:
        д = json.loads(выгрузка.read_text(encoding="utf-8"))
    except (OSError, ValueError) as сбой:
        return [], f"выгрузка не прочитана: {сбой}"
    цели = [x for x in д.get("domains") or [] if x.get("domain") == домен]
    if not цели:
        return [], f"домена {домен} в выгрузке нет"
    мера = next((м for м in цели[0].get("measurements") or []
                 if м.get("key") == "search_landing_pages"), None)
    if мера is None or not мера.get("measured"):
        return [], f"страницы входа: {(мера or {}).get('state') or 'показателя нет'}"
    строки = []
    for стр in мера.get("value") or []:
        изм = стр.get("dimensions") or []
        мет = стр.get("metrics") or []
        if len(изм) < 2 or not мет:
            continue
        if str((изм[0] or {}).get("id") or "") != "organic":
            continue
        строки.append((float(мет[0] or 0), str((изм[1] or {}).get("name") or "")))
    строки.sort(reverse=True)
    return [f"https://{домен}{путь}" for _, путь in строки[:верх]], ""


def замер(адрес: str, таймаут: int = 30) -> dict:
    """Один запрос: TTFB, полное время, размер, код."""
    г = subprocess.run(
        ["curl", "-sS", "-o", "/dev/null", "--max-time", str(таймаут),
         "-w", "%{http_code} %{time_starttransfer} %{time_total} %{size_download}",
         адрес], capture_output=True, text=True)
    if г.returncode != 0:
        return {"ок": False, "почему": f"curl код {г.returncode}"}
    части = (г.stdout or "").split()
    if len(части) != 4:
        return {"ок": False, "почему": f"ответ curl не разобран: {г.stdout[:60]!r}"}
    код, ttfb, всего, размер = части
    return {"ок": True, "код": код, "ttfb": float(ttfb), "всего": float(всего),
            "байт": int(float(размер))}


def опросить(адрес: str, повторов: int) -> dict:
    замеры = [замер(адрес) for _ in range(max(1, повторов))]
    удачные = [з for з in замеры if з["ок"]]
    if not удачные:
        return {"url": адрес, "измерено": False,
                "почему": замеры[0].get("почему", "нет ответа")}
    первый = удачные[0]
    прочие = удачные[1:]
    return {
        "url": адрес,
        "измерено": True,
        "код": первый["код"],
        "ttfb_первый": первый["ttfb"],
        "ttfb_медиана": statistics.median([з["ttfb"] for з in прочие]) if прочие else None,
        "всего_медиана": statistics.median([з["всего"] for з in прочие]) if прочие else None,
        "мб": round(первый["байт"] / 1048576, 2),
        "замеров": len(удачные),
    }


def main(аргв: list[str] | None = None) -> int:
    р = argparse.ArgumentParser(description="публичная скорость ответа витрины")
    р.add_argument("--domain", default="")
    р.add_argument("--url", action="append", default=[])
    р.add_argument("--top", type=int, default=5)
    р.add_argument("--repeat", type=int, default=3)
    р.add_argument("--file", default=str(ВЫГРУЗКА))
    р.add_argument("--ttfb", type=float, default=ПОРОГ_TTFB_С)
    р.add_argument("--weight", type=float, default=ПОРОГ_ВЕС_МБ)
    р.add_argument("--json", action="store_true")
    дов = р.parse_args(аргв)

    адреса = list(дов.url)
    беда = ""
    if дов.domain:
        свои, беда = страницы_спроса(pathlib.Path(дов.file), дов.domain, дов.top)
        адреса += свои
    if not адреса:
        print(f"НЕ ИЗМЕРЕНО: адресов нет{' — ' + беда if беда else ''}")
        return 2

    итоги = [опросить(а, дов.repeat) for а in адреса]
    измерены = [и for и in итоги if и["измерено"]]
    превышения = [
        и for и in измерены
        if (и["ttfb_медиана"] is not None and и["ttfb_медиана"] > дов.ttfb)
        or и["мб"] > дов.weight
    ]

    if дов.json:
        print(json.dumps({"порог_ttfb": дов.ttfb, "порог_мб": дов.weight,
                          "страницы": итоги}, ensure_ascii=False, indent=2))
    else:
        print(f"пороги: TTFB {дов.ttfb} с, вес {дов.weight} МБ;"
              f" повторов на адрес {дов.repeat}")
        print(f"{'код':>4} {'TTFB-1':>7} {'TTFB-мед':>9} {'всего':>7} {'МБ':>6}  адрес")
        for и in итоги:
            if not и["измерено"]:
                print(f"   —                                        НЕ ИЗМЕРЕНО"
                      f" ({и['почему']}) {и['url']}")
                continue
            мед = "—" if и["ttfb_медиана"] is None else f"{и['ttfb_медиана']:.2f}"
            всего = "—" if и["всего_медиана"] is None else f"{и['всего_медиана']:.2f}"
            метка = "  ← превышение" if и in превышения else ""
            print(f"{и['код']:>4} {и['ttfb_первый']:7.2f} {мед:>9} {всего:>7}"
                  f" {и['мб']:6.2f}  {и['url'][:64]}{метка}")
        print()
        print(f"страниц {len(итоги)}: измерено {len(измерены)},"
              f" превышений {len(превышения)}")
        print("Core Web Vitals здесь НЕ измеряются: для них нужен ключ CrUX/PageSpeed "
              "или браузер у настоящих посетителей (B027).")
    if not измерены:
        return 2
    return 1 if превышения else 0


if __name__ == "__main__":
    sys.exit(main())
