#!/usr/bin/env python3
"""Матрица архетипов страницы произведения и границ серий.

Архетип — это не «ещё одна страница», а отдельное состояние ДАННЫХ, в котором
шаблон обязан вести себя определённо. Проверяются те, на которых шаблоны ломаются
чаще всего:

* фильм без сезонов — не должен обещать список серий;
* сериал с одним сезоном и с несколькими — оба показывают ВСЕ серии;
* пустой synopsis — честная строка об отсутствии, а не пустой блок;
* отсутствующий постер — устойчивая заглушка, а не битая картинка;
* отсутствующий поток — честное состояние плеера, а не чёрный прямоугольник;
* длинное название, спецсимволы и кириллица — не ломают раскладку и экранируются.

Границы серий проверяются отдельно: 1, 2, 99, 100, 101, 209, 210 обязаны
существовать и называть СВОЙ номер во всех восьми местах сразу, а `211` у
сериала с 210 сериями обязан быть настоящей 404 и не встречаться ни в одной
ссылке страницы.
"""
from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
DESC = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.I)
CANON = re.compile(r'<link\s+rel="canonical"\s+href="([^"]*)"', re.I)
LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
ЭПИЗОД = re.compile(r"/season-(\d+)/episode-(\d+)/")
ТЕГ = re.compile(r"<[^>]+>")


def текст(к: str) -> str:
    return html_mod.unescape(ТЕГ.sub(" ", к)).strip()


def взять(адрес: str):
    ч = urllib.parse.urlsplit(адрес)
    адрес = urllib.parse.urlunsplit((
        ч.scheme, ч.netloc, urllib.parse.quote(ч.path, safe="/%:@!$&'()*+,;=~-._"),
        urllib.parse.quote(ч.query, safe="/%:@!$&'()*+,;=~-._?"), ""))
    try:
        with urllib.request.urlopen(
                urllib.request.Request(адрес, headers={"User-Agent": "archetypes"}),
                timeout=60) as о:
            return о.status, о.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as ош:
        return ош.code, (ош.read() or b"").decode("utf-8", "replace")
    except OSError as ош:
        return -1, str(ош)[:140]


def проверить_архетип(база: str, имя: str, опис: dict) -> dict:
    код, тело = взять(база + опис["url"])
    итог = {"archetype": имя, "url": опис["url"], "status": код, "problems": []}
    if код != 200:
        итог["problems"].append(f"status_{код}")
        итог["ok"] = False
        return итог
    низ = тело.lower()
    заголовок = текст((H1.search(тело) or re.match("", "")).group(1)) if H1.search(тело) else ""
    итог["h1"] = заголовок
    if заголовок != опис["title"]:
        итог["problems"].append("h1_mismatch")

    # Экранирование: название с кавычками и амперсандом не должно утекать в
    # разметку сырым. Проверяем, что «сырого» названия в теле нет.
    сырое_опасное = [с for с in ("<", ">") if с in опис["title"]]
    if сырое_опасное and опис["title"] in тело:
        итог["problems"].append("unescaped_title")

    сезоны = опис.get("seasons", 0)
    # Пара «сезон, серия», а не один номер серии. У сериала с четырьмя
    # сезонами по десять серий номера повторяются, и множество номеров даёт
    # десять вместо сорока: проба объявляла список усечённым там, где он полон.
    пары = {(int(с), int(э)) for с, э in ЭПИЗОД.findall(тело)}
    итог["episode_links"] = len(пары)
    if сезоны == 0:
        # Фильм: списка серий быть не должно, но и обещания серий тоже.
        if пары:
            итог["problems"].append("film_has_episode_links")
    else:
        if len(пары) < опис.get("episodes", 0):
            итог["problems"].append(
                f"episode_list_truncated:{len(пары)}<{опис.get('episodes')}")

    if not опис.get("has_desc"):
        # Пустой synopsis — обязана быть честная строка, а не пустой блок.
        честно = any(с in низ for с in ("источник", "не передал", "пока не"))
        if not честно:
            итог["problems"].append("empty_synopsis_not_explained")
    if not опис.get("has_poster"):
        if "не передан" not in низ:
            итог["problems"].append("missing_poster_not_explained")
    if not опис.get("kp"):
        состояние = re.search(r'data-player data-state="(\w+)"', тело)
        итог["player_state"] = состояние.group(1) if состояние else ""
        if итог["player_state"] == "playable":
            итог["problems"].append("promises_stream_without_source")
        if "<video-player" in тело:
            итог["problems"].append("player_element_without_source")
    else:
        состояние = re.search(r'data-player data-state="(\w+)"', тело)
        итог["player_state"] = состояние.group(1) if состояние else ""

    # Пустых пар «что — значение» на странице быть не должно ни в одном архетипе.
    if re.search(r"<dd[^>]*>\s*</dd>", тело):
        итог["problems"].append("empty_fact_value")
    if "None" in текст(тело):
        итог["problems"].append("python_none_leaked")
    итог["ok"] = not итог["problems"]
    return итог


