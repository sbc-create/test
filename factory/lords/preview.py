"""Стенд Lords: сборка и локальный запуск сайта на синтетическом каталоге.

Стенд отделён от штатной сборки намеренно. `factory build` выпускает сайт из
подтверждённого источника и останавливается на любом блокере — в том числе на
неподтверждённых правах на контент CDNVideoHub. Ослаблять это правило нельзя.
Стенд решает другую задачу: показать шаблон, пока источника нет. Его каталог
фабрика порождает сама, поэтому вопрос прав на чужой контент к нему не
относится — чужого контента в нём нет ни одной записи.

Чтобы разница не размылась, стенд:

* отказывается собираться для production;
* терпит ровно три известных блокера и падает на любом другом;
* складывает результат не в каталог сборок, а в `artifacts/lords/preview/`,
  откуда деплой ничего не берёт;
* помечает каждую страницу и отчёт источником `fixture/test`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from factory import validation
from factory.build import POST_BUILD_STAGES
from factory.errors import BlockedInput
from factory.lords import fixtures as fx
from factory.lords import render as render_mod
from factory.lords import serve as serve_mod
from factory.paths import PATHS

#: Блокеры, которые стенд переживает, и причина, по которой это не послабление.
TOLERATED = {
    "target_ref": "цель выката стенду не нужна: он не выкатывается",
    "content_source.rights_confirmed": "в каталоге стенда нет чужого контента —"
                                       " записи порождает сама фабрика",
}


@dataclass
class PreviewResult:
    site_id: str
    profile: str
    directory: Path
    site: render_mod.RenderedSite
    report: dict


def _package(site_id: str) -> tuple[dict, list]:
    result = validation.validate(site_id)
    package = result.package or {}
    if not package:
        blocker = result.blockers[0] if result.blockers else None
        raise BlockedInput(
            f"пакет «{site_id}» не читается: {blocker.reason if blocker else 'причина неизвестна'}",
            field="package", required_input="Корректный site package", blocks_stage="BUILDING",
        )
    unexpected = [
        b for b in result.blockers
        if b.field not in TOLERATED and (b.blocks_stage or "") not in POST_BUILD_STAGES
    ]
    if unexpected:
        first = unexpected[0]
        raise BlockedInput(
            f"стенд не собирается: {first.reason}",
            field=first.field, required_input=first.required_input, blocks_stage="BUILDING",
        )
    return package, list(result.blockers)


def _assert_no_real_source(package: dict) -> None:
    """Стенд допустим только там, где настоящего источника нет вовсе."""
    source = package.get("content_source") or {}
    api = package.get("content_api") or {}
    if source.get("rights_confirmed"):
        raise BlockedInput(
            "права на контент подтверждены — собирай штатной сборкой, а не стендом",
            field="content_source.rights_confirmed",
            required_input="python3 -m factory build", blocks_stage="BUILDING",
        )
    if str(api.get("mode") or "") != "disabled":
        raise BlockedInput(
            f"источник данных включён (mode={api.get('mode')}): стенд подменил бы настоящий каталог",
            field="content_api.mode", required_input="mode: disabled", blocks_stage="BUILDING",
        )


def build_preview(site_id: str, *, output: Path | None = None) -> PreviewResult:
    """Собирает стенд одного пакета в каталог с готовыми документами."""
    package, blockers = _package(site_id)
    if str(package.get("environment")) == "production":
        raise BlockedInput(
            "стенд в production не собирается: его каталог синтетический",
            field="environment", required_input="environment: staging", blocks_stage="BUILDING",
        )
    _assert_no_real_source(package)

    catalog = fx.build_catalog()
    site = render_mod.render_site(package, catalog=catalog, environ={})
    directory = Path(output) if output else PATHS.artifact_dir("lords", "preview", site_id)
    for existing in sorted(directory.rglob("*"), reverse=True):
        if existing.is_file():
            existing.unlink()
        elif existing.is_dir():
            existing.rmdir()
    export = serve_mod.export(site, directory)

    report = dict(site.report)
    report["documents"] = len(export["files"])
    report["directory"] = str(directory)
    report["catalog"] = {
        "source": fx.SOURCE,
        "titles": len(catalog.titles),
        "collections": len(catalog.collections),
    }
    report["tolerated_blockers"] = [
        {"field": b.field, "status": b.status, "reason": b.reason,
         "why_tolerated": TOLERATED.get(b.field, "этап после сборки")}
        for b in blockers
    ]
    report["digest"] = digest(site)
    (directory / "preview-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return PreviewResult(site_id=site_id, profile=site.profile, directory=directory,
                         site=site, report=report)


def digest(site: render_mod.RenderedSite) -> str:
    """Отпечаток собранного сайта.

    Повторная сборка обязана давать тот же отпечаток. Иначе «воспроизводимый
    стенд» — только слово: сравнить два выката было бы нечем.
    """
    sha = hashlib.sha256()
    for path in sorted(site.pages):
        sha.update(path.encode("utf-8"))
        sha.update(b"\0")
        sha.update(site.pages[path].body.encode("utf-8"))
        sha.update(b"\0")
    if site.not_found is not None:
        sha.update(site.not_found.body.encode("utf-8"))
    return sha.hexdigest()


def application(site_id: str) -> serve_mod.Application:
    """WSGI-приложение стенда без записи на диск."""
    package, _ = _package(site_id)
    _assert_no_real_source(package)
    site = render_mod.render_site(package, catalog=fx.build_catalog(), environ={})
    return serve_mod.Application(site)


def serve(site_id: str, *, host: str = "127.0.0.1", port: int = 0):
    """Запускает стенд локально. Адрес — только петлевой интерфейс."""
    from wsgiref.simple_server import make_server

    app = application(site_id)
    server = make_server(host, port, app)
    return server, app
