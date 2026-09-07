"""Покрытие оценок на одном зафиксированном снимке каталога.

Все доли считаются от одного знаменателя — общего числа записей снимка.
Проценты, посчитанные от разных знаменателей, складываются в картину, которой
нет: «половина записей с оценкой» и «половина записей с идентификатором» звучат
одинаково и означают разное.

Ничего не запрашивается наружу: это измерение того, что уже пришло от
поставщика.
"""

import json
import sys
from collections import Counter

путь = sys.argv[1] if len(sys.argv) > 1 else \
    "/srv/site-factory/repo/var/lords/lords/catalog-cache/lords-01.json"
with open(путь, encoding="utf-8") as ф:
    сырьё = json.load(ф)
записи = сырьё["items"] if isinstance(сырьё, dict) else сырьё
всего = len(записи)


def число(значение):
    if значение in (None, "", 0, "0"):
        return None
    try:
        return float(str(значение).replace(",", "."))
    except (TypeError, ValueError):
        return None


счёт = Counter()
подозрительные = []
for з in записи:
    ids = з.get("external_ids") or {}
    кп_id = str(ids.get("kinopoisk") or "").strip()
    imdb_id = str(ids.get("imdb") or "").strip()
    кп = число(з.get("kinopoisk_rating"))
    imdb = число(з.get("imdb_rating"))

    счёт["с кинопоиск id"] += bool(кп_id)
    счёт["с imdb id"] += bool(imdb_id)
    счёт["без единого id"] += not (кп_id or imdb_id)
    счёт["с оценкой кп"] += кп is not None
    счёт["с оценкой imdb"] += imdb is not None
    счёт["с обеими оценками"] += (кп is not None and imdb is not None)
    счёт["без единой оценки"] += (кп is None and imdb is None)
    счёт["кп id есть, оценки нет"] += bool(кп_id) and кп is None
    счёт["оценка кп есть, id нет"] += (кп is not None) and not кп_id
    счёт["оценка imdb есть, id нет"] += (imdb is not None) and not imdb_id
    if кп is not None and not (0 < кп <= 10):
        счёт["оценка кп вне шкалы"] += 1
        подозрительные.append(("кп вне шкалы", з.get("name"), кп))
    if imdb is not None and not (0 < imdb <= 10):
        счёт["оценка imdb вне шкалы"] += 1
    if кп is not None and imdb is not None and abs(кп - imdb) >= 3:
        счёт["расхождение оценок >= 3"] += 1
    счёт["голоса переданы"] += any(
        "vote" in str(к).lower() or "count" in str(к).lower() for к in з)

print(f"снимок: {путь}")
print(f"ВСЕГО ЗАПИСЕЙ (единый знаменатель): {всего}\n")
for имя, значение in sorted(счёт.items(), key=lambda п: -п[1]):
    print(f"  {имя:34} {значение:7}  {значение / всего * 100:5.1f} %")
print()
if подозрительные:
    print("примеры вне шкалы:", подозрительные[:3])
