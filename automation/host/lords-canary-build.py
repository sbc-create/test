#!/usr/bin/env python3
"""Сборка одной витрины Lords на живом каталоге.

Токен читается из systemd credential и наружу не печатается — печатается
только число собранных записей. Без токена сборка не падает: обогащение
пропускается, каталог и навигация от него не зависят.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from factory.lords import live_site  # noqa: E402


def token_from_credentials() -> str | None:
    directory = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
    if not directory:
        return None
    name = os.environ.get("CDNVIDEOHUB_API_TOKEN_CREDENTIAL", "cdnvideohub_api_token")
    try:
        return (Path(directory) / name).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


#: Каталог снимка живого каталога — явный вход, а не догадка.
#:
#: `load_live_items` по умолчанию ищет кэш относительно корня репозитория, из
#: которого запущен код. Для операции, идущей из отдельного дерева с
#: закреплённым артефактом, это неверный адрес: снимок наполняет служба
#: обновления и лежит он в боевом репозитории. Прежде переменную читала только
#: оболочка — для отчёта о числе записей, — а сборка уходила искать кэш рядом с
#: собой и падала BlockedInput при уже найденном снимке в 53 229 записей.
SNAPSHOT_DIR_ENV = "LORDS_SNAPSHOT_DIR"


def snapshot_dir() -> Path | None:
    value = os.environ.get(SNAPSHOT_DIR_ENV, "").strip()
    if not value:
        return None
    path = Path(value)
    if not path.is_dir():
        raise SystemExit(f"{SNAPSHOT_DIR_ENV} указывает не на каталог: {path}")
    return path


def main() -> int:
    site_id, out = sys.argv[1], Path(sys.argv[2])
    result = live_site.build_live_site(
        site_id, output=out, root=snapshot_dir(), enrich_budget=0,
        credentials_token=token_from_credentials(), playability_budget=0)
    print(result.report["catalog"]["titles"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
