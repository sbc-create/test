"""Быстрый путь Lords: переписать только то, что изменилось.

Зачем. Полный цикл `lords-content-refresh` идёт часами, и почти всё это время
занимает обход провайдера, а не отрисовка. Выход одной серии не требует ни
обхода, ни перезаписи 53 116 страниц: меняется страница тайтла и несколько
листингов, где стоит её карточка.

Что делает этот модуль. Берёт уже сохранённый кэш каталога, собирает сайт в
памяти, сличает каждую страницу с тем, что лежит в текущем релизе, и переносит
в новый релиз **только различающиеся**. Новый релиз — связанная копия прежнего
(жёсткие ссылки), поэтому неизменившиеся файлы не копируются вовсе.

Чего он не делает. Не ходит к провайдеру, не обогащает записи, не переключает
символьную ссылку. Переключение — отдельное решение вызывающего.

Свойство, ради которого всё это: если каталог не изменился, переписанных
страниц ноль и новый релиз не создаётся.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from factory.lords import detail_enrichment, live_catalog, live_site
from factory.lords import playability as playability_mod
from factory.lords import render as render_mod
from factory.lords import serve as serve_mod
from factory.paths import PATHS
from factory.site_engine import incremental


@dataclass
class FastPathResult:
    """Что произошло. Считается по факту, а не по намерению."""

    site_id: str
    pages_total: int
    pages_changed: int
    pages_added: int
    pages_removed: int
    release: Path | None
    base: Path
    seconds_catalog: float = 0.0
    seconds_render: float = 0.0
    seconds_diff: float = 0.0
    seconds_write: float = 0.0
    linked_files: int = 0
    changed_paths: tuple[str, ...] = ()
    base_untouched: bool = True
    base_violations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def seconds_total(self) -> float:
        return self.seconds_catalog + self.seconds_render + self.seconds_diff + self.seconds_write

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "pages_total": self.pages_total,
            "pages_changed": self.pages_changed,
            "pages_added": self.pages_added,
            "pages_removed": self.pages_removed,
            "release": str(self.release) if self.release else None,
            "base": str(self.base),
            "seconds": {
                "catalog": round(self.seconds_catalog, 2),
                "render": round(self.seconds_render, 2),
                "diff": round(self.seconds_diff, 2),
                "write": round(self.seconds_write, 2),
                "total": round(self.seconds_total, 2),
            },
            "linked_files": self.linked_files,
            "changed_paths": list(self.changed_paths[:50]),
            "base_untouched": self.base_untouched,
            "base_violations": list(self.base_violations),
        }


class _NoNetwork:
    """Загрузчик, который не ходит в сеть — и падает, если его об этом попросят.

    Быстрый путь обязан обходиться сохранённым: обход провайдера и есть та
    работа, которая занимает часы. Молчаливое падение в сеть выглядело бы как
    «просто медленно», поэтому попытка обрывается с ошибкой.
    """

    def fetch(self, *args, **kwargs):  # noqa: D102, ANN002, ANN003
        raise RuntimeError("быстрый путь не ходит к провайдеру")

    def __getattr__(self, name: str):  # noqa: D105
        raise RuntimeError(f"быстрый путь не ходит к провайдеру: {name}")


def _apply_cached_enrichment(
    entries: list[dict], site_id: str, var_root: Path | None = None
) -> list[dict]:
    """Накладывает уже сохранённые detail-данные и признак воспроизводимости.

    Без этого шага страницы выходят беднее релиза: пропадают жанровые фильтры и
    полки, которые строятся по обогащённым полям. Проверено сличением с живым
    релизом — разница была именно в них, а не в каталоге.

    Бюджет нулевой: ни одного сетевого запроса. Загрузчик заведомо неработающий,
    поэтому выход в сеть невозможен незаметно.
    """
    try:
        base_var = Path(var_root) if var_root else PATHS.root / "var"
        cache = detail_enrichment.DetailCache(detail_enrichment.cache_dir(base_var))
        entries, _ = detail_enrichment.enrich_items(
            entries, fetcher=_NoNetwork(), contract=None, cache=cache, budget=0
        )
    except Exception:  # noqa: BLE001
        # Обогащение — улучшение, а не условие. Если кэша нет, страницы будут
        # беднее, и это видно по сличению, а не молча.
        pass
    try:
        publisher = live_site.publisher_id_for(site_id)
        if publisher:
            playability_mod.annotate(
                entries,
                str(publisher),
                budget=0,
                cache=playability_mod.PlayabilityCache(
                    (Path(var_root) if var_root else PATHS.root / "var") / "lords" / "playability.json"
                ),
            )
    except Exception:  # noqa: BLE001
        pass
    return entries


def _relative_for(path: str) -> str:
    """Адрес страницы → путь файла в релизе. Та же раскладка, что у выгрузки."""
    if path.endswith("/"):
        return f"{path.strip('/')}/index.html" if path.strip("/") else "index.html"
    return path.lstrip("/")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_from_cache(
    site_id: str,
    *,
    cache_root: str | Path | None = None,
    var_root: str | Path | None = None,
    only_title_slugs: frozenset[str] | None = None,
):
    """Собирает сайт в памяти из сохранённого каталога. К провайдеру не ходит.

    `only_title_slugs` — те произведения, чьи страницы нужно отрисовать. Всё
    остальное (главная, листинги, расписание, подборки) строится всегда: эти
    страницы содержат карточки и меняются от выхода серии, а стоят дёшево.
    Страниц произведений 53 116, и именно они занимают почти всё время сборки.
    """
    started = time.monotonic()
    entries = live_site.load_live_items(site_id, root=cache_root)
    entries = _apply_cached_enrichment(entries, site_id, var_root)
    catalog = live_catalog.catalog_from_live(entries)
    seconds_catalog = time.monotonic() - started

    package = yaml.safe_load(PATHS.site_package(site_id).read_text(encoding="utf-8"))
    started = time.monotonic()
    site = render_mod.render_site(
        package,
        catalog=catalog,
        environ={},
        publisher_id=live_site.publisher_id_for(site_id),
        only_title_slugs=only_title_slugs,
    )
    return site, seconds_catalog, time.monotonic() - started


def diff_against(site, base: Path, *, partial: bool = False) -> tuple[dict[str, str], list[str], list[str]]:
    """Что различается между отрисованным сайтом и тем, что лежит в релизе.

    Возвращает: страницы к записи, добавленные адреса, удалённые адреса.
    Сравнение по содержимому, а не по времени изменения: время меняется при
    каждой сборке и ничего не говорит о том, изменилась ли страница.

    `partial=True` — отрисован не весь сайт. В этом режиме список удалённых не
    вычисляется: отсутствие страницы среди отрисованных ничего не значит, её
    просто не просили строить.
    """
    to_write: dict[str, str] = {}
    added: list[str] = []
    present: set[str] = set()

    for path, page in site.pages.items():
        relative = _relative_for(path)
        present.add(relative)
        payload = page.payload
        existing = base / relative
        if not existing.exists():
            added.append(relative)
            to_write[relative] = payload.decode("utf-8", errors="replace")
            continue
        if _digest(existing.read_bytes()) != _digest(payload):
            to_write[relative] = payload.decode("utf-8", errors="replace")

    removed = []
    if partial:
        return to_write, added, removed
    if base.exists():
        for existing in base.rglob("*.html"):
            relative = str(existing.relative_to(base))
            if relative not in present and relative != "404.html":
                removed.append(relative)

    return to_write, added, removed


def apply(
    site_id: str,
    *,
    base: Path,
    target: Path | None = None,
    cache_root: str | Path | None = None,
    var_root: str | Path | None = None,
    only_title_slugs: frozenset[str] | None = None,
    remove_relatives: tuple[str, ...] = (),
    write: bool = True,
) -> FastPathResult:
    """Быстрый путь целиком: собрать, сличить, переписать различающееся.

    `write=False` — сухой прогон: считает, что изменилось, и ничего не пишет.
    `target=None` при непустом изменении означает, что писать некуда; такой
    вызов равносилен сухому прогону.
    """
    base = Path(base)
    site, seconds_catalog, seconds_render = render_from_cache(
        site_id, cache_root=cache_root, var_root=var_root, only_title_slugs=only_title_slugs
    )

    started = time.monotonic()
    to_write, added, removed = diff_against(site, base, partial=only_title_slugs is not None)
    # В ограниченном режиме удалённые не вычисляются по отсутствию: их называет
    # вызывающий, сравнив снимки произведений.
    if only_title_slugs is not None and remove_relatives:
        removed = list(remove_relatives)
    seconds_diff = time.monotonic() - started

    result = FastPathResult(
        site_id=site_id,
        pages_total=len(site.pages),
        pages_changed=len(to_write),
        pages_added=len(added),
        pages_removed=len(removed),
        release=None,
        base=base,
        seconds_catalog=seconds_catalog,
        seconds_render=seconds_render,
        seconds_diff=seconds_diff,
        changed_paths=tuple(sorted(to_write)),
    )

    # Ничего не изменилось — нового релиза не возникает. Это и есть то
    # свойство, ради которого путь называется быстрым: неизменившийся цикл не
    # переписывает ни одной страницы и не трогает текущий релиз.
    if not to_write and not removed:
        return result

    if not write or target is None:
        return result

    checksums = incremental.checksums_of(base, tuple(sorted(to_write))[:64])
    built = incremental.build_incremental(
        base, Path(target), pages=to_write, remove=tuple(removed)
    )
    result.release = built.release
    result.linked_files = built.linked_files
    result.seconds_write = built.seconds
    violations = incremental.verify_base_untouched(base, checksums)
    result.base_untouched = not violations
    result.base_violations = tuple(violations)
    return result


#: Поля записи, влияющие на страницу произведения. Совпадает по смыслу с полями
#: отпечатка каталога: служебные времена сюда не входят, иначе «изменилось»
#: срабатывало бы на каждом прогоне.
TITLE_FIELDS = (
    "external_id", "name", "original_name", "year", "type", "is_series",
    "genres", "countries", "tags", "poster_url", "playback", "licensed",
    "kinopoisk_rating", "imdb_rating", "external_ids", "seasons",
    "episodes_count", "available_episodes_count", "description",
    "duration", "premiere_date", "voice_studios", "available_voices",
)


def title_digests(entries: Iterable[dict], catalog) -> dict[str, dict[str, str]]:
    """Отпечаток каждого произведения: `external_id → {slug, digest}`.

    Нужен, чтобы отвечать не на вопрос «изменился ли каталог», а на вопрос
    «какие именно страницы придётся переписать». Первый вопрос ворота уже
    решают; второй — то, ради чего существует быстрый путь.
    """
    slugs = {}
    for title in getattr(catalog, "titles", ()):  # slug считается при сборке каталога
        внешний = getattr(title, "external_id", None) or getattr(title, "provider_id", None)
        if внешний:
            slugs[str(внешний)] = title.slug
    итог: dict[str, dict[str, str]] = {}
    for запись in entries:
        внешний = запись.get("external_id")
        if not внешний:
            continue
        полезное = {f: запись.get(f) for f in TITLE_FIELDS if f in запись}
        итог[str(внешний)] = {
            "slug": slugs.get(str(внешний), ""),
            "digest": hashlib.sha256(
                json.dumps(полезное, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()[:32],
        }
    return итог


@dataclass
class TitleChanges:
    """Что изменилось между двумя снимками произведений."""

    changed_slugs: tuple[str, ...] = ()
    removed_slugs: tuple[str, ...] = ()
    added: int = 0
    modified: int = 0
    removed: int = 0

    @property
    def any(self) -> bool:
        return bool(self.changed_slugs or self.removed_slugs)

    def as_dict(self) -> dict:
        return {
            "added": self.added,
            "modified": self.modified,
            "removed": self.removed,
            "changed_slugs": list(self.changed_slugs[:20]),
            "removed_slugs": list(self.removed_slugs[:20]),
        }


def compare_titles(previous: dict, current: dict) -> TitleChanges:
    """Разница между снимками. Пустой прежний снимок означает «сравнивать не с чем»."""
    добавлено = [k for k in current if k not in previous]
    изменено = [
        k for k in current
        if k in previous and previous[k].get("digest") != current[k].get("digest")
    ]
    удалено = [k for k in previous if k not in current]
    return TitleChanges(
        changed_slugs=tuple(sorted(
            {current[k]["slug"] for k in добавлено + изменено if current[k].get("slug")}
        )),
        removed_slugs=tuple(sorted(
            {previous[k].get("slug", "") for k in удалено if previous[k].get("slug")}
        )),
        added=len(добавлено),
        modified=len(изменено),
        removed=len(удалено),
    )
