"""Занято ли произведение по сети: для каждого ждущего черновика.

Только чтение. Правило владельца 09.10 (seo_operator/regular.py, «Одно своё
описание произведения на сеть») запрещает второй домен с тем же произведением.
Ключ произведения — `work_key`: та же нормализация транслитерации, что в
регулярной проверке, иначе пары вида `ts/c` не свелись бы.
"""
import collections
import glob
import json
import pathlib


def work_key(slug: str) -> str:
    k = (slug or "").lower()
    for a, b in (("ts", "c"), ("kh", "h"), ("yo", "e"), ("ye", "e"),
                 ("iy", "y"), ("yy", "y")):
        k = k.replace(a, b)
    return k


опубликовано = collections.defaultdict(set)   # work_key → домены
for путь in sorted(glob.glob("/srv/sites/*/runtime/overlays/*/history.jsonl")):
    домен = pathlib.Path(путь).parent.name
    снято = set()
    for с in pathlib.Path(путь).read_text(encoding="utf-8").splitlines():
        if not с.strip():
            continue
        try:
            з = json.loads(с)
        except ValueError:
            continue
        if з.get("op") == "publish":
            опубликовано[work_key(з.get("slug"))].add(домен)
        if з.get("op") == "unpublish":
            снято.add(work_key(з.get("slug")))
    # Снятые публикации ключ не освобождают: `unpublish` в журнале есть, но
    # после него обычно идёт новая публикация того же слага, и считать ключ
    # свободным по одному снятию было бы ошибкой в сторону повторной работы.
    del снято

ЖДУТ = []
for путь in sorted(glob.glob("/srv/sites/*/runtime/overlays/*/drafts.json")):
    домен = pathlib.Path(путь).parent.name
    try:
        д = json.loads(pathlib.Path(путь).read_text(encoding="utf-8"))
    except ValueError:
        continue
    for слаг, з in (д.get("items") or {}).items():
        к = work_key(слаг)
        где = опубликовано.get(к, set())
        if домен in где:
            continue          # уже опубликован на этом домене — не ждёт
        ЖДУТ.append((домен, слаг, к, sorted(где), з.get("state"),
                     len(з.get("quality_problems") or []),
                     з.get("prepared_at"), з.get("sources")))

print(f"черновиков без публикации на своём домене: {len(ЖДУТ)}\n")
print("домен             слаг                             занят на              ворота")
for домен, слаг, ключ, где, состояние, бед, когда, источники in sorted(
        ЖДУТ, key=lambda з: (bool(з[3]), з[0])):
    отм = ", ".join(где) if где else "— свободно"
    print(f"{домен:17} {слаг[:32]:34} {отм[:28]:30} {состояние}/{бед}"
          f"  подготовлен {когда}  ключ {ключ[:28]}")
    if источники:
        print(f"                  источники: {источники}")
