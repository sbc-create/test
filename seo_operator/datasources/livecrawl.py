"""Обход живых витрин: только чтение, только разрешённые хосты.

Ежедневный отчёт до сих пор заканчивался строкой «нет данных обхода: анализ
страниц не выполнялся». Источников поисковой статистики нет, и это внешний
блокер — но обход собственных страниц не требует ни одного чужого доступа.
Из-за отсутствия этой стадии цикл не находил даже тех дефектов, которые видны
в отрисованном HTML: отсутствующий Open Graph, слишком длинный title,
канонизацию на чужой домен.

Границы модуля намеренно узкие.

*Только GET.* Ни один метод, меняющий состояние, здесь не предусмотрен, и
добавить его нельзя, не переписав модуль: адрес запрашивается единственной
функцией, которая другого метода не знает.

*Только хосты из inventory/network-allowlist.yaml, и только с методом GET.*
Проверка идёт перед запросом, а не после. Отсутствие записи означает отказ, а
не «наверное, можно»: сайт может быть чужим, как amd.online, и обходить его
оператору нечем и незачем.

*Ничего не отправляется наружу.* Карты сайта, уведомления об индексации,
обращения к Вебмастеру и Search Console этому модулю недоступны по построению.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from seo_operator.technical_seo import Page

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWLIST_PATH = REPO_ROOT / "inventory" / "network-allowlist.yaml"

#: Сколько адресов одного сайта обходит суточный цикл. Обход — вежливая
#: операция по отношению к собственному серверу: полный корпус в 53 тысячи
#: адресов не нужен ежедневно, нужна представительная выборка и её повторяемость.
DEFAULT_PAGE_BUDGET = 12

REQUEST_TIMEOUT_SEC = 25


class CrawlNotAllowedError(RuntimeError):
    """Хост не разрешён к чтению. Не перехватывать ради «мягкой деградации»."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status_code: int | None
    html: str
    redirects: int = 0


Fetcher = Callable[[str], FetchedPage]


def allowed_get_hosts(path: Path | None = None) -> frozenset[str]:
    data = yaml.safe_load((path or ALLOWLIST_PATH).read_text(encoding="utf-8"))
    return frozenset(
        entry["host"]
        for entry in data.get("hosts", [])
        if "GET" in (entry.get("methods") or [])
    )


def ensure_allowed(url: str, *, allowlist: frozenset[str] | None = None) -> str:
    host = (urlsplit(url).hostname or "").lower()
    allowed = allowlist if allowlist is not None else allowed_get_hosts()
    if host not in allowed:
        raise CrawlNotAllowedError(
            f"{host or url}: хост не разрешён к чтению в inventory/network-allowlist.yaml. "
            "Отсутствие записи — отказ, а не разрешение по умолчанию."
        )
    return host


def curl_fetcher(url: str) -> FetchedPage:
    """Единственное место, где происходит сетевой запрос. Метод один — GET."""
    marker = "@@@"
    proc = subprocess.run(
        [
            "curl", "-sS", "-L", "--get",
            "-w", f"\n{marker}%{{http_code}}{marker}%{{num_redirects}}",
            "--max-time", str(REQUEST_TIMEOUT_SEC),
            url,
        ],
        capture_output=True,
        text=True,
    )
    body = proc.stdout
    match = re.search(rf"{marker}(\d+){marker}(\d+)$", body)
    if not match:
        return FetchedPage(url=url, status_code=None, html=body)
    return FetchedPage(
        url=url,
        status_code=int(match.group(1)),
        html=body[: match.start()],
        redirects=int(match.group(2)),
    )


def _visible_text_length(html: str) -> int:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return len(re.sub(r"\s+", " ", text).strip())


def _structured_data(html: str) -> list[dict]:
    blocks: list[dict] = []
    for raw in re.findall(r"application/ld\+json[^>]*>(.*?)</script>", html, re.I | re.S):
        try:
            parsed = json.loads(raw)
        except ValueError:
            continue
        blocks.extend(parsed if isinstance(parsed, list) else [parsed])
    return [b for b in blocks if isinstance(b, dict)]


def page_from_html(fetched: FetchedPage) -> Page:
    html = fetched.html

    def first(pattern: str) -> str | None:
        match = re.search(pattern, html, re.I | re.S)
        return match.group(1).strip() if match else None

    headings = [
        re.sub(r"<[^>]+>", "", raw).strip()
        for raw in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    ]
    open_graph = dict(
        re.findall(r'<meta[^>]+property="(og:[^"]+)"[^>]+content="([^"]*)"', html, re.I)
    )
    host = urlsplit(fetched.url).hostname or ""
    # Только ссылки, по которым переходит читатель. rel=canonical и preload
    # тоже несут href на собственный домен, но перелинковкой не являются, и
    # засчитывать их — значит считать страницу связанной, когда на ней нет ни
    # одной ссылки.
    own_links = re.findall(
        rf'<a\s[^>]*href="(?:https://{re.escape(host)})?(/[^"]*)"', html, re.I
    )

    return Page(
        url=fetched.url,
        status_code=fetched.status_code,
        title=first(r"<title[^>]*>(.*?)</title>"),
        description=first(r'<meta[^>]+name="description"[^>]+content="([^"]*)"'),
        h1=[h for h in headings if h],
        canonical=first(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"'),
        indexable=False,
        rendered_text_length=_visible_text_length(html),
        open_graph=open_graph,
        structured_data=_structured_data(html),
        internal_links_in=1 if own_links else 0,
        internal_links_out=len(own_links),
        redirect_chain=["redirect"] * fetched.redirects,
    )


def crawl_site(
    base_url: str,
    paths: Sequence[str],
    *,
    fetcher: Fetcher = curl_fetcher,
    allowlist: frozenset[str] | None = None,
    page_budget: int = DEFAULT_PAGE_BUDGET,
) -> list[Page]:
    ensure_allowed(base_url, allowlist=allowlist)
    base = base_url.rstrip("/")
    pages: list[Page] = []
    for path in list(paths)[:page_budget]:
        url = base + path if path.startswith("/") else f"{base}/{path}"
        ensure_allowed(url, allowlist=allowlist)
        pages.append(page_from_html(fetcher(url)))
    return pages


def crawl_portfolio(
    sites: Iterable[dict],
    *,
    paths_for: Callable[[dict], Sequence[str]],
    fetcher: Fetcher = curl_fetcher,
    allowlist: frozenset[str] | None = None,
    page_budget: int = DEFAULT_PAGE_BUDGET,
) -> dict[str, list[Page]]:
    """Обход портфеля. Синтетические тенанты не обходятся: их некуда запрашивать."""
    out: dict[str, list[Page]] = {}
    for site in sites:
        if site.get("synthetic", False):
            continue
        out[site["site_id"]] = crawl_site(
            site["base_url"],
            paths_for(site),
            fetcher=fetcher,
            allowlist=allowlist,
            page_budget=page_budget,
        )
    return out
