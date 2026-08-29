"""Проверки SEO-разметки страницы против фактов источника.

Проверяется не «плотность ключей», а правдивость: совпадает ли то, что
напечатано на странице, с тем, что сказал поставщик. Длина заголовка и описания
считается предупреждением, а не отказом — короткий честный заголовок лучше
длинного, набитого словами.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field

# Разделителем бывает не только дефис: в заголовке стояло «Lords General»
# через пробел, и первая версия правила его пропускала.
TECHNICAL_NAMES = re.compile(
    r"\blords[-_\s]?(?:\d+|general|new|curated|genre)\b", re.I)
PLACEHOLDERS = ("lorem ipsum", "n/a", "нет данных", "undefined", "null", "TBD", "NR")
#: Значения, которые нельзя показывать как факт.
BAD_VALUES = re.compile(r"(?:^|[\s:>])(?:null|undefined|NaN|None|NR)(?:$|[\s<,.])", re.I)

TITLE_SOFT_MAX = 65
DESCRIPTION_SOFT_MIN = 70
DESCRIPTION_SOFT_MAX = 180


@dataclass
class Finding:
    check: str
    ok: bool
    detail: str = ""
    severity: str = "error"   # error | warning


@dataclass
class PageUnderTest:
    """Отрендеренная страница вместе с фактами, из которых она собрана."""

    path: str
    html: str
    domain: str
    indexable: bool = True
    facts: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)


def _tag(html: str, name: str) -> list[str]:
    return re.findall(rf"<{name}[^>]*>(.*?)</{name}>", html, re.S | re.I)


def _meta(html: str, attr: str, value: str) -> str | None:
    m = re.search(rf'<meta[^>]*{attr}=["\']{re.escape(value)}["\'][^>]*content=["\'](.*?)["\']',
                  html, re.I | re.S)
    if m:
        return m.group(1)
    m = re.search(rf'<meta[^>]*content=["\'](.*?)["\'][^>]*{attr}=["\']{re.escape(value)}["\']',
                  html, re.I | re.S)
    return m.group(1) if m else None


def _strip(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", text)


def _jsonld(html: str) -> list:
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I)
    out = []
    for raw in blocks:
        try:
            out.append(json.loads(raw))
        except ValueError:
            out.append(None)
    return out


def check_page(page: PageUnderTest) -> list[Finding]:
    """Все проверки одной страницы. Возвращает и успехи, и провалы."""
    html, found = page.html, []
    titles = _tag(html, "title")
    title = titles[0].strip() if titles else ""
    description = (_meta(html, "name", "description") or "").strip()
    h1s = _tag(html, "h1")
    text = _strip(html)

    # SEO-001 — заголовок есть и не содержит внутреннего имени сборки.
    found.append(Finding("SEO-001", bool(title) and not TECHNICAL_NAMES.search(title),
                         f"title={title!r}"))
    # SEO-005 — ровно один видимый H1.
    found.append(Finding("SEO-005", len(h1s) == 1, f"h1 найдено: {len(h1s)}"))
    # SEO-003 — у индексируемой страницы есть осмысленное описание.
    if page.indexable:
        found.append(Finding("SEO-003", len(description) >= 40,
                             f"description длиной {len(description)}"))
        if not (DESCRIPTION_SOFT_MIN <= len(description) <= DESCRIPTION_SOFT_MAX):
            found.append(Finding("SEO-003-len", False,
                                 f"длина описания {len(description)} вне рекомендуемой",
                                 severity="warning"))
    # SEO-008 — ни заглушек, ни сырых значений.
    lowered = text.lower()
    bad = [p for p in PLACEHOLDERS if p.lower() in lowered]
    found.append(Finding("SEO-008", not bad and not BAD_VALUES.search(text),
                         f"найдено: {bad}" if bad else ""))
    # SEO-009 — у каждой оценки есть подпись источника.
    numbers = re.findall(r'class="rating__value"[^>]*>([\d.]+)<', html)
    sources = re.findall(r'class="rating__source"[^>]*>([^<]+)<', html)
    found.append(Finding("SEO-009", len(numbers) == len(sources),
                         f"чисел {len(numbers)}, подписей {len(sources)}"))
    # SEO-010 — canonical ведёт на собственный домен и на этот же адрес.
    canonical = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\'](.*?)["\']', html, re.I)
    href = canonical.group(1) if canonical else ""
    # Хост сравнивается целиком, а не вхождением подстроки: «example.test»
    # содержится в «example.test.attacker.tld». Путь — тоже целиком: «/arhiv/a/»
    # заканчивается на «/a/», но это другая страница.
    canonical_parts = urllib.parse.urlparse(href) if href else None
    canonical_ok = bool(
        canonical_parts
        and canonical_parts.netloc.lower() == page.domain.lower()
        and (canonical_parts.path or "/") == page.path
    )
    found.append(Finding("SEO-010", canonical_ok, f"canonical={href!r}"))
    # SEO-013 — у постера осмысленный alt.
    alts = re.findall(r'<img[^>]*alt=["\'](.*?)["\']', html, re.I)
    meaningful = [a for a in alts if a.strip()]
    found.append(Finding("SEO-013", len(alts) == 0 or bool(meaningful) or all(a == "" for a in alts),
                         f"alt: {len(meaningful)} осмысленных из {len(alts)}",
                         severity="warning" if not meaningful else "error"))
    # SEO-014 — внутренние ссылки пригодны для обхода.
    links = re.findall(r'<a[^>]*href=["\'](/[^"\']*)["\']', html)
    broken = [href for href in links if " " in href or href.startswith("//")]
    found.append(Finding("SEO-014", not broken, f"негодные ссылки: {broken[:3]}"))
    # SEO-017 — без набивки ключами.
    #
    # Считается повтор ВНУТРИ описания, а не по связке «заголовок + описание +
    # H1». Две прошлые версии ошибались по-разному: первая объявляла набивкой
    # список серий, где «Серия 1 … Серия 24» повторяется по устройству
    # страницы; вторая — название фильма, которое обязано стоять и в
    # заголовке, и в описании, и в H1 по одному разу. Ни то, ни другое
    # набивкой не является.
    #
    # Слишком короткий текст не оценивается вовсе: на семи словах доля любого
    # из них скачет так, что мерить нечего.
    prose_words = re.findall(r"[а-яёa-z]{4,}", description.lower())
    if len(prose_words) >= 12:
        top = max(set(prose_words), key=prose_words.count)
        share = prose_words.count(top) / len(prose_words)
        found.append(Finding("SEO-017", share < 0.25,
                             f"в описании слово {top!r} занимает {share:.1%}"))
    # SEO-006 / SEO-007 — напечатанные факты совпадают с источником.
    for key in ("year", "country", "genre", "season"):
        value = page.facts.get(key)
        if value:
            found.append(Finding("SEO-006", str(value) in text,
                                 f"{key}={value!r} нет в тексте страницы"))
    for claim in page.facts.get("forbidden_claims", ()):
        found.append(Finding("SEO-007", claim.lower() not in lowered,
                             f"неподтверждённое утверждение: {claim!r}"))
    # SEO-018 — у синопсиса есть происхождение и отпечаток.
    if page.provenance:
        prov = page.provenance
        found.append(Finding("SEO-018", bool(prov.get("source")) and bool(prov.get("content_hash")),
                             f"provenance={prov.get('source')!r}"))
    # SEO-020 — JSON-LD не противоречит видимым фактам.
    for block in _jsonld(html):
        if not isinstance(block, dict):
            continue
        name = block.get("name")
        if isinstance(name, str) and name.strip():
            found.append(Finding("SEO-020", name.strip() in text or name.strip() in title,
                                 f"JSON-LD name={name!r} не встречается на странице"))
    return found


def failures(found) -> list[Finding]:
    return [f for f in found if not f.ok and f.severity == "error"]


def warnings(found) -> list[Finding]:
    return [f for f in found if not f.ok and f.severity == "warning"]


def check_corpus(pages) -> list[Finding]:
    """Проверки, которые имеют смысл только на наборе страниц."""
    found = []
    by_domain: dict = {}
    for page in pages:
        by_domain.setdefault(page.domain, []).append(page)

    for domain, group in by_domain.items():
        titles = [(_tag(p.html, "title") or [""])[0].strip() for p in group]
        # SEO-002 — заголовок уникален внутри домена.
        duplicates = {t for t in titles if titles.count(t) > 1 and t}
        found.append(Finding("SEO-002", not duplicates, f"{domain}: повторы {list(duplicates)[:3]}"))
        # SEO-004 — описания не повторяются дословно.
        descriptions = [(_meta(p.html, "name", "description") or "").strip()
                        for p in group if p.indexable]
        descriptions = [d for d in descriptions if d]
        dupes = {d for d in descriptions if descriptions.count(d) > 1}
        found.append(Finding("SEO-004", not dupes, f"{domain}: одинаковых описаний {len(dupes)}"))

    # SEO-011 — разные домены не отдают одинаковый SEO-блок.
    if len(by_domain) > 1:
        signatures = {}
        for domain, group in by_domain.items():
            home = next((p for p in group if p.path == "/"), None)
            if home is not None:
                signatures[domain] = ((_tag(home.html, "title") or [""])[0].strip(),
                                      (_meta(home.html, "name", "description") or "").strip())
        found.append(Finding("SEO-011", len(set(signatures.values())) == len(signatures),
                             f"совпадающие блоки: {len(signatures) - len(set(signatures.values()))}"))
    return found
