"""Сводные ворота качества: SEO, браузер, безопасность, производительность.

Каждая проверка возвращает фактическую команду, exit code и путь к артефакту.
Проверка без артефакта не считается пройденной — это прямое требование к отчёту.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from factory.paths import PATHS
from factory.redaction import redact_obj
from factory.seo import crawl as crawl_mod
from factory.seo import lint as lint_mod
from factory.seo import render_check
from factory.seo.model import Finding, Report


@dataclass
class Check:
    id: str
    command: str
    #: None означает «команда не запускалась»; синтетический ноль здесь запрещён.
    exit_code: int | None
    passed: bool
    artifact: str
    counts: dict = field(default_factory=dict)
    severity: str = "critical"

    def as_dict(self) -> dict:
        return {"id": self.id, "command": self.command, "exit_code": self.exit_code, "passed": self.passed,
                "artifact": self.artifact, "counts": self.counts, "severity": self.severity}


def _get(base_url: str, path: str, auth: str = "") -> tuple[int, dict, str]:
    request = urllib.request.Request(base_url.rstrip("/") + path, headers={"User-Agent": "factory-verify/1.0"})
    if auth:
        request.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {}, str(exc)


REQUIRED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": None,
    "Referrer-Policy": None,
    "Content-Security-Policy": None,
}

FORBIDDEN_PUBLIC_PATHS = (
    "/.env", "/.git/config", "/routes.json", "/build-manifest.json",
    "/shared/logs/php-server.log", "/backups/", "/install.php", "/engine/data/config.php",
)


def security_smoke(base_url: str, out_dir: Path, *, auth: str = "", environment: str = "staging") -> Report:
    report = Report("security-smoke")
    status, headers, body = _get(base_url, "/", auth)
    for header, expected in REQUIRED_HEADERS.items():
        value = headers.get(header)
        if not value:
            report.add(Finding("headers", "critical", "/", f"Отсутствует заголовок {header}."))
        elif expected and expected not in value:
            report.add(Finding("headers", "critical", "/", f"{header} = «{value}», ожидалось «{expected}»."))
    if headers.get("X-Powered-By"):
        report.add(Finding("headers", "major", "/", "X-Powered-By раскрывает стек."))
    if environment != "production" and "noindex" not in headers.get("X-Robots-Tag", ""):
        report.add(Finding("staging", "critical", "/", "Staging не отдаёт X-Robots-Tag: noindex."))
    if environment != "production":
        anon_status, anon_headers, _ = _get(base_url, "/", "")
        if anon_status != 401:
            report.add(Finding("staging", "critical", "/", f"Staging доступен без авторизации (HTTP {anon_status}). robots.txt защитой не считается."))
    for path in FORBIDDEN_PUBLIC_PATHS:
        code, _, _ = _get(base_url, path, auth)
        if code not in (401, 403, 404):
            report.add(Finding("exposure", "critical", path, f"Служебный путь доступен публично (HTTP {code})."))
    # directory listing
    code, _, listing = _get(base_url, "/assets/", auth)
    if code == 200 and re.search(r"Index of|<title>Directory listing", listing, re.I):
        report.add(Finding("exposure", "critical", "/assets/", "Включён листинг каталога."))
    # mixed content
    if "http://" in re.sub(r'http://(127\.0\.0\.1|localhost)', "", body):
        report.add(Finding("mixed-content", "major", "/", "На странице есть ссылки по http://."))
    report.counts = {"checked_paths": len(FORBIDDEN_PUBLIC_PATHS), "root_status": status}
    (out_dir / "security-smoke.json").write_text(json.dumps(redact_obj(report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def performance_budget(browser_report: Report, package: dict, out_dir: Path) -> Report:
    """Лабораторные бюджеты. Полевые CWV ими не заменяются — это записано в отчёте."""
    report = Report("performance-budget")
    budgets = ((package.get("acceptance") or {}).get("performance") or {})
    counts = browser_report.counts or {}
    lcp = counts.get("lab_lcp_ms_max")
    cls = counts.get("lab_cls_max")
    transfer = counts.get("lab_transfer_bytes_max")
    status = counts.get("status")
    if status == "skipped":
        # Оператор осознанно сократил объём приёмки: это не дефект сайта, но и не доказательство.
        report.add(Finding("performance", "major", "-", "Метрики не собраны: браузерная проверка пропущена флагом."))
    elif status != "ok":
        report.add(Finding("performance", "critical", "-", f"Метрики не собраны: браузерная проверка недоступна ({status})."))
    else:
        if budgets.get("lab_lcp_ms") and lcp is not None and lcp > budgets["lab_lcp_ms"]:
            report.add(Finding("performance", "critical", "-", f"Lab LCP {lcp} мс превышает бюджет {budgets['lab_lcp_ms']} мс."))
        if budgets.get("lab_cls") is not None and cls is not None and cls > budgets["lab_cls"]:
            report.add(Finding("performance", "critical", "-", f"Lab CLS {cls} превышает бюджет {budgets['lab_cls']}."))
        if budgets.get("lab_total_bytes") and transfer and transfer > budgets["lab_total_bytes"]:
            report.add(Finding("performance", "major", "-", f"Передано {transfer} байт при бюджете {budgets['lab_total_bytes']}."))
    report.counts = {
        # Статус наследуется от браузерной проверки: без него пропуск выглядел бы
        # как «проверка нашла замечания».
        "status": status if status in ("skipped", "unavailable", "failed") else "ok",
        "lab_lcp_ms_max": lcp, "lab_cls_max": cls, "lab_transfer_bytes_max": transfer,
        "budgets": budgets,
        "field_targets_note": "Полевые LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 на 75-м перцентиле измеряются только на реальном трафике.",
    }
    (out_dir / "performance-budget.json").write_text(json.dumps(redact_obj(report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def acceptance_routes(base_url: str, package: dict, out_dir: Path, *, auth: str = "") -> Report:
    report = Report("acceptance-routes")
    for route in (package.get("acceptance") or {}).get("routes") or []:
        status, headers, body = _get(base_url, route["path"], auth)
        if status != route["expected_status"]:
            report.add(Finding("acceptance", "critical", route["path"], f"Ожидался {route['expected_status']}, получен {status}."))
            continue
        if route.get("expect_indexable") is False and status == 200:
            robots = headers.get("X-Robots-Tag", "") + (re.search(r'<meta name="robots" content="([^"]+)"', body).group(1) if re.search(r'<meta name="robots" content="([^"]+)"', body) else "")
            if "noindex" not in robots:
                report.add(Finding("acceptance", "critical", route["path"], "Маршрут должен быть неиндексируемым, но noindex отсутствует."))
    report.counts = {"routes": len((package.get("acceptance") or {}).get("routes") or [])}
    (out_dir / "acceptance-routes.json").write_text(json.dumps(redact_obj(report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _get_host(base_url: str, path: str, host: str, *, follow: bool = True) -> tuple[int, dict, str]:
    """Запрос к стенду с явным Host: три сайта живут на одном порту."""
    request = urllib.request.Request(base_url.rstrip("/") + path,
                                     headers={"User-Agent": "factory-verify/1.0", "Host": host})
    handlers: list = [urllib.request.ProxyHandler({})]
    if not follow:
        handlers.append(_NoFollow())
    opener = urllib.request.build_opener(*handlers)
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {}, str(exc)


def _post_host(base_url: str, path: str, host: str, payload: dict) -> tuple[int, dict, str]:
    """Анонимный POST для проверки прав на запись."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + path, data=data, method="POST",
        headers={"User-Agent": "factory-verify/1.0", "Host": host,
                 "content-type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return 0, {}, str(exc)


class _NoFollow(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


_ROBOTS_RE = re.compile(r'<meta[^>]+name="robots"[^>]+content="([^"]*)"', re.I)
_CANONICAL_RE = re.compile(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', re.I)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
_DESCRIPTION_RE = re.compile(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', re.I)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)
_MAIN_RE = re.compile(r"<main[^>]*>(.*?)</main>", re.S | re.I)
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")


def _plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _SCRIPT_RE.sub(" ", html))).strip()


def acceptance_routes_multisite(base_url: str, package: dict, out_dir: Path) -> Report:
    """Маршруты приёмки проверяются на живом стенде с Host конкретного сайта."""
    report = Report("acceptance-routes")
    host = package["domain"]
    indexing_enabled = bool((package.get("tenant") or {}).get("indexing_enabled", True))
    rows = []
    for route in package["acceptance"]["routes"]:
        status, _, body = _get_host(base_url, route["path"], host)
        robots = _ROBOTS_RE.search(body)
        indexable = bool(robots) and robots.group(1).strip().startswith("index")
        rows.append({"path": route["path"], "status": status, "expected": route["expected_status"],
                     "indexable": indexable, "expect_indexable": route.get("expect_indexable")})
        if status != route["expected_status"]:
            report.add(Finding("acceptance-routes", "critical", route["path"],
                               f"Ожидался статус {route['expected_status']}, получен {status}.", "ACC-1"))
        if route.get("expect_indexable") is not None and status == 200:
            expected_indexable = bool(route["expect_indexable"]) and indexing_enabled
            if indexable != expected_indexable:
                report.add(Finding("acceptance-routes", "critical", route["path"],
                                   f"Индексируемость {indexable}, ожидалась {expected_indexable} "
                                   f"(профиль: {route['expect_indexable']}, "
                                   f"индексация сайта включена: {indexing_enabled}).", "ACC-2"))
        if status == 200 and indexable:
            canonical = _CANONICAL_RE.search(body)
            expected = f"https://{host}{route['path']}"
            if not canonical or canonical.group(1) != expected:
                report.add(Finding("acceptance-routes", "critical", route["path"],
                                   f"Ожидался self-canonical {expected}, получен "
                                   f"{canonical.group(1) if canonical else 'ничего'}.", "HR-1"))
            direct_status, _, _ = _get_host(base_url, route["path"], host, follow=False)
            if direct_status != 200:
                report.add(Finding("acceptance-routes", "critical", route["path"],
                                   f"Индексируемый адрес отвечает {direct_status} без перехода: "
                                   "canonical указывает на редирект.", "HR-2"))
    if not indexing_enabled:
        # Пока индексация выключена, профильная индексируемость не проверена ни разу.
        # Вместо ослабления ожиданий проверяется то, что обязано быть верно сейчас,
        # а сама проверка помечается частичной: полной приёмкой она не является.
        status, _, robots_body = _get_host(base_url, "/robots.txt", host)
        if status != 200 or "Disallow: /" not in robots_body:
            report.add(Finding("acceptance-routes", "critical", "/robots.txt",
                               "Индексация сайта выключена, но robots.txt не закрывает сайт целиком.",
                               "ACC-3"))
        status, _, _ = _get_host(base_url, "/sitemap.xml", host)
        if status == 200:
            report.add(Finding("acceptance-routes", "critical", "/sitemap.xml",
                               "Индексация сайта выключена, но карта сайта отдаётся.", "ACC-4"))

    report.counts = {"routes": len(rows), "indexing_enabled": indexing_enabled,
                     "status": "executed" if indexing_enabled else "partial",
                     "reason": None if indexing_enabled
                     else "индексация сайта выключена: профильная индексируемость не проверялась"}
    (out_dir / "acceptance-routes.json").write_text(
        json.dumps(redact_obj({"host": host, "routes": rows, **report.as_dict()}),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def security_smoke_multisite(base_url: str, package: dict, out_dir: Path,
                             *, environment: str = "staging") -> Report:
    """Публичная поверхность стенда: заголовки, закрытые пути, анонимный API."""
    report = Report("security-smoke")
    host = package["domain"]
    observed = {}

    status, headers, _ = _get_host(base_url, "/", host)
    observed["/"] = {"status": status, "headers": {k: v for k, v in headers.items()
                                                   if k.lower().startswith(("x-", "content-security", "referrer"))}}
    for header in ("X-Content-Type-Options", "Referrer-Policy", "Content-Security-Policy"):
        if header not in headers:
            report.add(Finding("security-smoke", "critical", "/",
                               f"Отсутствует заголовок {header}.", "SEC-1"))

    # Стенд с фикстурами не должен быть индексируемым: «в production попали
    # test/demo данные» начинается именно с индексируемого staging.
    indexing_enabled = bool((package.get("tenant") or {}).get("indexing_enabled", True))
    if environment != "production" and indexing_enabled:
        report.add(Finding("security-smoke", "critical", "/",
                           "На staging включена индексация сайта.", "SEC-5"))

    # Анонимный доступ к данным сайтов закрыт: иначе изоляция теряет смысл на публичном API.
    for path in ("/api/posts?limit=100", "/api/comments?limit=100", "/api/tenants?limit=100",
                 "/api/rights-records?limit=100", "/api/source-records?limit=100",
                 "/api/import-jobs?limit=100", "/api/player-profiles?limit=100",
                 "/api/audit-log?limit=100", "/api/media?limit=100"):
        status, _, body = _get_host(base_url, path, host)
        observed[path] = {"status": status}
        if status == 200 and '"docs":[]' not in body.replace(" ", ""):
            report.add(Finding("security-smoke", "critical", path,
                               f"Анонимный запрос к {path} вернул данные.", "SEC-2"))

    for path in ("/api/audit-log", "/api/comments", "/api/posts"):
        status, _, _ = _post_host(base_url, path, host, {})
        observed[f"POST {path}"] = {"status": status}
        # 400 означает, что доступ пройден и запрос дошёл до валидации полей.
        if status not in (401, 403):
            report.add(Finding("security-smoke", "critical", path,
                               f"Анонимная запись в {path} не отклонена (получен {status}).", "SEC-6"))

    # Первый пользователь Payload создаётся в обход прав доступа: пока таблица
    # пуста, любой может зарегистрировать себе супер-администратора.
    status, _, _ = _post_host(base_url, "/api/users/first-register", host,
                              {"email": "probe@factory.invalid", "password": "probe-not-used"})
    observed["POST /api/users/first-register"] = {"status": status}
    if status not in (401, 403):
        report.add(Finding("security-smoke", "critical", "/api/users/first-register",
                           f"Открыта регистрация первого пользователя (получен {status}): "
                           "стенд допускает анонимное создание супер-администратора.", "SEC-7"))

    for path in ("/.env", "/.git/config", "/var/db/anime.password", "/build-manifest.json"):
        status, _, _ = _get_host(base_url, path, host)
        observed[path] = {"status": status}
        if status == 200:
            report.add(Finding("security-smoke", "critical", path,
                               "Служебный путь доступен публично.", "SEC-3"))

    # Строки перевода живут в бандле и находятся на любой странице админки, поэтому
    # состояние панели определяется не текстом, а ответом API на анонимный запрос.
    status, _, _ = _get_host(base_url, "/admin", host)
    observed["/admin"] = {"status": status}
    me_status, _, me_body = _get_host(base_url, "/api/users/me", host)
    observed["/api/users/me"] = {"status": me_status}
    if me_status == 200 and '"user":null' not in me_body.replace(" ", ""):
        report.add(Finding("security-smoke", "critical", "/api/users/me",
                           "Анонимный запрос получает пользователя: сессия админки открыта.", "SEC-4"))

    report.counts = {"probes": len(observed), "status": "executed"}
    (out_dir / "security-smoke.json").write_text(
        json.dumps(redact_obj({"probes": observed, **report.as_dict()}), ensure_ascii=False, indent=2),
        encoding="utf-8")
    return report


def _surface(base_url: str, host: str) -> list[tuple[str, bool]]:
    """Индексируемая поверхность сайта.

    Основной источник — sitemap. Если сайт ещё не разрешил индексацию, sitemap
    пуст, и поверхность собирается обходом разделов: иначе ворота уникальности
    молча не выполнялись бы ровно тогда, когда они нужнее всего — до публикации.
    """
    found: list[tuple[str, bool]] = [("/", True)]

    # Карта сайта — заявление сайта о себе, а не независимый источник. Если брать
    # только её, страница, которую профиль индексирует, но которая в карту не
    # попала, никогда не сравнивается с другими сайтами. Поэтому карта и обход
    # объединяются.
    status, _, sitemap = _get_host(base_url, "/sitemap.xml", host)
    if status == 200:
        found.extend((urllib.parse.urlparse(loc).path, True) for loc in _LOC_RE.findall(sitemap))

    for listing in ("/catalog/", "/collections/", "/news/", "/schedule/"):
        listing_status, _, body = _get_host(base_url, listing, host)
        if listing_status != 200:
            continue
        robots = _ROBOTS_RE.search(body)
        owned = bool(robots) and "noindex" not in robots.group(1)
        found.append((listing, owned))
        prefix = re.escape(listing)
        for item in sorted(set(re.findall(r'href="(' + prefix + r'[^"/]+/)"', body))):
            found.append((item, True))
    for legal in ("/legal/rights/",):
        legal_status, _, _ = _get_host(base_url, legal, host)
        if legal_status == 200:
            found.append((legal, True))
    # Дубли путей не нужны: одна страница — одно наблюдение.
    seen: set[str] = set()
    unique: list[tuple[str, bool]] = []
    for path, intent in found:
        if path in seen:
            continue
        seen.add(path)
        unique.append((path, intent))
    return unique


def cross_site_uniqueness(base_url: str, package: dict, out_dir: Path) -> Report:
    """Ворота уникальности между сайтами одной группы.

    Собираются только сайты, объявленные в той же `cross_site_group`. Если в группе
    меньше двух развёрнутых сайтов, проверка помечается непроведённой: сравнивать
    не с чем, и «уникально» здесь было бы неправдой.
    """
    from factory import validation
    from factory.seo import uniqueness

    group = package.get("cross_site_group")
    hosts: list[tuple[str, str]] = []
    if group:
        for directory in sorted((PATHS.sites).iterdir()):
            if not (directory / "package.yaml").exists():
                continue
            try:
                other = validation.load_package(directory.name)
            except Exception:  # noqa: BLE001 — нечитаемый чужой пакет не должен ронять проверку
                continue
            if other.get("cross_site_group") == group:
                hosts.append((directory.name, other["domain"]))

    pages: list = []
    for _, host in hosts:
        for path, intent in _surface(base_url, host):
            page_status, _, body = _get_host(base_url, path, host)
            if page_status != 200:
                continue
            robots = _ROBOTS_RE.search(body)
            live_indexable = bool(robots) and robots.group(1).strip().startswith("index")
            main = _MAIN_RE.search(body)
            h1 = _H1_RE.search(body)
            title = _TITLE_RE.search(body)
            canonical = _CANONICAL_RE.search(body)
            description = _DESCRIPTION_RE.search(body)
            pages.append(uniqueness.PageObservation(
                site_id=host, path=path, page_type=_page_type_of(path),
                site_name=_site_name_of(body),
                # Здесь идентификатор сайта и есть его хост, но CSU-7 больше не
                # догадывается об этом сам: хост передаётся явно.
                site_host=host,
                # Пока индексация сайта выключена, все страницы отдают noindex.
                # Сравнивать при этом «нечего» неверно: вопрос дубля решается до
                # включения переключателя, поэтому берётся намерение профиля.
                indexable=live_indexable or intent,
                title=_plain(title.group(1)) if title else "",
                description=description.group(1) if description else "",
                h1=_plain(h1.group(1)) if h1 else "",
                own_text=_plain(main.group(1)) if main else "",
                # Canonical у noindex-страницы отсутствует по правилам матрицы,
                # поэтому проверка CSU-7 применима только к живым индексируемым.
                canonical=canonical.group(1) if canonical and live_indexable else ""))

    report = uniqueness.check(pages)
    (out_dir / "cross-site-uniqueness.json").write_text(
        json.dumps(redact_obj(report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    return report


_SITE_NAME_RE = re.compile(r'<a[^>]+class="site-header__brand"[^>]*>(.*?)</a>', re.S | re.I)


def _site_name_of(body: str) -> str:
    """Публичное имя сайта из шапки: оно вырезается из заголовков перед сравнением."""
    match = _SITE_NAME_RE.search(body)
    return _plain(match.group(1)) if match else ""


def _page_type_of(path: str) -> str:
    if path == "/":
        return "home"
    if path in ("/catalog/", "/news/", "/collections/", "/schedule/"):
        return "listing"
    if re.fullmatch(r"/catalog/[^/]+/season-\d+/episode-\d+/", path):
        return "episode"
    if re.fullmatch(r"/catalog/[^/]+/season-\d+/", path):
        return "season"
    if re.fullmatch(r"/catalog/[^/]+/", path):
        return "title"
    if re.fullmatch(r"/news/[^/]+/", path):
        return "article"
    if re.fullmatch(r"/collections/[^/]+/", path):
        return "collection"
    if re.fullmatch(r"/legal/[^/]+/", path):
        return "legal"
    return "page"


def player_contract_check(base_url: str, package: dict, out_dir: Path) -> Report:
    """Плеер на живой странице: только атрибуты контракта, без утечки токена."""
    report = Report("player-contract")
    host = package["domain"]
    # Список разрешённых атрибутов живёт там, где элемент собирается, и
    # проверяется вместе со сборкой: blueprints/payload-next-multisite/app/src/
    # player/contract.ts. Вторая копия здесь расходилась бы с первой молча.
    observed = {}

    token_env = (package.get("content_api") or {}).get("token_ref") or ""
    token_value = os.environ.get(token_env, "") if token_env else ""

    # Страницы серий ищутся обходом каталога, а не по sitemap: пока индексация
    # сайта выключена, sitemap пуст, и проверка контракта молча не выполнялась бы.
    episode_paths: list[str] = []
    catalog_status, _, catalog = _get_host(base_url, "/catalog/", host)
    if catalog_status == 200:
        title_paths = sorted(set(re.findall(r'href="(/catalog/[^"/]+/)"', catalog)))
        for title_path in title_paths[:5]:
            title_status, _, title_body = _get_host(base_url, title_path, host)
            if title_status != 200:
                continue
            for season_path in sorted(set(re.findall(r'href="(' + re.escape(title_path) + r'season-\d+/)"', title_body))):
                season_status, _, season_body = _get_host(base_url, season_path, host)
                if season_status != 200:
                    continue
                episode_paths.extend(sorted(set(
                    re.findall(r'href="(' + re.escape(season_path) + r'episode-\d+/)"', season_body))))
                if episode_paths:
                    break
            if episode_paths:
                break
    if not episode_paths:
        report.counts = {"status": "skipped", "reason": "на сайте нет индексируемых страниц серий"}
        (out_dir / "player-contract.json").write_text(
            json.dumps({"host": host, "checked": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    for path in episode_paths[:5]:
        page_status, _, body = _get_host(base_url, path, host)
        observed[path] = {"status": page_status}
        if page_status != 200:
            report.add(Finding("player-contract", "critical", path,
                               f"Страница серии отвечает {page_status}.", "PC-0"))
            continue

        # На уровне HTTP проверяется то, что HTTP видит достоверно: значения
        # атрибутов и отсутствие секрета. Полный состав атрибутов элемента
        # проверяется в браузере, где он собран и доступен без догадок.
        has_marker = "disable-licensed" in body
        observed[path]["player_present"] = has_marker
        if has_marker:
            if not re.search(r'disable-licensed[^a-zA-Z0-9]{1,8}false', body):
                report.add(Finding("player-contract", "critical", path,
                                   "disable-licensed присутствует, но не равен false.", "PC-3"))
            if "cdnvideohub.com" in body and "player.cdnvideohub.com/s2/stable/video-player.umd.js" not in body:
                report.add(Finding("player-contract", "critical", path,
                                   "Подключается не тот адрес скрипта плеера.", "PC-8"))
        if token_value and token_value in body:
            report.add(Finding("player-contract", "critical", path,
                               "Токен Content API попал в страницу.", "PC-7"))

    rendered = sum(1 for item in observed.values() if item.get("player_present"))
    report.counts = {
        "pages": len(observed),
        "players_rendered": rendered,
        # Ноль отрисованных плееров — это непроведённая проверка, а не «нарушений нет».
        "status": "executed" if rendered else "skipped",
        "reason": None if rendered else "ни на одной странице серии плеер не отрисован",
    }
    (out_dir / "player-contract.json").write_text(
        json.dumps(redact_obj({"host": host, "checked": observed, **report.as_dict()}),
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def verify_payload_multisite(site_id: str, package: dict, base_url: str, *, job_id: str) -> tuple[list, list]:
    """Ворота качества для blueprint payload-next-multisite."""
    out_dir = PATHS.artifact_dir("verify", site_id, job_id)
    reports = [
        acceptance_routes_multisite(base_url, package, out_dir),
        security_smoke_multisite(base_url, package, out_dir,
                                 environment=package.get("environment", "staging")),
        cross_site_uniqueness(base_url, package, out_dir),
        player_contract_check(base_url, package, out_dir),
    ]
    severity = {"cross-site-uniqueness": "critical", "player-contract": "critical",
                "acceptance-routes": "critical", "security-smoke": "critical"}
    checks = []
    for report in reports:
        artifact = str((out_dir / f"{report.name}.json").relative_to(PATHS.root))
        executed = report.counts.get("status") != "skipped"
        checks.append(Check(
            id=report.name,
            command=f"factory verify --site {site_id} ({report.name})",
            exit_code=0 if report.passed else (1 if executed else None),
            passed=report.passed,
            artifact=artifact,
            counts=report.counts,
            # Непроведённая проверка — не провал и не успех: она остаётся замечанием
            # уровня major, из-за которого приёмка считается неполной, а production закрыт.
            severity=severity.get(report.name, "critical") if executed else "major",
        ))
    return checks, reports


def verify(site_id: str, package: dict, build_dir: Path, base_url: str, *, auth: str = "",
           environment: str = "staging", skip_browser: bool = False,
           job_id: str | None = None) -> tuple[list[Check], list[Report]]:
    # Артефакты каждого задания лежат отдельно: общий каталог перетирался следующим
    # прогоном, и отчёт ссылался на чужие результаты.
    out_dir = PATHS.artifact_dir("qa", site_id, job_id) if job_id else PATHS.artifact_dir("qa", site_id)
    checks: list[Check] = []
    reports: list[Report] = []

    lint_report = lint_mod.lint(build_dir, environment=environment)
    (out_dir / "seo-lint.json").write_text(json.dumps(redact_obj(lint_report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(lint_report)
    checks.append(Check("seo-lint", f"python3 -m factory seo-lint --site {site_id}", 0 if lint_report.passed else 1,
                        lint_report.passed, str((out_dir / "seo-lint.json").relative_to(PATHS.root)), lint_report.counts))

    crawl_report = crawl_mod.crawl(base_url, build_dir, auth=auth, environment=environment)
    (out_dir / "seo-crawl.json").write_text(json.dumps(redact_obj(crawl_report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(crawl_report)
    checks.append(Check("seo-crawl", f"python3 -m factory seo-crawl --site {site_id} --base {base_url}",
                        0 if crawl_report.passed else 1, crawl_report.passed,
                        str((out_dir / "seo-crawl.json").relative_to(PATHS.root)), crawl_report.counts))

    if skip_browser:
        browser_report = Report("seo-render")
        # severity=major: это осознанное сокращение объёма приёмки оператором,
        # а не найденный дефект. Проверка при этом НЕ считается пройденной.
        browser_report.add(Finding("browser", "major", base_url,
                                   "Браузерная проверка не выполнялась (--skip-browser): приёмка неполная."))
        browser_report.counts = {"status": "skipped"}
    else:
        browser_report = render_check.run(base_url, build_dir, out_dir, auth=auth)
    (out_dir / "seo-render.json").write_text(json.dumps(redact_obj(browser_report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(browser_report)
    render_passed = browser_report.passed and not skip_browser
    render_exit = None if skip_browser else browser_report.counts.get("exit_code", 0 if render_passed else 1)
    checks.append(Check("seo-render",
                        "(не запускалась: --skip-browser)" if skip_browser else f"node tools/browser-audit.js --base {base_url}",
                        render_exit, render_passed,
                        str((out_dir / "seo-render.json").relative_to(PATHS.root)), browser_report.counts,
                        severity="major" if skip_browser else "critical"))

    security = security_smoke(base_url, out_dir, auth=auth, environment=environment)
    reports.append(security)
    checks.append(Check("security-smoke", f"python3 -m factory verify --site {site_id} (security)",
                        0 if security.passed else 1, security.passed,
                        str((out_dir / "security-smoke.json").relative_to(PATHS.root)), security.counts))

    acceptance = acceptance_routes(base_url, package, out_dir, auth=auth)
    reports.append(acceptance)
    checks.append(Check("acceptance-routes", f"python3 -m factory verify --site {site_id} (acceptance)",
                        0 if acceptance.passed else 1, acceptance.passed,
                        str((out_dir / "acceptance-routes.json").relative_to(PATHS.root)), acceptance.counts))

    # Бюджет major-находок: иначе замечания уровня major не влияют ни на что,
    # и «20 major thin-content» выглядят как полностью зелёная приёмка.
    budget = int(((package.get("acceptance") or {}).get("max_major_findings")) or 25)
    major_total = sum(len([f for f in r.findings if f.severity == "major"]) for r in reports)
    major_report = Report("major-findings-budget")
    major_report.counts = {"status": "ok", "major": major_total, "budget": budget}
    if major_total > budget:
        major_report.add(Finding("budget", "critical", "-",
                                 f"Замечаний уровня major {major_total} при бюджете {budget}."))
    (out_dir / "major-findings-budget.json").write_text(
        json.dumps(redact_obj(major_report.as_dict()), ensure_ascii=False, indent=2), encoding="utf-8")
    reports.append(major_report)
    checks.append(Check("major-findings-budget", f"python3 -m factory verify --site {site_id} (major budget)",
                        0 if major_report.passed else 1, major_report.passed,
                        str((out_dir / "major-findings-budget.json").relative_to(PATHS.root)), major_report.counts))

    performance = performance_budget(browser_report, package, out_dir)
    reports.append(performance)
    performance_passed = performance.passed and not skip_browser
    performance_exit = None if skip_browser else (0 if performance_passed else 1)
    checks.append(Check("performance-budget",
                        "(не запускалась: зависит от браузерной проверки)" if skip_browser
                        else f"python3 -m factory verify --site {site_id} (performance)",
                        performance_exit, performance_passed,
                        str((out_dir / "performance-budget.json").relative_to(PATHS.root)), performance.counts,
                        severity="major" if skip_browser else "critical"))

    return checks, reports
