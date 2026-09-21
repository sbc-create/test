#!/usr/bin/env python3
"""Паспорт шаблонного пакета: то, что нельзя изменить незаметно.

## Зачем паспорт, если есть манифест

Манифест описывает пакет сейчас. Паспорт фиксирует, каким пакет БЫЛ предъявлен
на приёмку, и делает последующее изменение обнаружимым. Без него пакет,
принятый владельцем, может тихо разойтись со снимками, по которым его
принимали, — и никто этого не заметит, потому что оба файла лежат рядом и оба
выглядят правдоподобно.

Поэтому паспорт несёт digest содержимого пакета и подпись композиции. Меняется
пакет — расходится digest, и проверка говорит об этом прямо, называя, что
именно разошлось.

## Что в паспорте

Объявленное: назначение, путь пользователя, состав блоков, грамматика
карточек, лестницы колонок, палитра и роль зелёного. Измеренное: балл,
жёсткие отказы и ключевые нули. Снимки: список файлов, по которым велась
приёмка.

Паспорт не заменяет приёмку владельца и прямо это говорит: поле
`owner_visual_accepted` создаётся пустым и агентом не заполняется.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import importlib.util
import json
import pathlib
import re

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]


def _модуль(имя: str, файл: str):
    spec = importlib.util.spec_from_file_location(имя, КОРЕНЬ / "shared" / файл)
    м = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(м)
    return м


def digest_пакета(пакет: pathlib.Path) -> str:
    """Отпечаток содержимого пакета: имя файла и байты, в устойчивом порядке."""
    h = hashlib.sha256()
    for файл in sorted(пакет.rglob("*")):
        if файл.is_file() and файл.name != "PASSPORT.json":
            h.update(файл.relative_to(пакет).as_posix().encode())
            h.update(файл.read_bytes())
    return h.hexdigest()


def собрать(пакет: pathlib.Path, баллы_корень: pathlib.Path,
            снимки_корень: pathlib.Path) -> dict:
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    tid = манифест["template_id"]

    подпись = _модуль("lords_distinctness", "distinctness.py").подпись(пакет)

    файл_баллов = баллы_корень / f"{tid}.json"
    балл = json.loads(файл_баллов.read_text(encoding="utf-8")) if файл_баллов.is_file() else {}

    каталог_снимков = снимки_корень / tid
    снимки = sorted(с.name for с in каталог_снимков.glob("*.png")) if каталог_снимков.is_dir() else []

    return {
        "schema": "lords-template-passport/1",
        "template_id": tid,
        "slug": манифест["slug"],
        "version": манифест["version"],
        "family": манифест["family"],
        "package_digest": digest_пакета(пакет),
        "declared": {
            "design_intent": манифест["design_intent"],
            "primary_user_journey": манифест["primary_user_journey"],
            "home_signature": [б["тип"] for б in манифест["home_block_order"]],
            "block_titles": [б["заголовок"] for б in манифест["home_block_order"]],
            "card_grammar": манифест["card_grammar"],
            "navigation_items": len(манифест["navigation"]),
            "green_identity": манифест["green_identity"],
            "ladders": подпись["ladders"],
            "desktop_density_1440": подпись["desktop_density_1440"],
        },
        "measured": {
            "visual_score": балл.get("TOTAL_SCORE"),
            "hard_fail_count": балл.get("HARD_FAIL_COUNT"),
            "zeroes": {к: v for к, v in (балл.get("measured") or {}).items()
                       if isinstance(v, int) and к.endswith(("COUNT", "VIOLATIONS", "SKIPS"))},
            "viewports": list(_модуль("lords_score", "score.py").ТОЧКИ),
        },
        "review_screenshots": снимки,
        # Заполняет владелец. Агент сюда не пишет: самооценка приёмкой не является.
        "owner_visual_accepted": None,
        "owner_note": "",
        "issued_at_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }


def проверить_дрейф(пакет: pathlib.Path) -> str | None:
    """Разошёлся ли пакет с выданным паспортом."""
    файл = пакет / "PASSPORT.json"
    if not файл.is_file():
        return f"{пакет.name}: паспорта нет"
    паспорт = json.loads(файл.read_text(encoding="utf-8"))
    текущий = digest_пакета(пакет)
    if текущий != паспорт["package_digest"]:
        return (f"{пакет.name}: пакет изменён после выдачи паспорта "
                f"({паспорт['package_digest'][:12]} → {текущий[:12]})")
    манифест = json.loads((пакет / "template.json").read_text(encoding="utf-8"))
    объявлено = паспорт["declared"]["home_signature"]
    сейчас = [б["тип"] for б in манифест["home_block_order"]]
    if объявлено != сейчас:
        return f"{пакет.name}: состав блоков разошёлся с паспортом: {объявлено} → {сейчас}"
    return None


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(КОРЕНЬ))
    parser.add_argument("--scores", default="var/scores")
    parser.add_argument("--shots", default="var/shots")
    parser.add_argument("--check", action="store_true", help="только проверить дрейф")
    args = parser.parse_args()

    корень = pathlib.Path(args.root)
    пакеты = sorted(p for p in корень.iterdir()
                    if p.is_dir() and re.match(r"^T\d{3}-", p.name))

    if args.check:
        беды = [b for b in (проверить_дрейф(п) for п in пакеты) if b]
        print(json.dumps({"packages": len(пакеты), "drift": беды,
                          "PASS": not беды}, ensure_ascii=False, indent=2))
        return 0 if not беды else 2

    выдано = 0
    for п in пакеты:
        паспорт = собрать(п, pathlib.Path(args.scores), pathlib.Path(args.shots))
        (п / "PASSPORT.json").write_text(
            json.dumps(паспорт, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        выдано += 1
    print(json.dumps({"passports_issued": выдано,
                      "owner_visual_accepted": "везде null — заполняет владелец"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
