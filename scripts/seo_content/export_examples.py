#!/usr/bin/env python3
"""Выборка принятых и отклонённых черновиков с причинами.

Не «лучшие» и не «показательные»: берутся первые по порядку прогона, чтобы
подборку нельзя было подогнать. Для отклонённых сохраняется код причины и
объяснение — отказ без причины ничему не учит.

    python3 scripts/seo_content/export_examples.py \
        --run artifacts/evidence/fleet-seo-004/golden-run.json \
        --out docs/seo-content/examples
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

ОБЪЯСНЕНИЯ = {
    "NEEDS_FACTS": "фактов не хватает на честный текст — это исправный исход, а не сбой",
    "FACT_CONFLICT": "источники расходятся; выбирать удобный вариант модель не вправе",
    "DUPLICATE": "текст совпадает с уже существующим настолько, что новой ценности не создаёт",
    "NEAR_DUPLICATE_REVIEW": "близость к чужому тексту выше порога — нужен человек",
    "EPISODE_IDENTITY_CONFLICT": "не разрешено, о какой именно серии речь",
    "IDENTITY_DETAIL": "подробность конфликта личности",
    "ENTITY_IDENTITY_ERROR": "маршрут ведёт не к описываемой сущности",
    "CONTRADICTED_CLAIMS": "текст утверждает то, что опровергается фактом",
    "UNSUPPORTED_MATERIAL_CLAIMS": "существенное утверждение не подтверждено ни одним фактом",
    "PLAYER_AVAILABILITY_FALSE_CLAIM": "обещан просмотр там, где источника нет",
    "LANGUAGE_CRITICAL": "критическая языковая ошибка",
    "STRUCTURED_DATA": "разметка расходится с фактами или с видимой страницей",
    "STALE_NUMBER": "в тексте остался номер, отставший от разрешённой личности",
    "PROMPT_INJECTION_ESCAPED": "управляющий оборот из данных попал в выдачу",
    "DOORWAY_RISK": "у витрины нет собственного угла — уместнее канонизация или noindex",
    "BLIND_SCORE": "балл слепого судьи ниже проходного",
}


def объяснить(причина: str) -> str:
    код = причина.split(":", 1)[0]
    return ОБЪЯСНЕНИЯ.get(код, "см. код причины")


def карточка(з: dict) -> str:
    строки = [f"### `{з['case_id']}` — {з['status']}", ""]
    строки.append(f"*Вид:* {з['kind']}; *метки:* {', '.join(з['tags'])}")
    строки.append("")
    т = з["texts"]
    if т.get("meta_title"):
        строки.append(f"**meta title** ({з['meta_title_len']}) — {т['meta_title']}")
    if т.get("meta_description"):
        строки.append(f"**meta description** ({з['meta_description_len']}) — "
                      f"{т['meta_description']}")
    if т.get("h1"):
        строки.append(f"**H1** — {т['h1']}")
    if т.get("body"):
        строки.append("")
        строки.append(f"**Описание** ({з['body_len']} символов)")
        строки.append("")
        строки.append("> " + т["body"])
    if з.get("notes"):
        строки.append("")
        строки.append("**Редакционные заметки**")
        строки.extend(f"- {н}" for н in з["notes"])
    if з["reasons"]:
        строки.append("")
        строки.append("**Почему отклонено**")
        for п in з["reasons"]:
            строки.append(f"- `{п[:160]}` — {объяснить(п)}")
    if з.get("warnings"):
        строки.append("")
        строки.append("**Предупреждения**")
        строки.extend(f"- `{в[:160]}`" for в in з["warnings"])
    строки.append("")
    строки.append(f"*Балл слепого судьи:* {з['blind_score']}"
                  + (f"; критические: {з['judge_critical']}"
                     if з["judge_critical"] else ""))
    строки.append("")
    return "\n".join(строки)


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--run", required=True)
    р.add_argument("--out", required=True)
    р.add_argument("--accepted", type=int, default=20)
    р.add_argument("--rejected", type=int, default=20)
    а = р.parse_args(аргв)

    данные = json.loads(pathlib.Path(а.run).read_text("utf-8"))
    записи = данные["records"]
    принятые = [з for з in записи if з["status"] == "PASSED"][:а.accepted]

    # Отклонённые берутся по одной на код причины, пока коды не кончатся, и
    # только потом добираются по порядку: подборка из двадцати однотипных
    # отказов ничего не показала бы.
    по_кодам: dict[str, list[dict]] = defaultdict(list)
    for з in записи:
        if з["status"] == "PASSED" or not з["reasons"]:
            continue
        по_кодам[з["reasons"][0].split(":", 1)[0]].append(з)
    отклонённые: list[dict] = []
    круг = 0
    while len(отклонённые) < а.rejected and any(
            len(v) > круг for v in по_кодам.values()):
        for код in sorted(по_кодам):
            if len(по_кодам[код]) > круг and len(отклонённые) < а.rejected:
                отклонённые.append(по_кодам[код][круг])
        круг += 1

    корень = pathlib.Path(а.out)
    корень.mkdir(parents=True, exist_ok=True)
    заголовок = (
        "<!-- Собрано scripts/seo_content/export_examples.py. "
        "Случаи синтетические: названия вымышлены, витрины — seo-test-*. -->\n")
    (корень / "accepted.md").write_text(
        заголовок + "# Принятые черновики\n\n"
        f"Первые {len(принятые)} черновиков прогона, прошедших все ворота. "
        "Подборка не отобрана вручную: берётся начало очереди.\n\n"
        + "\n".join(карточка(з) for з in принятые), encoding="utf-8")
    (корень / "rejected.md").write_text(
        заголовок + "# Отклонённые черновики и причины\n\n"
        f"{len(отклонённые)} отказов, по одному на код причины, пока коды не "
        "кончились. Каждый отказ назван кодом и объяснён словами.\n\n"
        + "\n".join(карточка(з) for з in отклонённые), encoding="utf-8")
    print(f"принятых: {len(принятые)}, отклонённых: {len(отклонённые)}, "
          f"кодов причин: {len(по_кодам)}")
    return 0


if __name__ == "__main__":
    sys.exit(главное())
