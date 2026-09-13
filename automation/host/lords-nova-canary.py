#!/usr/bin/env python3
"""Выкладка артефакта nova на ОДНУ витрину и штатный откат.

## Почему отдельная процедура

`deploy-nova-lords.sh` раскатывает витрину целиком: каталог, манифест, юнит и
nginx. Приёмщик заявок (`lords-deploy-broker`) запускает полную отрисовку
статического релиза — часы работы. Ни то, ни другое не выражает «поменять
артефакт рантайма на одной витрине и посмотреть», а именно это и есть canary.

## Что делает и чего не делает

Делает ровно три записи:

1. кладёт артефакт в `/srv/lords/.frontend/lords-frontend.py`;
2. переписывает манифест ОДНОЙ названной витрины;
3. перезапускает юнит этой витрины.

Не трогает: nginx, сертификаты, DNS, каталоги содержимого, юниты и манифесты
соседних витрин.

## Почему смена общего файла не меняет соседей

Артефакт один на шесть витрин, и подменить его — значит подменить код у всех.
Но ЧТО этот код делает, решает манифест витрины: `design_version` выбирает
ветку отрисовки. Витрина, чей манифест остался на 1.0.2, исполняет прежнюю
ветку и отдаёт прежние байты — это проверено побайтовым сличением
(`artifacts/.../legacy-byte-identity.json`), а не объявлено.

## Откат

Прежний артефакт и прежний манифест сохраняются ДО первой записи, в каталог
`.rollback/<метка>/`. Откат возвращает оба файла и перезапускает юнит. Если
сохранить точку отката не удалось, выкладка не начинается: выкладка без
возврата — это не выкладка, а замена без права передумать.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ФРОНТ = Path("/srv/lords/.frontend")
АРТЕФАКТ = ФРОНТ / "lords-frontend.py"
ОТКАТЫ = ФРОНТ / ".rollback"

#: Витрины, которые процедура согласна трогать, и всё, что о них нужно знать.
#: Расширять перечень по своей инициативе нельзя: витрина, которой здесь нет,
#: не выкатывается, а получает отказ.
ВИТРИНЫ = {
    "lords-01": {"unit": "lords-nova-01.service", "domain": "lordfilm47.space",
                 "manifest": "template-manifest.json", "family": "lords",
                 "profile": "lords-general"},
}

#: Адреса, по которым проверяется здоровье витрины после перезапуска. Пустая
#: двухсотка здоровьем не считается: у страницы обязано быть тело.
ПРОБЫ = ("/healthz", "/", "/catalog/")
МИНИМУМ_ТЕЛА = 2000


class Отказ(Exception):
    """Отказ до записи либо с уже выполненным возвратом. Всегда с причиной."""


def _sha(путь: Path) -> str:
    return hashlib.sha256(путь.read_bytes()).hexdigest()


def _сейчас() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _атомарно(цель: Path, данные: bytes) -> None:
    врем = цель.with_name(цель.name + ".tmp")
    врем.write_bytes(данные)
    врем.replace(цель)


def _юнит(действие: str, юнит: str) -> tuple[bool, str]:
    try:
        р = subprocess.run(["systemctl", действие, юнит],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as ош:
        return False, str(ош)[:200]
    return р.returncode == 0, (р.stderr or р.stdout or "").strip()[:300]


def _проба(домен: str) -> dict:
    итог = {"domain": домен, "checks": [], "ok": True}
    for путь in ПРОБЫ:
        адрес = f"https://{домен}{путь}"
        запись = {"path": путь}
        try:
            запрос = urllib.request.Request(адрес, headers={"User-Agent": "nova-canary"})
            with urllib.request.urlopen(запрос, timeout=30) as ответ:
                тело = ответ.read()
                запись["status"] = ответ.status
                запись["bytes"] = len(тело)
                запись["version"] = ответ.headers.get("X-Site-Factory-Template-Version", "")
                запись["artifact"] = ответ.headers.get("X-Site-Factory-Artifact-Sha256", "")
        except (urllib.error.HTTPError, OSError) as ош:
            запись["status"] = getattr(ош, "code", -1)
            запись["error"] = str(ош)[:120]
        хорошо = запись.get("status") == 200 and (
            путь == "/healthz" or запись.get("bytes", 0) >= МИНИМУМ_ТЕЛА)
        запись["ok"] = хорошо
        итог["ok"] &= хорошо
        итог["checks"].append(запись)
    return итог


def _точка_отката(метка: str, манифест: Path) -> Path:
    каталог = ОТКАТЫ / метка
    каталог.mkdir(parents=True, exist_ok=True)
    if not АРТЕФАКТ.is_file():
        raise Отказ(f"нечего сохранять: {АРТЕФАКТ} не существует")
    shutil.copy2(АРТЕФАКТ, каталог / "lords-frontend.py")
    if манифест.is_file():
        shutil.copy2(манифест, каталог / манифест.name)
    (каталог / "point.json").write_text(json.dumps({
        "saved_at_utc": _сейчас(),
        "artifact_sha256": _sha(каталог / "lords-frontend.py"),
        "manifest": манифест.name,
        "manifest_content": json.loads(манифест.read_text(encoding="utf-8")) if манифест.is_file() else None,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return каталог


def установить(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site)
    if not витрина:
        raise Отказ(f"витрина {арг.site!r} вне перечня: {sorted(ВИТРИНЫ)}")
    источник = Path(арг.artifact)
    if not источник.is_file():
        raise Отказ(f"артефакта нет: {источник}")
    отпечаток = _sha(источник)
    if арг.expect_sha256 and арг.expect_sha256 != отпечаток:
        raise Отказ(f"отпечаток артефакта не тот: ожидался {арг.expect_sha256}, "
                    f"получен {отпечаток}")
    манифест = ФРОНТ / витрина["manifest"]

    метка = f"{_сейчас()}-{арг.site}"
    точка = _точка_отката(метка, манифест)
    прежний = json.loads((точка / "point.json").read_text(encoding="utf-8"))

    новый_манифест = {
        "schema_version": 1,
        "template_family": витрина["family"],
        "design_version": арг.design_version,
        "source_commit": арг.commit,
        "build_id": арг.build_id,
        "artifact_sha256": отпечаток,
        "profile": витрина["profile"],
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # Манифест пишется ПЕРВЫМ: рантайм читает его при старте, и артефакт без
    # манифеста своей версии поднялся бы на прежней ветке отрисовки.
    _атомарно(манифест, (json.dumps(новый_манифест, ensure_ascii=False, indent=2) + "\n").encode())
    _атомарно(АРТЕФАКТ, источник.read_bytes())
    АРТЕФАКТ.chmod(0o755)

    ок, вывод = _юнит("restart", витрина["unit"])
    time.sleep(4)
    проба = _проба(витрина["domain"]) if ок else {"ok": False, "checks": [],
                                                  "domain": витрина["domain"]}
    запись = {
        "action": "install", "site": арг.site, "unit": витрина["unit"],
        "domain": витрина["domain"], "rollback_point": str(точка),
        "artifact_sha256": отпечаток, "previous_artifact_sha256": прежний["artifact_sha256"],
        "manifest": новый_манифест, "previous_manifest": прежний["manifest_content"],
        "restart_ok": ок, "restart_output": вывод, "health": проба,
        "at_utc": _сейчас(),
    }
    if not ок or not проба["ok"]:
        # Возврат немедленный и до отчёта об успехе: витрина, которую подняли
        # и оставили нездоровой, хуже витрины, которую не трогали.
        _атомарно(АРТЕФАКТ, (точка / "lords-frontend.py").read_bytes())
        АРТЕФАКТ.chmod(0o755)
        if прежний["manifest_content"] is not None:
            _атомарно(манифест, (json.dumps(прежний["manifest_content"],
                                            ensure_ascii=False, indent=2) + "\n").encode())
        возврат_ок, возврат_вывод = _юнит("restart", витрина["unit"])
        time.sleep(4)
        запись["auto_rolled_back"] = True
        запись["rollback_restart_ok"] = возврат_ок
        запись["rollback_output"] = возврат_вывод
        запись["health_after_rollback"] = _проба(витрина["domain"])
        запись["verdict"] = "ROLLED_BACK_NO_CHANGE"
    else:
        запись["verdict"] = "DEPLOYED_AND_VERIFIED"
    _напечатать(запись, арг.record)
    return 0 if запись["verdict"] == "DEPLOYED_AND_VERIFIED" else 1


def откатить(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site)
    if not витрина:
        raise Отказ(f"витрина {арг.site!r} вне перечня: {sorted(ВИТРИНЫ)}")
    точка = Path(арг.point)
    if not (точка / "lords-frontend.py").is_file() or not (точка / "point.json").is_file():
        raise Отказ(f"точка отката неполна: {точка}")
    сохранено = json.loads((точка / "point.json").read_text(encoding="utf-8"))
    манифест = ФРОНТ / витрина["manifest"]
    было = _sha(АРТЕФАКТ) if АРТЕФАКТ.is_file() else ""

    if сохранено.get("manifest_content") is not None:
        _атомарно(манифест, (json.dumps(сохранено["manifest_content"],
                                        ensure_ascii=False, indent=2) + "\n").encode())
    _атомарно(АРТЕФАКТ, (точка / "lords-frontend.py").read_bytes())
    АРТЕФАКТ.chmod(0o755)
    ок, вывод = _юнит("restart", витрина["unit"])
    time.sleep(4)
    запись = {
        "action": "rollback", "site": арг.site, "point": str(точка),
        "artifact_before_rollback": было,
        "artifact_after_rollback": _sha(АРТЕФАКТ),
        "expected_artifact": сохранено["artifact_sha256"],
        "restored_manifest": сохранено.get("manifest_content"),
        "restart_ok": ок, "restart_output": вывод,
        "health": _проба(витрина["domain"]), "at_utc": _сейчас(),
    }
    запись["verdict"] = (
        "ROLLED_BACK_VERIFIED"
        if (запись["artifact_after_rollback"] == сохранено["artifact_sha256"]
            and ок and запись["health"]["ok"]) else "ROLLBACK_FAILED")
    _напечатать(запись, арг.record)
    return 0 if запись["verdict"] == "ROLLED_BACK_VERIFIED" else 1


def состояние(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site) or {}
    запись = {
        "action": "status", "site": арг.site,
        "artifact_sha256": _sha(АРТЕФАКТ) if АРТЕФАКТ.is_file() else "",
        "manifest": json.loads((ФРОНТ / витрина["manifest"]).read_text(encoding="utf-8"))
        if витрина and (ФРОНТ / витрина["manifest"]).is_file() else None,
        "health": _проба(витрина["domain"]) if витрина else None,
        "rollback_points": sorted(п.name for п in ОТКАТЫ.glob("*") if п.is_dir()),
    }
    _напечатать(запись, арг.record)
    return 0


def _напечатать(запись: dict, куда: str | None) -> None:
    текст = json.dumps(запись, ensure_ascii=False, indent=1)
    if куда:
        Path(куда).parent.mkdir(parents=True, exist_ok=True)
        Path(куда).write_text(текст + "\n", encoding="utf-8")
    print(текст)


def main(argv=None) -> int:
    разбор = argparse.ArgumentParser(description=__doc__)
    под = разбор.add_subparsers(dest="команда", required=True)

    у = под.add_parser("install", help="выложить артефакт на витрину")
    у.add_argument("--site", required=True)
    у.add_argument("--artifact", required=True)
    у.add_argument("--expect-sha256", default="")
    у.add_argument("--design-version", required=True)
    у.add_argument("--commit", required=True)
    у.add_argument("--build-id", required=True)
    у.add_argument("--record")
    у.set_defaults(функция=установить)

    о = под.add_parser("rollback", help="вернуть сохранённую точку")
    о.add_argument("--site", required=True)
    о.add_argument("--point", required=True)
    о.add_argument("--record")
    о.set_defaults(функция=откатить)

    с = под.add_parser("status", help="что сейчас установлено")
    с.add_argument("--site", required=True)
    с.add_argument("--record")
    с.set_defaults(функция=состояние)

    арг = разбор.parse_args(argv)
    try:
        return арг.функция(арг)
    except Отказ as ош:
        print(f"ОТКАЗ: {ош}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
