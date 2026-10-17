#!/usr/bin/env python3
"""Произведения без постера, которые ВИДИТ посетитель, — с идентификаторами.

Зачем. «Постеров нет» — это не одно состояние. Карточка без картинки бывает
по трём причинам, и они требуют разных действий: у поставщика нет адреса
(вопрос к поставщику или к дополнительному источнику), адрес есть и не
открывается (вопрос доставки), адрес открывается, но это не изображение
(вопрос содержимого). Первую причину инструмент и перечисляет поимённо, с
идентификаторами произведения, чтобы заявку можно было подать по записи, а не
«по витрине вообще».

Берутся публичные страницы восьми витрин, адреса дедуплицируются, детали
дополняются из доставленного бокового файла.

    python3 automation/local/k2-posterless-works.py [--out файл.json]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"
ИСХОДНИКИ = КОРЕНЬ / "var" / "k2-data" / "publish-stage8"
СТРАНИЦЫ = ["/", "/new/", "/catalog/", "/movies/", "/series/"]
КАРТОЧКА = re.compile(
    r'<a class="[^"]*" href="(?P<адрес>/title/[^"]+)"[^>]*'
    r'title="(?P<имя>[^"]*)"[^>]*>(?P<тело>.*?)</a>', re.S)


def витрины() -> dict[str, str]:
    j = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ячейки = j.get("cells") or []
    записи = ячейки.values() if isinstance(ячейки, dict) else ячейки
    return {з["site_id"]: з["domain"] for з in записи
            if isinstance(з, dict) and з.get("site_id") and з.get("domain")}


def страница(домен: str, путь: str) -> str:
    return subprocess.run(["curl", "-sS", "--max-time", "60",
                           f"https://{домен}{путь}"],
                          capture_output=True, text=True).stdout or ""


def безкартинки(домен: str) -> dict[str, str]:
    """{slug: название} карточек, у которых картинки в разметке нет вовсе."""
    итог = {}
    for путь in СТРАНИЦЫ:
        html = страница(домен, путь)
        for м in КАРТОЧКА.finditer(html):
            if "<img" in м.group("тело"):
                continue
            slug = м.group("адрес").strip("/").split("/")[-1]
            итог[slug] = м.group("имя")
    return итог


def главная(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--out", default=str(КОРЕНЬ / "var" / "k2-data" /
                                        "posterless-works.json"))
    а = р.parse_args(аргв)

    пары = [(с, д) for с, д in витрины().items()
            if с in {f"lords-{н}" for н in range(10, 18)}]
    with ThreadPoolExecutor(max_workers=4) as пул:
        найдено = list(пул.map(lambda п: (п[0], безкартинки(п[1])), пары))

    все: dict[str, dict] = {}
    for site_id, карты in найдено:
        подробности = {}
        п = ИСХОДНИКИ / f"{site_id}-details.json"
        if п.is_file():
            подробности = json.loads(п.read_text(encoding="utf-8")).get("details") or {}
        for slug, имя in карты.items():
            з = все.setdefault(slug, {"slug": slug, "title": имя,
                                      "витрины": [], "year": None,
                                      "external_ids": {}, "type": None})
            if site_id not in з["витрины"]:
                з["витрины"].append(site_id)
            д = подробности.get(slug)
            if д:
                з["year"] = д.get("year")
                з["type"] = д.get("type")
                з["external_ids"] = д.get("external_ids") or {}
                з["poster_url_в_исходнике"] = д.get("poster_url") or ""

    печать = sorted(все.values(), key=lambda з: (-len(з["витрины"]), з["slug"]))
    print(f"произведений без картинки на публичных страницах: {len(печать)}")
    print(f"{'слуг':44} {'год':>5}  витрин  идентификаторы")
    for з in печать:
        ид = ", ".join(f"{к}={v}" for к, v in (з["external_ids"] or {}).items())
        print(f"{з['slug'][:44]:44} {str(з['year'] or '—'):>5}  "
              f"{len(з['витрины']):6}  {ид or 'нет'}")
    п_вых = pathlib.Path(а.out)
    п_вых.parent.mkdir(parents=True, exist_ok=True)
    п_вых.write_text(json.dumps(печать, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print("сохранено:", п_вых)
    return 0


if __name__ == "__main__":
    sys.exit(главная())
