"""Задания и витрины для эксплуатации.

Два правила, каждое из-за конкретной лжи, которую легко показать оператору.

**Принятое задание — не выполненное.** Панель, отвечающая «готово» на
постановку в очередь, обманывает: работа ещё не начиналась. Состояние
собирается из очереди И из результата, а не из факта успешного HTTP.

**HTTP 200 — не здоровье витрины.** Витрина с пустым или устаревшим каталогом
отвечает 200 и при этом неисправна. Именно так каталог тридцатипятичасовой
давности месяцами считался работающим.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "admin-ops/1.0.0"

#: Как называется состояние задания снаружи. Отдельно от внутреннего статуса:
#: «DONE с непройденной проверкой» и «DONE» — разные вещи для оператора.
СОСТОЯНИЕ_ПО_СТАТУСУ = {
    "DONE": "SUCCEEDED",
    "READY": "SUCCEEDED",
    "BUILT": "SUCCEEDED",
    "FAILED": "FAILED",
    "QA_FAILED": "FAILED",
}


class OpsError(RuntimeError):
    """Запрос к эксплуатационным данным невыполним."""


def _safe(значение: str) -> str:
    if not значение or "/" in значение or ".." in значение or len(значение) > 128:
        raise OpsError(f"негодный идентификатор {значение!r}")
    return значение


def _результаты(root: Path) -> list[dict]:
    каталог = Path(root) / "artifacts" / "jobs"
    if not каталог.is_dir():
        return []
    итог = []
    for витрина in sorted(каталог.iterdir()):
        if not витрина.is_dir():
            continue
        for файл in sorted(витрина.glob("*.json")):
            try:
                итог.append(json.loads(файл.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return итог


def _состояние(результат: dict) -> str:
    статус = str(результат.get("status") or "")
    if статус.startswith("BLOCKED"):
        return "BLOCKED"
    return СОСТОЯНИЕ_ПО_СТАТУСУ.get(статус, "UNKNOWN")


def задание_строка(результат: dict) -> dict[str, Any]:
    проверки = результат.get("checks") or []
    не_прошли = [str(п.get("id")) for п in проверки if not п.get("passed")]
    состояние = _состояние(результат)
    return {
        "jobId": результат.get("job_id"),
        "siteId": результат.get("site_id"),
        "status": результат.get("status"),
        "state": состояние,
        # Успех — это не «дошло до конца», а «ни одна проверка не провалена».
        # Иначе DONE с непройденной проверкой выглядит как успех.
        "succeeded": состояние == "SUCCEEDED" and not не_прошли,
        "failedChecks": не_прошли,
        "blockers": результат.get("blockers") or [],
        "startedAt": результат.get("started_at"),
        "finishedAt": результат.get("finished_at"),
        "releaseId": результат.get("release_id"),
        "factoryCommit": результат.get("factory_commit"),
    }


def jobs(
    root: Path, *, site_id: str = "", state: str = "", offset: int = 0, limit: int = 50
) -> dict[str, Any]:
    """Задания: очередь и результаты вместе."""
    from factory import queue as queue_mod

    try:
        очередь = queue_mod.counts()
    except Exception:  # noqa: BLE001
        очередь = None

    строки = [задание_строка(р) for р in _результаты(Path(root))]
    отобрано = [
        s
        for s in строки
        if (not site_id or s["siteId"] == site_id) and (not state or s["state"] == state)
    ]
    отобрано.sort(
        key=lambda s: (str(s.get("finishedAt") or ""), str(s.get("jobId") or "")), reverse=True
    )
    по_состояниям: dict[str, int] = {}
    for s in строки:
        по_состояниям[s["state"]] = по_состояниям.get(s["state"], 0) + 1
    return {
        "queue": очередь,
        "byState": по_состояниям,
        "total": len(отобрано),
        "offset": offset,
        "limit": limit,
        "items": отобрано[offset : offset + limit],
        "contractVersion": CONTRACT_VERSION,
    }


def job(root: Path, job_id: str) -> dict[str, Any]:
    """Одно задание целиком, включая непройденные проверки поимённо."""
    _safe(job_id)
    for результат in _результаты(Path(root)):
        if str(результат.get("job_id")) == job_id:
            строка = задание_строка(результат)
            строка["checks"] = результат.get("checks") or []
            строка["notes"] = результат.get("notes") or []
            строка["steps"] = результат.get("steps") or []
            строка["contractVersion"] = CONTRACT_VERSION
            return строка
    raise OpsError(f"задания {job_id} нет")


def site_status(root: Path, site_id: str, *, env=None) -> dict[str, Any]:
    """Состояние витрины. Здоровье считается по содержимому, а не по коду ответа."""
    _safe(site_id)
    профиль_путь = Path(root) / "config" / "site-profiles" / f"{site_id}.json"
    if not профиль_путь.is_file():
        raise OpsError(f"профиля витрины {site_id} нет")
    try:
        профиль = json.loads(профиль_путь.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ошибка:
        raise OpsError(f"профиль витрины {site_id} не читается") from ошибка

    from factory.site_engine.api import overview as overview_mod

    сводка = overview_mod.сводка_витрины(Path(root), site_id, env=env)

    проблемы: list[str] = []
    if сводка["titles"] is None:
        проблемы.append("CATALOG_UNREADABLE")
    elif сводка["titles"] == 0:
        проблемы.append("EMPTY_CATALOG")
    if сводка["freshnessState"] == "STALE":
        проблемы.append("STALE_CATALOG")
    if (сводка["playbackCoverage"] or 0) < overview_mod.PLAYBACK_COVERAGE_FLOOR and сводка[
        "titles"
    ]:
        проблемы.append("LOW_PLAYBACK_COVERAGE")

    состояние = (
        "HEALTHY"
        if not проблемы
        else "DEGRADED"
        if проблемы == ["LOW_PLAYBACK_COVERAGE"]
        else "UNHEALTHY"
    )

    return {
        "siteId": site_id,
        "domains": профиль.get("domains") or [],
        "canonicalHost": профиль.get("canonical_host"),
        "siteType": профиль.get("site_type"),
        "renderMode": профиль.get("render_mode"),
        "indexingEnabled": профиль.get("indexing_enabled"),
        "contracts": {
            "cms": профиль.get("cms_contract"),
            "engine": профиль.get("engine_contract"),
            "seo": профиль.get("seo_contract"),
            "template": профиль.get("template_contract"),
        },
        "featureFlags": профиль.get("feature_flags") or {},
        "keepReleases": профиль.get("keep_releases"),
        "cachePolicy": профиль.get("cache_policy") or {},
        "catalog": {
            "titles": сводка["titles"],
            "playable": сводка["playable"],
            "playbackCoverage": сводка["playbackCoverage"],
            "source": сводка["source"],
        },
        "freshness": {"seconds": сводка["freshnessSeconds"], "state": сводка["freshnessState"]},
        "health": {
            "state": состояние,
            "problems": проблемы,
            "note": "здоровье считается по содержимому каталога, а не по "
            "коду ответа: витрина с пустым каталогом отвечает 200",
        },
        "contractVersion": CONTRACT_VERSION,
    }


#: Наложение канареек. Отдельный каталог, а не общий: витрина, попавшая в
#: каталог профилей, участвует в обходах, полках и выкладке раньше, чем её
#: проверили.
CANARY_DIR = "var/state/canary-profiles"


def _канарейки(root: Path) -> list[dict[str, Any]]:
    """Канареечные витрины отдельным списком и с отметкой.

    Прятать их от оператора нельзя: витрина, которой нет в списке, не будет
    ни проверена, ни откачена — про неё просто забудут.
    """
    каталог = Path(root) / CANARY_DIR
    строки: list[dict[str, Any]] = []
    for файл in sorted(каталог.glob("*.json")) if каталог.is_dir() else []:
        try:
            профиль = json.loads(файл.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            строки.append(
                {
                    "siteId": файл.stem,
                    "canary": True,
                    "health": {"state": "UNKNOWN", "problems": ["PROFILE_UNREADABLE"]},
                }
            )
            continue
        строки.append(
            {
                "siteId": профиль.get("site_id", файл.stem),
                "canary": True,
                "indexingEnabled": bool(профиль.get("indexing_enabled")),
                "domains": list(профиль.get("domains") or []),
                "health": {
                    "state": "CANARY",
                    "problems": [] if профиль.get("noindex") else ["CANARY_INDEXABLE"],
                },
            }
        )
    return строки


def sites(root: Path, *, env=None) -> dict[str, Any]:
    """Все витрины разом, для списка. Канарейки — с отметкой, а не вперемешку."""
    каталог = Path(root) / "config" / "site-profiles"
    имена = sorted(п.stem for п in каталог.glob("*.json")) if каталог.is_dir() else []
    строки = []
    for имя in имена:
        try:
            строки.append(site_status(Path(root), имя, env=env))
        except OpsError:
            строки.append(
                {"siteId": имя, "health": {"state": "UNKNOWN", "problems": ["PROFILE_UNREADABLE"]}}
            )
    канареечные = _канарейки(Path(root))
    return {
        "total": len(строки) + len(канареечные),
        "items": строки + канареечные,
        "canaryCount": len(канареечные),
        "contractVersion": CONTRACT_VERSION,
    }
