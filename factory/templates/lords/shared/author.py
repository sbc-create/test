#!/usr/bin/env python3
"""Сборка шаблонного пакета из явной спецификации.

## Почему спецификация, а не генератор

Пятьдесят шаблонов легко «сгенерировать» формулой — и получить пятьдесят
перекрашенных копий, что прямо запрещено. Поэтому композиция каждого пакета
записана поимённо: порядок блоков, грамматика карточек, лестницы колонок,
токены и приём оформления. Спецификации лежат в репозитории рядом с пакетами,
их видно в истории, и проверка различимости меряет результат, а не намерение.

Инструмент лишь раскладывает объявленное по файлам пакета: `template.json`,
`tokens.css`, `layout.css`, `components.css`. Ничего своего он не добавляет —
в том числе не придумывает доменов, названий и палитр.

Запуск: `author.py --spec factory/templates/lords/specs/wave02.json`
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[1]


def лестница_css(класс: str, ступени: list[list[int]]) -> str:
    """CSS-лестница колонок: [[точка, колонок], ...]; точка 0 — базовое правило."""
    строки = []
    for точка, колонок in ступени:
        правило = f".{класс}{{grid-template-columns:repeat({колонок},minmax(0,1fr))}}"
        строки.append(правило if точка == 0 else f"@media(min-width:{точка}px){{{правило}}}")
    return "\n".join(строки)


def собрать(спец: dict, корень: pathlib.Path) -> pathlib.Path:
    каталог = корень / f"{спец['template_id']}-{спец['slug']}"
    каталог.mkdir(parents=True, exist_ok=True)

    манифест = {
        "template_id": спец["template_id"],
        "slug": спец["slug"],
        "version": спец.get("version", "1.0.0"),
        "family": спец["family"],
        "title": спец["title"],
        "brand": спец.get("brand", "LORDS"),
        # Домен только превью и только на зарезервированном example: настоящий
        # домен в шаблоне был бы привязкой, которую нельзя переназначить.
        "preview_domain": f"lords-{спец['template_id'].lower()}.example",
        "footer": спец["footer"],
        "design_intent": спец["design_intent"],
        "primary_user_journey": спец["journey"],
        "card_grammar": спец["card_grammar"],
        "green_identity": спец["green_identity"],
        "navigation": спец["navigation"],
        "home_block_order": спец["blocks"],
    }
    (каталог / "template.json").write_text(
        json.dumps(манифест, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    токены = спец["tokens"]
    (каталог / "tokens.css").write_text(
        f"/* {спец['template_id']} — {спец['tokens_note']} */\n:root{{\n"
        + "\n".join(f"  {строка}" for строка in токены)
        + "\n}\n", encoding="utf-8")

    лестницы = "\n\n".join(
        лестница_css(класс, ступени) for класс, ступени in спец["ladders"].items())
    (каталог / "layout.css").write_text(
        f"/* {спец['template_id']} — {спец['layout_note']} */\n{лестницы}\n"
        + ("\n" + "\n".join(спец.get("layout_extra", [])) + "\n" if спец.get("layout_extra") else ""),
        encoding="utf-8")

    (каталог / "components.css").write_text(
        f"/* {спец['template_id']} — {спец['components_note']} */\n"
        + "\n".join(спец["components"]) + "\n", encoding="utf-8")
    return каталог


def главное() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--root", default=str(КОРЕНЬ))
    args = parser.parse_args()

    спецификации = json.loads(pathlib.Path(args.spec).read_text(encoding="utf-8"))
    корень = pathlib.Path(args.root)
    созданные = []
    for спец in спецификации["templates"]:
        созданные.append(собрать(спец, корень).name)
    print(json.dumps({"spec": args.spec, "created": созданные}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
