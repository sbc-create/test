"""AMD Online — публичные HTML-страницы. Не API и не фид.

Источник называется ``AMD_ONLINE_PUBLIC_HTML``, и это не формальность:
официального API у сайта нет, договорного фида нет, письменного
разрешения владельца нет.Назвать источник «официальным» значило бы записать в
provenance неправду, которую потом невозможно отличить от правды.

**Границы, заданные robots.txt сайта.** Правила ``Disallow: */page/*`` и
``Disallow: */page*`` закрывают пагинацию, а раздел онгоингов листается
именно через ``/ongoingi/page/N/``. Обходить это нельзя, поэтому полный
перечень произведений берётся из ``sitemap.xml`` — файла, который
robots.txt объявляет сам и ровно для этого предназначен. Первая страница
раздела (``/ongoingi/``) под запрет не попадает и читается напрямую.

Скорость: один запрос за раз, не чаще одного в секунду, со случайной
добавкой. Кэш в пределах запуска, конечные таймауты, ограниченные
повторы. Источник гасится целиком при 403, 429, признаках CAPTCHA,
массовых 5xx и при расхождении разметки — молча собирать мусор хуже, чем
остановиться.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import random
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from factory.ratings.adapters.base import AdapterError
from factory.unified_ratings.adapters.base import Capabilities, HealthState, SourceFetch

SOURCE_KEY = "amd_online"
ADAPTER_VERSION = "amd_online_public_html/2.0.0"
ORIGIN = "https://amd.online"
SITEMAP = f"{ORIGIN}/news_pages.xml"
ONGOING_FIRST_PAGE = f"{ORIGIN}/ongoingi/"

#: Пути, запрещённые robots.txt сайта. Проверяются до запроса.
ROBOTS_DISALLOW_PATTERNS = (
    re.compile(r"/page/"),
    re.compile(r"/page\d"),
    re.compile(r"/engine/"),
    re.compile(r"/user/"),
    re.compile(r"/uploads/"),
    re.compile(r"/mylists/"),
    re.compile(r"/newposts/"),
    re.compile(r"/friends/"),
    re.compile(r"/pm/"),
    re.compile(r"\?"),
    re.compile(r"do=\w+"),
    re.compile(r"/anime/dat/"),
)

TITLE_URL_RE = re.compile(r"^https://amd\.online/(?P<id>\d+)-(?P<slug>[^/?#]+)\.html$")

#: Компоненты подписаны на самой странице; безымянные числа не берём.
COMPONENT_LABELS = {
    "story": "Сюжет",
    "actors": "Персонажи",
    "graph": "Рисовка",
    "sound": "Озвучка",
}

_SCORE_RE = re.compile(r'multirating-itog-rateval[^>]*>\s*([0-9]+(?:[.,][0-9]+)?)')
_VOTES_RE = re.compile(r'multirating-itog-votes[^>]*>\s*\(?\s*([0-9\s]+)\s*\)?')
_COMPONENT_RE = re.compile(
    r'data-area="(?P<area>[a-z]+)"\s+title="(?P<label>[^"]+)"(?P<rest>.{0,400}?)'
    r'multirating-item-rateval-num">\s*(?P<value>[0-9]+(?:[.,][0-9]+)?)',
    re.S,
)
_H1_RE = re.compile(r"<h1[^>]*>(.{0,200}?)</h1>", re.S)
_SUB_RE = re.compile(r'class="amd-sub"[^>]*>([^<]{0,200})')
_LOC_RE = re.compile(r"<loc>([^<]+)</loc>")
_CAPTCHA_RE = re.compile(r"captcha|проверк[аи]\s+браузера|cf-challenge", re.I)
_FACET_RE = re.compile(r'href="https://amd\.online/anime/([a-z_]+)/([^"/]+)/"[^>]*>([^<]{0,60})</a>')


def _facets(html_text: str) -> dict[str, list[str]]:
    """Поля таксономии сайта: год, тип, жанры, сезон, студия.

    Берём видимый текст ссылки, а не её адрес: адрес транслитерирован и
    обрезан, а подпись — то, что сайт показывает читателю.
    """
    out: dict[str, list[str]] = {}
    for group, _slug, label in _FACET_RE.findall(html_text):
        value = html_mod.unescape(label).strip()
        if value and value not in out.setdefault(group, []):
            out[group].append(value)
    return out


def robots_allows(url: str) -> bool:
    """Разрешает ли robots.txt сайта обращаться по этому адресу."""
    if not url.startswith(ORIGIN):
        return False
    path = url[len(ORIGIN) :] or "/"
    return not any(p.search(path) for p in ROBOTS_DISALLOW_PATTERNS)


def _clean(text: str) -> str:
    return html_mod.unescape(re.sub(r"<[^>]+>", " ", text)).strip()


def _to_decimal_str(raw: str) -> str | None:
    text = (raw or "").strip().replace(",", ".")
    return text if re.fullmatch(r"[0-9]+(\.[0-9]+)?", text) else None


@dataclass
class AmdKillSwitch:
    """Отдельный выключатель источника. Гасится и вручную, и автоматически."""

    active: bool = False
    reason: str = ""

    def trip(self, reason: str) -> None:
        self.active = True
        self.reason = reason

    def check(self) -> None:
        if self.active:
            raise AdapterError("SOURCE_KILLED", self.reason, hard_circuit=True)


@dataclass
class AmdOnlineAdapter:
    source_key: str = SOURCE_KEY
    adapter_version: str = ADAPTER_VERSION
    min_interval: float = 1.0
    jitter: float = 0.4
    timeout: float = 25.0
    max_retries: int = 2
    user_agent: str = (
        "site-factory-unified-ratings/1.0 (ratings collection; 1 req/s; contact: operator)"
    )
    opener: Callable | None = None
    sleeper: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    kill_switch: AmdKillSwitch = field(default_factory=AmdKillSwitch)
    #: кэш в пределах запуска: одна страница не скачивается дважды
    cache: dict[str, str] = field(default_factory=dict)
    requests: int = 0
    retries: int = 0
    _last_request: float = 0.0

    # ------------------------------------------------------------------

    def capabilities(self) -> Capabilities:
        return Capabilities(
            source_key=SOURCE_KEY,
            supports_batch=False,
            max_batch_size=1,
            supports_vote_count=True,
            supports_user_count=False,
            supports_distribution=False,
            supports_source_side_incremental=False,
            incremental_mode=(
                "sitemap по lastmod + первая страница раздела онгоингов; "
                "пагинация раздела закрыта robots.txt и не обходится"
            ),
            external_id_space="amd_online_numeric_id из URL карточки",
            requires_credential=False,
        )

    # ------------------------------------------------------------------

    def _wait(self) -> None:
        elapsed = self.clock() - self._last_request
        delay = self.min_interval - elapsed
        delay += random.uniform(0, self.jitter)  # noqa: S311 — пауза, не криптография
        if delay > 0:
            self.sleeper(delay)
        self._last_request = self.clock()

    def fetch_page(self, url: str, *, use_cache: bool = True) -> str:
        self.kill_switch.check()
        if not robots_allows(url):
            raise AdapterError(
                "ROBOTS_DISALLOWED",
                f"robots.txt сайта закрывает {url}; обход запрещён",
                hard_circuit=False,
            )
        if use_cache and url in self.cache:
            return self.cache[url]

        attempt = 0
        while True:
            self._wait()
            self.requests += 1
            request = urllib.request.Request(
                url, headers={"User-Agent": self.user_agent, "Accept": "text/html,application/xml"}
            )
            open_fn = self.opener or (
                lambda r, timeout: urllib.request.urlopen(r, timeout=timeout)  # noqa: S310
            )
            try:
                with open_fn(request, self.timeout) as response:
                    body = response.read(2_000_000).decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429):
                    self.kill_switch.trip(f"HTTP {exc.code} от источника на {url}")
                    raise AdapterError(
                        "SOURCE_REFUSED", f"HTTP {exc.code}", hard_circuit=True
                    ) from exc
                if 500 <= exc.code < 600 and attempt < self.max_retries:
                    attempt += 1
                    self.retries += 1
                    self.sleeper(2**attempt)
                    continue
                if 500 <= exc.code < 600:
                    self.kill_switch.trip(f"повторяющиеся {exc.code} от источника")
                    raise AdapterError(
                        "UPSTREAM_5XX", f"HTTP {exc.code}", hard_circuit=True
                    ) from exc
                raise AdapterError("HTTP_ERROR", f"HTTP {exc.code}", retryable=False) from exc
            except (TimeoutError, urllib.error.URLError) as exc:
                attempt += 1
                if attempt > self.max_retries:
                    raise AdapterError("TIMEOUT", str(exc), retryable=False) from exc
                self.retries += 1
                self.sleeper(2**attempt)
                continue

            if _CAPTCHA_RE.search(body[:4000]):
                self.kill_switch.trip("страница похожа на проверку браузера/CAPTCHA")
                raise AdapterError("CAPTCHA_SUSPECTED", "источник просит проверку", hard_circuit=True)
            if use_cache:
                self.cache[url] = body
            return body

    # ------------------------------------------------------------------
    # перечисление
    # ------------------------------------------------------------------

    def discover_title_urls(self) -> list[str]:
        """Все страницы произведений из sitemap — путь, разрешённый robots."""
        xml = self.fetch_page(SITEMAP)
        urls = [u for u in _LOC_RE.findall(xml) if TITLE_URL_RE.match(u)]
        # Дубликаты в sitemap встречаются; порядок сохраняем.
        seen: set[str] = set()
        out: list[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                out.append(url)
        return out

    def discover_ongoing_urls(self) -> dict[str, Any]:
        """Онгоинги с первой страницы раздела.

        Остальные страницы раздела закрыты robots.txt. Что раздел ими не
        исчерпывается — факт, и он возвращается наружу, а не скрывается.
        """
        html_text = self.fetch_page(ONGOING_FIRST_PAGE)
        cards = []
        seen: set[str] = set()
        for url in re.findall(r'href="(https://amd\.online/\d+-[^"]+\.html)"', html_text):
            if url not in seen:
                seen.add(url)
                cards.append(url)
        pagination = sorted(set(re.findall(r'href="(https://amd\.online/ongoingi/page/\d+/)"', html_text)))
        max_page = 0
        for link in pagination:
            match = re.search(r"/page/(\d+)/", link)
            if match:
                max_page = max(max_page, int(match.group(1)))
        return {
            "first_page_urls": cards,
            "pagination_links_seen": len(pagination),
            "max_page_advertised": max_page,
            "pagination_fetched": False,
            "pagination_blocked_by": "robots.txt: Disallow */page/* и */page*",
            "enumeration_fallback": "sitemap news_pages.xml",
        }

    # ------------------------------------------------------------------
    # разбор
    # ------------------------------------------------------------------

    def parse_title(self, url: str, html_text: str) -> SourceFetch:
        match = TITLE_URL_RE.match(url)
        if match is None:
            raise AdapterError("INVALID_URL", f"не страница произведения: {url}", retryable=False)
        external_id = match.group("id")
        slug = match.group("slug")

        score_raw = None
        score_match = _SCORE_RE.search(html_text)
        if score_match:
            score_raw = _to_decimal_str(score_match.group(1))

        votes = None
        votes_match = _VOTES_RE.search(html_text)
        if votes_match:
            digits = re.sub(r"\s+", "", votes_match.group(1))
            if digits.isdigit():
                votes = int(digits)

        components: dict[str, Any] = {}
        for comp in _COMPONENT_RE.finditer(html_text):
            area = comp.group("area")
            label = comp.group("label").strip()
            # Берём только те области, подпись которых совпадает с
            # объявленной. Число без своей подписи остаётся неизвестной
            # метрикой и в оценку не идёт.
            if COMPONENT_LABELS.get(area) != label:
                continue
            value = _to_decimal_str(comp.group("value"))
            if value is not None:
                components[area] = {"label": label, "raw": value}

        h1 = _H1_RE.search(html_text)
        title_ru = _clean(h1.group(1)) if h1 else ""
        sub = _SUB_RE.search(html_text)
        title_original = _clean(sub.group(1)) if sub else ""

        # Год, тип, жанры и сезон сайт публикует ссылками таксономии
        # (/anime/god/2023/, /anime/tip/ona/ …). Это подписанные поля, а
        # не числа, выловленные из текста: год из заголовка «Клан Тан 2»
        # угадывался бы, а отсюда он прочитан.
        facets = _facets(html_text)
        year_value = None
        for candidate in facets.get("god", []):
            if re.fullmatch(r"(19[3-9]\d|20[0-5]\d)", candidate):
                year_value = int(candidate)
                break
        kind = (facets.get("tip") or [""])[0]
        is_ongoing = bool(re.search(r"онгоинг", html_text, re.I))

        if not title_ru and score_raw is None:
            # Ни заголовка, ни рейтинга — разметка изменилась.
            self.kill_switch.trip(f"разметка страницы не распознана: {url}")
            raise AdapterError("DOM_DRIFT", f"не разобрана страница {url}", hard_circuit=True)

        payload = {
            "url": url,
            "slug": slug,
            "title_ru": title_ru,
            "title_original": title_original,
            "score_raw": score_raw,
            "votes_raw": votes,
            "components": components,
            "is_ongoing": is_ongoing,
            "year": year_value,
            "kind": kind,
            "genres": facets.get("ghanr", []),
            "season": (facets.get("sezon_goda") or [""])[0],
            "studio": (facets.get("stydiya") or [""])[0],
            "parser_version": ADAPTER_VERSION,
            "html_sha256": hashlib.sha256(html_text.encode("utf-8")).hexdigest(),
            "access_method": "PUBLIC_HTML",
        }
        return SourceFetch(
            source_key=SOURCE_KEY,
            external_id=external_id,
            found=score_raw is not None,
            raw_score=score_raw,
            vote_count=votes,
            crosswalk_ids={},
            source_rating_date="",
            provenance_url=url,
            titles={"ru": title_ru, "original": title_original},
            year=year_value,
            kind=kind,
            raw_payload=payload,
        )

    def fetch_by_external_ids(self, external_ids: list[str]) -> dict[str, SourceFetch]:
        """Здесь идентификатор — полный URL карточки."""
        out: dict[str, SourceFetch] = {}
        for url in external_ids:
            try:
                out[url] = self.parse_title(url, self.fetch_page(url))
            except AdapterError as exc:
                if exc.hard_circuit:
                    raise
                out[url] = SourceFetch(
                    source_key=SOURCE_KEY, external_id=url, found=False, error=f"{exc.code}"
                )
        return out

    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        if self.kill_switch.active:
            return {
                "source_key": SOURCE_KEY,
                "state": HealthState.BLOCKED,
                "reason": self.kill_switch.reason,
            }
        return {
            "source_key": SOURCE_KEY,
            "state": HealthState.HEALTHY,
            "access_method": "PUBLIC_HTML",
            "robots_respected": True,
            "pagination_blocked": "Disallow */page/*",
            "requests": self.requests,
            "retries": self.retries,
        }
