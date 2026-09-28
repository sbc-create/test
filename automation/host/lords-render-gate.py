#!/usr/bin/env python3
"""Ворота перед сборкой: нужно ли вообще рендерить эту витрину.

Нынешний сценарий узнаёт ответ только после сборки — идентификатор релиза
считается от содержимого уже собранной витрины. Поэтому цикл всегда платит
полную цену: два часа двадцать две минуты на витрину, даже когда менять нечего.

Эти ворота считают отпечаток входных данных за секунды и отвечают до работы.

Коды возврата:

    0 — рендер нужен, вход изменился (или сравнивать не с чем)
    10 — рендер не нужен, вход тот же
    2 — ответить не удалось; в этом случае рендер нужен, потому что молчание
        не повод пропустить обновление

Последнее важнее, чем кажется. Ворота, которые при собственной поломке
отвечают «не надо», останавливают обновление каталога навсегда и незаметно —
ровно так, как это уже произошло с неактивным таймером.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords.detail_enrichment import DETAIL_FIELDS, cache_dir  # noqa: E402
from factory.site_engine.fingerprint import (  # noqa: E402
    RenderInputs,
    catalog_digest,
    compare,
    digest,
    enrichment_digest,
    load,
    mapping_digest,
    save,
    tree_digest,
)

НУЖЕН = 0
НЕ_НУЖЕН = 10
НЕЯСНО = 2


def _renderer_version(repo: Path) -> str:
    """Отпечаток кода, который строит страницы.

    Считается по файлам рендерера, а не по номеру версии в переменной: номер
    забывают поднять, а содержимое не соврёт.
    """
    файлы = [
        repo / "factory" / "lords" / "render.py",
        repo / "factory" / "lords" / "live_catalog.py",
        repo / "factory" / "lords" / "live_site.py",
        repo / "factory" / "lords" / "theme.py",
        repo / "factory" / "lords" / "player.py",
        # Разбиение каталога на страницы входит в замороженный артефакт
        # шаблона и меняет каждую страницу листинга. В отпечатке его не было:
        # правка пагинации не вызывала пересборку.
        repo / "factory" / "lords" / "pagination.py",
    ]
    h = hashlib.sha256()
    for путь in файлы:
        h.update(путь.name.encode("utf-8"))
        h.update(hashlib.sha256(путь.read_bytes()).digest() if путь.exists() else b"-")
    return h.hexdigest()


def _template_version(repo: Path) -> str:
    """Отпечаток шаблона направления: blueprint и профили витрин.

    Раньше здесь стояло ``tree_digest(blueprints/lords, ("*.html", "*.j2"))``.
    Маска не совпадала ни с одним файлом: рендерер Lords написан на Python, а
    профили — YAML, и `.html`/`.j2` в каталоге нет вовсе. Отпечаток выходил
    равным ``sha256("[]")`` — хешу пустого списка — на всех витринах и во всех
    прогонах. Поле выглядело как отпечаток и не несло ни одного бита о шаблоне,
    поэтому смена профиля не вызывала пересборку: ворота отвечали «вход не
    изменился», и выложенный шаблон не доезжал до страниц.
    """
    blueprint = repo / "blueprints" / "lords"
    файлы: list[tuple[str, str]] = []
    for путь in sorted(blueprint.rglob("*.yaml")) + sorted(blueprint.rglob("*.yml")):
        if путь.is_file():
            файлы.append((путь.relative_to(blueprint).as_posix(),
                          hashlib.sha256(путь.read_bytes()).hexdigest()))
    if not файлы:
        # Пустой шаблон — не «пусто», а «нечем считать». Значение отличается от
        # хеша пустого списка нарочно: молчаливое равенство пустот и было тем,
        # что скрывало поломку.
        return "absent:no-template-sources"
    return digest(sorted(set(файлы)))


def _route_registry(repo: Path, site_id: str) -> str:
    """Отпечаток реестра маршрутов витрины.

    Каталога ``var/lords/routes`` на машине нет, и ``tree_digest`` возвращал для
    него ``digest(None)`` — правдоподобный отпечаток отсутствующего входа.
    Отсутствие называется прямо: так его видно в отчёте, а не принимают за
    посчитанное значение.
    """
    путь = repo / "var" / "lords" / "routes" / f"{site_id}.json"
    if not путь.is_file():
        return "absent:no-route-registry"
    return digest(hashlib.sha256(путь.read_bytes()).hexdigest())


def collect(repo: Path, site_id: str, cache: Path) -> RenderInputs:
    items = json.loads(cache.read_text(encoding="utf-8")).get("items") or []
    package = repo / "sites" / site_id / "package.yaml"
    var = repo / "var"
    return RenderInputs(
        catalog=catalog_digest(items),
        # Списочный каталог не содержит ни жанров, ни описаний, ни состава: всё
        # это приносит обогащение и хранит отдельно. Ворота, смотревшие только
        # на каталог, отвечали «не надо» при изменившихся страницах.
        enrichment=enrichment_digest(cache_dir(var), DETAIL_FIELDS),
        # Признак воспроизводимости решает, попадёт ли запись на полку.
        playability=mapping_digest(var / "lords" / "playability.json", keep=("playable",)),
        renderer_version=_renderer_version(repo),
        template_version=_template_version(repo),
        site_profile=digest(package.read_text(encoding="utf-8") if package.exists() else ""),
        shelf_configuration=tree_digest(repo / "factory" / "lords", ("plan.py",)),
        route_registry=_route_registry(repo, site_id),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_id")
    parser.add_argument("--repo", default="/srv/site-factory/repo")
    parser.add_argument("--cache", default=None)
    parser.add_argument("--state", default=None)
    parser.add_argument("--record", action="store_true",
                        help="записать отпечаток как принятый (после удачной сборки)")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    cache = Path(args.cache or repo / "var" / "lords" / "lords" / "catalog-cache"
                 / f"{args.site_id}.json")
    state = Path(args.state or repo / "var" / "lords" / "fingerprints"
                 / f"{args.site_id}.json")

    try:
        текущий = collect(repo, args.site_id, cache)
    except (OSError, ValueError, KeyError) as error:
        # Не смогли посчитать — значит, не знаем. Не знать и пропустить рендер
        # значит остановить обновление молча.
        print(f"[render-gate] {args.site_id}: отпечаток не посчитан ({error}); рендер нужен",
              file=sys.stderr)
        return НЕЯСНО

    if args.record:
        save(state, текущий)
        print(f"[render-gate] {args.site_id}: отпечаток принят {текущий.fingerprint()[:12]}")
        return НУЖЕН

    прежний = load(state)
    разница = compare(прежний, текущий)
    if not разница.any_change:
        print(f"[render-gate] {args.site_id}: вход не изменился "
              f"({текущий.fingerprint()[:12]}) — рендер не нужен")
        return НЕ_НУЖЕН

    причина = разница.describe()
    полная = " (нужна полная пересборка)" if разница.needs_full_rebuild else ""
    print(f"[render-gate] {args.site_id}: {причина}{полная} — рендер нужен")
    return НУЖЕН


if __name__ == "__main__":
    raise SystemExit(main())
