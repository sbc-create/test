"""Проверка того, что у записи действительно есть поток.

Наличие пары «агрегатор + идентификатор» в каталоге ничего не обещает: она есть
у всех 4800 записей, в том числе у тех, для которых источник потока ещё не
завёл. Поэтому прежний отбор «ведущих» записей ничего не отбирал — условие было
истинным всегда, и на первом экране оказывались самые свежие поступления,
то есть ровно те, у которых потока чаще всего нет.

Единственный достоверный признак — ответ самого плеера: плейлист либо есть
(200 с телом), либо его нет (204). Проверка стоит одного запроса на запись,
поэтому проверяются не все 4800, а те, что претендуют на первый экран.

Правило, которое здесь важнее остальных: неизвестность — не приговор. Запись,
которую не успели или не смогли проверить, считается пригодной. Ошибка сети
не должна снимать плеер с тайтла, который до этого прекрасно играл.
"""
from __future__ import annotations

import concurrent.futures as futures
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PLAYLIST_URL = "https://plapi.cdnvideohub.com/api/v1/player/sv/playlist"

#: Подтверждение живёт долго: поток, однажды появившийся, редко исчезает.
OK_TTL_SECONDS = 24 * 3600
#: Отказ живёт мало: у свежего поступления поток появляется в ближайшие часы,
#: и держать запись «немой» сутки значило бы прятать её дольше, чем нужно.
SILENT_TTL_SECONDS = 30 * 60

DEFAULT_BUDGET = 400
DEFAULT_WORKERS = 8
DEFAULT_TIMEOUT = 15


@dataclass
class Probe:
    """Один ответ источника о воспроизводимости."""

    playable: bool
    checked_at: float


class PlayabilityCache:
    """Кэш ответов на диске. Формат простой: ключ → {playable, checked_at}."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else None
        self._entries: dict[str, Probe] = {}
        if self.path and self.path.is_file():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                raw = {}
            for key, value in (raw or {}).items():
                if isinstance(value, dict) and "playable" in value:
                    self._entries[key] = Probe(
                        playable=bool(value["playable"]),
                        checked_at=float(value.get("checked_at") or 0.0),
                    )

    def get(self, key: str, now: float | None = None) -> bool | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        now = time.time() if now is None else now
        ttl = OK_TTL_SECONDS if entry.playable else SILENT_TTL_SECONDS
        if now - entry.checked_at > ttl:
            return None
        return entry.playable

    def put(self, key: str, playable: bool, now: float | None = None) -> None:
        self._entries[key] = Probe(playable, time.time() if now is None else now)

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            key: {"playable": entry.playable, "checked_at": entry.checked_at}
            for key, entry in self._entries.items()
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._entries)


def cache_key(playback: dict) -> str:
    return f"{playback.get('aggregator')}:{playback.get('title_id')}"


def probe_one(playback: dict, publisher_id: str, *, referer: str = "",
              timeout: int = DEFAULT_TIMEOUT, opener=None) -> bool | None:
    """True — поток есть, False — источник ответил «пусто», None — не выяснилось.

    None и False различаются намеренно: только подтверждённое «пусто» имеет
    последствия. Любая неопределённость трактуется в пользу записи.
    """
    aggregator = str(playback.get("aggregator") or "").strip()
    title_id = str(playback.get("title_id") or "").strip()
    if not aggregator or not title_id or not publisher_id:
        return None
    url = f"{PLAYLIST_URL}?pub={publisher_id}&aggr={aggregator}&id={title_id}"
    request = urllib.request.Request(url)
    if referer:
        request.add_header("Referer", referer)
    try:
        opened = (opener or urllib.request.urlopen)(request, timeout=timeout)
        with opened as response:
            status = getattr(response, "status", None) or response.getcode()
            if status == 204:
                return False
            if status != 200:
                return None
            return bool(response.read(1))
    except urllib.error.HTTPError as error:
        # 404 у плейлиста — тоже «нечего играть», а не поломка.
        return False if error.code in (204, 404) else None
    except Exception:
        return None


def annotate(items: list[dict], publisher_id: str | None, *, budget: int = DEFAULT_BUDGET,
             cache: PlayabilityCache | None = None, referer: str = "",
             workers: int = DEFAULT_WORKERS, probe=probe_one) -> dict:
    """Проставляет `playable` записям, которые претендуют на первый экран.

    Проверяются самые свежие поступления: именно там сосредоточены записи без
    потока, и именно они попадают на главную. Остальные остаются с `None` —
    неизвестно, а значит пригодно.
    """
    report = {"checked": 0, "playable": 0, "silent": 0, "unknown": 0, "cached": 0}
    if not publisher_id:
        for item in items:
            item["playable"] = None
        report["unknown"] = len(items)
        return report

    cache = cache if cache is not None else PlayabilityCache()
    for item in items:
        item["playable"] = None

    # Порядок проверки — от новых к старым: у свежих поступлений поток
    # отсутствует чаще всего, и именно они стоят на первом экране.
    candidates = [i for i in items if (i.get("playback") or {}).get("title_id")]
    candidates.sort(key=lambda i: str(i.get("created_at") or ""), reverse=True)

    pending = []
    for item in candidates:
        known = cache.get(cache_key(item["playback"]))
        if known is not None:
            item["playable"] = known
            report["cached"] += 1
            report["playable" if known else "silent"] += 1
            continue
        if len(pending) < budget:
            pending.append(item)

    if pending:
        with futures.ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            results = list(pool.map(
                lambda i: probe(i["playback"], publisher_id, referer=referer), pending))
        for item, result in zip(pending, results, strict=False):
            item["playable"] = result
            report["checked"] += 1
            if result is True:
                report["playable"] += 1
                cache.put(cache_key(item["playback"]), True)
            elif result is False:
                report["silent"] += 1
                cache.put(cache_key(item["playback"]), False)
            else:
                report["unknown"] += 1

    report["unknown"] += sum(1 for i in items if i.get("playable") is None)
    return report
