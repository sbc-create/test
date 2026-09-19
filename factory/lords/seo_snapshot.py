"""SEO-снимок закрытой Lords-nova витрины: существующие поля, fail-closed.

Снимок — **композиция** уже принятых контрактов, не второй формат:

* provenance nova (`build_manifest` / template-manifest):
  `schema_version`, `template_family`, `design_version`, `source_commit`,
  `runtime_commit`, `build_id`, `artifact_sha256`, `profile`, `built_at`
* идентичность каталога (`lords-release-manifest`):
  `content_snapshot_id`, `content_count`
* страница (`Meta` / `PageObservation`):
  `path`, `page_type`, `title`, `description`, `h1`, `canonical`, `indexable`

`content_snapshot_id` — sha256(catalog_bytes + NUL + details_bytes). Один
идентификатор закрывает согласованность каталога и деталей без выдуманных
`catalog_snapshot_id` / `details_snapshot_id`.

Индексация закрытой витрины не открывается: `indexable` всегда false,
`indexing_expected` = `"closed"`. Подготовка снимка не меняет robots/policy.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit

#: Типы страниц, которые обязан покрыть полный снимок Lords.
#: Имена — из матрицы SEO (`home`/`title`/`season`/`episode`/`search`/
#: `collection`) и из `schemas/template-manifest.schema.json` section enum
#: (`catalog_index`, `movies_index`, …). Новых идентификаторов нет.
REQUIRED_PAGE_TYPES: tuple[str, ...] = (
    "home",
    "catalog_index",
    "movies_index",
    "series_index",
    "animation_index",
    "collections_index",
    "collection",
    "title",
    "season",
    "episode",
    "search",
)

#: Поля provenance, которые обязаны совпасть с фактически развёрнутым build.
PROVENANCE_FIELDS: tuple[str, ...] = (
    "schema_version",
    "template_family",
    "design_version",
    "source_commit",
    "runtime_commit",
    "build_id",
    "artifact_sha256",
    "profile",
    "built_at",
)

#: Обязательные SEO-поля одной страницы (Meta + uniqueness).
PAGE_FIELDS: tuple[str, ...] = (
    "path",
    "page_type",
    "title",
    "description",
    "h1",
    "canonical",
    "indexable",
)

#: Фрагменты, которым нельзя оказаться в SEO-тексте (title/description/h1).
FORBIDDEN_SEO_FRAGMENTS: tuple[str, ...] = (
    "Lords ·",
    "data-build-id",
    "data-template-version",
    "Template",
    "DEBUG",
    "fixture",
    "synthetic",
)

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SeoSnapshotError(Exception):
    """Снимок не пригоден. Выкладка / приёмка отклоняются."""


def отпечаток_файла(путь: Path | str) -> str:
    ш = hashlib.sha256()
    with open(путь, "rb") as ф:
        for кусок in iter(lambda: ф.read(1024 * 1024), b""):
            ш.update(кусок)
    return ш.hexdigest()


def content_snapshot_id(*, catalog: Path | str, details: Path | str | None) -> str:
    """Один id на пару catalog+details. Пустые details — только catalog."""
    ш = hashlib.sha256()
    ш.update(Path(catalog).read_bytes())
    ш.update(b"\0")
    if details is not None and Path(details).is_file():
        ш.update(Path(details).read_bytes())
    return ш.hexdigest()


def content_count(catalog: Path | str) -> int:
    сырьё = json.loads(Path(catalog).read_text(encoding="utf-8"))
    items = сырьё.get("items") if isinstance(сырьё, dict) else сырьё
    if not isinstance(items, list):
        raise SeoSnapshotError("каталог не содержит списка items")
    return len(items)


def _страница_ок(page: Mapping[str, Any]) -> list[str]:
    беды: list[str] = []
    for поле in PAGE_FIELDS:
        if поле not in page:
            беды.append(f"страница без поля {поле}")
            continue
        значение = page[поле]
        if поле == "indexable":
            if значение is not False:
                беды.append(
                    f"{page.get('path')}: indexable={значение!r} "
                    "(закрытая витрина допускает только false)"
                )
            continue
        if not isinstance(значение, str) or not значение.strip():
            беды.append(f"{page.get('path')}: пустое поле {поле}")
    путь = str(page.get("path") or "")
    канон = str(page.get("canonical") or "")
    if канон:
        host = (urlsplit(канон).hostname or "").lower()
        if not канон.startswith("https://") or not host:
            беды.append(f"{путь}: canonical не абсолютный https")
        if путь and urlsplit(канон).path not in (путь, путь.rstrip("/") + "/"):
            # kind-фильтры раньше канонизировали на /catalog/ — это нарушение.
            if urlsplit(канон).path.rstrip("/") != путь.rstrip("/"):
                беды.append(
                    f"{путь}: canonical path {urlsplit(канон).path!r} "
                    f"не совпадает с path"
                )
    for поле in ("title", "description", "h1"):
        текст = str(page.get(поле) or "")
        for запрет in FORBIDDEN_SEO_FRAGMENTS:
            if запрет.lower() in текст.lower():
                беды.append(
                    f"{путь}: SEO-поле {поле} содержит служебный фрагмент {запрет!r}"
                )
                break
    return беды


def нарушения(
    снимок: Mapping[str, Any],
    *,
    expected: Mapping[str, Any] | None = None,
) -> list[str]:
    """Список нарушений. Пустой — снимок принимаем."""
    из: list[str] = []
    if not isinstance(снимок, dict) or not снимок:
        return ["снимок пуст или не объект"]

    for поле in PROVENANCE_FIELDS:
        if поле not in снимок or снимок[поле] in (None, ""):
            из.append(f"нет provenance-поля {поле}")

    for поле in ("content_snapshot_id", "content_count"):
        if поле not in снимок or снимок[поле] in (None, ""):
            из.append(f"нет поля {поле}")

    if снимок.get("indexing_expected") != "closed":
        из.append(
            f"indexing_expected={снимок.get('indexing_expected')!r} "
            "(ожидалось closed; подготовка SEO не открывает индексацию)"
        )

    cid = str(снимок.get("content_snapshot_id") or "")
    if cid and not _SHA256.match(cid):
        из.append(f"content_snapshot_id не sha256: {cid[:16]}…")

    счёт = снимок.get("content_count")
    if not isinstance(счёт, int) or isinstance(счёт, bool) or счёт <= 0:
        из.append(f"content_count негоден: {счёт!r}")

    for поле in ("source_commit", "runtime_commit"):
        значение = str(снимок.get(поле) or "")
        if значение and not _SHA40.match(значение):
            из.append(f"{поле} не SHA40")

    арт = str(снимок.get("artifact_sha256") or "")
    if арт and not _SHA256.match(арт):
        из.append(f"artifact_sha256 не sha256: {арт[:16]}…")

    pages = снимок.get("pages")
    if not isinstance(pages, list) or not pages:
        из.append("pages пуст: частичный или пустой снимок")
        return из

    by_type: dict[str, list[Mapping[str, Any]]] = {}
    for page in pages:
        if not isinstance(page, Mapping):
            из.append("элемент pages не объект")
            continue
        из.extend(_страница_ок(page))
        by_type.setdefault(str(page.get("page_type") or ""), []).append(page)

    for нужный in REQUIRED_PAGE_TYPES:
        if нужный not in by_type:
            из.append(f"нет страницы page_type={нужный}")

    if expected:
        for поле in (
            "source_commit",
            "runtime_commit",
            "build_id",
            "artifact_sha256",
            "profile",
            "design_version",
            "content_snapshot_id",
        ):
            if поле in expected and снимок.get(поле) != expected.get(поле):
                из.append(
                    f"несогласованность {поле}: снимок={снимок.get(поле)!r} "
                    f"ожидалось={expected.get(поле)!r}"
                )
        # stale: build_id из expected новее / другой, чем в снимке
        if expected.get("build_id") and снимок.get("build_id") != expected.get("build_id"):
            if f"несогласованность build_id" not in " ".join(из):
                из.append(
                    f"устаревший снимок: build_id={снимок.get('build_id')!r} "
                    f"live={expected.get('build_id')!r}"
                )

    return из


def проверить(
    снимок: Mapping[str, Any],
    *,
    expected: Mapping[str, Any] | None = None,
) -> None:
    беды = нарушения(снимок, expected=expected)
    if беды:
        raise SeoSnapshotError("; ".join(беды))


def собрать(
    *,
    provenance: Mapping[str, Any],
    catalog: Path | str,
    details: Path | str | None,
    pages: Iterable[Mapping[str, Any]],
    domain: str,
    site_id: str,
) -> dict[str, Any]:
    """Собрать документ снимка из уже известных полей и наблюдений страниц."""
    cid = content_snapshot_id(catalog=catalog, details=details)
    count = content_count(catalog)
    doc: dict[str, Any] = {
        "schema_version": int(provenance.get("schema_version") or 1),
        "template_family": provenance["template_family"],
        "design_version": provenance["design_version"],
        "source_commit": provenance["source_commit"],
        "runtime_commit": provenance["runtime_commit"],
        "build_id": provenance["build_id"],
        "artifact_sha256": provenance["artifact_sha256"],
        "profile": provenance["profile"],
        "built_at": provenance["built_at"],
        "content_snapshot_id": cid,
        "content_count": count,
        "tenant_id": site_id,
        "domain": domain,
        "indexing_expected": "closed",
        "pages": [dict(p) for p in pages],
    }
    проверить(doc)
    return doc


def прочитать(путь: Path | str) -> dict[str, Any]:
    п = Path(путь)
    try:
        данные = json.loads(п.read_text(encoding="utf-8"))
    except FileNotFoundError as ошибка:
        raise SeoSnapshotError(f"SEO-снимка нет: {п}") from ошибка
    except (OSError, ValueError) as ошибка:
        raise SeoSnapshotError(f"SEO-снимок не читается: {п}: {ошибка}") from ошибка
    if not isinstance(данные, dict):
        raise SeoSnapshotError(f"SEO-снимок не объект: {п}")
    return данные


def записать(путь: Path | str, снимок: Mapping[str, Any]) -> None:
    проверить(снимок)
    Path(путь).write_text(
        json.dumps(снимок, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


#: Карта path → page_type для обязательного набора. Детали title/season/
#: episode/collection заполняются вызывающим кодом по фактическим URL.
STATIC_PATH_TYPES: dict[str, str] = {
    "/": "home",
    "/catalog/": "catalog_index",
    "/movies/": "movies_index",
    "/series/": "series_index",
    "/animation/": "animation_index",
    "/collections/": "collections_index",
    "/search/": "search",
}
