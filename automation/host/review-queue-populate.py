#!/usr/bin/env python3
"""Наполнение очереди разбора из конфликтов каталога.

Пересчёт не имеет права стереть решение редактора: `upsert` обновляет
утверждения и рекомендацию, но состояние, решение и историю сохраняет.
Поэтому сценарий безопасно запускать повторно — он для того и написан, чтобы
запускаться после каждого обновления каталога.

Рекомендация вычисляется, но НЕ применяется. Для конфликта
PROVIDER_TYPE_VS_KIND_TAG её вообще нет: у поставщика нет приоритета между
собственным полем `type` и собственным тегом, и предлагать один из них
значило бы выдать догадку за совет.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from factory.site_engine import catalog_identity  # noqa: E402
from factory.site_engine.review_queue import (  # noqa: E402
    Claim,
    ReviewItem,
    ReviewQueue,
    item_id_for,
)

spec = importlib.util.spec_from_file_location(
    "registry", REPO / "automation/host/content-identity-registry.py"
)
registry = importlib.util.module_from_spec(spec)
sys.argv_backup, sys.argv = list(sys.argv), ["registry"]
spec.loader.exec_module(registry)
sys.argv = sys.argv_backup

#: Как назвать источник утверждения, чтобы редактор понял, кому верить.
ИСТОЧНИК = {
    "provider_type": "поле type поставщика",
    "kind_tag": "тег вида у поставщика",
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", required=True)
    p.add_argument(
        "--state-root",
        required=True,
        help="корень состояния; очередь ляжет в var/state/review-queue",
    )
    p.add_argument("--limit", type=int, default=0)
    a = p.parse_args()

    очередь = ReviewQueue(a.state_root)
    записи = list(registry.читать_каталог(Path(a.catalog)))
    if a.limit:
        записи = записи[: a.limit]

    добавлено = обновлено = 0
    for site, запись, _ in записи:
        решение = catalog_identity.decide(
            provider_type=запись.get("type"), tags=запись.get("tags") or ()
        )
        if not решение.conflicted:
            continue
        eid = f"{site}:{запись.get('external_id')}"
        iid = item_id_for(eid, "contentKind")
        было = (очередь.dir / f"{iid}.json").exists()

        утверждения = [
            Claim(
                value=решение.provider_kind.value,
                source=ИСТОЧНИК["provider_type"],
                evidence=f"type={запись.get('type')!r}",
                confidence=0.5,
            )
        ]
        for вид in решение.tag_kinds:
            теги = [t for t in (запись.get("tags") or []) if str(t).lower() == вид.value.lower()]
            утверждения.append(
                Claim(
                    value=вид.value,
                    source=ИСТОЧНИК["kind_tag"],
                    evidence=f"tags={теги or [вид.value.lower()]}",
                    confidence=0.5,
                )
            )

        очередь.upsert(
            ReviewItem(
                item_id=iid,
                internal_entity_id=eid,
                site_id=site,
                conflict_code=решение.conflicts[0] if решение.conflicts else "UNKNOWN",
                field="contentKind",
                claims=tuple(утверждения),
                title=запись.get("name") or "",
                year=запись.get("year") if isinstance(запись.get("year"), int) else None,
                external_ids={
                    k: str(v) for k, v in (запись.get("external_ids") or {}).items() if v
                },
                recommendation="",
                recommendation_reason=решение.reason,
            )
        )
        обновлено += было
        добавлено += not было

    свод = очередь.list(limit=0)
    print(
        json.dumps(
            {
                "added": добавлено,
                "updated": обновлено,
                "queueTotal": свод["totalAll"],
                "byState": свод["byState"],
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
