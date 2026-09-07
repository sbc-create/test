"""Редакторское управление витриной из командной строки.

Полноценной админки пока нет — здесь заложен интерфейс, поверх которого её
можно построить, не переписывая ранжировщик. Все команды работают с одним
YAML-файлом решений: его можно прочитать глазами, показать в code review и
откатить как обычный файл.

Два ограничения соблюдаются здесь так же строго, как в ранжировщике:

* закрепление и подъём не отменяют проверку доступности. Редактор управляет
  порядком показа, а не правом показать то, что не играет;
* у каждого решения есть срок. Закрепление без срока переживает повод, по
  которому его поставили.

Секретов файл решений не содержит и содержать не может: в нём только
идентификаторы записей, позиции и сроки.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from factory.recs.editorial import Editorial

DEFAULT_TTL_DAYS = 14


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load(path: Path) -> list:
    if not path.is_file():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def _save(path: Path, documents: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(documents, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")


def _expiry(days: int | None) -> str:
    return (_now() + timedelta(days=days or DEFAULT_TTL_DAYS)).isoformat()


def _add(path: Path, decision: dict, *, dry_run: bool) -> dict:
    documents = _load(path)
    documents.append(decision)
    # Проверка до записи: непонятное решение не должно попасть в файл.
    Editorial.from_documents(documents)
    if not dry_run:
        _save(path, documents)
    return decision


def _remove(path: Path, kind: str, content_id: str, *, dry_run: bool) -> int:
    documents = _load(path)
    kept = [d for d in documents
            if not (str(d.get("action") or d.get("kind")) == kind
                    and str(d.get("content_id")) == content_id)]
    removed = len(documents) - len(kept)
    if not dry_run:
        _save(path, kept)
    return removed


def cmd_pin(args) -> int:
    decision = {"action": "pin", "content_id": args.content_id,
                "position": args.position, "expires_at": _expiry(args.days),
                "reason": args.reason, "author": args.author}
    if args.shelf:
        decision["shelf"] = args.shelf
    if args.domain:
        decision["domain"] = args.domain
    _add(Path(args.file), decision, dry_run=args.dry_run)
    print(json.dumps({"закреплено": decision}, ensure_ascii=False))
    return 0


def cmd_unpin(args) -> int:
    removed = _remove(Path(args.file), "pin", args.content_id, dry_run=args.dry_run)
    print(json.dumps({"снято закреплений": removed}, ensure_ascii=False))
    return 0 if removed else 1


def cmd_ban(args) -> int:
    decision = {"action": "ban", "content_id": args.content_id,
                "expires_at": _expiry(args.days), "reason": args.reason,
                "author": args.author}
    if args.domain:
        decision["domain"] = args.domain
    _add(Path(args.file), decision, dry_run=args.dry_run)
    print(json.dumps({"скрыто": decision}, ensure_ascii=False))
    return 0


def cmd_unban(args) -> int:
    removed = _remove(Path(args.file), "ban", args.content_id, dry_run=args.dry_run)
    print(json.dumps({"снято запретов": removed}, ensure_ascii=False))
    return 0 if removed else 1


def cmd_boost(args) -> int:
    decision = {"action": "boost", "content_id": args.content_id,
                "value": args.value, "expires_at": _expiry(args.days),
                "reason": args.reason, "author": args.author}
    _add(Path(args.file), decision, dry_run=args.dry_run)
    print(json.dumps({"поднято": decision}, ensure_ascii=False))
    return 0


def cmd_replace(args) -> int:
    decision = {"action": "replace", "content_id": args.content_id,
                "replacement_id": args.replacement_id,
                "expires_at": _expiry(args.days), "reason": args.reason,
                "author": args.author}
    _add(Path(args.file), decision, dry_run=args.dry_run)
    print(json.dumps({"заменено": decision}, ensure_ascii=False))
    return 0


def cmd_audit(args) -> int:
    """Что сейчас действует и что уже просрочено."""
    editorial = Editorial.from_documents(_load(Path(args.file)))
    now = _now()
    rows = []
    for decision in editorial.decisions:
        rows.append({
            "решение": decision.kind,
            "запись": decision.content_id,
            "действует": decision.active(now),
            "истекает": decision.expires_at.isoformat() if decision.expires_at else "бессрочно",
            "причина": decision.reason,
            "автор": decision.author,
        })
    print(json.dumps({"всего": len(rows), "действующих": sum(r["действует"] for r in rows),
                      "решения": rows}, ensure_ascii=False, indent=1))
    return 0


def cmd_rollback(args) -> int:
    """Откат редакторской конфигурации: файл решений возвращается к пустому
    состоянию или к указанной копии. Ранжировщик при этом не меняется."""
    path = Path(args.file)
    if args.to:
        source = Path(args.to)
        if not source.is_file():
            print(f"нет копии {source}", file=sys.stderr)
            return 1
        documents = _load(source)
    else:
        documents = []
    Editorial.from_documents(documents)
    if not args.dry_run:
        _save(path, documents)
    print(json.dumps({"откат к": str(args.to) if args.to else "пустой конфигурации",
                      "решений": len(documents)}, ensure_ascii=False))
    return 0



def _load_catalog(site_id: str):
    """Живой каталог сайта — тот же, из которого собирается витрина.

    Предпросмотр обязан смотреть на те же записи, что и сборка; иначе он
    показывает не то, что увидит посетитель.
    """
    from factory.lords import live_catalog, live_site, playability
    from factory.paths import PATHS

    items = live_site.load_live_items(site_id)

    # Признак воспроизводимости живёт в отдельном кэше и проставляется сборкой.
    # Без него предпросмотр показывал пустую полку: допуск справедливо
    # отвергал все записи, потому что поток не был подтверждён ни у одной.
    cache = playability.PlayabilityCache(PATHS.root / "var" / "lords" / "playability.json")
    for item in items:
        playback = item.get("playback") or {}
        item["playable"] = (cache.get(playability.cache_key(playback))
                            if playback.get("title_id") else None)
    return live_catalog.catalog_from_live(items)


def cmd_preview(args) -> int:
    """Состав полки до публикации, с учётом редакторских решений."""
    from factory.lords import recommend

    editorial = Editorial.from_documents(_load(Path(args.file)))
    catalog = _load_catalog(args.site)
    shelf = recommend.carousel_shelf(
        catalog.titles, limit=args.limit, domain=args.domain, editorial=editorial)
    rows = [{"позиция": i + 1, "запись": s.item.content_id,
             "название": s.item.title, "счёт": round(s.score, 4),
             "поток": s.item.playback_state}
            for i, s in enumerate(shelf.items)]
    print(json.dumps({"полка": shelf.shelf_id, "версия": shelf.algorithm_version,
                      "записей": len(rows), "состав": rows},
                     ensure_ascii=False, indent=1))
    return 0


def cmd_explain(args) -> int:
    """Почему запись стоит там, где стоит: сигналы и их вклад."""
    from factory.lords import recommend
    from factory.recs.ranker import WEIGHTS, is_eligible, score_item

    editorial = Editorial.from_documents(_load(Path(args.file)))
    catalog = _load_catalog(args.site)
    wanted = None
    for title in catalog.titles:
        item = recommend.features_from_title(title)
        if item.content_id == args.content_id or title.slug == args.content_id:
            wanted = item
            break
    if wanted is None:
        print(f"запись {args.content_id!r} в каталоге не найдена", file=sys.stderr)
        return 1

    now = _now()
    allowed, reason = is_eligible(wanted, domain=args.domain, editorial=editorial, now=now)
    scored = score_item(wanted, now, editorial=editorial)
    present = {k: v for k, v in scored.signals.items() if v is not None}
    total = sum(WEIGHTS[k] for k in present) or 1.0
    contributions = {k: round(WEIGHTS[k] * v / total, 4) for k, v in present.items()}
    print(json.dumps({
        "запись": wanted.content_id,
        "название": wanted.title,
        "допущена": allowed,
        "причина": reason,
        "счёт": round(scored.score, 4),
        "сигналы": {k: (round(v, 4) if v is not None else None)
                    for k, v in scored.signals.items()},
        "вклад": contributions,
        "отсутствуют": [k for k, v in scored.signals.items() if v is None],
        "пометки": list(scored.reasons),
    }, ensure_ascii=False, indent=1))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lords-curation",
        description="Редакторское управление витриной поверх Ranker v1.")
    parser.add_argument("--file", default="config/lords/editorial.yaml",
                        help="файл редакторских решений")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать результат, ничего не записывая")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, *, author=True, days=True, reason=True):
        if days:
            p.add_argument("--days", type=int, default=DEFAULT_TTL_DAYS,
                           help="срок действия решения в днях")
        if reason:
            p.add_argument("--reason", default="", help="зачем это решение")
        if author:
            p.add_argument("--author", default="", help="кто принял решение")

    p = sub.add_parser("pin", help="закрепить запись на позиции")
    p.add_argument("content_id")
    p.add_argument("--position", type=int, default=1)
    p.add_argument("--shelf")
    p.add_argument("--domain")
    common(p)
    p.set_defaults(func=cmd_pin)

    p = sub.add_parser("unpin", help="снять закрепление")
    p.add_argument("content_id")
    p.set_defaults(func=cmd_unpin)

    p = sub.add_parser("ban", help="скрыть запись с витрины")
    p.add_argument("content_id")
    p.add_argument("--domain")
    common(p)
    p.set_defaults(func=cmd_ban)

    p = sub.add_parser("unban", help="снять запрет")
    p.add_argument("content_id")
    p.set_defaults(func=cmd_unban)

    p = sub.add_parser("boost", help="поднять запись в выдаче")
    p.add_argument("content_id")
    p.add_argument("--value", type=float, default=0.1)
    common(p)
    p.set_defaults(func=cmd_boost)

    p = sub.add_parser("replace", help="заменить запись другой")
    p.add_argument("content_id")
    p.add_argument("replacement_id")
    common(p)
    p.set_defaults(func=cmd_replace)

    p = sub.add_parser("audit", help="показать действующие решения")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("preview", help="показать состав полки до публикации")
    p.add_argument("--site", default="lords-01")
    p.add_argument("--domain")
    p.add_argument("--limit", type=int, default=18)
    p.set_defaults(func=cmd_preview)

    p = sub.add_parser("explain", help="объяснить счёт записи")
    p.add_argument("content_id")
    p.add_argument("--site", default="lords-01")
    p.add_argument("--domain")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("rollback", help="откатить редакторскую конфигурацию")
    p.add_argument("--to", help="файл-копия, к которой откатиться")
    p.set_defaults(func=cmd_rollback)
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
