"""Валидация site package: JSON Schema + семантика домена.

Пустое обязательное поле даёт точную ошибку с указанием поля и требуемого входа.
Никаких неявных умолчаний для домена, лицензии, юридических данных, контента, прав,
production target и интеграционных ID.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from pathlib import Path

import jsonschema
import yaml

from factory import inventory, licensing
from factory.analytics.yandex import normalize_domain
from factory.paths import PATHS

STATUS_PRIORITY = (
    "BLOCKED_INPUT",
    "BLOCKED_AUTHORIZATION",
    "BLOCKED_LICENSE",
    "BLOCKED_RIGHTS",
    "BLOCKED_SECRET",
    "BLOCKED_ACCESS",
    "BLOCKED_SEO",
)


@dataclass
class Blocker:
    status: str
    field: str
    reason: str
    required_input: str
    blocks_stage: str = "-"

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "field": self.field,
            "reason": self.reason,
            "required_input": self.required_input,
            "blocks_stage": self.blocks_stage,
        }


@dataclass
class ValidationResult:
    site_id: str
    package: dict | None
    blockers: list[Blocker] = dc_field(default_factory=list)
    warnings: list[str] = dc_field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blockers

    @property
    def status(self) -> str:
        if self.ok:
            return "READY"
        for status in STATUS_PRIORITY:
            if any(b.status == status for b in self.blockers):
                return status
        return self.blockers[0].status

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "status": self.status,
            "blockers": [b.as_dict() for b in self.blockers],
            "warnings": self.warnings,
        }


def load_schema() -> dict:
    return json.loads((PATHS.schemas / "site-package.schema.json").read_text(encoding="utf-8"))


def load_package(site_id: str) -> dict:
    path = PATHS.site_package(site_id)
    if not path.exists():
        raise FileNotFoundError(str(path))
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: ожидался YAML-объект")
    return data


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_site_file(site_id: str, ref: str) -> Path | None:
    """Ссылки пакета указывают внутрь sites/<site_id>/ и не выходят за его пределы."""
    if not ref:
        return None
    base = PATHS.site_dir(site_id).resolve()
    candidate = (base / ref).resolve()
    if not str(candidate).startswith(str(base) + os.sep):
        return None
    return candidate if candidate.exists() else None


def _secret_available(ref: str) -> tuple[bool, str]:
    if not ref:
        return False, "ссылка пуста"
    if ref.startswith("env:"):
        name = ref.split(":", 1)[1]
        return (name in os.environ and bool(os.environ[name])), f"переменная окружения {name}"
    if ref.startswith("file:"):
        path = Path(ref.split(":", 1)[1]).expanduser()
        return path.exists(), f"файл {path}"
    if ref.startswith(("vault:", "secret:")):
        return False, "внешнее secret-хранилище недоступно из фабрики без настроенного клиента"
    return False, "неизвестная схема secret_ref (ожидается env:/file:/vault:/secret:)"


def _matrix() -> dict:
    path = PATHS.knowledge / "SEO_INDEXABILITY_MATRIX.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# --------------------------------------------------------------------------- #
#  семантические проверки                                                      #
# --------------------------------------------------------------------------- #

def _check_schema(pkg: dict, out: list[Blocker]) -> bool:
    validator = jsonschema.Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(pkg), key=lambda e: list(e.absolute_path))
    for err in errors:
        location = "/".join(str(p) for p in err.absolute_path) or "(корень пакета)"
        out.append(
            Blocker(
                "BLOCKED_INPUT",
                location,
                err.message,
                "Заполни поле значением, переданным заказчиком. Значение по умолчанию не подставляется.",
                "VALIDATING",
            )
        )
    return not errors


def _check_environment(pkg: dict, out: list[Blocker]) -> None:
    env = pkg.get("environment")
    if pkg.get("fixture") and env == "production":
        out.append(Blocker("BLOCKED_INPUT", "fixture", "Пакет-фикстура не может быть выкачен в production.", "Убери fixture: true или используй staging.", "AUTHORIZATION_CHECK"))
    if env == "production" and not pkg.get("production_authorized"):
        out.append(Blocker("BLOCKED_AUTHORIZATION", "production_authorized", "Production не авторизован в manifest.", "production_authorized: true и заполненные authorized_by/authorized_at", "AUTHORIZATION_CHECK"))
    if env == "staging" and pkg.get("production_authorized"):
        out.append(Blocker("BLOCKED_INPUT", "production_authorized", "production_authorized: true при environment: staging — противоречие manifest.", "Приведи environment и production_authorized в соответствие", "VALIDATING"))


#: Темы, объявленные blueprint payload-next-multisite. Они живут в самом
#: приложении как наборы токенов, а не отдельными пакетами в themes/.
PAYLOAD_THEMES = {"portal_light", "pulse", "editorial"}


def blueprint_of(pkg: dict) -> str:
    """Пакет без явного blueprint — исторический DLE-пакет."""
    return pkg.get("blueprint") or "dle20"


def _check_license(pkg: dict, out: list[Blocker], warnings: list[str]) -> None:
    if blueprint_of(pkg) != "dle20":
        # Лицензия DLE к другому blueprint отношения не имеет. Проверять её здесь
        # значило бы выдавать шум вместо проверки прав на контент.
        if pkg.get("dle_license_ref"):
            out.append(Blocker("BLOCKED_INPUT", "dle_license_ref",
                               "Лицензия DLE указана для blueprint, который DLE не использует.",
                               "Убери dle_license_ref из пакета payload-next-multisite", "VALIDATING"))
        return
    env = pkg.get("environment")
    domain = pkg.get("domain", "")
    result = licensing.check_domain(domain, license_ref=pkg.get("dle_license_ref"))
    if result.covered:
        return
    if env == "production":
        out.append(Blocker("BLOCKED_LICENSE", "dle_license_ref", result.reason, "Запись в inventory/dle-licenses.yaml с covered_domain = домену второго уровня сайта", "PRODUCTION_DEPLOY"))
    else:
        warnings.append(f"Лицензия DLE не подтверждена ({result.reason}). Для staging это допустимо, для production — блокер.")


def _check_targets(pkg: dict, out: list[Blocker]) -> None:
    env = pkg.get("environment")
    try:
        tgt = inventory.target(pkg.get("target_ref", ""))
    except Exception as exc:  # BlockedAccess/BlockedInput
        out.append(Blocker(getattr(exc, "status", "BLOCKED_ACCESS"), "target_ref", str(exc), getattr(exc, "required_input", "запись в inventory/targets.yaml"), "STAGING_DEPLOY"))
        return
    if env not in (tgt.get("environments") or []):
        out.append(Blocker("BLOCKED_ACCESS", "target_ref", f"Цель «{tgt.get('ref')}» не разрешена для окружения {env}.", "Разреши окружение в inventory/targets.yaml или выбери другую цель", "STAGING_DEPLOY"))
    if env == "production" and not tgt.get("production_capable"):
        out.append(Blocker("BLOCKED_ACCESS", "target_ref", f"Цель «{tgt.get('ref')}» помечена как не пригодная для production.", "production_capable: true у проверенной цели", "PRODUCTION_DEPLOY"))
    if tgt.get("adapter") == "ssh_ansible":
        ref = pkg.get("ssh_host_ref")
        if not ref:
            out.append(Blocker("BLOCKED_ACCESS", "ssh_host_ref", "Цель использует SSH, но ssh_host_ref не задан.", "ref хоста из inventory/ssh-hosts.yaml", "STAGING_DEPLOY"))
        else:
            try:
                inventory.ssh_host(ref)
            except Exception as exc:
                out.append(Blocker(getattr(exc, "status", "BLOCKED_ACCESS"), "ssh_host_ref", str(exc), getattr(exc, "required_input", "корректная запись хоста"), "STAGING_DEPLOY"))
    if pkg.get("dns_zone_ref"):
        try:
            zone = inventory.dns_zone(pkg["dns_zone_ref"])
            zname = str(zone.get("zone", "")).lower()
            domain = str(pkg.get("domain", "")).lower()
            if zname and domain != zname and not domain.endswith("." + zname):
                out.append(Blocker("BLOCKED_ACCESS", "dns_zone_ref", f"Домен {domain} не принадлежит зоне {zname}.", "Зона, содержащая домен сайта", "PRODUCTION_DEPLOY"))
        except Exception as exc:
            out.append(Blocker(getattr(exc, "status", "BLOCKED_ACCESS"), "dns_zone_ref", str(exc), "запись в inventory/dns-zones.yaml", "PRODUCTION_DEPLOY"))


def _check_domain_consistency(pkg: dict, out: list[Blocker]) -> None:
    domain = str(pkg.get("domain", "")).lower()
    canonical = str(pkg.get("canonical_url", ""))
    policy = (pkg.get("metadata") or {}).get("canonical_policy") or {}
    m = re.match(r"^https://([^/]+)(/.*)?$", canonical)
    if not m:
        return
    host, path = m.group(1).lower(), m.group(2) or "/"
    expected_host = f"www.{domain}" if policy.get("host_form") == "www" else domain
    if host != expected_host:
        out.append(Blocker("BLOCKED_SEO", "canonical_url", f"canonical_url указывает на «{host}», а политика требует «{expected_host}».", "Приведи canonical_url в соответствие с domain и canonical_policy.host_form", "BUILDING"))
    if policy.get("trailing_slash") and not path.endswith("/"):
        out.append(Blocker("BLOCKED_SEO", "canonical_url", "Политика требует завершающий слэш, а canonical_url его не содержит.", "canonical_url со слэшем на конце", "BUILDING"))
    aliases = [a.lower() for a in pkg.get("aliases") or []]
    if domain in aliases:
        out.append(Blocker("BLOCKED_INPUT", "aliases", "Основной домен продублирован в aliases.", "Убери основной домен из списка алиасов", "VALIDATING"))
    if len(set(aliases)) != len(aliases):
        out.append(Blocker("BLOCKED_INPUT", "aliases", "В aliases есть дубликаты.", "Уникальный список алиасов", "VALIDATING"))


#: Владение разделами объявлено в профиле приложения. Пакет обязан ему соответствовать:
#: иначе поле в манифесте выглядит настройкой, но ни на что не влияет.
PROFILE_OWNED_LISTINGS = {
    "catalog_authority": ["/catalog/", "/collections/", "/news/"],
    "release_pulse": ["/schedule/", "/news/"],
    "editorial_guide": ["/collections/", "/news/"],
}


def _check_tenant_profile(pkg: dict, out: list[Blocker]) -> None:
    """Согласие манифеста с профилем сайта.

    CLAUDE.md ставит манифест первым источником истины. Поле, которое никто не
    читает, этот порядок нарушает: оператор правит пакет и не получает ни эффекта,
    ни ошибки. Поэтому расхождение — блокер, а не молчание.
    """
    if blueprint_of(pkg) != "payload-next-multisite":
        return
    tenant = pkg.get("tenant") or {}
    profile = tenant.get("seo_profile")
    expected = PROFILE_OWNED_LISTINGS.get(profile)
    if expected is None:
        out.append(Blocker("BLOCKED_INPUT", "tenant.seo_profile",
                           f"Неизвестный SEO-профиль «{profile}».",
                           "catalog_authority | release_pulse | editorial_guide", "VALIDATING"))
        return
    declared = list(tenant.get("owned_listings") or [])
    if sorted(declared) != sorted(expected):
        out.append(Blocker(
            "BLOCKED_INPUT", "tenant.owned_listings",
            f"Разделы пакета {declared} не совпадают с профилем {profile}: {expected}.",
            "Приведите owned_listings к профилю или измените профиль", "VALIDATING"))

    theme = tenant.get("theme")
    if theme != pkg.get("theme_ref"):
        out.append(Blocker("BLOCKED_INPUT", "tenant.theme",
                           f"tenant.theme={theme!r} расходится с theme_ref={pkg.get('theme_ref')!r}.",
                           "Одно и то же значение темы", "VALIDATING"))

    player = pkg.get("player_profile") or {}
    if pkg.get("environment") == "production" and player.get("mode") != "live":
        out.append(Blocker("BLOCKED_PLAYER_CONTRACT", "player_profile.mode",
                           "Режим плеера mock недопустим в production.",
                           "player_profile.mode: live", "PRODUCTION_DEPLOY"))
    content_api = pkg.get("content_api") or {}
    if pkg.get("environment") == "production" and content_api.get("mode") == "mock":
        out.append(Blocker("BLOCKED_INPUT", "content_api.mode",
                           "Режим фикстур Content API недопустим в production.",
                           "content_api.mode: live | disabled", "PRODUCTION_DEPLOY"))


def _check_publication_rights(pkg: dict, out: list[Blocker]) -> None:
    """Публикация без подтверждённых прав блокируется отдельным статусом.

    Общий BLOCKED_RIGHTS описывает происхождение исходных данных; здесь речь о
    праве ПУБЛИКОВАТЬ материал на сайте, и оператору нужно видеть разницу.
    """
    source = pkg.get("content_source") or {}
    if source.get("rights_confirmed") is True:
        return
    out.append(Blocker(
        "BLOCKED_CONTENT_RIGHTS", "content_source.rights_confirmed",
        "Права на публикацию контента не подтверждены в пакете сайта.",
        "Подтверждённый rights manifest и content_source.rights_confirmed: true",
        "BUILDING"))


def _check_content_rights(pkg: dict, site_id: str, out: list[Blocker]) -> None:
    cs = pkg.get("content_source") or {}
    kind = cs.get("kind")

    # Контрольная сумма и наличие каталога проверяются независимо от типа источника:
    # подменённая выгрузка одинаково опасна и для fixture, и для лицензионного каталога.
    catalog_ref = cs.get("catalog_ref")
    if catalog_ref:
        path = _resolve_site_file(site_id, catalog_ref)
        if not path:
            out.append(Blocker("BLOCKED_RIGHTS", "content_source.catalog_ref", f"Каталог контента «{catalog_ref}» не найден.", "Передай выгрузку каталога в каталог сайта", "BUILDING"))
        elif cs.get("catalog_sha256") and _sha256(path) != cs["catalog_sha256"]:
            out.append(Blocker("BLOCKED_RIGHTS", "content_source.catalog_sha256", "SHA-256 переданного каталога не совпадает с заявленным в пакете.", "Актуальная контрольная сумма переданной выгрузки", "BUILDING"))
    if pkg.get("content_package_ref"):
        path = _resolve_site_file(site_id, pkg["content_package_ref"])
        if not path:
            out.append(Blocker("BLOCKED_INPUT", "content_package_ref", f"Файл контентного пакета «{pkg['content_package_ref']}» не найден.", "Передай контентный пакет", "BUILDING"))
        elif pkg.get("content_package_sha256") and _sha256(path) != pkg["content_package_sha256"]:
            out.append(Blocker("BLOCKED_RIGHTS", "content_package_sha256", "SHA-256 контентного пакета не совпадает с заявленным.", "Актуальная контрольная сумма", "BUILDING"))

    if kind == "fixture":
        if pkg.get("environment") == "production":
            out.append(Blocker("BLOCKED_RIGHTS", "content_source.kind", "Fixture-контент запрещён в production.", "Реальный лицензионный каталог VK с rights manifest", "AUTHORIZATION_CHECK"))
        return
    if not cs.get("rights_confirmed"):
        out.append(Blocker("BLOCKED_RIGHTS", "content_source.rights_confirmed", "Права на контент не подтверждены.", "rights_confirmed: true и rights_manifest_ref с документом прав", "BUILDING"))
    ref = cs.get("rights_manifest_ref")
    if ref and not _resolve_site_file(site_id, ref):
        out.append(Blocker("BLOCKED_RIGHTS", "content_source.rights_manifest_ref", f"Файл rights manifest «{ref}» не найден внутри sites/{site_id}/.", "Положи rights manifest в каталог сайта", "BUILDING"))


def _check_vk_and_ads(pkg: dict, site_id: str, out: list[Blocker]) -> None:
    env = pkg.get("environment")
    vk = pkg.get("vk_video") or {}
    ads = pkg.get("advertising") or {}
    if vk.get("enabled"):
        ref = vk.get("contract_ref")
        if ref and not _resolve_site_file(site_id, ref):
            out.append(Blocker("BLOCKED_RIGHTS", "vk_video.contract_ref", f"Contract «{ref}» не найден в каталоге сайта.", "Положи переданный contract в sites/<site_id>/ и сошлись на него", "BUILDING"))
        if not vk.get("contract_ref"):
            out.append(Blocker("BLOCKED_RIGHTS", "vk_video.contract_ref", "VK-плеер включён без ссылки на contract.", "Официальный/внутренний contract белого плеера", "BUILDING"))
        if not vk.get("video_ids"):
            out.append(Blocker("BLOCKED_INPUT", "vk_video.video_ids", "VK-плеер включён, но список video_ids пуст.", "Явно переданные video/content ID из разрешённого каталога", "BUILDING"))
        if vk.get("adapter") == "mock" and env == "production":
            out.append(Blocker("BLOCKED_RIGHTS", "vk_video.adapter", "Mock-адаптер VK технически запрещён в production.", "adapter: official с подтверждённым contract", "PRODUCTION_DEPLOY"))
    if ads.get("enabled"):
        ref = ads.get("contract_ref")
        if ref and not _resolve_site_file(site_id, ref):
            out.append(Blocker("BLOCKED_RIGHTS", "advertising.contract_ref", f"Рекламный contract «{ref}» не найден в каталоге сайта.", "Положи переданный contract в sites/<site_id>/", "BUILDING"))
        if not ads.get("contract_ref"):
            out.append(Blocker("BLOCKED_RIGHTS", "advertising.contract_ref", "Рекламный слой включён без contract VK/Adman/AdTech.", "Согласованный рекламный contract с placement/product IDs", "BUILDING"))
        if ads.get("provider") in (None, "none"):
            out.append(Blocker("BLOCKED_INPUT", "advertising.provider", "Рекламный слой включён без указания provider.", "provider: vk_adman_adtech", "BUILDING"))
        if not ads.get("placements"):
            out.append(Blocker("BLOCKED_INPUT", "advertising.placements", "Не переданы placement ID.", "Список placement с page_types и reserved_size", "BUILDING"))
        if ads.get("adapter") == "mock" and env == "production":
            out.append(Blocker("BLOCKED_RIGHTS", "advertising.adapter", "Mock рекламного контура технически запрещён в production.", "adapter: official", "PRODUCTION_DEPLOY"))


def _check_secrets(pkg: dict, out: list[Blocker]) -> None:
    refs: list[tuple[str, str]] = []
    ads = pkg.get("advertising") or {}
    if ads.get("enabled") and ads.get("secret_ref"):
        refs.append(("advertising.secret_ref", ads["secret_ref"]))
    db = ((pkg.get("runtime") or {}).get("database") or {})
    if db.get("engine") not in (None, "none") and db.get("password_secret_ref"):
        refs.append(("runtime.database.password_secret_ref", db["password_secret_ref"]))
    for idx, integ in enumerate(pkg.get("integrations") or []):
        if integ.get("enabled") and integ.get("secret_ref"):
            refs.append((f"integrations/{idx}/secret_ref", integ["secret_ref"]))
    for field, ref in refs:
        available, what = _secret_available(ref)
        if not available:
            out.append(Blocker("BLOCKED_SECRET", field, f"secret_ref «{ref}» не резолвится: {what}.", "Значение секрета в согласованном хранилище/переменной окружения (в пакет и git оно не попадает)", "STAGING_DEPLOY"))
    # секрет не должен быть указан значением
    for field, ref in refs:
        if not re.match(r"^(env|file|vault|secret):", ref):
            out.append(Blocker("BLOCKED_SECRET", field, "Секрет задан значением, а не ссылкой.", "Используй secret_ref вида env:NAME / file:/path / vault:path", "VALIDATING"))


def _check_seo(pkg: dict, out: list[Blocker], warnings: list[str]) -> None:
    matrix = _matrix()
    url_policy = matrix.get("url_policy") or {}
    seo = pkg.get("seo") or {}
    meta = pkg.get("metadata") or {}
    policy = meta.get("canonical_policy") or {}

    if seo.get("pagination_template") != url_policy.get("pagination_template"):
        out.append(Blocker("BLOCKED_SEO", "seo.pagination_template", f"Шаблон пагинации «{seo.get('pagination_template')}» не совпадает с политикой матрицы «{url_policy.get('pagination_template')}». Смешивать схемы запрещено.", "Один утверждённый шаблон пагинации", "BUILDING"))
    if policy.get("host_form") and url_policy.get("host_form") and policy["host_form"] != url_policy["host_form"]:
        out.append(Blocker("BLOCKED_SEO", "metadata.canonical_policy.host_form", "Политика www/non-www пакета противоречит матрице.", "Единая политика хоста", "BUILDING"))
    if policy.get("trailing_slash") is not None and url_policy.get("trailing_slash") is not None and policy["trailing_slash"] != url_policy["trailing_slash"]:
        out.append(Blocker("BLOCKED_SEO", "metadata.canonical_policy.trailing_slash", "Политика trailing slash пакета противоречит матрице.", "Единая политика слэша", "BUILDING"))

    required_non_indexable = set((matrix.get("query_parameters") or {}).get("non_indexable") or [])
    declared = set(seo.get("non_indexable_parameters") or [])
    missing = sorted(required_non_indexable - declared)
    if missing:
        out.append(Blocker("BLOCKED_SEO", "seo.non_indexable_parameters", f"Не объявлены как неиндексируемые: {', '.join(missing)}.", "Полный список неиндексируемых параметров из матрицы", "BUILDING"))

    known_types = {p["id"] for p in matrix.get("page_types") or []}
    for idx, route in enumerate((pkg.get("acceptance") or {}).get("routes") or []):
        if route.get("page_type") not in known_types:
            out.append(Blocker("BLOCKED_SEO", f"acceptance/routes/{idx}/page_type", f"Тип страницы «{route.get('page_type')}» отсутствует в матрице индексируемости.", "Добавь тип в матрицу через /research-freeze или исправь маршрут", "BUILDING"))

    pagination_title = (meta.get("title_templates") or {}).get("pagination", "")
    if pagination_title and "{n}" not in pagination_title and "{page}" not in pagination_title:
        out.append(Blocker("BLOCKED_SEO", "metadata.title_templates.pagination", "Шаблон title для страниц пагинации не содержит номера страницы — страницы 2+ получат дубли title.", "Шаблон с плейсхолдером {n}", "BUILDING"))

    for idx, facet in enumerate(seo.get("indexable_facets_allowlist") or []):
        if not str(facet.get("url", "")).startswith("/"):
            out.append(Blocker("BLOCKED_SEO", f"seo/indexable_facets_allowlist/{idx}/url", "URL индексируемого фасета должен быть относительным путём от корня.", "URL вида /path/", "BUILDING"))
        if not facet.get("internal_links_from"):
            out.append(Blocker("BLOCKED_SEO", f"seo/indexable_facets_allowlist/{idx}/internal_links_from", "Индексируемый фасет без входящих внутренних ссылок станет orphan page.", "Список страниц, с которых стоит ссылка", "BUILDING"))

    if (meta.get("robots") or {}).get("staging_policy") != "noindex_all_plus_auth":
        warnings.append("Staging обязан быть закрыт авторизацией и noindex — один robots.txt защитой не считается.")


def _check_analytics(pkg: dict, out: list[Blocker], warnings: list[str]) -> None:
    """Аналитика и Вебмастер: пакет не должен утверждать больше, чем сделано.

    Проверяется согласованность manifest, а не доступность API: сеть — дело
    ворот конвейера (`factory.analytics.gate`), а здесь ловится то, что видно
    из самого пакета. Главный класс ошибки — статус, который красивее
    реальности: `VERIFIED` на неразвёрнутом домене, индексация без прав,
    счётчик, привязанный к чужому hostname.
    """
    analytics = pkg.get("analytics") or {}
    webmaster = pkg.get("webmaster") or {}
    # normalize_domain, а не lstrip("www."): lstrip срезает любые из символов
    # набора, и «web.tld» превращался в «eb.tld».
    domain = normalize_domain(str(pkg.get("domain") or ""))
    environment = pkg.get("environment")
    test_domain = domain.endswith((".localhost", ".localhost.test", ".test", ".local"))

    if analytics.get("enabled"):
        if analytics.get("provider") in (None, "none"):
            out.append(Blocker(
                "BLOCKED_INPUT", "analytics.provider",
                "Аналитика включена, но провайдер не назван.",
                "analytics.provider: yandex_metrika", "VALIDATING"))
        if analytics.get("webvisor"):
            out.append(Blocker(
                "BLOCKED_INPUT", "analytics.webvisor",
                "Вебвизор включён. Заданием запись сессий должна быть выключена.",
                "analytics.webvisor: false", "VALIDATING"))

        hosts = [str(h).strip().lower() for h in (analytics.get("allowed_hosts") or [])]
        for host in hosts:
            if host.endswith((".localhost", ".localhost.test", ".test", ".local")):
                out.append(Blocker(
                    "BLOCKED_INPUT", "analytics.allowed_hosts",
                    f"В списке разрешённых hostname тестовый адрес «{host}»: "
                    "production-счётчик не должен получать события со стенда.",
                    "Только боевые hostname этого сайта", "VALIDATING"))
        if environment == "production" and hosts and domain not in hosts:
            out.append(Blocker(
                "BLOCKED_INPUT", "analytics.allowed_hosts",
                f"Домен пакета «{domain}» отсутствует в analytics.allowed_hosts.",
                f"Добавить {domain} в analytics.allowed_hosts", "PRODUCTION_DEPLOY"))
        if analytics.get("counter_id") and test_domain:
            out.append(Blocker(
                "BLOCKED_INPUT", "analytics.counter_id",
                f"Счётчик Метрики привязан к тестовому домену «{domain}».",
                "Боевой домен или analytics.enabled: false для стенда", "VALIDATING"))
        if environment != "production":
            warnings.append(
                "Аналитика включена в пакете, но окружение не production: "
                "клиент событий тег Метрики не загрузит.")

    status = webmaster.get("verification_status")
    if webmaster.get("enabled"):
        if status == "VERIFIED" and test_domain:
            out.append(Blocker(
                "BLOCKED_INPUT", "webmaster.verification_status",
                f"Права на «{domain}» объявлены подтверждёнными, но домен тестовый: "
                "Вебмастер такой сайт подтвердить не мог.",
                "PLANNED или BLOCKED_DEPLOYMENT до реального развёртывания", "VALIDATING"))
        if status == "VERIFIED" and not webmaster.get("verification_marker"):
            out.append(Blocker(
                "BLOCKED_INPUT", "webmaster.verification_marker",
                "Права объявлены подтверждёнными, но маркер не сохранён — "
                "следующий релиз потеряет подтверждение.",
                "Маркер из ответа API в webmaster.verification_marker", "VALIDATING"))

    if pkg.get("seo_indexing_enabled"):
        # Индексация — необратимое по последствиям действие: выключить её
        # обратно легко, а убрать сайт из выдачи — нет.
        if environment != "production":
            out.append(Blocker(
                "BLOCKED_SEO", "seo_indexing_enabled",
                f"Индексация включена в окружении {environment}.",
                "seo_indexing_enabled: false вне production", "VALIDATING"))
        if not pkg.get("production_authorized"):
            out.append(Blocker(
                "BLOCKED_SEO", "seo_indexing_enabled",
                "Индексация включена без production_authorized: true.",
                "Авторизация владельца в manifest", "VALIDATING"))
        if status != "VERIFIED":
            out.append(Blocker(
                "BLOCKED_SEO", "seo_indexing_enabled",
                f"Индексация включена, но права в Вебмастере не подтверждены (статус {status}).",
                "Подтверждённые права (VERIFIED) до включения индексации", "VALIDATING"))
        if pkg.get("fixture"):
            out.append(Blocker(
                "BLOCKED_SEO", "seo_indexing_enabled",
                "Индексация включена для fixture-пакета: в выдачу попали бы тестовые данные.",
                "fixture: false и настоящий контент", "VALIDATING"))


def _check_files(pkg: dict, site_id: str, out: list[Blocker]) -> None:
    brand = pkg.get("brand") or {}
    for field, ref in (("brand.logo_ref", brand.get("logo_ref")), ("brand.favicon_ref", brand.get("favicon_ref"))):
        if ref and not _resolve_site_file(site_id, ref):
            out.append(Blocker("BLOCKED_INPUT", field, f"Файл «{ref}» не найден в sites/{site_id}/.", "Передай файл бренда в каталог сайта", "BUILDING"))
    for idx, doc in enumerate((pkg.get("legal") or {}).get("documents") or []):
        ref = doc.get("body_ref")
        if ref and not _resolve_site_file(site_id, ref):
            out.append(Blocker("BLOCKED_INPUT", f"legal/documents/{idx}/body_ref", f"Текст юридического документа «{ref}» не найден.", "Передай утверждённый текст документа", "BUILDING"))
    theme = pkg.get("theme_ref")
    if not theme:
        return
    if blueprint_of(pkg) == "payload-next-multisite":
        if theme not in PAYLOAD_THEMES:
            out.append(Blocker("BLOCKED_INPUT", "theme_ref",
                               f"Тема «{theme}» не объявлена blueprint payload-next-multisite "
                               f"(доступны: {', '.join(sorted(PAYLOAD_THEMES))}).",
                               "Тема из набора blueprint", "BUILDING"))
        return
    if not (PATHS.themes / theme).exists():
        out.append(Blocker("BLOCKED_INPUT", "theme_ref", f"Тема «{theme}» отсутствует в themes/.", "Одобренный theme pack", "BUILDING"))


def _check_network_allowlist(pkg: dict, out: list[Blocker], warnings: list[str]) -> None:
    allowlist = pkg.get("network_allowlist") or []
    for entry in allowlist:
        if "*" in entry and not entry.startswith("*."):
            out.append(Blocker("BLOCKED_ACCESS", "network_allowlist", f"Запись «{entry}» слишком широкая.", "Точные endpoint или поддомены вида *.example.tld", "STAGING_DEPLOY"))
    if not allowlist:
        warnings.append("network_allowlist пуст: сеть в режиме CLOSED_WORLD будет полностью запрещена для этого задания.")


def _check_cross_site_leakage(pkg: dict, site_id: str, out: list[Blocker]) -> None:
    """Идентификаторы одного сайта не должны встречаться в другом."""
    mine = {}
    verif = ((pkg.get("seo") or {}).get("webmaster_verification_refs") or {})
    for key, value in verif.items():
        if value:
            mine[f"seo.webmaster_verification_refs.{key}"] = value
    if not mine:
        return
    for other_dir in sorted(PATHS.sites.glob("*/package.yaml")):
        other_id = other_dir.parent.name
        if other_id == site_id:
            continue
        try:
            other = yaml.safe_load(other_dir.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        other_verif = ((other.get("seo") or {}).get("webmaster_verification_refs") or {})
        for field, value in mine.items():
            if value in [v for v in other_verif.values() if v]:
                out.append(Blocker("BLOCKED_INPUT", field, f"Verification ID совпадает с сайтом «{other_id}» — cross-site утечка идентификатора.", "Уникальный verification ID для каждого сайта", "BUILDING"))


def validate(site_id: str) -> ValidationResult:
    blockers: list[Blocker] = []
    warnings: list[str] = []
    try:
        pkg = load_package(site_id)
    except FileNotFoundError:
        return ValidationResult(site_id, None, [Blocker("BLOCKED_INPUT", "sites/<site_id>/package.yaml", f"Пакет сайта «{site_id}» не найден.", "Положи package.yaml в sites/<site_id>/", "RECEIVED")])
    except (ValueError, yaml.YAMLError) as exc:
        return ValidationResult(site_id, None, [Blocker("BLOCKED_INPUT", "package.yaml", f"Пакет нечитаем: {exc}", "Корректный YAML по schemas/site-package.schema.json", "RECEIVED")])

    if not _check_schema(pkg, blockers):
        # без валидной схемы семантические проверки дают шум, а не пользу
        return ValidationResult(site_id, pkg, blockers, warnings)

    _check_environment(pkg, blockers)
    _check_license(pkg, blockers, warnings)
    _check_targets(pkg, blockers)
    _check_domain_consistency(pkg, blockers)
    _check_content_rights(pkg, site_id, blockers)
    _check_publication_rights(pkg, blockers)
    _check_tenant_profile(pkg, blockers)
    _check_vk_and_ads(pkg, site_id, blockers)
    _check_secrets(pkg, blockers)
    _check_seo(pkg, blockers, warnings)
    _check_files(pkg, site_id, blockers)
    _check_analytics(pkg, blockers, warnings)
    _check_network_allowlist(pkg, blockers, warnings)
    _check_cross_site_leakage(pkg, site_id, blockers)
    return ValidationResult(site_id, pkg, blockers, warnings)
