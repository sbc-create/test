#!/usr/bin/env python3
"""Проекция каталога семейства на новую витрину — ровно одно поле, с провенансом.

Зачем. Для восьми новых витрин снимков `<site>-catalog.json` в хранилище
производителя нет, и издатель моей ветви их не соберёт: ему нужны модули
`factory.lords`, которых в этой ветви нет (`rating_gateway` и соседние живут в
живом репозитории), а живая копия издателя про восемь витрин не знает. Пока
обновление издателя не установлено владельцем, данные берутся проекцией.

Что измерено и на чём проекция стоит (2026-10-13, живое хранилище
`/srv/lords/.frontend`):

* `lords-01-catalog.json` и `lords-02-catalog.json` отличаются РОВНО одним
  скалярным полем — `site`; `count` 63776 у обоих, `items[0]` совпадает;
* то же у sidecar подробностей: различается только `site`,
  `catalog_revision` = `fe166350d2cd2c23d55d9b211c4452d7` у обоих;
* направление витрины (фильмы или сериалы) задаёт её ПРОФИЛЬ при отрисовке, а
  не отдельный снимок — это записано и в самом издателе.

Поэтому проекция — это тот же рабочий каталог, а не демонстрационный: меняется
одно поле `site`, и рядом пишется провенанс: источник, его SHA-256, ревизия
каталога, время. Ничего не придумывается и ничего не удаляется.

Проверки после записи (иначе это была бы вера, а не проверка):
количество элементов, равенство первого и последнего элемента источнику,
совпадение `catalog_revision`, совпадение всех скалярных полей кроме `site`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ХРАНИЛИЩЕ = Path("/srv/lords/.frontend")
#: Источник проекции по семейству. Для обоих профилей это один снимок
#: поставщика: различие профилей — в отрисовке, а не в данных.
ИСТОЧНИК = {"lords-films": "lords-01", "lords-serials": "lords-02"}


def сумма(путь: Path) -> str:
    h = hashlib.sha256()
    with путь.open("rb") as ф:
        for кусок in iter(lambda: ф.read(1 << 20), b""):
            h.update(кусок)
    return h.hexdigest()


def скаляры(д: dict) -> dict:
    return {к: з for к, з in д.items() if not isinstance(з, (list, dict))}


def спроецировать(источник: Path, цель: Path, site_id: str) -> dict:
    данные = json.loads(источник.read_text(encoding="utf-8"))
    было = данные.get("site")
    данные["site"] = site_id
    цель.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    return {"source": str(источник), "source_sha256": сумма(источник),
            "source_site": было, "site": site_id,
            "catalog_revision": данные.get("catalog_revision")
            or данные.get("revision"),
            "count": данные.get("count") or данные.get("items_total"),
            "result_sha256": сумма(цель), "result_bytes": цель.stat().st_size}


def проверить(источник: Path, цель: Path, site_id: str) -> list[str]:
    """Прикладная проверка данных, а не «файл создан»."""
    беды: list[str] = []
    и = json.loads(источник.read_text(encoding="utf-8"))
    ц = json.loads(цель.read_text(encoding="utf-8"))
    if ц.get("site") != site_id:
        беды.append(f"{цель.name}: поле site = {ц.get('site')!r}, ожидалось {site_id!r}")
    лишние = {к: (з, ц.get(к)) for к, з in скаляры(и).items()
              if к != "site" and ц.get(к) != з}
    if лишние:
        беды.append(f"{цель.name}: изменились поля помимо site: {sorted(лишние)}")
    for поле in ("items", "details", "entries"):
        if isinstance(и.get(поле), list):
            if len(ц.get(поле) or []) != len(и[поле]):
                беды.append(f"{цель.name}: {поле} — {len(ц.get(поле) or [])} "
                            f"вместо {len(и[поле])}")
            elif и[поле] and (ц[поле][0] != и[поле][0] or ц[поле][-1] != и[поле][-1]):
                беды.append(f"{цель.name}: крайние элементы {поле} не совпали")
    return беды


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", required=True, help="site_id новой витрины")
    р.add_argument("--family", required=True, choices=sorted(ИСТОЧНИК),
                   help="шаблон витрины: lords-films или lords-serials")
    р.add_argument("--out", required=True, help="каталог для данных витрины")
    р.add_argument("--store", default=str(ХРАНИЛИЩЕ))
    а = р.parse_args()

    хранилище = Path(а.store)
    донор = ИСТОЧНИК[а.family]
    выход = Path(а.out)
    выход.mkdir(parents=True, exist_ok=True)

    провенанс = {"generated_at": datetime.now(timezone.utc)
                 .strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "tool": "automation/local/project-family-catalog.py",
                 "family": а.family, "donor": донор, "files": {}}
    беды: list[str] = []
    for вид in ("catalog", "details"):
        источник = хранилище / f"{донор}-{вид}.json"
        if not источник.is_file():
            print(f"ОТКАЗ: нет источника {источник}", file=sys.stderr)
            return 2
        цель = выход / f"{а.site}-{вид}.json"
        провенанс["files"][цель.name] = спроецировать(источник, цель, а.site)
        беды += проверить(источник, цель, а.site)

    (выход / f"{а.site}-data-provenance.json").write_text(
        json.dumps(провенанс, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    for имя, св in sorted(провенанс["files"].items()):
        print(f"{имя}: {св['result_bytes']/2**20:.1f} МиБ, элементов "
              f"{св['count']}, ревизия {св['catalog_revision']}, "
              f"источник {Path(св['source']).name}")
    if беды:
        print(f"ПРОВЕРКА НЕ ПРОШЛА ({len(беды)}):")
        for б in беды:
            print(f"   {б}")
        return 1
    print("проверка данных пройдена: кроме поля site ничего не изменилось")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
