#!/usr/bin/env python3
"""Замер покрытия воспроизведения по всему массиву.

Отвечает на один вопрос — «сколько карточек без видео и почему» — так, чтобы
ответ можно было повторить и сравнить с прежним. Разбивка по витрине, месяцу
поступления, набору идентификаторов источника и коду причины: без неё средняя
величина по массиву скрывает то, ради чего замер и делается. Проверено:
общая доля отсутствия видео 1,2 процента, а среди поступлений августа —
сорок процентов.

Проба потока не выполняется: здесь считается состояние каталога. Кэш проб
подключается файлом var/lords/playability.json, если он есть.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from factory.site_engine.api import reasons  # noqa: E402


def месяц(запись: dict) -> str:
    значение = str(запись.get("created_at") or "")
    return значение[:7] if len(значение) >= 7 else "неизвестно"


def набор(запись: dict) -> str:
    ext = запись.get("external_ids")
    if not isinstance(ext, dict) or not ext:
        return "—"
    return "+".join(sorted(ext))


def замер(файл: Path, пробы: dict) -> dict:
    данные = json.loads(файл.read_text(encoding="utf-8"))
    записи = [i for i in данные.get("items") or [] if isinstance(i, dict)]
    итог = {
        "витрина": файл.stem,
        "всего": len(записи),
        "источник": данные.get("source"),
        "собран": данные.get("fetched_at_ms"),
        "коды": collections.Counter(),
        "по_месяцам": collections.defaultdict(lambda: [0, 0]),
        "по_наборам": collections.defaultdict(lambda: [0, 0]),
        "по_типам": collections.defaultdict(lambda: [0, 0]),
        "агрегаторы": collections.Counter(),
    }
    for запись in записи:
        pb = запись.get("playback")
        проба = None
        if isinstance(pb, dict):
            ключ = f"{pb.get('aggregator')}:{pb.get('title_id')}"
            проба = пробы.get(ключ)
        код = запись.get("playback_blocked_reason") or reasons.classify_descriptor(
            запись.get("external_ids"), pb, probe=проба
        )
        итог["коды"][код] += 1
        играет = код == "OK"
        тип = "сериал" if запись.get("is_series") else "фильм"
        for ключ, куда in (
            (месяц(запись), "по_месяцам"),
            (набор(запись), "по_наборам"),
            (тип, "по_типам"),
        ):
            итог[куда][ключ][0] += 1
            итог[куда][ключ][1] += 1 if играет else 0
        итог["агрегаторы"][(pb or {}).get("aggregator") if isinstance(pb, dict) else "нет"] += 1
    return итог


def печать(и: dict, *, месяцев: int) -> None:
    всего, ок = и["всего"], и["коды"].get("OK", 0)
    доля = 100.0 * ок / всего if всего else 0.0
    print(
        f"\n### {и['витрина']}  всего {всего}  играет {ок} ({доля:.2f} %)  "
        f"источник {и['источник']}"
    )
    print("  коды причин:")
    for код, n in и["коды"].most_common():
        print(f"    {код:36s} {n:6d}  {100.0*n/всего:6.2f} %")
    print("  агрегаторы дескриптора:")
    for a, n in и["агрегаторы"].most_common():
        print(f"    {str(a):36s} {n:6d}")
    print(f"  по месяцу поступления (последние {месяцев}):")
    for м in sorted(и["по_месяцам"], reverse=True)[:месяцев]:
        n, o = и["по_месяцам"][м]
        print(f"    {м:36s} {n:6d}  играет {o:6d}  нет {n-o:5d}  ({100.0*(n-o)/n:6.2f} %)")
    print("  по набору идентификаторов источника (топ-10):")
    топ = sorted(и["по_наборам"].items(), key=lambda kv: -kv[1][0])[:10]
    for к, (n, o) in топ:
        print(f"    {к:36s} {n:6d}  играет {o:6d}  нет {n-o:5d}  ({100.0*(n-o)/n:6.2f} %)")
    print("  по типу:")
    for к, (n, o) in sorted(и["по_типам"].items()):
        print(f"    {к:36s} {n:6d}  играет {o:6d}  нет {n-o:5d}  ({100.0*(n-o)/n:6.2f} %)")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cache-dir", default=str(REPO / "var/lords/lords/catalog-cache"))
    p.add_argument("--probes", default=str(REPO / "var/lords/playability.json"))
    p.add_argument("--months", type=int, default=8)
    p.add_argument("--json", help="куда сложить машинный результат")
    a = p.parse_args()

    пробы = {}
    путь_проб = Path(a.probes)
    if путь_проб.is_file():
        try:
            сырое = json.loads(путь_проб.read_text(encoding="utf-8"))
            пробы = сырое.get("entries", сырое) if isinstance(сырое, dict) else {}
            плоские = {}
            for k, v in пробы.items():
                плоские[k] = v.get("state") if isinstance(v, dict) else v
            пробы = плоские
        except (OSError, json.JSONDecodeError):
            пробы = {}
    print(f"проб в кэше: {len(пробы)}")

    файлы = sorted(Path(a.cache_dir).glob("*.json"))
    if not файлы:
        print("каталог пуст — замер невозможен", file=sys.stderr)
        return 2
    все = []
    for ф in файлы:
        и = замер(ф, пробы)
        все.append(и)
        печать(и, месяцев=a.months)
    if a.json:
        Path(a.json).write_text(
            json.dumps(
                [
                    {
                        "витрина": и["витрина"],
                        "всего": и["всего"],
                        "коды": dict(и["коды"]),
                        "агрегаторы": {str(k): v for k, v in и["агрегаторы"].items()},
                        "по_месяцам": dict(и["по_месяцам"]),
                    }
                    for и in все
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\nмашинный результат: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
