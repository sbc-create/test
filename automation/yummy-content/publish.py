#!/usr/bin/env python3
"""Публикация проекции Yummy из контура с канареечным переключением.

Формат — тот же, что читает `yummy-frontend.py` (класс `Данные`): шаблон не
меняется ни на строку, меняются только данные под ним. Плеер, его точки входа
и логика воспроизведения не затрагиваются вовсе.

Канарейка: одна витрина, проба, откат при неудаче. Прежняя проекция
сохраняется рядом и возвращается на место, если проба не прошла.
"""
from __future__ import annotations

import argparse, json, shutil, sqlite3, subprocess, sys, time
import urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import readmodel

ФРОНТ = Path("/srv/lords/.frontend")
БАЗА = "/srv/site-factory/yummy-content/state/yummy-content.sqlite3"
ВИТРИНЫ = {
    "yummy-site": {"unit": "nova-yummy-site.service", "port": 9132, "host": "yummyani.site"},
    "yummy-biz":  {"unit": "nova-yummy-biz.service",  "port": 9130, "host": "yummyani.biz"},
    "yummy-org":  {"unit": "nova-yummy-org.service",  "port": 9131, "host": "yummyani.org"},
}
РЕЗЕРВ = Path("/srv/site-factory/yummy-content/state/rollback")
ВИД = {"MOVIE": "Фильм", "SERIES": "Сериал"}


def проекция(соед: sqlite3.Connection) -> dict:
    строки = [dict(р) for р in соед.execute(
        "SELECT entity_id, slug, canonical_path, title_ru, title_original, "
        "kind, year, poster_path, published_at, airing_status, episodes_released "
        "FROM entity WHERE canonical_path IS NOT NULL "
        "ORDER BY published_at DESC, entity_id")]
    items = [{
        "entity_id": с["entity_id"], "slug": с["slug"],
        "url": с["canonical_path"],          # адрес только из таблицы маршрутов
        "title": с["title_ru"], "original_title": с["title_original"],
        "poster": с["poster_path"] or None, "year": с["year"],
        "kind": ВИД.get(с["kind"]), "published_at": с["published_at"],
        "airing_status": с["airing_status"],
        "episodes_released": с["episodes_released"]} for с in строки]
    сборка = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    return {"version": 2, "schema": "yummy-projection/1.0.0",
            "build_id": f"{сборка}-yummy-content",
            "count": len(items),
            "without_poster": sum(1 for i in items if not i["poster"]),
            "fields_present": ["entity_id", "slug", "url", "title",
                               "original_title", "poster", "year", "kind",
                               "published_at"],
            "fields_absent": ["genres", "countries", "age_rating"],
            "absent_reason": "этих полей нет в контуре; выдумывать запрещено",
            "builtAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "items": items,
            "feeds": {
                "actual": [к["entityId"] for к in
                           readmodel.актуальное(соед, предел=24)["items"]],
                "new": [к["entityId"] for к in readmodel.новые(соед)["items"]],
                "new_episodes": [к["entityId"] for к in
                                 readmodel.новые_серии(соед)["items"]],
                "ongoing": [к["entityId"] for к in
                            readmodel.сейчас_выходит(соед, предел=60)["items"]],
                "announcements": [], "news": []}}


def проба(порт: int, слаги: list[str]) -> tuple[bool, str]:
    """HTTP 200 сам по себе доказательством не считается."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{порт}/", timeout=25) as о:
            тело = о.read().decode("utf-8", "replace")
    except Exception as e:                        # noqa: BLE001
        return False, f"главная не ответила: {type(e).__name__}"
    if len(тело) < 4000:
        return False, f"главная короче 4000 байт ({len(тело)})"
    ссылок = тело.count('href="/anime/')
    if ссылок < 12:
        return False, f"ссылок на произведения {ссылок}"
    for слаг in слаги[:8]:
        зпр = urllib.request.Request(f"http://127.0.0.1:{порт}/anime/{слаг}",
                                     headers={"User-Agent": "canary/1.0"})
        try:
            with urllib.request.urlopen(зпр, timeout=20) as о:
                if о.status != 200:
                    return False, f"/anime/{слаг} -> {о.status}"
        except urllib.error.HTTPError as e:
            return False, f"/anime/{слаг} -> {e.code}"
        except Exception as e:                    # noqa: BLE001
            return False, f"/anime/{слаг} -> {type(e).__name__}"
    return True, f"{len(тело)} байт, ссылок {ссылок}, карточек 8"


def выложить(витрина: str, данные: dict) -> dict:
    опис = ВИТРИНЫ[витрина]
    цель = ФРОНТ / f"{витрина}-catalog.json"
    РЕЗЕРВ.mkdir(parents=True, exist_ok=True)
    резерв = РЕЗЕРВ / f"{витрина}-catalog.before.json"
    if цель.exists() and not резерв.exists():
        shutil.copyfile(цель, резерв)             # last-known-good, один раз
    прежнее = цель.read_bytes() if цель.exists() else None
    врем = цель.with_suffix(".tmp")
    врем.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
    врем.replace(цель)
    subprocess.run(["sudo", "-n", "systemctl", "restart", опис["unit"]],
                   capture_output=True, timeout=120)
    time.sleep(4)
    ок, почему = проба(опис["port"], [i["slug"] for i in данные["items"][:8]])
    if not ок and прежнее is not None:
        цель.write_bytes(прежнее)
        subprocess.run(["sudo", "-n", "systemctl", "restart", опис["unit"]],
                       capture_output=True, timeout=120)
        time.sleep(3)
        назад, _ = проба(опис["port"], [])
        return {"site": витрина, "ok": False, "reason": почему,
                "rolledBack": True, "healthyAfterRollback": назад}
    return {"site": витрина, "ok": ок, "reason": почему, "rolledBack": False,
            "records": данные["count"], "buildId": данные["build_id"]}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site", action="append", required=True)
    a = p.parse_args()
    соед = sqlite3.connect(БАЗА)
    соед.row_factory = sqlite3.Row
    д = проекция(соед)
    print(f"проекция {д['build_id']}: {д['count']} записей, "
          f"без постера {д['without_poster']}, ленты: "
          + ", ".join(f"{k}={len(v)}" for k, v in д["feeds"].items()))
    плохо = 0
    for витрина in a.site:
        р = выложить(витрина, д)
        плохо += 0 if р["ok"] else 1
        print(json.dumps(р, ensure_ascii=False))
    return 1 if плохо else 0


if __name__ == "__main__":
    sys.exit(main())
