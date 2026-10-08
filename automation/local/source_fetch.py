"""Чтение редакционных источников фактов — только разрешённым путём (D199).

    python3 automation/local/source_fetch.py shikimori <shikimori_id>
    python3 automation/local/source_fetch.py official <shikimori_id>

* `shikimori` — карточка и официальные ссылки через API Shikimori (shikimori.io,
  своё имя приложения в User-Agent, не чаще 4 запросов в секунду). ID берётся
  из каталога сети (`ratings_by_source.shikimori.external_id`), не из поиска.
* `official` — ОДНА страница официального сайта: адрес берётся только из
  `external_links` Shikimori того же ID с kind `official_site`; перед чтением
  проверяется robots.txt этого сайта для нашего User-Agent и для ИИ-агентов
  (`ClaudeBot`, `anthropic-ai`). Запрет — отказ, а не обход.
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
from urllib.parse import urlsplit

USER_AGENT = "site-factory-editor/1 (editorial fact check)"
SHIKIMORI = "https://shikimori.io"
AI_AGENTS = ("ClaudeBot", "anthropic-ai", "Claude-Web")
LOG = Path(__file__).resolve().parents[2] / "var" / "editor-runs" / "sources.jsonl"
_last = [0.0]


def _log(**fields) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **fields},
                            ensure_ascii=False) + "\n")


def _get(url: str, timeout: int = 20) -> tuple[int | None, bytes]:
    pause = 0.25 - (time.monotonic() - _last[0])
    if pause > 0:
        time.sleep(pause)
    _last[0] = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html"})
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
    return {"ok": True, "source_id": "src-shikimori", "url": f"{SHIKIMORI}/animes/{anime_id}",
            "russian": d.get("russian"), "name": d.get("name"), "kind": d.get("kind"),
            "status": d.get("status"), "episodes": d.get("episodes"),
            "episodes_aired": d.get("episodes_aired"), "aired_on": d.get("aired_on"),
            "released_on": d.get("released_on"), "description": desc or None,
            "official_links": [x.get("url") for x in links if x.get("kind") == "official_site"]}


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
    meta = re.findall(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']+)', text)
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S)
    return {"ok": status == 200, "source_id": "src-official-site", "url": url, "status": status,
            "title": html.unescape(title.group(1)).strip() if title else None,
            "descriptions": [html.unescape(m) for m in meta][:3], "robots": why}


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] not in ("shikimori", "official"):
        print(__doc__)
        return 64
    result = (shikimori if argv[0] == "shikimori" else official)(int(argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("ok") else 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
