"""Аудит одной страницы по её HTML: только измерения и названные находки.

Что проверяется и почему именно это:

* title, H1, meta description — то, что поисковик показывает в выдаче и по
  чему посетитель решает, кликать ли. Шаблонная meta вида «Название: Аниме
  2023» (animedia.icu до 2026-10-08) ничего не сообщает о странице;
* canonical — должен указывать на саму страницу; чужой или пустой canonical
  отдаёт вес другому адресу;
* meta robots — noindex на странице, которую мы хотим видеть в поиске;
* заглушка вместо текста — «Описание пока не передано источником»;
* объём видимого текста основного блока и число внутренних ссылок — пустая
  страница без навигации не отвечает на запрос и не ведёт дальше.

Оценок «хорошо/плохо» модуль не ставит: находка — это измеренное отклонение
с порогом, записанным в коде. Ни одного прогноза позиций.
"""

from __future__ import annotations

import html as _html
import re
from urllib.parse import urljoin, urlsplit

PLACEHOLDERS = ("описание пока не передано", "описание отсутствует", "lorem ipsum")
#: Порог «содержательной» meta description: короче — это название с годом.
META_MIN = 70
TITLE_MAX = 70
INTERNAL_LINKS_MIN = 5


def _first(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return _html.unescape(m.group(1)).strip() if m else None


def _visible(text: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def _norm(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc.lower()}{parts.path or '/'}"


def audit(html_text: str, url: str) -> dict:
    """Измерения и находки одной страницы."""
    host = urlsplit(url).netloc.lower()
    title = _first(r"<title[^>]*>(.*?)</title>", html_text)
    h1s = [_visible(h) for h in re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", html_text)]
    meta = _first(
        r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html_text
    )
    robots = _first(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']*)["\']', html_text)
    canonical = _first(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html_text)
    main = _first(r"(?is)<main[^>]*>(.*?)</main>", html_text)
    # Потоковая отрисовка (React, Yummy): в <main> только <template>, а текст
    # приходит ниже в том же HTML. Считать такой <main> пустым — ложная тревога
    # (так и было на первом прогоне 2026-10-08), поэтому берётся вся страница.
    streamed = main is not None and not _visible(main)
    visible = _visible(html_text if (main is None or streamed) else main)
    links = set()
    for href in re.findall(r'(?i)<a[^>]+href=["\']([^"\'#]+)', html_text):
        absolute = urljoin(url, href)
        if urlsplit(absolute).netloc.lower() == host and absolute.rstrip("/") != url.rstrip("/"):
            links.add(_norm(absolute))
    out = {
        "url": url,
        "title": title,
        "h1": h1s,
        "meta_description": meta,
        "meta_robots": robots,
        "canonical": canonical,
        "words_main": len(re.findall(r"\w+", visible)),
        "internal_links": len(links),
        "main_streamed": streamed,
        "findings": [],
    }
    f = out["findings"]

    def add(code: str, detail: str, severity: str = "warning") -> None:
        f.append({"code": code, "severity": severity, "detail": detail})

    if not title:
        add("TITLE_MISSING", "нет <title>")
    elif len(title) > TITLE_MAX:
        add("TITLE_LONG", f"title {len(title)} знаков (> {TITLE_MAX}) — в выдаче обрежется", "info")
    if not h1s:
        add("H1_MISSING", "нет H1")
    elif len(h1s) > 1:
        add("H1_MULTIPLE", f"H1 на странице: {len(h1s)}", "info")
    if not meta:
        add("META_MISSING", "нет meta description")
    elif len(meta) < META_MIN:
        add("META_THIN", f"meta description {len(meta)} знаков: «{meta}»")
    if robots and "noindex" in robots.lower():
        add("PAGE_NOINDEX", f"meta robots = {robots}", "critical")
    if not canonical:
        add("CANONICAL_MISSING", "нет rel=canonical")
    elif _norm(urljoin(url, canonical)).rstrip("/") != _norm(url).rstrip("/"):
        add("CANONICAL_OTHER", f"canonical указывает на {canonical}", "critical")
    low = visible.lower()
    for marker in PLACEHOLDERS:
        if marker in low:
            add("PLACEHOLDER_TEXT", f"в основном блоке заглушка «{marker}»")
            break
    if not any(word in low for word in ("описание", "сюжет")) and out["words_main"] < 120:
        add(
            "NO_DESCRIPTION",
            f"описания на странице нет, видимого текста {out['words_main']} слов",
            "info",
        )
    if len(links) < INTERNAL_LINKS_MIN:
        add("FEW_INTERNAL_LINKS", f"внутренних ссылок {len(links)} (< {INTERNAL_LINKS_MIN})")
    return out


def duplicate_titles(audits: list[dict]) -> list[dict]:
    """Один title у разных адресов одного домена — страницы конкурируют в выдаче."""
    seen: dict[tuple[str, str], list[str]] = {}
    for a in audits:
        if a.get("title"):
            seen.setdefault((urlsplit(a["url"]).netloc, a["title"]), []).append(a["url"])
    return [{"domain": d, "title": t, "urls": u} for (d, t), u in seen.items() if len(u) > 1]
