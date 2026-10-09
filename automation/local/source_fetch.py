"""Чтение редакционных источников фактов — только разрешённым путём (D199).

    python3 automation/local/source_fetch.py shikimori <shikimori_id>
    python3 automation/local/source_fetch.py credits <shikimori_id>
    python3 automation/local/source_fetch.py official <shikimori_id>
    python3 automation/local/source_fetch.py film <imdb> <название> <оригинальное> <год> <movie|tv>
    python3 automation/local/source_fetch.py wikidata <QID>
    python3 automation/local/source_fetch.py page <url>

* `shikimori` — карточка и официальные ссылки через API Shikimori (shikimori.io,
  своё имя приложения в User-Agent, не чаще 4 запросов в секунду). ID берётся
  из каталога сети (`ratings_by_source.shikimori.external_id`), не из поиска.
* `official` — ОДНА страница официального сайта: адрес берётся только из
  `external_links` Shikimori того же ID с kind `official_site`; перед чтением
  проверяется robots.txt этого сайта для нашего User-Agent и для ИИ-агентов
  (`ClaudeBot`, `anthropic-ai`). Запрет — отказ, а не обход.
* `film` — фильмы и сериалы (решение владельца 2026-10-09, D200): статья
  Википедии ru/en по детерминированным вариантам названия из каталога, без
  поиска (API и поиск Википедии закрыты robots.txt для всех агентов, открыты
  только страницы `/wiki/<название>`). Идентичность — совпадение IMDb ID статьи
  с каталогом; иначе статья не принимается. Википедия — дополнительный источник.
* `wikidata` — HTML-страница элемента `www.wikidata.org/wiki/Q…` (API и SPARQL
  закрыты robots.txt): официальный сайт (P856), IMDb (P345), Кинопоиск (P2603).
* `page` — одна страница официального сайта или правообладателя с проверкой
  robots.txt; сюжет фильма/сериала сверяется по ней.
* MyAnimeList не читается: его robots.txt запрещает ИИ-агентам весь сайт
  (проверено 2026-10-08), а API требует client id, которого нет.

Каждое обращение пишется в var/editor-runs/sources.jsonl. Вывод — JSON с
фактами и адресом; тексты источников редактор пересказывает, а не копирует.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from pathlib import Path
from urllib.parse import quote, urlsplit

USER_AGENT = "site-factory-editor/1 (editorial fact check)"
SHIKIMORI = "https://shikimori.io"
AI_AGENTS = ("ClaudeBot", "anthropic-ai", "Claude-Web")
LOG = Path(__file__).resolve().parents[2] / "var" / "editor-runs" / "sources.jsonl"
_last = [0.0]


def _log(**fields) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields},
                ensure_ascii=False,
            )
            + "\n"
        )


def _get(url: str, timeout: int = 20) -> tuple[int | None, bytes]:
    pause = 0.25 - (time.monotonic() - _last[0])
    if pause > 0:
        time.sleep(pause)
    _last[0] = time.monotonic()
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(3_000_000)
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except (urllib.error.URLError, OSError) as exc:
        _log(url=url, error=f"{type(exc).__name__}: {exc}")
        return None, b""


def shikimori(anime_id: int) -> dict:
    status, raw = _get(f"{SHIKIMORI}/api/animes/{anime_id}")
    _log(source="src-shikimori", url=f"{SHIKIMORI}/api/animes/{anime_id}", status=status)
    if status != 200:
        return {"ok": False, "status": status}
    d = json.loads(raw)
    s2, raw2 = _get(f"{SHIKIMORI}/api/animes/{anime_id}/external_links")
    _log(source="src-shikimori", url=f"{SHIKIMORI}/api/animes/{anime_id}/external_links", status=s2)
    links = json.loads(raw2) if s2 == 200 else []
    desc = re.sub(r"\[[^\]]+\]", "", d.get("description") or "").strip()
    return {
        "ok": True,
        "source_id": "src-shikimori",
        "url": f"{SHIKIMORI}/animes/{anime_id}",
        "russian": d.get("russian"),
        "name": d.get("name"),
        "kind": d.get("kind"),
        "status": d.get("status"),
        "episodes": d.get("episodes"),
        "episodes_aired": d.get("episodes_aired"),
        "aired_on": d.get("aired_on"),
        "released_on": d.get("released_on"),
        "description": desc or None,
        "english": d.get("english"),
        "japanese": d.get("japanese"),
        "synonyms": d.get("synonyms"),
        "license_name_ru": d.get("license_name_ru"),
        "studios": [x.get("name") for x in d.get("studios") or []],
        "official_links": [x.get("url") for x in links if x.get("kind") == "official_site"],
    }


def _api(path: str):
    status, raw = _get(f"{SHIKIMORI}/api/{path}")
    _log(source="src-shikimori", url=f"{SHIKIMORI}/api/{path}", status=status)
    return json.loads(raw) if status == 200 else None


def credits(anime_id: int) -> dict:
    """Кто автор оригинала и где он выходил: роли и связанная манга того же ID."""
    info = shikimori(anime_id)
    if not info.get("ok"):
        return info
    roles = _api(f"animes/{anime_id}/roles") or []
    creators = [
        {
            "person": (r.get("person") or {}).get("name"),
            "person_ru": (r.get("person") or {}).get("russian"),
            "roles": r.get("roles"),
        }
        for r in roles
        if r.get("person") and any("Original" in x for x in r.get("roles") or [])
    ]
    sources = []
    for rel in _api(f"animes/{anime_id}/related") or []:
        manga = rel.get("manga")
        if not manga or rel.get("relation_russian") != "Адаптация":
            continue
        m = _api(f"mangas/{manga['id']}") or {}
        sources.append(
            {
                "manga_id": manga["id"],
                "kind": manga.get("kind"),
                "russian": manga.get("russian"),
                "name": manga.get("name"),
                "status": m.get("status"),
                "publishers": [p.get("name") for p in m.get("publishers") or []],
                "url": f"{SHIKIMORI}/mangas/{manga['id']}",
            }
        )
    return {**info, "original_creators": creators, "adapted_from": sources}


def _robots_allows(url: str) -> tuple[bool, str]:
    parts = urlsplit(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    status, raw = _get(robots)
    if status == 404:
        return True, "robots.txt нет"
    if status != 200:
        return False, f"robots.txt не прочитан ({status}) — без него не читаем"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(raw.decode("utf-8", "replace").splitlines())
    for agent in (USER_AGENT, *AI_AGENTS):
        if not rp.can_fetch(agent, url):
            return False, f"robots.txt запрещает {agent}"
    return True, "robots.txt разрешает"


def official(anime_id: int) -> dict:
    info = shikimori(anime_id)
    links = info.get("official_links") or []
    if not links:
        return {"ok": False, "reason": "у Shikimori нет официальной ссылки для этого ID"}
    url = links[0]
    allowed, why = _robots_allows(url)
    _log(source="src-official-site", url=url, robots=why, shikimori_id=anime_id)
    if not allowed:
        return {"ok": False, "url": url, "reason": why}
    status, raw = _get(url)
    _log(source="src-official-site", url=url, status=status)
    text = raw.decode("utf-8", "replace")
    meta = re.findall(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']+)',
        text,
    )
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
    return {
        "ok": status == 200,
        "source_id": "src-official-site",
        "url": url,
        "status": status,
        "title": html.unescape(title.group(1)).strip() if title else None,
        "descriptions": [html.unescape(m) for m in meta][:3],
        "robots": why,
    }


def _text(fragment: str) -> str:
    t = re.sub(r"<(script|style|sup)[^>]*>.*?</\1>", " ", fragment, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def _allowed_get(url: str, source_id: str) -> tuple[int | None, str, str]:
    allowed, why = _robots_allows(url)
    if not allowed:
        _log(source=source_id, url=url, robots=why)
        return None, "", why
    status, raw = _get(url)
    _log(source=source_id, url=url, status=status)
    return status, raw.decode("utf-8", "replace"), why


def _wiki_article(lang: str, title: str) -> tuple[int | None, str, str]:
    url = f"https://{lang}.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="():,_")
    status, text, why = _allowed_get(url, "src-wikipedia")
    return status, text, url


def _section(page: str, names: tuple[str, ...]) -> str:
    """Текст раздела статьи (до следующего заголовка того же уровня)."""
    for name in names:
        m = re.search(
            r'<h2[^>]*id="'
            + re.escape(name)
            + r'"[^>]*>.*?</h2>(.*?)(?=<div class="mw-heading mw-heading2|<h2)',
            page,
            re.S,
        )
        if m:
            return _text(m.group(1))[:4000]
    return ""


def film(imdb: str, name: str, original: str, year: str, kind: str) -> dict:
    """Статья о фильме/сериале с подтверждённой идентичностью по IMDb ID."""
    imdb = imdb.removeprefix("tt")
    ru_suffix = (
        ["", " (телесериал)", " (сериал)", f" (телесериал, {year})"]
        if kind == "tv"
        else ["", " (фильм)", f" (фильм, {year})"]
    )
    en_suffix = (
        ["", " (TV series)", f" ({year} TV series)"]
        if kind == "tv"
        else ["", " (film)", f" ({year} film)"]
    )
    tried = []
    for lang, base, suffixes in (("ru", name, ru_suffix), ("en", original, en_suffix)):
        if not base:
            continue
        for suf in suffixes:
            status, page, where = _wiki_article(lang, base + suf)
            tried.append({"url": where, "status": status})
            if status != 200:
                continue
            if f"tt{imdb}" not in page and f"/title/tt{imdb}" not in page:
                continue
            qid = re.search(r"wikidata\.org/wiki/(?:Special:EntityPage/)?(Q\d+)", page)
            lead = re.search(
                r'<div class="mw-content-ltr mw-parser-output"[^>]*>.*?<p>(.*?)</p>', page, re.S
            )
            plot = _section(page, ("Сюжет", "Синопсис", "Plot", "Premise", "Synopsis"))
            return {
                "ok": True,
                "source_id": "src-wikipedia",
                "url": where,
                "identity": f"IMDb tt{imdb} найден в статье",
                "wikidata": qid.group(1) if qid else None,
                "lead": _text(lead.group(1))[:1500] if lead else None,
                "plot": plot or None,
                "tried": tried,
            }
    return {"ok": False, "reason": f"статьи с IMDb tt{imdb} среди вариантов нет", "tried": tried}


def wikidata(qid: str) -> dict:
    url = f"https://www.wikidata.org/wiki/{qid}"
    status, page, why = _allowed_get(url, "src-wikidata")
    if status != 200:
        return {"ok": False, "url": url, "status": status, "reason": why}

    def prop(pid: str) -> list[str]:
        m = re.search(
            r'id="' + pid + r'".*?(?=<div class="wikibase-statementgroupview |$)', page, re.S
        )
        if not m:
            return []
        block = m.group(0)
        links = re.findall(r'class="external free"[^>]*href="([^"]+)"', block)
        if links:
            return list(dict.fromkeys(links))
        return list(
            dict.fromkeys(
                _text(x)
                for x in re.findall(
                    r'<div class="wikibase-snakview-value[^"]*"[^>]*>(.*?)</div>', block, re.S
                )
                if _text(x)
            )
        )

    return {
        "ok": True,
        "source_id": "src-wikidata",
        "url": url,
        "official_site": prop("P856"),
        "imdb": prop("P345")[:1],
        "kinopoisk": prop("P2603")[:1],
    }


def page(url: str) -> dict:
    status, text, why = _allowed_get(url, "src-official-site")
    if status != 200:
        return {"ok": False, "url": url, "status": status, "reason": why}
    meta = re.findall(
        r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']+)',
        text,
    )
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
    main = re.search(r"<main.*?</main>", text, re.S)
    return {
        "ok": True,
        "source_id": "src-official-site",
        "url": url,
        "robots": why,
        "title": html.unescape(title.group(1)).strip() if title else None,
        "descriptions": [html.unescape(m) for m in meta][:3],
        "text": _text(main.group(0) if main else text)[:4000],
    }


def main(argv: list[str]) -> int:
    commands = {"shikimori": shikimori, "credits": credits, "official": official}
    if argv and argv[0] == "film" and len(argv) == 6:
        result = film(*argv[1:])
    elif argv and argv[0] == "wikidata" and len(argv) == 2:
        result = wikidata(argv[1])
    elif argv and argv[0] == "page" and len(argv) == 2:
        result = page(argv[1])
    elif len(argv) == 2 and argv[0] in commands:
        result = commands[argv[0]](int(argv[1]))
    else:
        print(__doc__)
        return 64
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
