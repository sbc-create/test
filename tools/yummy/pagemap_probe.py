#!/usr/bin/env python3
"""Сверка карты страниц Yummy с тем, что отвечает витрина.

Зачем
-----

`docs/templates/PAGE-MAP-yummy.md` объявляет 52 типа страниц: адрес,
ожидаемый код ответа и реализован ли тип. Документ и поведение расходятся
молча — именно так «реализовано: да» годами стоит рядом с адресом, который
отдаёт пустую страницу. Здесь объявленное сверяется с измеренным.

Что считается находкой
----------------------

* **расхождение с картой** — карта объявляет 404, получен 200, или наоборот;
* **пустая страница** (`EMPTY_200`) — код 200 без единого заголовка `h1` и без
  ссылок на произведения. Это и есть признак мягкого 404 в ответе сервера.

Адреса с подстановками (`{slug}`, `{year}`, `*`) и незаполненные строки
запроса пропускаются: подставлять в них значение — значит проверять свою
фантазию, а не карту. Они выводятся отдельным списком, чтобы пропуск был
виден.

Чего здесь НЕ проверяется и почему
----------------------------------

Мягкий 404 нельзя искать фразой «страница не найдена» в теле ответа. Первая
версия этой проверки так и делала и объявила мягким 404 все 34 адреса, включая
главную: приложение приходит потоком, и шаблон своей страницы ошибки лежит
отдельным куском в КАЖДОМ документе, даже когда на экране его не будет.
Проверка измеряла присутствие шаблона, а не состояние страницы.

Настоящий мягкий 404 виден только в собранном DOM — этим занимается
`audit.mjs`: там считаются заголовки и видимый текст после отрисовки. Так и
был найден `/catalog/genre/*`, где код 200, а на экране «Код 404».
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

СТРОКА = re.compile(
    r"^\|\s*(?P<тип>[^|]+?)\s*\|\s*`(?P<адрес>[^`]+)`\s*\|"
    r"\s*(?P<индекс>[^|]*?)\s*\|\s*(?P<http>[^|]*?)\s*\|\s*(?P<есть>[^|]*?)\s*\|\s*$")
ПОДСТАНОВКА = re.compile(r"[{}]")
ССЫЛКА = re.compile(r'href="(/anime/[^"]+)"')


def карта(файл: Path) -> tuple[list[dict], list[dict]]:
    конкретные, с_подстановкой = [], []
    for строка in файл.read_text(encoding="utf-8").splitlines():
        м = СТРОКА.match(строка)
        if not м or м.group("тип").lower() in ("тип страницы", "---"):
            continue
        запись = {"type": м.group("тип"), "path": м.group("адрес"),
                  "declared_http": м.group("http"),
                  "implemented": м.group("есть").strip().lower().startswith("да")}
        адрес = запись["path"]
        шаблонный = (ПОДСТАНОВКА.search(адрес) or "*" in адрес
                     or re.search(r"[?&][^=&]+=(&|$)", адрес))
        (с_подстановкой if шаблонный else конкретные).append(запись)
    return конкретные, с_подстановкой


def взять(основа: str, путь: str) -> dict:
    адрес = основа + urllib.parse.quote(путь, safe="/?&=")
    try:
        with urllib.request.urlopen(адрес, timeout=120) as о:
            тело = о.read().decode("utf-8", "replace")
            код = о.status
    except urllib.error.HTTPError as о:
        тело = о.read().decode("utf-8", "replace")
        код = о.code
    except (urllib.error.URLError, OSError) as ош:
        return {"status": None, "error": str(ош)[:120]}
    return {
        "status": код,
        "bytes": len(тело),
        "h1": len(re.findall(r"<h1\b", тело, re.I)),
        "title_links": len(set(ССЫЛКА.findall(тело))),
    }


def разобрать(запись: dict, замер: dict) -> list[str]:
    находки = []
    if замер.get("status") is None:
        return ["NO_RESPONSE"]
    объявлено = запись["declared_http"]
    if "404" in объявлено and "200" not in объявлено and замер["status"] != 404:
        находки.append("DECLARED_404_GOT_" + str(замер["status"]))
    if замер["status"] == 404 and объявлено.strip().startswith("200") \
            and "404" not in объявлено:
        находки.append("DECLARED_200_GOT_404")
    # Карта сайта и robots — не страницы: заголовков и карточек в них нет
    # по определению, и требовать их значило бы объявить дефектом формат.
    не_страница = запись["path"].endswith((".xml", ".txt"))
    if (замер["status"] == 200 and замер["h1"] == 0
            and замер["title_links"] == 0 and not не_страница):
        находки.append("EMPTY_200")
    return находки


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--map", default="docs/templates/PAGE-MAP-yummy.md")
    р.add_argument("--base", required=True)
    р.add_argument("--out", required=True)
    а = р.parse_args()
    конкретные, с_подстановкой = карта(Path(а.map))
    строки = []
    for запись in конкретные:
        замер = взять(а.base, запись["path"])
        находки = разобрать(запись, замер)
        строки.append({**запись, **замер, "findings": находки})
    свод = {
        "captured_at_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "base": а.base, "map": а.map,
        "probed": len(строки),
        "skipped_templated": [з["path"] for з in с_подстановкой],
        "with_findings": sum(1 for с in строки if с["findings"]),
        "rows": строки,
    }
    Path(а.out).write_text(json.dumps(свод, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"проверено адресов: {len(строки)}; с находками: {свод['with_findings']}; "
          f"пропущено с подстановкой: {len(с_подстановкой)}")
    for с in строки:
        if с["findings"]:
            print(f"   {с['path']:34} {с['status']} {','.join(с['findings'])}"
                  f"  (карта: {с['declared_http']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
