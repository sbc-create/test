"""Пополнение очереди технического SEO без сообщения владельца (B006, 14.10).

Пустая очередь не означает «ждать задания». Источники, все без модели:

* **диагностика регулярной проверки** — `var/seo-regular/state.json`, открытые
  находки (`open_issues_check`, `open_issues_daily`) с кодами, которые чинятся в
  коде витрины (TECH_CODES). Находки инфраструктуры, счётчиков и данных — не
  задачи сессии (их ведёт Архитектор или владелец) и сюда не попадают;
* **аудит внутренних ссылок** (раз в сутки) — главная и /catalog/ продвигаемых
  витрин: внутренняя ссылка, отвечающая 3xx/4xx/5xx, — задача. Намеренные
  переходы (/random/, поиск, вид выдачи) пропускаются;
* **переносы** — задача с полем `port_to`, выпущенная хотя бы на одном сайте,
  порождает задачи для перечисленных сайтов того же семейства;
* **незавершённые** — задача, исчерпавшая попытки, не возвращается в очередь, а
  попадает в `attention.json`: это работа сессии, а не повтор вслепую.

Задачи пишутся в `var/seo-tech/auto-tasks.json` (служба не правит отслеживаемый
config/), id — `A0001…`; `tech_run.load_queue` читает их вместе с очередью.
Повтор находки не порождает вторую задачу: у каждой — подпись `source`.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from seo_operator import tech_run

REPO = tech_run.REPO
REGULAR_STATE = REPO / "var" / "seo-regular" / "state.json"
CELLS = REPO / "config" / "site-cells.json"

#: Коды регулярной проверки, которые чинятся в коде витрины → шаблон задачи.
TECH_CODES: dict[str, dict[str, str]] = {
    "ROBOTS_WITHOUT_SITEMAP": {
        "norm": "открытая витрина объявляет карту сайта в robots.txt (Sitemap: https://<домен>/sitemap.xml)",
        "expected": "в открытом режиме robots.txt содержит строку Sitemap на свою карту",
    },
    "SITEMAP_SLOW": {
        "norm": "карта сайта отвечает быстрее предела прокси и обходчика (ориентир — 5 с)",
        "expected": "карта и её части отдаются из готового файла или кеша, без синхронной сборки в запросе",
    },
    "SITEMAP_LASTMOD_OLD": {
        "norm": "lastmod карты отражает фактическое изменение страниц",
        "expected": "карта пересобирается при смене снимка; lastmod не старше недели у обновляемых разделов",
    },
    "CANONICAL_FOREIGN_HOST": {
        "norm": "canonical страницы указывает на свой домен",
        "expected": "canonical главной и разделов — https://<свой домен>/…",
    },
    "HOME_SLOW": {
        "norm": "главная отвечает быстро (ориентир — до 1 с из кеша)",
        "expected": "главная отдаётся из кеша снимка; холодный ответ не превышает предела прокси",
    },
}

#: Внутренние переходы, которые 3xx по замыслу, — не дефект ссылки.
НАМЕРЕННЫЕ = (re.compile(r"^/random/?"), re.compile(r"^/search"), re.compile(r"[?&]view="),
              re.compile(r"^/catalog/random"), re.compile(r"^/login|^/logout|^/lists/?"))


def _сейчас() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(m: dt.datetime) -> str:
    return m.strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def promoted_cells(cells_path: Path = CELLS) -> dict[str, dict[str, str]]:
    """Продвигаемые витрины: домен → {repo, direction, site_id}. Восемь новых — вне."""
    from seo_operator import editor_run

    данные = _read_json(cells_path, {})
    ячейки = данные.get("cells", данные) if isinstance(данные, dict) else данные
    ячейки = ячейки if isinstance(ячейки, list) else list(ячейки.values())
    итог = {}
    for c in ячейки:
        домен = c.get("domain") or ""
        путь = ((c.get("repo") or {}).get("path") or "") if isinstance(c.get("repo"), dict) else ""
        # not_extracted — запись реестра отстала (lords-02/03 работают из ячеек, выпуски 14.10);
        # решает наличие репозитория витрины. Восемь новых доменов отсекаются ниже по списку.
        if not домен or not путь or c.get("status") not in (None, "live", "active", "not_extracted"):
            continue
        if not (REPO / путь).is_dir():
            continue
        # Yummy: код страниц — в контейнере Next.js, вне var/site-repos и вне cell trigger
        # (B016, T081) — задачи туда ставить нельзя: правка легла бы не в тот репозиторий.
        if домен.startswith("yummyani"):
            continue
        if домен in tech_run.ВНЕ_ПРОДВИЖЕНИЯ or tech_run.вне_продвижения({"site": домен, "repo": путь}):
            continue
        направление = editor_run.направление_домена(домен) or ("zona" if "zona" in домен else "network")
        итог[домен] = {"repo": путь, "direction": направление, "site_id": c.get("site_id") or ""}
    return итог


def _подпись(*части: str) -> str:
    return "auto:" + ":".join(части)


def from_regular(state_path: Path, cells: dict[str, dict]) -> list[dict]:
    """Находки регулярной проверки с кодами TECH_CODES на продвигаемых витринах."""
    st = _read_json(state_path, {})
    находки: dict[str, dict] = {}
    for ключ in ("open_issues_check", "open_issues_daily"):
        for k, v in (st.get(ключ) or {}).items():
            находки[k] = v
    итог = []
    for k, v in sorted(находки.items()):
        домен = v.get("domain") or k.split("|")[0]
        код = str(v.get("code") or k.split("|", 1)[-1]).split(":")[0]
        if код not in TECH_CODES or домен not in cells:
            continue
        шаблон = TECH_CODES[код]
        c = cells[домен]
        итог.append({
            "site": домен, "direction": c["direction"], "repo": c["repo"],
            "urls": [f"https://{домен}/"],
            "problem": f"Регулярная проверка: {код} — {str(v.get('detail') or '')[:300]}",
            "norm": шаблон["norm"], "expected": шаблон["expected"],
            "check": f"checks/auto_{код.lower()}.py",
            "verify_live": f"после выпуска регулярная проверка не показывает {код} для {домен}",
            "source": _подпись("regular", домен, код),
        })
    return итог


Fetch = Callable[[str], tuple[int, str, str]]


def _fetch(url: str) -> tuple[int, str, str]:
    """(код, Location, тело) без следования переходам."""
    class _Без(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):  # noqa: ANN001, ANN002
            return None
    op = urllib.request.build_opener(_Без)
    запрос = urllib.request.Request(url, headers={"User-Agent": "seo-tech-backlog"})
    try:
        with op.open(запрос, timeout=30) as о:
            return о.status, о.headers.get("Location") or "", о.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location") or "", ""


def from_links(cells: dict[str, dict], fetch: Fetch = _fetch, *, per_site: int = 40) -> list[dict]:
    """Внутренние ссылки главной и /catalog/, отвечающие 3xx/4xx/5xx (кроме намеренных)."""
    итог = []
    for домен, c in sorted(cells.items()):
        ссылки: dict[str, str] = {}
        for страница in ("/", "/catalog/"):
            try:
                код, _, тело = fetch(f"https://{домен}{страница}")
            except Exception:  # noqa: BLE001 — недоступный сайт — находка регулярной проверки
                continue
            if код != 200:
                continue
            for h in re.findall(r'<a[^>]+href="([^"#]+)"', тело):
                h = html.unescape(h)
                if h.startswith(f"https://{домен}"):
                    h = h[len(f"https://{домен}"):] or "/"
                if h.startswith("/") and not h.startswith("//") and not any(п.search(h) for п in НАМЕРЕННЫЕ):
                    ссылки.setdefault(h, страница)
        плохие = []
        for h, откуда in list(ссылки.items())[:per_site]:
            try:
                код, куда, тело = fetch(f"https://{домен}{h}")
            except Exception:  # noqa: BLE001
                continue
            if код >= 300:
                плохие.append((h, код, куда, откуда))
            elif код == 200 and "?" not in h and _noindex(тело):
                # Ссылка навигации на закрытый от индекса раздел без параметров — пустой слот
                # (как служебные метки в подвале, T054). Параметрические выборки — намеренно noindex.
                плохие.append((h, "noindex", "", откуда))
        if not плохие:
            continue
        образцы = "; ".join(f"{h} → {к}{(' ' + к2) if к2 else ''} (с {о})" for h, к, к2, о in плохие[:5])
        итог.append({
            "site": домен, "direction": c["direction"], "repo": c["repo"],
            "urls": [f"https://{домен}{h}" for h, *_ in плохие[:5]],
            "problem": f"Аудит ссылок: {len(плохие)} внутренних ссылок главной и /catalog/ ведут на переход, ошибку или закрытую от индекса страницу: {образцы}",
            "norm": "внутренние ссылки ведут на конечный адрес со статусом 200 (без перехода и без ошибки)",
            "expected": "ссылки главной и /catalog/ указывают сразу на канонический индексируемый адрес; битых и ведущих в noindex нет",
            "check": "checks/auto_internal_links.py",
            "verify_live": "после выпуска ссылки главной и /catalog/ отвечают 200",
            "source": _подпись("links", домен, hashlib.sha1("|".join(sorted(h for h, *_ in плохие)).encode()).hexdigest()[:10]),
        })
    return итог


def _noindex(тело: str) -> bool:
    м = re.search(r'<meta name="robots" content="([^"]*)"', тело)
    return bool(м and "noindex" in м.group(1))


def from_pages(cells: dict[str, dict], fetch: Fetch = _fetch, *, per_site: int = 5) -> list[dict]:
    """Выборка страниц тайтлов из карты: canonical на себя, description, один H1, JSON-LD разбирается."""
    итог = []
    for домен, c in sorted(cells.items()):
        try:
            код, _, индекс = fetch(f"https://{домен}/sitemap.xml")
        except Exception:  # noqa: BLE001
            continue
        if код != 200:
            continue
        адреса: list[str] = []
        прочие: list[str] = []
        части = re.findall(r"<loc>([^<]+)</loc>", индекс)
        for часть in части[:1] + части[-2:]:
            try:
                _, _, тело = fetch(html.unescape(часть))
            except Exception:  # noqa: BLE001
                continue
            for u in (html.unescape(x) for x in re.findall(r"<loc>([^<]+)</loc>", тело)):
                (адреса if "/title/" in u else прочие).append(u)
        шаг = lambda xs: xs[:: max(1, len(xs) // per_site)][:per_site] if xs else []
        отобрано = шаг(адреса) + шаг([u for u in прочие if not u.endswith(".xml")])
        беды = []
        for u in отобрано:
            try:
                код, _, тело = fetch(u)
            except Exception:  # noqa: BLE001
                continue
            if код != 200:
                беды.append((u, f"в карте, но код {код}"))
                continue
            if _noindex(тело):
                # В карте — только индексируемые страницы: noindex у адреса карты — дефект карты.
                беды.append((u, "в карте, но noindex"))
                continue
            канон = re.search(r'<link rel="canonical" href="([^"]*)"', тело)
            if not канон:
                беды.append((u, "нет canonical"))
            elif канон.group(1).rstrip("/") != u.rstrip("/"):
                беды.append((u, f"canonical на {канон.group(1)}"))
            if not re.search(r'<meta name="description" content="[^"]{20,}"', тело):
                беды.append((u, "нет description"))
            h1 = len(re.findall(r"<h1[\s>]", тело))
            if h1 != 1:
                беды.append((u, f"H1: {h1}"))
            for блок in re.findall(r'<script type="application/ld\+json">(.*?)</script>', тело, re.S):
                try:
                    json.loads(блок)
                except ValueError:
                    беды.append((u, "JSON-LD не разбирается"))
                    break
        if not беды:
            continue
        итог.append({
            "site": домен, "direction": c["direction"], "repo": c["repo"],
            "urls": sorted({u for u, _ in беды})[:5],
            "problem": "Аудит адресов карты сайта (выборка тайтлов и разделов): " + "; ".join(f"{u} — {б}" for u, б in беды[:6]),
            "norm": "в карте — только индексируемые страницы 200 с canonical на себя; у страницы — содержательный description, один H1, разбираемый JSON-LD",
            "expected": "все отклонения выборки устранены; проверка поднимает витрину и проверяет те же признаки",
            "check": "checks/auto_title_page.py",
            "verify_live": "после выпуска выборка тех же адресов без отклонений",
            "source": _подпись("pages", домен, hashlib.sha1("|".join(sorted(f"{u}{б}" for u, б in беды)).encode()).hexdigest()[:10]),
        })
    return итог


def from_ports(задачи: list[dict], опубликовано: set[str], cells: dict[str, dict]) -> list[dict]:
    """Переносы: у выпущенной задачи с `port_to` — задача на каждый названный сайт."""
    итог = []
    for з in задачи:
        if not з.get("port_to"):
            continue
        if з["id"] not in опубликовано and з.get("status") not in ("released", "live_verified", "done"):
            continue
        for домен in з["port_to"]:
            c = cells.get(домен)
            if not c:
                continue
            итог.append({
                "site": домен, "direction": c["direction"], "repo": c["repo"],
                "urls": [u.replace(з.get("site", ""), домен) for u in (з.get("urls") or [])][:3],
                "problem": f"Перенос {з['id']} ({з.get('site')}, выпущено): {з.get('problem', '')[:400]}",
                "norm": з.get("norm", ""), "expected": з.get("expected", ""),
                "check": з.get("check", ""), "verify_live": з.get("verify_live", ""),
                **({"live_check": з["live_check"]} if з.get("live_check") else {}),
                "source": _подпись("port", з["id"], домен),
            })
    return итог


def attention(задачи: list[dict], state: Path) -> list[dict]:
    """Задачи, исчерпавшие попытки: им нужен человек или сессия, а не повтор."""
    сводка = tech_run.task_state(state)
    итог = []
    for з in задачи:
        с = сводка.get(з["id"], {})
        if з.get("status") == "queued" and с.get("failures", 0) >= tech_run.MAX_ATTEMPTS:
            последний = с.get("last") or {}
            итог.append({"id": з["id"], "site": з.get("site"), "failures": с["failures"],
                         "last_verdict": последний.get("verdict"), "notes": (последний.get("notes") or [])[:2]})
    return итог


def _опубликованные(state: Path) -> set[str]:
    f = state / "publish.jsonl"
    if not f.exists():
        return set()
    out = set()
    for с in f.read_text(encoding="utf-8").splitlines():
        try:
            р = json.loads(с)
        except ValueError:
            continue
        if р.get("outcome") in ("live_verified", "released"):
            out.add(р.get("task_id"))
    return out


def run(state: Path | None = None, *, links: bool | None = None, fetch: Fetch = _fetch,
        regular_state: Path = REGULAR_STATE, cells_path: Path = CELLS,
        now: dt.datetime | None = None) -> dict[str, Any]:
    """Один проход пополнения. Возвращает добавленные задачи и список внимания."""
    state = state or tech_run.STATE
    now = now or _сейчас()
    state.mkdir(parents=True, exist_ok=True)
    отметка = _read_json(state / "backlog.json", {})
    if links is None:
        прошлый = отметка.get("last_links")
        links = not прошлый or (now - dt.datetime.fromisoformat(прошлый.replace("Z", "+00:00"))).total_seconds() > 86400
    cells = promoted_cells(cells_path)
    задачи = tech_run.load_queue(state=state)
    кандидаты = from_regular(regular_state, cells) + from_ports(задачи, _опубликованные(state), cells)
    if links:
        кандидаты += from_links(cells, fetch) + from_pages(cells, fetch)
    известные = {з.get("source") for з in задачи if з.get("source")}
    # Адреса, которые уже разбирает другая задача (например, T085 «Онгоинги»), повторно не ставятся.
    занятые_адреса = {u for з in задачи if з.get("status") != "done" for u in (з.get("urls") or [])}
    кандидаты = [к for к in кандидаты
                 if not (к["source"].startswith(("auto:links", "auto:pages")) and set(к.get("urls") or []) <= занятые_адреса)]
    авто_файл = state / tech_run.AUTO_QUEUE_NAME
    авто = _read_json(авто_файл, {"tasks": []})
    номер = max([int(з["id"][1:]) for з in авто["tasks"] if re.fullmatch(r"A\d{4}", з.get("id", ""))] + [0])
    добавлено = []
    проверить = _валидатор_задачи()
    for к in кандидаты:
        if к["source"] in известные:
            continue
        задача = {"id": f"A{номер + 1:04d}", "status": "queued",
                  "evidence": f"{_iso(now)}: поставлено пополнением очереди (tech_backlog, {к['source']})", **к}
        ошибки = проверить(задача)
        if ошибки:
            # Невалидная задача не ставится: таймер не должен брать то, что verify не сможет подтвердить.
            отметка.setdefault("rejected", []).append({"source": к["source"], "errors": ошибки[:3]})
            continue
        номер += 1
        авто["tasks"].append(задача)
        известные.add(к["source"])
        добавлено.append(задача)
    if добавлено:
        tmp = авто_файл.with_suffix(".tmp")
        tmp.write_text(json.dumps(авто, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, авто_файл)
    внимание = attention(tech_run.load_queue(state=state), state)
    (state / "attention.json").write_text(json.dumps({"at": _iso(now), "tasks": внимание}, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    отметка["last_run"] = _iso(now)
    if links:
        отметка["last_links"] = _iso(now)
    (state / "backlog.json").write_text(json.dumps(отметка, ensure_ascii=False), encoding="utf-8")
    return {"added": [з["id"] for з in добавлено], "sources": [з["source"] for з in добавлено],
            "attention": внимание, "links_audit": bool(links)}


def _валидатор_задачи() -> Callable[[dict], list[str]]:
    """Проверка задачи по $defs/task схемы очереди (тот же контракт, что у config)."""
    try:
        import jsonschema
        схема = json.loads((REPO / "schemas" / "seo-tech-queue.schema.json").read_text(encoding="utf-8"))
        обёртка = {"$schema": схема.get("$schema"), "$defs": схема["$defs"], "$ref": "#/$defs/task"}
        валидатор = jsonschema.Draft202012Validator(обёртка)
    except Exception as ош:  # noqa: BLE001 — без схемы задачи не ставятся вовсе
        return lambda _з: [f"схема недоступна: {type(ош).__name__}"]
    return lambda з: [f"{'/'.join(map(str, e.path))}: {e.message}"[:200] for e in валидатор.iter_errors(з)]


def due(state: Path, every_s: int, now: dt.datetime | None = None) -> bool:
    """Пора ли пополнять: прошлый проход старше every_s."""
    now = now or _сейчас()
    прошлый = _read_json(state / "backlog.json", {}).get("last_run")
    if not прошлый:
        return True
    return (now - dt.datetime.fromisoformat(прошлый.replace("Z", "+00:00"))).total_seconds() >= every_s
