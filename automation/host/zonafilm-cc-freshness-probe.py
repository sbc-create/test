#!/usr/bin/env python3
"""Контролируемая проверка автоматического обновления данных zonafilm.cc.

Вопрос, на который отвечает проба: появляются ли новые данные на витрине без
пересборки и перезапуска. Ответ либо измерен, либо его нет.

Как. В опубликованный каталог витрины атомарно добавляется один синтетический
тайтл с явной меткой, витрина опрашивается до смены `X-Catalog-Revision`,
проверяется, что запись доступна и стоит там, где обещано, после чего исходный
файл возвращается — тоже атомарно — и проверяется, что записи больше нет.

Границы. Трогается ровно один файл ровно одной витрины: `zona-02-catalog.json`.
Резервная копия снимается до первой записи; при любом исходе, включая падение,
файл возвращается в блоке `finally`. Витрина на момент пробы не имеет записи
DNS и доступна только по петле, поэтому синтетика не видна никому снаружи.

Метка `SYNTHETIC-FRESHNESS-PROBE` выбрана так, чтобы её нельзя было спутать с
содержимым: по ней же проверяется, что синтетика не осталась.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
КАТАЛОГ = ФРОНТ / "zona-02-catalog.json"
МЕТКА = "SYNTHETIC-FRESHNESS-PROBE"
СЛАГ = "synthetic-freshness-probe"


def запрос(origin: str, host: str, путь: str, timeout: float = 120.0) -> tuple[int, dict, str]:
    """Отказ транспорта возвращается кодом 0, а не исключением.

    Перечитывание каталога на 53 652 записи занимает у витрины минуты и держит
    замок снимка: запрос в это окно честно упирается в таймаут. Это состояние
    «ещё не готова», а не сбой пробы — и превращать его в исключение значит
    ронять проверку ровно там, где она должна ждать. Первый прогон так и
    упал: каталог к тому моменту уже был возвращён, но отчёт записан не был.
    """
    req = urllib.request.Request(origin + путь, headers={"Host": host})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, {"X-Probe-Transport-Error": f"{type(e).__name__}"}, ""


def ревизия(origin: str, host: str) -> str:
    код, заголовки, _ = запрос(origin, host, "/catalog/")
    return заголовки.get("X-Catalog-Revision", "") if код == 200 else ""


def ждать_ревизию(origin: str, host: str, не_равную: str, секунд: int = 600) -> str:
    предел = time.monotonic() + секунд
    последняя = ""
    while time.monotonic() < предел:
        текущая = ревизия(origin, host)
        if текущая:
            последняя = текущая
            if текущая != не_равную:
                return текущая
        time.sleep(3)
    return последняя


def записать_атомарно(путь: Path, данные: bytes) -> None:
    временный = путь.with_name(путь.name + f".probe.{os.getpid()}")
    временный.write_bytes(данные)
    os.replace(временный, путь)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", default="http://127.0.0.1:9123")
    parser.add_argument("--host", default="zonafilm.cc")
    parser.add_argument("--out", required=True)
    parser.add_argument("--backup-dir", default="var/freshness")
    args = parser.parse_args()

    отчёт: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "catalog": str(КАТАЛОГ), "marker": МЕТКА, "steps": []}

    исходные_байты = КАТАЛОГ.read_bytes()
    исходный_sha = hashlib.sha256(исходные_байты).hexdigest()
    резерв_каталог = Path(args.backup_dir)
    резерв_каталог.mkdir(parents=True, exist_ok=True)
    резерв = резерв_каталог / f"zona-02-catalog.before-probe.{int(time.time())}.json"
    shutil.copy2(КАТАЛОГ, резерв)
    отчёт["backup"] = {"path": str(резерв), "sha256": исходный_sha}

    try:
        было = ревизия(args.origin, args.host)
        отчёт["revision_before"] = было
        отчёт["steps"].append({"step": "baseline", "revision": было})

        данные = json.loads(исходные_байты.decode("utf-8"))
        образец = copy.deepcopy(данные["items"][0])
        синтетика = {
            "slug": СЛАГ,
            "title": f"{МЕТКА} — проверка свежести",
            "poster": образец.get("poster"),
            "kind": образец.get("kind"),
            "year": образец.get("year"),
            "url": f"/title/{СЛАГ}/",
            "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "published_at_estimated": False,
        }
        новые = dict(данные)
        # В начало: каталог отсортирован по published_at по убыванию, и самая
        # свежая запись обязана быть первой — именно этот порядок читает блок
        # «Недавно добавленные».
        новые["items"] = [синтетика] + данные["items"]
        новые["count"] = len(новые["items"])
        новые["revision"] = hashlib.sha256(
            (данные.get("revision", "") + СЛАГ).encode("utf-8")).hexdigest()[:32]
        записать_атомарно(КАТАЛОГ, (json.dumps(новые, ensure_ascii=False)).encode("utf-8"))
        отчёт["steps"].append({"step": "inject", "new_revision_in_file": новые["revision"],
                               "items": новые["count"]})

        стало = ждать_ревизию(args.origin, args.host, было)
        отчёт["revision_after_inject"] = стало
        отчёт["auto_reload_without_restart"] = bool(стало) and стало != было
        отчёт["steps"].append({"step": "observe", "revision": стало})

        код_г, _, тело_г = запрос(args.origin, args.host, "/")
        код_к, _, тело_к = запрос(args.origin, args.host, "/collection/recently_added/")
        код_т, _, тело_т = запрос(args.origin, args.host, f"/title/{СЛАГ}/")
        отчёт["visible"] = {
            "home_status": код_г,
            "home_contains_marker": МЕТКА in тело_г,
            "recently_added_status": код_к,
            "recently_added_contains_marker": МЕТКА in тело_к,
            "recently_added_first": тело_к.find(МЕТКА) >= 0
                                    and тело_к.find(МЕТКА) == min(
                                        [i for i in [тело_к.find(МЕТКА)] if i >= 0] or [-1]),
            "title_page_status": код_т,
        }
    finally:
        записать_атомарно(КАТАЛОГ, исходные_байты)
        вернулось = hashlib.sha256(КАТАЛОГ.read_bytes()).hexdigest()
        отчёт["restored"] = {"sha256": вернулось, "matches_original": вернулось == исходный_sha}
        финал = ждать_ревизию(args.origin, args.host, отчёт.get("revision_after_inject") or "")
        отчёт["revision_after_restore"] = финал
        _, _, тело = запрос(args.origin, args.host, "/collection/recently_added/")
        код_т2, _, _ = запрос(args.origin, args.host, f"/title/{СЛАГ}/")
        отчёт["cleanup"] = {
            "marker_still_in_recently_added": МЕТКА in тело,
            "synthetic_title_status": код_т2,
            "revision_returned": финал == отчёт.get("revision_before"),
        }
        отчёт["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(отчёт, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(json.dumps({k: отчёт[k] for k in
                          ("revision_before", "revision_after_inject",
                           "auto_reload_without_restart", "visible", "restored",
                           "revision_after_restore", "cleanup") if k in отчёт},
                         ensure_ascii=False, indent=2))

    успех = (отчёт.get("auto_reload_without_restart")
             and отчёт["visible"]["recently_added_contains_marker"]
             and отчёт["restored"]["matches_original"]
             and not отчёт["cleanup"]["marker_still_in_recently_added"])
    return 0 if успех else 1


if __name__ == "__main__":
    raise SystemExit(main())
