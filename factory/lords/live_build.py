"""Сборка трёх сайтов Lords на живом каталоге CDNVideoHub.

Вызывается активатором, когда секреты уже переданы. Отличие от обычной сборки
ровно одно: каталог берётся из источника, а не из фикстуры, и плеер получает
настоящие Publisher ID и пару агрегатор/идентификатор.

Ничего не применяется к работающим службам: здесь только артефакты. Раскладку
релизов и перезапуск делает активатор, и только после того, как отчёт признан
пригодным.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

from factory.lords import content_live, player
from factory.lords import staging as staging_mod
from factory.paths import PATHS

TOKEN_ENV = "CDNVIDEOHUB_API_TOKEN"
PUBLISHER_ENV = "CDNVIDEOHUB_PUBLISHER_ID"

#: Каталог, ниже которого сайт не публикуется. Раздел, отвечающий 200 без
#: единого материала, — обещание, которого сайт не выполняет.
MIN_ITEMS = 1


class LiveBuildError(RuntimeError):
    """Живая сборка невозможна. Переключение обязано быть отменено."""


@dataclass(frozen=True)
class Credentials:
    token: str
    publisher_id: str

    @classmethod
    def from_env(cls, env: dict | None = None) -> Credentials:
        source = os.environ if env is None else env
        player.assert_no_public_publisher_id(source)
        token = (source.get(TOKEN_ENV) or "").strip()
        publisher = (source.get(PUBLISHER_ENV) or "").strip()
        missing = [
            name for name, value in ((TOKEN_ENV, token), (PUBLISHER_ENV, publisher))
            if not value
        ]
        if missing:
            raise LiveBuildError("не переданы: " + ", ".join(missing))
        if not player.is_valid_publisher_id(publisher):
            raise LiveBuildError("Publisher ID обязан быть положительным целым")
        return cls(token=token, publisher_id=publisher)


def _catalog_dir() -> Path:
    return PATHS.root / "var" / "lords"


def build_live(
    *,
    credentials: Credentials,
    contract: content_live.LiveContract | None = None,
    fetcher_factory=None,
    now_ms: int | None = None,
) -> dict:
    """Живой каталог для трёх сайтов и отчёт о нём.

    Возвращает отчёт, пригодный как доказательство: статус источника по каждому
    сайту, число записей, включённые разделы и страница тайтла для проверки
    плеера. Значения секретов в отчёт не попадают — только факт их наличия.
    """
    live_contract = contract or content_live.load_live_contract()
    stamp = now_ms if now_ms is not None else int(time.time() * 1000)
    sites = staging_mod.sites()

    report: dict = {
        "generated_at_ms": stamp,
        "contract_ref": "knowledge/cdnvideohub/content-api.yaml",
        "publisher_id_present": True,
        "api_token_present": True,
        "sites": {},
    }

    for site in sites:
        cache_file = content_live.cache_path(_catalog_dir(), site.site_id)
        fetcher = (
            fetcher_factory(site)
            if fetcher_factory
            else content_live.Fetcher(contract=live_contract, token=credentials.token)
        )
        outcome = content_live.fetch_catalog(
            contract=live_contract,
            fetcher=fetcher,
            cache_file=cache_file,
            now_ms=stamp,
        )
        sections = content_live.enabled_sections(outcome.items, live_contract)
        enabled = sorted(name for name, spec in sections.items() if spec.get("enabled"))

        playable = [i for i in outcome.items if i.get("playback")]
        sample_path = ""
        if playable:
            sample_path = f"/title/{playable[0]['external_id']}/"

        entry = outcome.as_dict()
        entry.update({
            "sections": sections,
            "sections_enabled": enabled,
            "playable_count": len(playable),
            "sample_title_path": sample_path,
        })
        report["sites"][site.site_id] = entry

    return report


def write_report(report: dict, *, output: Path | None = None) -> Path:
    target = Path(output) if output else PATHS.root / "artifacts" / "lords" / "live" / "report.json"
    content_live.write_atomic(target, report)
    return target


def verify_report(report: dict) -> list[str]:
    """Пригоден ли результат для публикации. Пустой список — пригоден."""
    problems: list[str] = []
    sites = report.get("sites") or {}
    if not sites:
        return ["в отчёте нет ни одного сайта"]
    for site_id, entry in sites.items():
        if entry.get("status") != content_live.FRESH:
            problems.append(f"{site_id}: статус источника {entry.get('status')}")
        if entry.get("item_count", 0) < MIN_ITEMS:
            problems.append(f"{site_id}: каталог пуст")
        if not entry.get("sections_enabled"):
            problems.append(f"{site_id}: ни одного раздела с материалами")
        if entry.get("playable_count", 0) < 1:
            problems.append(f"{site_id}: ни одного тайтла с парой агрегатор/идентификатор")
    return problems


def redact(report: dict) -> str:
    """Отчёт в виде текста. Секретов в нём нет по построению."""
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
