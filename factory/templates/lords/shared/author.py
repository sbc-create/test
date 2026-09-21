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


#: Минимальная ширина колонки для строки-карточки. Порог откалиброван по
#: измерениям, а не назначен: в браузере обрезание даты наблюдалось на колонках
#: 136–182 px, а колонка 236 px проходила чисто. Взято 210 px — между
#: наибольшим наблюдавшимся провалом и наименьшим наблюдавшимся проходом.
#: Геометрия объясняет эти числа: миниатюра 64 px плюс отступы 24 px плюс дата
#: «2026-09-20» шириной 70 px уже дают 158 px, а к ним добавляется название.
МИН_КОЛОНКА_COMPACT = 210


def ширина_колонки(точка: int, колонок: int, отступ: int = 16, шаг: int = 16) -> float:
    """Примерная ширина колонки на этой точке перелома."""
    ширина = точка if точка else 320
    return (ширина - 2 * отступ - (колонок - 1) * шаг) / колонок


def проверить_спецификацию(спец: dict) -> list[str]:
    """Композиционные запреты, нарушение которых видно только в браузере.

    Сейчас запрет один, и он выведен из настоящего дефекта: строка-карточка,
    поставленная в плотную сетку, теряет ширину подписи, и обязательная дата
    обрезается. На 320 px колонка сжималась до 16 px при нужных 70.
    """
    беды = []
    лестницы = спец.get("ladders", {})
    for блок in спец.get("blocks", []):
        if блок.get("грамматика") != "compact":
            continue
        класс = блок.get("класс")
        if not класс:
            continue
        for точка, колонок in лестницы.get(класс, []):
            ширина = ширина_колонки(точка, колонок)
            if ширина < МИН_КОЛОНКА_COMPACT:
                беды.append(
                    f"{спец['template_id']}: блок «{блок['заголовок']}» — строка-карточка в сетке "
                    f"{класс} на {точка or 320}px даёт колонку {ширина:.0f}px при минимуме "
                    f"{МИН_КОЛОНКА_COMPACT}px: обязательная дата обрежется"
                )
    return беды


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
    беды = []
    for спец in спецификации["templates"]:
        беды.extend(проверить_спецификацию(спец))
    if беды:
        for б in беды:
            print("ОТКАЗ:", б, file=sys.stderr)
        return 2

    созданные = []
    for спец in спецификации["templates"]:
        созданные.append(собрать(спец, корень).name)
    print(json.dumps({"spec": args.spec, "created": созданные}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
