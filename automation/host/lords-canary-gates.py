#!/usr/bin/env python3
"""Предпереключательные ворота содержимого одной витрины.

Печатает человекочитаемый итог в stderr и машинный JSON в stdout; код возврата
и есть вердикт. Разделение намеренно: сценарий читает stdout, а оператор
читает журнал, и смешивать их — значит однажды разобрать вывод не тем.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import canary  # noqa: E402
from factory.lords.live_catalog import slugify  # noqa: E402

#: Сколько адресов проверяется поимённо. Выборка идёт с равным шагом по всему
#: снимку, а не с начала: первые записи собираются и при частичном рендере, и
#: проверка по ним ничего бы не различила.
SAMPLE_SIZE = 25


def slug_of(item: dict) -> str:
    external = str(item.get("external_id") or "")
    return slugify(str(item.get("name") or "")) or slugify(external) or external.lower()


def main() -> int:
    staging, snapshot_path = Path(sys.argv[1]), Path(sys.argv[2])
    previous = Path(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] else None

    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    items = raw.get("items") if isinstance(raw, dict) else raw
    items = items or []
    step = max(1, len(items) // SAMPLE_SIZE)
    sample = [slug_of(i) for i in items[::step]][:SAMPLE_SIZE]

    report = canary.pre_switch_gates(
        staging, expected_titles=len(items), sample_slugs=sample, previous_site=previous)

    print(json.dumps(report.describe(), ensure_ascii=False))
    out = sys.stderr
    print(f"  страниц произведений: {report.catalog_titles} при снимке {report.expected_titles}",
          file=out)
    print(f"  выборочных адресов собрано: {report.sample_slugs_found}"
          f"/{report.sample_slugs_checked}", file=out)
    print(f"  страниц с плеером: {report.players_new}, было {report.players_previous}", file=out)
    for failure in report.failures:
        print(f"  ОТКАЗ: {failure}", file=out)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
