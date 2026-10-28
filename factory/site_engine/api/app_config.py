"""Главная, подборки и оформление приложения «Кинатека» — ревизии по каналам.

Контракт для клиента — `kinateka-config/1` (ott-app-sandbox
`docs/APP_CONFIG_CONTRACT.md`, передача 135). Здесь — сторона записи: черновик
канала, проверка, публикация, откат и история. Читает опубликованное служба
`app-read-api` (маршрут `config/{канал}`); она же подставляет в позиции
подборок поля из текущего снимка каталога.

Раскладка каталога `var/app-config/<site>/` (общее состояние фабрики, не релиз:
откат кода Control API не должен уносить опубликованные ревизии):

* `draft-<канал>.json` — черновик, который правит админка; версия — sha256
  содержимого, правка сверяется с ней (409, как у настроек витрин);
* `revisions/<n>.json` — неизменяемые ревизии, номер сквозной по каналам;
* `published-<канал>.json` — указатель `{"revision": n}`; меняется атомарной
  подменой файла, поэтому читатель видит либо прежнюю ревизию, либо новую;
* `history.jsonl` — кто, когда, что: публикация, откат, перенос между каналами.

Каналы раздельны: публикация в `sandbox` пишет только указатель `sandbox`.
Перенос в `production` — отдельное действие с отдельной ревизией.

Почему не движок ченджсетов: он требует цепочки подписей и закрыт для
автономного применения в рабочую среду. Здесь меняются только данные главной
приложения, обратимые одним переводом указателя; для них достаточно сверки
версии, блокировки и записи в журнал аудита — как у `_patch_settings`.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "kinateka-config/1"
CHANNELS = ("sandbox", "production")
BLOCK_KINDS = ("hero", "continue", "collection", "recent", "genre")
HERO_STYLES = ("backdrop", "poster")
CARD_STYLES = ("poster", "landscape")
ACCENT_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,47}$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})$")
MAX_COLLECTIONS = 20
MAX_ITEMS = 60
MAX_BLOCKS = 20
MAX_REASON = 140

# Общая витрина (баннер, ряды и подборки главной) не показывает откровенных
# изображений. Пригодность ИЗОБРАЖЕНИЯ — редакционное решение по конкретной
# картинке (`artwork.reviews`: адрес изображения → «ok» или «explicit»), а не
# свойство произведения: возрастная маркировка и жанры вроде «гарем» о самой
# обложке ничего не доказывают и витрину не фильтруют. Жанры ниже — только
# признак риска: обложка такого тайтла попадает на витрину после того, как
# редактор её посмотрел и отметил «ok». Обложка с отметкой «explicit» не
# попадает никогда, какого бы жанра ни был тайтл. Поиск и карточки тайтлов
# правило не трогает. Те же правила — в app-read-api при отдаче и в клиенте.
COVER_RISK_GENRES = frozenset({"этти", "хентай", "эротика"})
VERDICTS = ("ok", "explicit")
MAX_REVIEWS = 500
MAX_NOTE = 140

# Приложение → витрина, чей каталог оно показывает. Закрытый список: имя в пути
# не должно выбирать произвольный каталог на диске.
APPS = {"kinateka": {"site": "animedia-01", "title": "Кинатека"}}

EMPTY_DRAFT: dict[str, Any] = {
    "schema": SCHEMA,
    "appearance": {"accent": "#E3B26B", "heroStyle": "backdrop", "rowCardStyle": "poster",
                   "focusScale": 1.08},
    "home": {"blocks": [{"id": "continue", "kind": "continue", "visible": True},
                        {"id": "recent", "kind": "recent", "title": "Недавно добавлено",
                         "visible": True}]},
    "collections": [],
}


class AppConfigError(Exception):
    """Отказ операции: статус, код и подробности для ответа API."""

    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra


def _now_iso(now: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))


def _canon(doc: Any) -> str:
    return json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def version_of(doc: Any) -> str:
    return hashlib.sha256(_canon(doc).encode("utf-8")).hexdigest()[:16]


def _parse_iso(value: str) -> datetime.datetime | None:
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


# ---- каталог ----------------------------------------------------------------

@dataclass(frozen=True)
class Title:
    content_id: str
    title: str
    type: str
    poster: str | None
    year: int | None
    genres: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"contentId": self.content_id, "title": self.title, "type": self.type,
                "posterUrl": self.poster, "year": self.year, "genres": list(self.genres)}


class CatalogIndex:
    """Узкий указатель по снимку витрины: id → название, тип, постер, год, жанры.

    Перечитывается по метке файла подробностей. Нужен для проверки состава
    (существует ли тайтл, есть ли постер, не попадает ли под запрет жанров) и
    для предпросмотра. Если снимок не читается, проверка состава называет это
    проблемой, а не пропускает молча.
    """

    def __init__(self, data_dir: Path, site_id: str) -> None:
        self.path = Path(data_dir) / f"{site_id}-details.json"
        self._mark: tuple[int, int] | None = None
        self._titles: dict[str, Title] = {}
        self._revision = ""
        self._lock = threading.Lock()
        self.error: str | None = None

    def _load(self) -> None:
        try:
            st = self.path.stat()
        except OSError as exc:
            self.error = f"снимок каталога не найден: {exc.strerror or type(exc).__name__}"
            return
        mark = (st.st_mtime_ns, st.st_size)
        if mark == self._mark:
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.error = f"снимок каталога не читается: {type(exc).__name__}"
            return
        titles: dict[str, Title] = {}
        for d in (raw.get("details") or {}).values():
            cid = str(d.get("id") or "")
            if not cid:
                continue
            titles[cid] = Title(cid, str(d.get("name") or ""),
                                "movie" if d.get("type") == "movie" else "series",
                                d.get("poster_url") or None, d.get("year") or None,
                                tuple(str(g).lower() for g in d.get("genres") or []))
        self._titles, self._mark, self.error = titles, mark, None
        self._revision = str(raw.get("catalog_revision") or "")

    def get(self, content_id: str) -> Title | None:
        with self._lock:
            self._load()
            return self._titles.get(content_id)

    @property
    def revision(self) -> str:
        with self._lock:
            self._load()
            return self._revision

    def search(self, needle: str, limit: int = 20) -> list[Title]:
        needle = needle.strip().lower()
        if len(needle) < 2:
            return []
        with self._lock:
            self._load()
            found = [t for cid, t in self._titles.items()
                     if needle in t.title.lower() or needle == cid]
        return found[:limit]


# ---- пригодность изображений для общей витрины -------------------------------

def artwork_reviews(doc: Any) -> dict[tuple[str, str], str]:
    """(contentId, адрес изображения) → вердикт редактора; неверные записи пропущены."""
    art = doc.get("artwork") if isinstance(doc, dict) else None
    reviews = art.get("reviews") if isinstance(art, dict) else None
    out: dict[tuple[str, str], str] = {}
    for r in reviews if isinstance(reviews, list) else []:
        if isinstance(r, dict) and r.get("verdict") in VERDICTS:
            out[(str(r.get("contentId") or ""), str(r.get("imageUrl") or ""))] = r["verdict"]
    return out


def showcase_problem(t: Title, reviews: dict[tuple[str, str], str]) -> str | None:
    """Почему изображение тайтла не идёт на общую витрину, или None — идёт."""
    if not t.poster:
        return "в каталоге нет постера"
    verdict = reviews.get((t.content_id, t.poster))
    if verdict == "explicit":
        return "обложка отмечена редактором как откровенная"
    risk = COVER_RISK_GENRES.intersection(t.genres)
    if risk and verdict != "ok":
        return (f"обложка не проверена (жанр {', '.join(sorted(risk))}) — посмотрите её "
                "в разделе «Обложки» и отметьте")
    return None


def artwork_overview(doc: Any, catalog: CatalogIndex) -> dict[str, Any]:
    """Для раздела «Обложки»: отметки черновика с текущим постером тайтла и
    очередь — позиции подборок, чью обложку редактор ещё не смотрел."""
    reviews = artwork_reviews(doc)
    rows = []
    art = doc.get("artwork") if isinstance(doc, dict) else None
    for r in (art.get("reviews") if isinstance(art, dict) else None) or []:
        if not isinstance(r, dict):
            continue
        t = catalog.get(str(r.get("contentId") or ""))
        rows.append({**r, "title": t.title if t else None, "currentPosterUrl": t.poster if t else None,
                     # Отметка относится к картинке: сменился постер — смотреть заново.
                     "applies": bool(t and t.poster == r.get("imageUrl"))})
    queue, seen = [], set()
    for c in (doc.get("collections") if isinstance(doc, dict) else None) or []:
        for it in (c.get("items") if isinstance(c, dict) else None) or []:
            cid = str((it or {}).get("contentId") or "")
            t = catalog.get(cid)
            if t is None or not t.poster or cid in seen:
                continue
            risk = COVER_RISK_GENRES.intersection(t.genres)
            if risk and (cid, t.poster) not in reviews:
                seen.add(cid)
                queue.append({**t.as_dict(), "risk": sorted(risk), "collection": c.get("id")})
    return {"reviews": rows, "queue": queue, "coverRiskGenres": sorted(COVER_RISK_GENRES)}


# ---- проверка ---------------------------------------------------------------

def check(doc: Any, catalog: CatalogIndex | None, *, now: float) -> list[dict[str, str]]:
    """Все проблемы документа сразу (не первая): редактор правит одним заходом.

    Проблема — `{"where": "...", "problem": "..."}`. Пустой список — документ
    можно публиковать. `catalog=None` — проверка только формы (сохранение
    черновика); публикация всегда проверяет и состав.
    """
    p: list[dict[str, str]] = []

    def bad(where: str, problem: str) -> None:
        p.append({"where": where, "problem": problem})

    if not isinstance(doc, dict):
        return [{"where": "документ", "problem": "нужен объект JSON"}]
    if doc.get("schema") != SCHEMA:
        bad("schema", f"нужно {SCHEMA}")

    ap = doc.get("appearance") or {}
    if not isinstance(ap, dict):
        bad("appearance", "нужен объект")
        ap = {}
    for key in ap:
        if key not in ("accent", "heroStyle", "rowCardStyle", "focusScale"):
            bad(f"appearance.{key}", "параметр не поддерживается клиентом")
    if "accent" in ap and not (isinstance(ap["accent"], str) and ACCENT_RE.match(ap["accent"])):
        bad("appearance.accent", "цвет в виде #RRGGBB")
    if "heroStyle" in ap and ap["heroStyle"] not in HERO_STYLES:
        bad("appearance.heroStyle", f"одно из {', '.join(HERO_STYLES)}")
    if "rowCardStyle" in ap and ap["rowCardStyle"] not in CARD_STYLES:
        bad("appearance.rowCardStyle", f"одно из {', '.join(CARD_STYLES)}")
    if "focusScale" in ap:
        fs = ap["focusScale"]
        if isinstance(fs, bool) or not isinstance(fs, (int, float)) or not 1.0 <= fs <= 1.12:
            bad("appearance.focusScale", "число от 1.00 до 1.12")

    reviews = artwork_reviews(doc)
    art = doc.get("artwork")
    if art is not None:
        rows = art.get("reviews") if isinstance(art, dict) else None
        if not isinstance(rows, list):
            bad("artwork", "нужен объект с отзывами reviews: []")
            rows = []
        if len(rows) > MAX_REVIEWS:
            bad("artwork", f"не больше {MAX_REVIEWS} отметок")
        for n, r in enumerate(rows, 1):
            rw = f"обложки, отметка {n}"
            if not isinstance(r, dict):
                bad(rw, "нужен объект")
                continue
            if not str(r.get("contentId") or "").strip():
                bad(rw, "нет contentId")
            if not str(r.get("imageUrl") or "").startswith("https://"):
                bad(rw, "адрес изображения https://")
            if r.get("verdict") not in VERDICTS:
                bad(rw, "вердикт ok или explicit")
            if not ISO_RE.match(str(r.get("reviewedAt") or "")):
                bad(rw, "дата просмотра reviewedAt в ISO 8601 с зоной")
            if len(str(r.get("note") or "")) > MAX_NOTE:
                bad(rw, f"примечание длиннее {MAX_NOTE} знаков")

    collections = doc.get("collections") or []
    if not isinstance(collections, list):
        bad("collections", "нужен список")
        collections = []
    if len(collections) > MAX_COLLECTIONS:
        bad("collections", f"не больше {MAX_COLLECTIONS}")
    ids: set[str] = set()
    for i, c in enumerate(collections):
        where = f"подборка {i + 1}"
        if not isinstance(c, dict):
            bad(where, "нужен объект")
            continue
        cid = c.get("id")
        if not (isinstance(cid, str) and ID_RE.match(cid)):
            bad(where, "id: латиница в нижнем регистре, цифры, дефис")
        elif cid in ids:
            bad(where, f"id {cid} повторяется")
        else:
            ids.add(cid)
            where = f"подборка {cid}"
        if not str(c.get("title") or "").strip():
            bad(where, "нет названия")
        elif len(c["title"]) > 60:
            bad(where, "название длиннее 60 знаков")
        if not str(c.get("source") or "").strip():
            bad(where, "не указан источник")
        if not ISO_RE.match(str(c.get("checkedAt") or "")):
            bad(where, "дата проверки checkedAt в ISO 8601 с зоной")
        if c.get("validUntil"):
            until = _parse_iso(str(c["validUntil"]))
            if until is None:
                bad(where, "validUntil в ISO 8601 с зоной")
            elif until.timestamp() <= now:
                bad(where, "срок validUntil уже прошёл — подборка не будет показана")
        items = c.get("items") or []
        if not isinstance(items, list) or not items:
            bad(where, "пустой состав")
            items = []
        if len(items) > MAX_ITEMS:
            bad(where, f"не больше {MAX_ITEMS} позиций")
        seen: set[str] = set()
        for n, it in enumerate(items, 1):
            iw = f"{where}, позиция {n}"
            if not isinstance(it, dict):
                bad(iw, "нужен объект")
                continue
            content_id = str(it.get("contentId") or "")
            if not content_id:
                bad(iw, "нет contentId")
                continue
            if content_id in seen:
                bad(iw, f"{content_id} уже есть в подборке")
            seen.add(content_id)
            reason = str(it.get("reason") or "").strip()
            if not reason:
                bad(iw, "нет причины (reason)")
            elif len(reason) > MAX_REASON:
                bad(iw, f"причина длиннее {MAX_REASON} знаков")
            if not str(it.get("source") or "").strip():
                bad(iw, "не указан источник позиции")
            if not ISO_RE.match(str(it.get("checkedAt") or "")):
                bad(iw, "дата проверки позиции в ISO 8601 с зоной")
            if catalog is not None:
                t = catalog.get(content_id)
                if catalog.error:
                    bad(iw, catalog.error)
                elif t is None:
                    bad(iw, f"{content_id} нет в каталоге")
                else:
                    problem = showcase_problem(t, reviews)
                    if problem:
                        bad(iw, f"«{t.title}»: {problem}")

    home = doc.get("home") or {}
    blocks = home.get("blocks") if isinstance(home, dict) else None
    if not isinstance(blocks, list) or not blocks:
        bad("home.blocks", "нужен непустой список блоков")
        blocks = []
    if len(blocks) > MAX_BLOCKS:
        bad("home.blocks", f"не больше {MAX_BLOCKS}")
    bids: set[str] = set()
    for i, b in enumerate(blocks):
        where = f"блок {i + 1}"
        if not isinstance(b, dict):
            bad(where, "нужен объект")
            continue
        bid = b.get("id")
        if not (isinstance(bid, str) and ID_RE.match(bid)):
            bad(where, "id: латиница в нижнем регистре, цифры, дефис")
        elif bid in bids:
            bad(where, f"id {bid} повторяется")
        else:
            bids.add(bid)
            where = f"блок {bid}"
        kind = b.get("kind")
        if kind not in BLOCK_KINDS:
            bad(where, f"вид одно из {', '.join(BLOCK_KINDS)}")
        if kind in ("hero", "collection"):
            if b.get("collectionId") not in ids:
                bad(where, f"нет подборки {b.get('collectionId')!r}")
        if kind in ("collection", "recent", "genre") and not str(b.get("title") or "").strip():
            bad(where, "нет заголовка")
        if kind == "genre" and not str(b.get("genre") or "").strip():
            bad(where, "не указан жанр")
        if kind == "genre" and str(b.get("genre") or "").strip().lower() in COVER_RISK_GENRES:
            bad(where, "строка этого жанра состояла бы из непроверенных обложек — соберите подборку")
        if "cardStyle" in b and b["cardStyle"] not in CARD_STYLES:
            bad(where, f"карточки одно из {', '.join(CARD_STYLES)}")
        if "visible" in b and not isinstance(b["visible"], bool):
            bad(where, "visible — да/нет")
        cover = b.get("cover")
        if cover is not None and not (isinstance(cover, str) and cover.startswith("https://")):
            bad(where, "обложка — адрес https:// или пусто")
    return p


def preview(doc: dict[str, Any], catalog: CatalogIndex) -> dict[str, Any]:
    """Документ в том виде, в каком его отдаст служба чтения: позиции дополнены
    из текущего снимка, отсутствующие и с обложкой не для витрины — в `missing`."""
    out = json.loads(json.dumps(doc))
    reviews = artwork_reviews(doc)
    for c in out.get("collections") or []:
        kept, missing = [], []
        for it in c.get("items") or []:
            t = catalog.get(str(it.get("contentId") or ""))
            if t is None or showcase_problem(t, reviews):
                missing.append(it.get("contentId"))
                continue
            kept.append({**it, "title": t.title, "type": t.type, "posterUrl": t.poster,
                         "year": t.year})
        c["items"], c["missing"] = kept, missing
    return out


# ---- хранилище --------------------------------------------------------------

class ConfigStore:
    """Файлы ревизий одного приложения. Все изменения — под блокировкой каталога."""

    def __init__(self, root: Path, *, now=time.time) -> None:
        self.root = Path(root)
        self._now = now

    # чтение

    def _read_json(self, path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    def draft(self, channel: str) -> tuple[dict[str, Any], str]:
        path = self.root / f"draft-{channel}.json"
        if path.exists():
            doc = self._read_json(path)
        else:
            current = self.current(channel)
            doc = self.document_of(self.revision(current)) if current else json.loads(json.dumps(EMPTY_DRAFT))
        return doc, version_of(doc)

    def current(self, channel: str) -> int | None:
        path = self.root / f"published-{channel}.json"
        if not path.exists():
            return None
        return int(self._read_json(path)["revision"])

    def revision(self, n: int) -> dict[str, Any]:
        path = self.root / "revisions" / f"{int(n)}.json"
        if not path.exists():
            raise AppConfigError(404, "revision_not_found", f"ревизии {n} нет")
        return self._read_json(path)

    @staticmethod
    def document_of(revision: dict[str, Any]) -> dict[str, Any]:
        return {k: revision[k] for k in ("schema", "appearance", "home", "collections", "artwork")
                if k in revision}

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        path = self.root / "history.jsonl"
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]][::-1]

    def revisions(self) -> list[int]:
        d = self.root / "revisions"
        return sorted(int(p.stem) for p in d.glob("*.json") if p.stem.isdigit()) if d.exists() else []

    # запись

    def _write_atomic(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(path)

    def _append_history(self, entry: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / "history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def save_draft(self, channel: str, doc: dict[str, Any], expected: str) -> str:
        _, current = self.draft(channel)
        if expected != current:
            raise AppConfigError(409, "version_conflict", "черновик изменился с момента чтения",
                                 expected_version=expected, current_version=current)
        self._write_atomic(self.root / f"draft-{channel}.json", doc)
        return version_of(doc)

    def publish(self, channel: str, doc: dict[str, Any], *, by: str, comment: str,
                expected_revision: int | None, action: str = "publish",
                origin: dict[str, Any] | None = None) -> dict[str, Any]:
        current = self.current(channel)
        if expected_revision != current:
            raise AppConfigError(409, "revision_conflict", "в канале уже опубликовано другое",
                                 expected_revision=expected_revision, current_revision=current)
        n = (self.revisions() or [0])[-1] + 1
        stamp = self._now()
        revision = {**self.document_of(doc), "channel": channel, "revision": n,
                    "revisionId": f"r{n}-{version_of(doc)[:8]}",
                    "publishedAt": _now_iso(stamp), "publishedBy": by, "rollbackOf": None}
        path = self.root / "revisions" / f"{n}.json"
        if path.exists():  # пишется один раз; совпадение значит гонку мимо блокировки
            raise AppConfigError(409, "revision_exists", f"ревизия {n} уже есть")
        self._write_atomic(path, revision)
        self._write_atomic(self.root / f"published-{channel}.json", {"revision": n})
        self._append_history({"at": _now_iso(stamp), "action": action, "channel": channel,
                              "revision": n, "revisionId": revision["revisionId"],
                              "previous": current, "by": by, "comment": comment,
                              **({"origin": origin} if origin else {})})
        return revision

    def rollback(self, channel: str, to: int, *, by: str, comment: str,
                 expected_revision: int | None) -> dict[str, Any]:
        current = self.current(channel)
        if expected_revision != current:
            raise AppConfigError(409, "revision_conflict", "в канале уже опубликовано другое",
                                 expected_revision=expected_revision, current_revision=current)
        target = self.revision(to)
        if target.get("channel") != channel:
            # Ревизия другого канала через откат не переносится: для этого
            # есть явный перенос, у которого своя запись в истории.
            raise AppConfigError(422, "wrong_channel",
                                 f"ревизия {to} опубликована в {target.get('channel')}, а не в {channel}")
        if to == current:
            raise AppConfigError(422, "already_current", f"ревизия {to} уже действует")
        self._write_atomic(self.root / f"published-{channel}.json", {"revision": to})
        self._append_history({"at": _now_iso(self._now()), "action": "rollback", "channel": channel,
                              "revision": to, "revisionId": target.get("revisionId"),
                              "previous": current, "rollbackOf": current, "by": by,
                              "comment": comment})
        return target
