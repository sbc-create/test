"""Детерминированная сборка сайта.

build_id — контентный адрес: одинаковые вход дают одинаковый идентификатор, поэтому
повторная сборка и повторный деплой не создают новый релиз (идемпотентность, §3.11).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from factory import validation
from factory.errors import (
    BlockedAccess,
    BlockedAuthorization,
    BlockedInput,
    BlockedLicense,
    BlockedRights,
    BlockedSecret,
    BlockedSeo,
)

#: Статус валидации → класс ошибки. Общего «failed» не существует.
from factory.paths import PATHS
from factory.render import SiteRenderer

STATUS_TO_ERROR = {
    "BLOCKED_INPUT": BlockedInput,
    "BLOCKED_LICENSE": BlockedLicense,
    "BLOCKED_RIGHTS": BlockedRights,
    "BLOCKED_SECRET": BlockedSecret,
    "BLOCKED_ACCESS": BlockedAccess,
    "BLOCKED_AUTHORIZATION": BlockedAuthorization,
    "BLOCKED_SEO": BlockedSeo,
}

RENDERER_VERSION = "1.0.0"


@dataclass
class BuildResult:
    site_id: str
    build_id: str
    output: Path
    counts: dict
    skipped: list[dict]
    routes: int
    redirects: int
    php_lint: list[dict]

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "build_id": self.build_id,
            "output": str(self.output),
            "routes": self.routes,
            "redirects": self.redirects,
            "counts": self.counts,
            "skipped": self.skipped,
            "php_lint": self.php_lint,
            "renderer_version": RENDERER_VERSION,
        }


def _canonical(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dir_digest(path: Path) -> str:
    h = hashlib.sha256()
    if not path.exists():
        return "absent"
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        h.update(str(file.relative_to(path)).encode())
        h.update(file.read_bytes())
    return h.hexdigest()


def _content_digest(site_id: str, package: dict) -> str:
    """Дайджест ВСЕХ файлов сайта, а не только каталога.

    Правка юридического текста, логотипа или медиа обязана менять адрес сборки:
    иначе сборка вернётся из кеша, деплой посчитает релиз применённым, и сайт
    продолжит отдавать старую редакцию документа.
    """
    return _dir_digest(PATHS.site_dir(site_id))


def factory_source_digest() -> str:
    """Дайджест кода, влияющего на результат рендера.

    Без него изменившийся рендер даёт прежний build_id, деплой считает релиз уже
    применённым и продолжает отдавать старое содержимое. Это реальная ловушка
    контентной адресации, поэтому код входит в адрес наравне с данными.
    """
    h = hashlib.sha256()
    root = Path(__file__).resolve().parent
    for file in sorted(p for p in root.rglob("*.py") if p.is_file()):
        h.update(str(file.relative_to(root)).encode())
        h.update(file.read_bytes())
    automation = PATHS.automation / "local"
    if automation.exists():
        for file in sorted(p for p in automation.rglob("*") if p.is_file()):
            h.update(str(file.relative_to(automation)).encode())
            h.update(file.read_bytes())
    return h.hexdigest()


#: Исходники blueprint payload-next-multisite. Их содержимое входит в build_id:
#: правка рендера без смены build_id заставила бы деплой переиспользовать старый релиз.
PAYLOAD_APP = PATHS.root / "blueprints" / "payload-next-multisite" / "app"


def blueprint_of(package: dict) -> str:
    return package.get("blueprint") or "dle20"


def _payload_app_digest() -> str:
    h = hashlib.sha256()
    for sub in ("src", "public", "next.config.mjs", "package.json", "tsconfig.json"):
        path = PAYLOAD_APP / sub
        if path.is_file():
            h.update(sub.encode())
            h.update(path.read_bytes())
        elif path.is_dir():
            for file in sorted(p for p in path.rglob("*") if p.is_file()):
                h.update(str(file.relative_to(PAYLOAD_APP)).encode())
                h.update(file.read_bytes())
    return h.hexdigest()


def compute_build_id(site_id: str, package: dict) -> str:
    if blueprint_of(package) == "payload-next-multisite":
        matrix_path = PATHS.knowledge / "SEO_INDEXABILITY_MATRIX.yaml"
        material = _canonical({
            "package": package,
            # Тексты юридических документов и прочие файлы сайта читаются сборкой,
            # значит обязаны влиять на её адрес: иначе правка файла не доезжает.
            "content": _content_digest(site_id, package),
            "app": _payload_app_digest(),
            "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
            "factory_source": factory_source_digest(),
        })
        return hashlib.sha256(material.encode()).hexdigest()[:16]
    theme_dir = PATHS.themes / package["theme_ref"]
    matrix_path = PATHS.knowledge / "SEO_INDEXABILITY_MATRIX.yaml"
    matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8")) or {}
    material = _canonical({
        "package": package,
        "content": _content_digest(site_id, package),
        "theme": _dir_digest(theme_dir),
        "matrix_policy_version": matrix.get("policy_version"),
        # Содержимое матрицы, а не только объявленная версия: правка правил
        # индексации без бампа policy_version меняла бы рендер незаметно.
        "matrix_sha256": hashlib.sha256(matrix_path.read_bytes()).hexdigest(),
        "renderer": RENDERER_VERSION,
        "factory_source": factory_source_digest(),
    })
    return hashlib.sha256(material.encode()).hexdigest()[:16]


def php_lint(paths: list[Path]) -> list[dict]:
    results: list[dict] = []
    for path in paths:
        for php_file in sorted(path.rglob("*.php")) if path.exists() else []:
            proc = subprocess.run(["php", "-l", str(php_file)], capture_output=True, text=True, timeout=60, check=False)
            results.append({"file": str(php_file.relative_to(PATHS.root)), "exit_code": proc.returncode,
                            "output": (proc.stdout + proc.stderr).strip()[:500]})
    return results


def build(site_id: str, *, environment: str | None = None, force: bool = False) -> BuildResult:
    result = validation.validate(site_id)
    if not result.ok:
        # Точный статус, а не общий QUARANTINED: иначе отсутствие прав или лицензии
        # становится «временной» ошибкой и ретраится.
        blocker = result.blockers[0]
        error_class = STATUS_TO_ERROR.get(result.status, BlockedInput)
        raise error_class(
            f"Пакет не прошёл валидацию ({result.status}). Первый блокер: {blocker.reason}",
            field=blocker.field,
            required_input=blocker.required_input,
            blocks_stage="BUILDING",
        )
    package = result.package or {}
    env = environment or package["environment"]
    build_id = compute_build_id(site_id, package)
    out = PATHS.build_dir(site_id, build_id)
    if out.exists() and not force:
        manifest = out / "build-manifest.json"
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            return BuildResult(site_id, build_id, out, data.get("counts", {}), data.get("skipped", []),
                               data.get("routes", 0), data.get("redirects", 0), data.get("php_lint", []))
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)

    if blueprint_of(package) == "payload-next-multisite":
        return _build_payload(site_id, package, env, build_id, out)

    renderer = SiteRenderer(package, site_id, output=out)
    render_result = renderer.render(env)
    lint = php_lint([PATHS.themes / package["theme_ref"], PATHS.plugins])
    failed_lint = [r for r in lint if r["exit_code"] != 0]
    if failed_lint:
        raise BlockedInput(
            f"php -l завершился с ошибкой в {len(failed_lint)} файле(ах): {failed_lint[0]['file']}",
            field="themes/plugins",
            required_input="Синтаксически корректный PHP",
            blocks_stage="BUILDING",
        )

    build_result = BuildResult(
        site_id=site_id, build_id=build_id, output=out,
        counts=render_result.counts, skipped=render_result.skipped,
        routes=len(render_result.routes), redirects=len(render_result.redirects), php_lint=lint,
    )
    manifest = {
        **build_result.as_dict(),
        "environment": env,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "package_sha256": hashlib.sha256(_canonical(package).encode()).hexdigest(),
    }
    (out / "build-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_dir = PATHS.artifact_dir("build", site_id, build_id)
    (report_dir / "report.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return build_result


def _build_payload(site_id: str, package: dict, env: str, build_id: str, out: Path) -> BuildResult:
    """Сборка для blueprint payload-next-multisite.

    Приложение одно на три сайта, поэтому «сборка сайта» — это не отдельный HTML,
    а детерминированная конфигурация тенанта, которую деплой применяет к CMS.
    Само приложение собирается на шаге деплоя, где существует каталог релиза.
    """
    tenant = package.get("tenant") or {}
    player = package.get("player_profile") or {}
    comments = package.get("comments") or {}
    settings = package.get("metadata") or {}
    navigation = package.get("navigation") or {}
    legal = package.get("legal") or {}

    config = {
        "site_id": site_id,
        "environment": env,
        "domain": package["domain"],
        "tenant": {
            "slug": tenant.get("slug"),
            "name": package["brand"]["name"],
            "domain": package["domain"],
            "seoProfile": tenant.get("seo_profile"),
            "theme": tenant.get("theme"),
            "indexingEnabled": bool(tenant.get("indexing_enabled")),
            "allowGuestComments": bool(tenant.get("allow_guest_comments")),
        },
        "siteSettings": {
            "siteName": package["brand"]["name"],
            "tagline": (settings.get("description_templates") or {}).get("home"),
            "defaultDescription": (settings.get("description_templates") or {}).get("home"),
            "commentsEnabled": bool(comments.get("enabled", True)),
            "premoderation": bool(comments.get("premoderation", True)),
            "minIntervalSeconds": int(comments.get("min_interval_seconds", 30)),
            "maxLength": int(comments.get("max_length", 4000)),
            "rightsNotice": (legal.get("documents") or [{}])[0].get("summary"),
        },
        "navigation": {
            "header": [{"title": item.get("label"), "href": item.get("url")}
                       for item in navigation.get("primary") or []],
            "footerGroups": [{"title": "О сайте",
                              "links": [{"title": item.get("label"), "href": item.get("url")}
                                        for item in navigation.get("footer") or []]}],
        },
        "playerProfile": {
            "name": f"Плеер {tenant.get('slug')}",
            "publisherIdRef": player.get("publisher_id_ref"),
            "aggregator": player.get("aggregator"),
            "showBanner": bool(player.get("show_banner")),
            "showVoiceOnly": bool(player.get("show_voice_only")),
        },
        "legalDocuments": [
            {
                "slug": doc.get("slug"),
                "name": doc.get("title"),
                "summary": doc.get("summary"),
                "body": (_resolve_site_text(site_id, doc.get("body_ref")) or ""),
            }
            for doc in legal.get("documents") or []
        ],
    }
    (out / "tenant-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    build_result = BuildResult(site_id=site_id, build_id=build_id, output=out,
                               counts={"tenants": 1, "legal_documents": len(config["legalDocuments"])},
                               skipped=[], routes=0, redirects=0, php_lint=[])
    manifest = {
        **build_result.as_dict(),
        "blueprint": "payload-next-multisite",
        "environment": env,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "package_sha256": hashlib.sha256(_canonical(package).encode()).hexdigest(),
        "app_digest": _payload_app_digest(),
    }
    (out / "build-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report_dir = PATHS.artifact_dir("build", site_id, build_id)
    (report_dir / "report.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return build_result


def _resolve_site_text(site_id: str, ref: str | None) -> str | None:
    if not ref:
        return None
    path = PATHS.sites / site_id / ref
    return path.read_text(encoding="utf-8") if path.exists() else None


def latest_build(site_id: str) -> Path | None:
    base = PATHS.builds / site_id
    if not base.exists():
        return None
    builds = sorted((p for p in base.iterdir() if (p / "build-manifest.json").exists()),
                    key=lambda p: json.loads((p / "build-manifest.json").read_text(encoding="utf-8")).get("built_at", ""))
    return builds[-1] if builds else None