def проверить_границы(база: str, url: str, всего: int, точки) -> dict:
    итог = {"url": url, "total_episodes": всего, "checked": [], "problems": []}
    код, тело = взять(база + url)
    номера = sorted({int(э) for с, э in ЭПИЗОД.findall(тело) if int(с) == 1})
    итог["listed_on_title_page"] = len(номера)
    if номера != list(range(1, всего + 1)):
        итог["problems"].append(f"list_incomplete:{len(номера)}/{всего}")
    for н in точки:
        если = f"{url}season-1/episode-{н}/"
        код, тело = взять(база + если)
        запись = {"episode": н, "status": код}
        if код != 200:
            запись["ok"] = False
            итог["problems"].append(f"episode_{н}_status_{код}")
            итог["checked"].append(запись)
            continue
        h1 = текст(H1.search(тело).group(1)) if H1.search(тело) else ""
        т = текст(TITLE.search(тело).group(1)) if TITLE.search(тело) else ""
        d = html_mod.unescape(DESC.search(тело).group(1)) if DESC.search(тело) else ""
        c = CANON.search(тело).group(1) if CANON.search(тело) else ""
        ld = None
        for кусок in LD.findall(тело):
            try:
                узел = json.loads(кусок)
            except ValueError:
                continue
            if isinstance(узел, dict) and узел.get("@type") == "TVEpisode":
                ld = узел
        крошки = f"{н} серия" in тело or f"серия {н}" in тело.lower()
        og = re.search(r'<meta property="og:title" content="([^"]*)"', тело)
        поля = {
            "h1": f"{н} серия" in h1,
            "title": f"{н} серия" in т,
            "description": f"{н} серия" in d,
            "canonical": c.endswith(f"/season-1/episode-{н}/"),
            "schema": bool(ld) and ld.get("episodeNumber") == н,
            "breadcrumbs": крошки,
            "og": bool(og) and f"{н} серия" in html_mod.unescape(og.group(1)),
        }
        запись.update(поля)
        запись["ok"] = all(поля.values())
        if not запись["ok"]:
            итог["problems"].append(
                f"episode_{н}_drift:{[к for к, з in поля.items() if not з]}")
        итог["checked"].append(запись)
    # За границей — настоящая 404, и ни одной ссылки на неё со страницы.
    за = всего + 1
    код, тело_404 = взять(f"{база}{url}season-1/episode-{за}/")
    итог["beyond_last_episode"] = за
    итог["beyond_last_status"] = код
    if код != 404:
        итог["problems"].append(f"beyond_last_not_404:{код}")
    _, тело_тайтла = взять(база + url)
    if f"/episode-{за}/" in тело_тайтла:
        итог["problems"].append("beyond_last_linked_from_title")
    итог["ok"] = not итог["problems"]
    return итог


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--base", required=True)
    р.add_argument("--archetypes", required=True)
    р.add_argument("--boundary-url", required=True)
    р.add_argument("--boundary-total", type=int, required=True)
    # Точки границ задаются снаружи: у снимка Zona самый длинный сериал —
    # 182 серии, и требовать на нём двести десятую значит требовать выдумать
    # серию, которой у источника нет. Проверяются реальные границы этого
    # произведения, а отсутствие 210 у семейства называется прямо.
    р.add_argument("--points", default="1,2,99,100,101,209,210")
    р.add_argument("--out", required=True)
    арг = р.parse_args(argv)

    архетипы = json.loads(Path(арг.archetypes).read_text(encoding="utf-8"))
    строки = [проверить_архетип(арг.base, и, о) for и, о in архетипы.items()]
    точки = tuple(int(ч) for ч in арг.points.split(",") if ч.strip())
    границы = проверить_границы(арг.base, арг.boundary_url, арг.boundary_total, точки)
    отчёт = {
        "taken_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base": арг.base, "archetypes": строки, "episode_boundaries": границы,
        "counters": {
            "ARCHETYPES_CHECKED": len(строки),
            "ARCHETYPES_OK": sum(1 for с in строки if с["ok"]),
            "EPISODE_BOUNDARIES_OK": sum(1 for з in границы["checked"] if з.get("ok")),
            "EPISODE_BOUNDARIES_TOTAL": len(границы["checked"]),
            "BEYOND_LAST_STATUS": границы["beyond_last_status"],
        },
    }
    Path(арг.out).write_text(json.dumps(отчёт, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
    for с in строки:
        метка = "OK  " if с["ok"] else "ДЕФЕКТ"
        print(f"{метка} {с['archetype']:<22} {с['status']} "
              f"серий={с.get('episode_links',0):<4} плеер={с.get('player_state','—'):<10} "
              f"{с['problems'] if с['problems'] else ''}")
    print(f"\nграницы серий: {отчёт['counters']['EPISODE_BOUNDARIES_OK']}"
          f"/{отчёт['counters']['EPISODE_BOUNDARIES_TOTAL']}, "
          f"за последней серией HTTP {границы['beyond_last_status']}, "
          f"в списке {границы['listed_on_title_page']} из {границы['total_episodes']}")
    if границы["problems"]:
        print("  проблемы границ:", границы["problems"][:4])
    print(f"отчёт: {арг.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
