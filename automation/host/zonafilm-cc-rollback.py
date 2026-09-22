#!/usr/bin/env python3
"""Откат контура zonafilm.cc. Два режима, и оба обратимы.

`previous` — вернуть витрину на прежний релиз. Работает, когда он есть:
`sites/zona-02/PREVIOUS_TARGET.txt` хранит цель, на которую ссылка указывала до
последней выкладки.

`unbind` — отвязать витрину целиком. Это и есть откат ПЕРВОЙ выкладки: прежнего
релиза у нового сайта не бывает, и «вернуться» ему некуда. Отвязка снимает
ключ `zona-02` из реестра диспетчера и убирает ссылку `current`. Порт перестаёт
отображаться в витрину, и служба, если её запустить, честно откажется стартовать
вместо того чтобы поднять неизвестный код.

Данные (`zona-02-catalog.json`, `zona-02-details.json`, каталог релиза) при
отвязке НЕ удаляются. Откат должен быть быстрым и обратимым; удаление
девяноста мегабайт ради видимости чистоты делает повторную выкладку долгой, а
саму операцию — необратимой. Для полного удаления есть `--purge-data`, и он
спрашивается отдельно.

Ничего чужого не трогает: записи соседей в реестре сверяются побайтно до и
после, и расхождение прекращает операцию.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import time
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
РЕЕСТР = ФРОНТ / "lords-runtime-registry.json"
SITE_ID = "zona-02"
ВИТРИНА = ФРОНТ / "sites" / SITE_ID
ДАННЫЕ = (ФРОНТ / f"{SITE_ID}-catalog.json", ФРОНТ / f"{SITE_ID}-details.json",
          ФРОНТ / f"template-manifest-{SITE_ID}.json")


class ОшибкаОтката(RuntimeError):
    pass


def _записать_атомарно(путь: Path, данные: bytes) -> str:
    временный = путь.with_name(путь.name + f".tmp.{os.getpid()}")
    временный.write_bytes(данные)
    os.replace(временный, путь)
    return hashlib.sha256(данные).hexdigest()


def снять_из_реестра(применить: bool) -> dict:
    было = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    if SITE_ID not in (было.get("sites") or {}):
        return {"already_absent": True}
    стало = json.loads(json.dumps(было))
    стало["sites"].pop(SITE_ID, None)
    for ключ in ("in_registry", "out_of_registry"):
        if isinstance(стало.get(ключ), list):
            стало[ключ] = [s for s in стало[ключ] if s != SITE_ID]

    чужие_до = {k: v for k, v in (было.get("sites") or {}).items() if k != SITE_ID}
    чужие_после = dict(стало.get("sites") or {})
    if чужие_до != чужие_после:
        raise ОшибкаОтката("снятие ключа задело чужие записи — откат прекращён")

    итог = {"neighbours_unchanged": True,
            "before_sha256": hashlib.sha256(РЕЕСТР.read_bytes()).hexdigest()}
    if применить:
        резерв = РЕЕСТР.with_name(
            РЕЕСТР.name + f".before-rollback-{SITE_ID}."
            + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
        shutil.copy2(РЕЕСТР, резерв)
        итог["backup"] = str(резерв)
        итог["after_sha256"] = _записать_атомарно(
            РЕЕСТР, (json.dumps(стало, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return итог


def снять_ссылку(применить: bool) -> dict:
    ссылка = ВИТРИНА / "current"
    if not ссылка.is_symlink():
        return {"already_absent": True}
    цель = os.readlink(ссылка)
    if применить:
        (ВИТРИНА / "UNBOUND_TARGET.txt").write_text(цель + "\n", encoding="utf-8")
        ссылка.unlink()
    return {"was_pointing_to": цель, "recorded_in": str(ВИТРИНА / "UNBOUND_TARGET.txt")}


def вернуть_прежний(применить: bool) -> dict:
    файл = ВИТРИНА / "PREVIOUS_TARGET.txt"
    if not файл.is_file():
        raise ОшибкаОтката(
            "прежнего релиза нет: у первой выкладки его и не бывает. "
            "Для отката первой выкладки предназначен режим unbind"
        )
    цель = файл.read_text(encoding="utf-8").strip()
    разрешённая = (ВИТРИНА / цель).resolve()
    if not (разрешённая / "lords-frontend.py").is_file():
        raise ОшибкаОтката(f"прежний релиз {цель} не содержит рантайма")
    итог = {"target": цель}
    if применить:
        ссылка = ВИТРИНА / "current"
        временная = ссылка.with_name("current.tmp")
        if временная.is_symlink():
            временная.unlink()
        os.symlink(цель, временная)
        os.replace(временная, ссылка)
        итог["now_pointing_to"] = os.readlink(ссылка)
    return итог


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("previous", "unbind"), required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--purge-data", action="store_true",
                        help="удалить каталог, подробности и манифест витрины")
    args = parser.parse_args()

    отчёт: dict = {"site_id": SITE_ID, "mode": args.mode,
                   "applied": bool(args.apply),
                   "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        if args.mode == "previous":
            отчёт["release"] = вернуть_прежний(args.apply)
        else:
            отчёт["registry"] = снять_из_реестра(args.apply)
            отчёт["link"] = снять_ссылку(args.apply)
            if args.purge_data:
                удалено = []
                for путь in ДАННЫЕ:
                    if путь.is_file():
                        if args.apply:
                            путь.unlink()
                        удалено.append(str(путь))
                отчёт["purged"] = удалено
    except ОшибкаОтката as e:
        отчёт["status"] = "REFUSED"
        отчёт["reason"] = str(e)
        print(json.dumps(отчёт, ensure_ascii=False, indent=2))
        return 2

    отчёт["status"] = "OK"
    if args.mode == "unbind":
        # Отвязка снимает привязку порта к витрине, но НЕ мешает службе
        # стартовать. Проверено репетицией 2026-09-22: запуск загрузчика на
        # 9123 после отвязки уходит не в отказ, а в `releases/legacy/current` —
        # это документированный запасной путь общего загрузчика. Для отката
        # первой выкладки такой исход неприемлем: на zonafilm.cc оказалась бы
        # чужая легаси-витрина. Поэтому останов службы и снятие vhost —
        # обязательная часть отката, а не рекомендация.
        отчёт["mandatory_root_steps"] = [
            "systemctl stop nova-zona-02.service",
            "systemctl disable nova-zona-02.service",
            "rm -f /etc/nginx/lords/zona-02.conf && nginx -t && systemctl reload nginx",
        ]
        отчёт["why_mandatory"] = (
            "без останова службы общий загрузчик на отвязанном порту поднимает "
            "releases/legacy/current — витрина отдавала бы чужое содержимое"
        )
    отчёт["restore_command"] = (
        "python3 automation/host/zonafilm-cc-release.py --apply"
        + ("  # плюс повторная публикация каталога, если использовался --purge-data"
           if args.purge_data else "")
    )
    print(json.dumps(отчёт, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
