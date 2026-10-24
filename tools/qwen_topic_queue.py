"""Очередь тем для Qwen (qwen-dish/1): следующие блюда для bestreciept.site и myfood.mobi.

    python3 tools/qwen_topic_queue.py [--out tools/qwen_contract/queue.json] [--per-day 24,16]

Откуда темы:
* bestreciept.site — действующая карта тем `fooddaily/topics.py` (site_id food-daily): метка —
  кириллическая запись наблюдённого слага, приоритет — сравнительная оценка, не поисковый спрос.
* myfood.mobi — в карте тем выпечки 12; здесь — названия выпечки и десертов из адресов рецептов
  кулинарных каталогов реестра обхода (`var/food-daily/crawl/*/urls.jsonl`) и число каталогов
  из 12, где такой адрес есть (`catalogs`). Это покрытие каталогов, не частотность запросов.
* Первыми — блюда, уже поставленные Qwen и остановленные приёмником (`redo`): тот же
  `dish_id`, нужна страница конкретного рецепта вместо статьи энциклопедии.

Из очереди исключаются блюда, уже опубликованные на любом из двух сайтов (сравнение названий —
правилом приёмника). Файл перезаписывается целиком; после импорта очередь становится короче.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("intake", REPO / "tools" / "qwen_recipes_intake.py")
intake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(intake)

DAILY_TEMPLATE = REPO.parent / "wt-template-food-daily-c" / "templates" / "food-daily"

# (слаг из адресов каталогов, число каталогов из 12, название, раздел myfood)
BAKING = [
    ("vatrushki-s-tvorogom", 4, "Ватрушки с творогом", "bulochki"),
    ("tort-zebra", 4, "Торт «Зебра»", "tort"),
    ("tort-tri-moloka", 4, "Торт «Три молока»", "tort"),
    ("tiramisu", 4, "Тирамису", "deserty"),
    ("tort-ptiche-moloko", 4, "Торт «Птичье молоко»", "tort"),
    ("tort-mishka", 4, "Торт «Мишка»", "tort"),
    ("tart-taten", 4, "Тарт Татен", "pirog"),
    ("sochniki-s-tvorogom", 4, "Сочники с творогом", "pechene"),
    ("shtrudel-s-yablokami", 4, "Штрудель с яблоками", "pirog"),
    ("shtrudel-s-vishnej", 4, "Штрудель с вишней", "pirog"),
    ("rulet-s-makom", 4, "Рулет с маком", "bulochki"),
    ("rogaliki-s-povidlom", 4, "Рогалики с повидлом", "pechene"),
    ("pryaniki", 4, "Пряники", "pechene"),
    ("ponchiki", 4, "Пончики", "bulochki"),
    ("pirozhnoe-kartoshka", 4, "Пирожное «Картошка»", "deserty"),
    ("pirozhki-s-yablokami", 4, "Пирожки с яблоками", "pirog"),
    ("pirozhki-s-kapustoj", 4, "Пирожки с капустой", "pirog"),
    ("pirog-s-vishnej", 4, "Пирог с вишней", "pirog"),
    ("pirog-s-tvorogom", 4, "Пирог с творогом", "pirog"),
    ("pirog-s-kapustoj", 4, "Пирог с капустой", "pirog"),
    ("pirog-s-myasom", 4, "Пирог с мясом", "pirog"),
    ("pirog-s-kartofelem", 4, "Пирог с картофелем", "pirog"),
    ("pirog-s-gribami", 4, "Пирог с грибами", "pirog"),
    ("pirog-s-limonom", 4, "Пирог с лимоном", "pirog"),
    ("pirog-s-abrikosami", 4, "Пирог с абрикосами", "pirog"),
    ("pirog-perevertysh", 4, "Пирог-перевёртыш", "pirog"),
    ("pechene-iz-tvoroga", 4, "Печенье из творога", "pechene"),
    ("panna-kotta", 4, "Панна-котта", "deserty"),
    ("maffiny", 4, "Маффины", "keks"),
    ("kulebyaka", 4, "Кулебяка", "pirog"),
    ("kruassany", 4, "Круассаны", "sloyki"),
    ("keks-na-smetane", 4, "Кекс на сметане", "keks"),
    ("keks-s-vishnej", 4, "Кекс с вишней", "keks"),
    ("kapkejki", 4, "Капкейки", "keks"),
    ("fokachcha", 4, "Фокачча", "hleb"),
    ("eklery", 4, "Эклеры", "zavarnoe"),
    ("chizkejk", 4, "Чизкейк", "deserty"),
    ("chiabatta", 4, "Чиабатта", "hleb"),
    ("bulochki-s-tvorogom", 4, "Булочки с творогом", "bulochki"),
    ("bubliki", 4, "Бублики", "bulochki"),
    ("brauni", 4, "Брауни", "deserty"),
    ("biskvit", 4, "Бисквит", "tort"),
    ("baton", 4, "Батон", "hleb"),
    ("zefir", 4, "Зефир", "deserty"),
    ("pastila", 4, "Пастила", "deserty"),
    ("vafli-venskie", 3, "Венские вафли", "deserty"),
    ("tort-zaher", 3, "Торт «Захер»", "tort"),
    ("tort-smetannik", 3, "Торт «Сметанник»", "tort"),
    ("lepeshki-s-syrom", 4, "Лепёшки с сыром", "hleb"),
    ("puding", 4, "Пудинг", "deserty"),
]

# поставлено Qwen (NEW-002, 23.10.2026), остановлено приёмником: источник — статья Википедии
REDO = [
    ("FD-NIGHT-NEW-001", "bestreciept.site", "Оливье с колбасой"),
    ("FD-NIGHT-NEW-002", "bestreciept.site", "Сельдь под шубой"),
    ("FD-NIGHT-NEW-004", "bestreciept.site", "Борщ с говядиной"),
    ("FD-NIGHT-NEW-005", "bestreciept.site", "Цезарь с курицей"),
    ("FD-NIGHT-NEW-006", "bestreciept.site", "Крабовый салат с рисом"),
    ("FD-NIGHT-NEW-007", "bestreciept.site", "Винегрет"),
    ("FD-NIGHT-NEW-003", "myfood.mobi", "Шарлотка с яблоками"),
    ("FD-NIGHT-NEW-008", "myfood.mobi", "Манник на кефире"),
    ("FD-NIGHT-NEW-009", "myfood.mobi", "Медовик со сметанным кремом"),
    ("FD-NIGHT-NEW-010", "myfood.mobi", "Овсяное печенье"),
]
REDO_FIX = (
    "повторить с тем же dish_id: source.url — страница конкретного опубликованного рецепта "
    "(не энциклопедия), количества, порции и время — из неё; редакционные шаги со ссылками "
    "base_steps на шаги источника"
)


def daily_topics() -> list[dict]:
    sys.path.insert(0, str(DAILY_TEMPLATE))
    from fooddaily.topics import TOPICS  # noqa: PLC0415 — карта тем живёт в шаблоне сайта

    return [t for t in TOPICS if t.get("site_id") == "food-daily"]


def build(per_day: tuple[int, int] = (24, 16), existing: dict | None = None) -> dict:
    existing = intake.published_titles() if existing is None else existing
    published = [k for site in existing.values() for _, k, _ in site]

    def taken(title: str) -> bool:
        k = intake.title_key(title)
        return any(intake.similar(k, p) or k <= p or p <= k for p in published)

    queue: dict[str, list[dict]] = {"bestreciept.site": [], "myfood.mobi": []}
    seen: list = []

    def add(site: str, item: dict) -> None:
        k = intake.title_key(item["title"])
        # «Борщ» и «Борщ с говядиной» — одно блюдо: название целиком входит в другое
        if taken(item["title"]) or any(intake.similar(k, s) or k <= s or s <= k for s in seen):
            return
        seen.append(k)
        queue[site].append(item)

    for did, site, title in REDO:
        add(site, {"dish_id": did, "title": title, "kind": "redo", "fix": REDO_FIX})
    for t in daily_topics():
        add(
            "bestreciept.site",
            {
                "topic_id": t["topic_id"],
                "title": t["label"],
                "kind": "new",
                "category": t.get("category"),
                "basis": "карта тем fooddaily/topics.py (сравнительная оценка, не поисковый спрос)",
            },
        )
    for slug, n, title, group in BAKING:
        add(
            "myfood.mobi",
            {
                "topic_id": slug,
                "title": title,
                "kind": "new",
                "category": group,
                "catalogs": n,
                "basis": f"адрес есть в {n} из 12 каталогов реестра обхода (не поисковый спрос)",
            },
        )
    # раскладка по дням: 24 + 16 в день; очередь длиннее суток — запас на следующие
    for site, n in zip(queue, per_day, strict=True):
        for i, item in enumerate(queue[site]):
            item["day"] = i // n + 1
    return {
        "format": "qwen-dish-queue/1",
        "built": date.today().isoformat(),
        "contract": "tools/qwen_contract/README.md (qwen-dish/1)",
        "per_day": dict(zip(queue, per_day, strict=True)),
        "totals": {site: len(v) for site, v in queue.items()},
        "rules": [
            "одно блюдо — один файл dishes/<dish_id>.json; исправление — с тем же dish_id",
            "source.url — страница конкретного рецепта; энциклопедия — BLOCKED_RIGHTS",
            "перед отправкой: tools/qwen_recipes_intake.py check <поставка> — код 0, READY",
        ],
        "queue": queue,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="qwen_topic_queue")
    ap.add_argument("--out", type=Path, default=REPO / "tools" / "qwen_contract" / "queue.json")
    ap.add_argument("--per-day", default="24,16")
    a = ap.parse_args(argv)
    per_day = tuple(int(x) for x in a.per_day.split(","))
    res = build(per_day)  # type: ignore[arg-type]
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"out": str(a.out), "totals": res["totals"], "per_day": res["per_day"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
