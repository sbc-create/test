#!/usr/bin/env python3
"""Привести копию реестра приложения Yummy к решению владельца по yummyani.biz.

Зачем отдельный инструмент, а не правка руками. У семейства Yummy ДВА реестра
режима индексации, и оба настоящие:

* реестр площадки ячеек (`/srv/lords/.frontend/indexing-core-registry.json`) —
  его пишет штатная операция `indexing-core` фабрики, и в нём yummyani.biz
  стоит `OPEN`, `policy_revision 6`, `owner_authorization_id`
  52799b26-3ca6-42f1-912b-63ac2bcfa9cc с 2026-10-05. Он управляет слоем
  ячейки: заголовком `X-Robots-Tag` и `robots.txt`;
* реестр проекта приложения
  (`/srv/sites/yummyani-staging/runtime/indexing-core-registry.json`) — его
  читает предпусковая проверка `deploy/staging/indexability-preflight.sh`. В
  нём запись yummyani.biz осталась `CLOSED`, `policy_revision 1`,
  `BOOTSTRAP-CLOSED` с 20 сентября.

Из-за этого расхождения выпуск отказывается: кандидат отдаёт
`SEO_INDEXING_ENABLED=true` (правильно, домен открыт решением владельца), а
копия приложения говорит «закрыт». Штатная операция фабрики эту копию НЕ
пишет — она пишет реестр площадки, и 05.10 свою работу уже сделала.

Что делает этот инструмент: переносит в копию приложения ровно одно решение —
по yummyani.biz, — и берёт идентификатор разрешения ИЗ ЯКОРЯ СОГЛАСИЯ
владельца, а не из аргумента. Чего он не делает: не создаёт записей, не
трогает другие домены, не придумывает идентификатор, не меняет режим на
закрытие и ничего не пишет без `--apply`.

    python3 automation/host/yummy-staging-registry-open-biz.py            # план
    python3 automation/host/yummy-staging-registry-open-biz.py --apply    # запись
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ДОМЕН = "yummyani.biz"
РЕЕСТР = Path("/srv/sites/yummyani-staging/runtime/indexing-core-registry.json")
ЯКОРЬ = Path(f"/var/lib/site-cells/owner-consent/{ДОМЕН}.json")
РЕВИЗИЯ = 6
ПРОВЕРКА = Path("/srv/sites/yummyani-staging/repo/deploy/staging/"
                "indexability-preflight.sh")


def разрешение() -> str:
    """Идентификатор разрешения — только из якоря согласия владельца."""
    if not ЯКОРЬ.is_file():
        raise SystemExit(f"якоря согласия нет: {ЯКОРЬ}. Без него открывать "
                         "индексацию нечем, и придумать идентификатор нельзя")
    д = json.loads(ЯКОРЬ.read_text(encoding="utf-8"))
    if д.get("domain") != ДОМЕН:
        raise SystemExit(f"якорь принадлежит домену {д.get('domain')!r}, а не "
                         f"{ДОМЕН}: чужое согласие не применяется")
    if д.get("authorized") is not True:
        raise SystemExit(f"в якоре authorized = {д.get('authorized')!r}; "
                         "разрешением считается только булево true")
    ид = str(д.get("id") or "").strip()
    if not ид:
        raise SystemExit("якорь не называет идентификатора разрешения")
    return ид


def главное(аргв=None) -> int:
    р = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--apply", action="store_true",
                   help="записать; без него только план")
    опции = р.parse_args(аргв)

    ид = разрешение()
    д = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    домены = д.get("domains") or {}
    если_нет = ДОМЕН not in домены
    if если_нет:
        raise SystemExit(f"в {РЕЕСТР} нет записи о {ДОМЕН}: отсутствие записи "
                         "означает отсутствие решения владельца о домене, и "
                         "создавать её этот инструмент не будет")
    было = dict(домены[ДОМЕН])
    print(f"якорь согласия: {ЯКОРЬ} → id {ид}")
    print(f"реестр приложения: {РЕЕСТР}")
    print(f"  было:  desired_state={было.get('desired_state')} "
          f"policy_revision={было.get('policy_revision')} "
          f"owner_authorization_id={было.get('owner_authorization_id')}")
    print(f"  станет: desired_state=OPEN policy_revision={РЕВИЗИЯ} "
          f"owner_authorization_id={ид}")
    for поле in ("exact_domain", "tenant_id", "compose_service"):
        print(f"  не меняется: {поле}={было.get(поле)!r}")
    прочие = [к for к in домены if к != ДОМЕН]
    print(f"  прочие записи не трогаются: {прочие}")

    if было.get("desired_state") == "OPEN" and \
            str(было.get("owner_authorization_id")) == ид:
        print("запись уже соответствует решению — делать нечего")
        return 0

    if not опции.apply:
        print("это план; для записи — тот же вызов с --apply")
        return 0

    отметка = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    копия = РЕЕСТР.with_suffix(f".json.bak.{отметка}")
    shutil.copy2(РЕЕСТР, копия)
    print(f"копия прежнего файла: {копия}")

    запись = домены[ДОМЕН]
    запись["desired_state"] = "OPEN"
    запись["policy_revision"] = РЕВИЗИЯ
    запись["owner_authorization_id"] = ид
    прежняя_причина = str(запись.get("reason") or "").strip()
    запись["reason"] = (
        f"owner-approved OPEN; решение {ид} от 2026-10-05, перенесено в копию "
        f"проекта приложения {отметка}"
        + (f"; прежняя причина: {прежняя_причина}" if прежняя_причина else ""))
    РЕЕСТР.write_text(json.dumps(д, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    print("запись обновлена")

    if ПРОВЕРКА.is_file():
        print("проверяю штатной предпусковой проверкой (однофайловый путь):")
        г = subprocess.run(["bash", str(ПРОВЕРКА)], capture_output=True,
                           text=True, timeout=300)
        хвост = ((г.stdout or "") + (г.stderr or "")).strip().splitlines()
        for строка in хвост[-8:]:
            print("   " + строка)
        print(f"   код возврата {г.returncode}")
    print("откат: вернуть файл из копии рядом")
    return 0


if __name__ == "__main__":
    raise SystemExit(главное())
