"""Fixture-данные шаблона: чем шаблон показывают, пока сайта ещё нет.

Шаблон и сайт — разные вещи. Сайт — это домен, права на контент, счётчик и
решение владельца об индексации; шаблон — раскладка. Чтобы посмотреть на новый
шаблон, не нужно ни одного из этих решений, поэтому здесь собирается пакет,
существующий только в памяти, и синтетический каталог `factory/lords/fixtures.py`
(источник помечен `fixture/test`).

Пакет умышленно беден: домена нет, индексация выключена, Content API выключен,
права не подтверждены. Это не упрощение, а требование — стенд, у которого
что-нибудь из перечисленного включено, перестал бы отличаться от боевой сборки
(см. factory/lords/preview.py).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from factory.lords import fixtures as fx
from factory.lords import render as render_mod
from factory.templates import contract

#: Типы контента стенда. Совпадают с теми, что подтверждает синтетический
#: каталог: объявить тип, которого каталог не отдаёт, значит получить раздел в
#: состоянии disabled_by_api и пустую навигацию.
FIXTURE_CONTENT_TYPES = {
    "movies": True,
    "series": True,
    "animation": True,
    "anime": False,
    "dorama": False,
    "collections": True,
}


@dataclass(frozen=True)
class ContractTitle(fx.Title):
    """Запись стенда, дополненная тем, что требуют блоки главной.

    `fx.Title` описывает произведение, а не его доступность: у него нет ни
    оценки, ни ответа источника о потоке, ни даты поступления. Живая запись
    (`factory/lords/live_catalog.py title_from_item`) всё это имеет, и три блока
    главной опираются именно на эти поля:

    * `top_carousel` — ранжировщик берёт только записи с подтверждённым потоком
      и известной датой поступления (`factory/recs/ranker.py:194`, `:198`);
    * `top_rated` — только записи с подтверждённой оценкой, и меньше четырёх
      таких означает отсутствие полки целиком (`render.py _top_rated`);
    * `latest_grid` — порядок ведёт туда, где есть что смотреть (`_watchable_first`).

    Поэтому на голом каталоге стенда эти блоки не появляются вовсе, и проверить
    шаблон, который их объявил, там нечем. Здесь недостающие поля добавлены —
    детерминированно, без сети и без обращения к источнику.
    """

    external_id: str = ""
    playback: dict = field(default_factory=dict)
    playable: bool | None = None
    created_at: str | None = None
    updated_at: str | None = None
    kinopoisk_rating: float | None = None
    imdb_rating: float | None = None


#: Отсчёт дат поступления. Фиксированный: у стенда не должно быть «сегодня»,
#: иначе два прогона в разные дни дают разные страницы.
EPOCH = datetime(2026, 6, 1, tzinfo=timezone.utc)

#: Каждая четвёртая запись — с подтверждённым отсутствием потока, каждая третья
#: — без оценки. Это не украшение: блоки обязаны быть проверены и на том, что
#: часть каталога в них не попадает, иначе проверка не отличит «блок работает»
#: от «блок показывает всё подряд».
SILENT_EVERY = 4
UNRATED_EVERY = 3


def contract_catalog() -> fx.Catalog:
    """Каталог стенда, на котором каждый блок контракта может появиться."""
    base = fx.build_catalog()
    titles = []
    for index, title in enumerate(base.titles):
        playable = index % SILENT_EVERY != SILENT_EVERY - 1
        rated = index % UNRATED_EVERY != UNRATED_EVERY - 1
        added = EPOCH - timedelta(days=index)
        titles.append(ContractTitle(
            **vars(title),
            external_id=title.slug,
            playback={"aggregator": "kp", "title_id": f"kp-{index + 1000}"},
            playable=playable,
            created_at=added.isoformat(),
            updated_at=added.isoformat(),
            # Оценки разложены по убыванию, чтобы порядок полки был проверяем.
            kinopoisk_rating=round(9.4 - (index % 40) * 0.1, 1) if rated else None,
            imdb_rating=round(9.1 - (index % 35) * 0.1, 1) if rated else None,
        ))
    return fx.Catalog(
        titles=tuple(titles),
        collections=base.collections,
        _by_slug={t.slug: t for t in titles},
    )


def fixture_package(profile: str, *, site_id: str | None = None) -> dict:
    """Минимальный пакет, достаточный для рендера шаблона на стенде."""
    return {
        "schema_version": 1,
        "site_id": site_id or f"template-{profile}",
        "blueprint": "lords",
        "fixture": True,
        "domain": "",
        "environment": "staging",
        "production_authorized": False,
        "seo_indexing_enabled": False,
        "language": "ru",
        "content_types": dict(FIXTURE_CONTENT_TYPES),
        "brand": {"name": profile},
        "tenant": {"seo_profile": profile, "indexing_enabled": False},
        "seo": {"items_per_page": 24},
        "comments": {"enabled": False},
        "analytics": {"enabled": False},
        "content_api": {"mode": "disabled"},
        "content_source": {"rights_confirmed": False},
    }


def scratch_root(manifest: dict, *, base: Path, source: Path | None = None) -> Path:
    """Корень с одним новым шаблоном рядом с существующими.

    `render_site()` читает из корня только `blueprints/lords/`, поэтому копия
    двух файлов заменяет копию репозитория. Настоящее дерево при этом не
    меняется: шаблон можно посмотреть до того, как он куда-либо записан.
    """
    src = Path(source) if source else contract.PATHS.root
    base = Path(base)
    profiles = base / contract.PROFILE_DIR
    profiles.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / contract.BLUEPRINT_FILE, base / contract.BLUEPRINT_FILE)
    for path in (src / contract.PROFILE_DIR).glob("*.yaml"):
        shutil.copy2(path, profiles / path.name)
    name = str(manifest.get("profile") or "")
    (profiles / f"{name}.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return base


def render_fixture_site(manifest: dict, *, base: Path, source: Path | None = None):
    """Собранный сайт шаблона на синтетическом каталоге."""
    root = scratch_root(manifest, base=base, source=source)
    package = fixture_package(str(manifest.get("profile") or ""))
    return render_mod.render_site(package, catalog=contract_catalog(), root=root, environ={})
