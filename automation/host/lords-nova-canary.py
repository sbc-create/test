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
                 "profile": "lords-general", "port": 9110},
    "lords-02": {"unit": "nova-lords-02.service", "domain": "lordserial33.biz",
                 "manifest": "template-manifest-lords-02.json", "family": "lords",
                 "profile": "lords-new", "port": 9111},
    "lords-03": {"unit": "nova-lords-03.service", "domain": "1lordserials1.online",
                 "manifest": "template-manifest-lords-03.json", "family": "lords",
                 "profile": "lords-curated", "port": 9112},
    "zona-01": {"unit": "nova-zona-01.service", "domain": "zonafilm.space",
                "manifest": "template-manifest-zona-01.json", "family": "zona",
                "profile": "zona-general", "port": 9120},
}

#: Каталоги, из которых разрешено брать артефакт. Путь вне этого списка —
#: отказ. Иначе привилегированный запуск с `--artifact /любой/файл` записывает
#: произвольные байты в файл, который исполняет каждая витрина парка.
РАЗРЕШЁННЫЕ_ИСТОЧНИКИ = (
    Path("/home/claude/wt-lords-r2/automation/host"),
    Path("/home/claude/wt-lords-default-episode-01/automation/host"),
    Path("/srv/site-factory/repo/automation/host"),
    ФРОНТ / ".rollback",
)


def проверить_источник(путь: Path) -> Path:
    """Артефакт обязан быть обычным файлом из разрешённого каталога.

    Проверки идут по РАЗРЕШЁННОМУ пути (`resolve`), а не по написанному: иначе
    `.../automation/host/../../../etc/passwd` проходит проверку префикса, а
    символическая ссылка из разрешённого каталога уводит куда угодно. Оба
    случая закрываются одним сравнением после разрешения.
    """
    if путь.is_symlink():
        raise Отказ(f"артефакт — символическая ссылка: {путь}")
    разрешённый = путь.resolve(strict=False)
    if not разрешённый.is_file():
        raise Отказ(f"артефакта нет или это не обычный файл: {разрешённый}")
    for корень in РАЗРЕШЁННЫЕ_ИСТОЧНИКИ:
        база = корень.resolve(strict=False)
        if разрешённый == база or база in разрешённый.parents:
            return разрешённый
    raise Отказ(f"артефакт вне разрешённых каталогов: {разрешённый}; "
                f"разрешены {[str(к) for к in РАЗРЕШЁННЫЕ_ИСТОЧНИКИ]}")


def доказать_цепочку(витрина: str, описание: dict) -> dict:
    """Сверка «сайт → домен → nginx → порт → юнит» с живой конфигурацией.

    Имя юнита в таблице выше — не источник истины, а ОЖИДАНИЕ. Истина лежит в
    nginx и systemd, и перед перезапуском ожидание обязано с ней совпасть.
    Догадка «сайт lords-01 обслуживается юнитом lords-01.service» выглядит
    очевидной и неверна: этот юнит слушает 9101 и публично не проксируется, а
    домен отдаёт `lords-nova-01.service` на 9110.
    """
    import importlib.util
    # parents[2], а не [1]: файл лежит в automation/host/, и один уровень вверх
    # даёт automation/, где никаких scripts/ нет. Ошибка на единицу в пути к
    # доказателю превращала бы обязательную сверку в отказ на ровном месте.
    модуль_путь = Path(__file__).resolve().parents[2] / "scripts" / "prove_serving_chain.py"
    if not модуль_путь.is_file():
        raise Отказ(f"нет доказателя цепочки: {модуль_путь}")
    спец = importlib.util.spec_from_file_location("prove_serving_chain", модуль_путь)
    доказатель = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(доказатель)
    цепь = доказатель.цепочка(описание["domain"], доказатель.юниты())
    if цепь.get("upstream_port") != описание["port"]:
        raise Отказ(f"{витрина}: nginx ведёт домен {описание['domain']} на порт "
                    f"{цепь.get('upstream_port')}, ожидался {описание['port']}")
    if цепь.get("unit") != описание["unit"]:
        raise Отказ(f"{витрина}: домен {описание['domain']} обслуживает юнит "
                    f"{цепь.get('unit')!r}, а не {описание['unit']!r}")
    ожидаемый_манифест = str(ФРОНТ / описание["manifest"])
    if цепь.get("manifest_path") != ожидаемый_манифест:
        raise Отказ(f"{витрина}: юнит читает манифест {цепь.get('manifest_path')!r}, "
                    f"ожидался {ожидаемый_манифест!r}")
    if цепь.get("executable") != str(АРТЕФАКТ):
        raise Отказ(f"{витрина}: юнит исполняет {цепь.get('executable')!r}, "
                    f"а не {АРТЕФАКТ}")
    return цепь

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


def _замок_витрины(сайт: str):
    """Fail-closed exclusive lease for one site's frontend install.

    Prevents two worktrees from racing writes to the shared lords-frontend.py.
    """
    import fcntl
    ОТКАТЫ.mkdir(parents=True, exist_ok=True)
    путь = ОТКАТЫ / f".lock-{сайт}"
    дескриптор = open(путь, "a+", encoding="utf-8")
    try:
        fcntl.flock(дескриптор.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as ош:
        дескриптор.close()
        raise Отказ(f"витрина {сайт} уже занята другим install (lease {путь})") from ош
    return дескриптор


def _проверить_player_contract(источник: Path) -> None:
    """Refuse install when full-bleed-v1 player contract is absent."""
    текст = источник.read_text(encoding="utf-8", errors="replace")
    нужно = (
        'data-player-layout-contract="full-bleed-v1"',
        "fitPlayerTree",
        "ensureLayoutObserver",
        "[data-player-layout-contract=\"full-bleed-v1\"] iframe",
    )
    нет = [с for с in нужно if с not in текст]
    if нет:
        raise Отказ("player layout contract missing from artifact: " + "; ".join(нет))


def установить(арг) -> int:
    витрина = ВИТРИНЫ.get(арг.site)
    if not витрина:
        raise Отказ(f"витрина {арг.site!r} вне перечня: {sorted(ВИТРИНЫ)}")
    источник = проверить_источник(Path(арг.artifact))
    отпечаток = _sha(источник)
    # Отпечаток сверяется ДО первой записи и обязателен. Прежде проверка была
    # условной (`if арг.expect_sha256`), то есть запуск без флага устанавливал
    # что угодно: единственное, что отличало артефакт от произвольного файла,
    # можно было просто не указать.
    if арг.expect_sha256 != отпечаток:
        raise Отказ(f"отпечаток артефакта не тот: ожидался {арг.expect_sha256}, "
                    f"получен {отпечаток}")
    _проверить_player_contract(источник)
    замок = _замок_витрины(арг.site)
    try:
        return _установить_под_замком(арг, витрина, источник, отпечаток)
    finally:
        import fcntl
        fcntl.flock(замок.fileno(), fcntl.LOCK_UN)
        замок.close()


def _установить_под_замком(арг, витрина: dict, источник: Path, отпечаток: str) -> int:
    # Юнит определяется по живым nginx и systemd, а не по таблице. Совпадение
    # не удостоверено — выкладки не будет.
    цепь = доказать_цепочку(арг.site, витрина)
    манифест = ФРОНТ / витрина["manifest"]

    # Concurrent overwrite detector: if disk bytes changed since caller measured
    # expect-sha of previous install intent, still proceed with our artifact but
    # record the drift for the operator.
    было_на_диске = _sha(АРТЕФАКТ) if АРТЕФАКТ.is_file() else ""

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
        "source_dirty": False,
        "domain": витрина["domain"],
        "player_layout_contract": "full-bleed-v1",
    }
    # Манифест пишется ПЕРВЫМ: рантайм читает его при старте, и артефакт без
    # манифеста своей версии поднялся бы на прежней ветке отрисовки.
    _атомарно(манифест, (json.dumps(новый_манифест, ensure_ascii=False, indent=2) + "\n").encode())
    манифест.chmod(0o644)
    _атомарно(АРТЕФАКТ, источник.read_bytes())
    АРТЕФАКТ.chmod(0o755)

    после = _sha(АРТЕФАКТ)
    if после != отпечаток:
        raise Отказ(f"CONCURRENT_DEPLOYMENT_DETECTED: disk sha {после} != staged {отпечаток}")

    defer = bool(getattr(арг, "no_restart", False))
    if defer:
        запись = {
            "action": "install", "site": арг.site, "unit": витрина["unit"],
            "domain": витрина["domain"], "rollback_point": str(точка),
            "artifact_sha256": отпечаток, "previous_artifact_sha256": прежний["artifact_sha256"],
            "disk_sha_before_write": было_на_диске,
            "manifest": новый_манифест, "previous_manifest": прежний["manifest_content"],
            "restart_ok": None, "restart_deferred": True,
            "restart_output": "deferred: --no-restart; owner must restart unit",
            "health": {"ok": None, "note": "not probed; process still stale until restart"},
            "proven_chain": {к: цепь.get(к) for к in
                             ("nginx_config", "upstream_port", "unit", "executable",
                              "manifest_path", "verdict")},
            "at_utc": _сейчас(),
            "verdict": "STAGED_AWAITING_OWNER_RESTART",
            "player_layout_contract": "full-bleed-v1",
        }
        _напечатать(запись, арг.record)
        return 0

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
        "proven_chain": {к: цепь.get(к) for к in
                         ("nginx_config", "upstream_port", "unit", "executable",
                          "manifest_path", "verdict")},
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
        здоровье = _проба(витрина["domain"])
        запись["health_after_rollback"] = здоровье
        отданные = {п.get("artifact") for п in здоровье["checks"] if п.get("artifact")}
        запись["served_artifact_after_rollback"] = sorted(отданные)
        запись["baseline_fingerprint_match"] = (
            отданные == {прежний["artifact_sha256"]} if отданные else False)
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
    здоровье = _проба(витрина["domain"])
    # Отпечаток на диске и отпечаток, ОТДАННЫЙ домену, — разные утверждения.
    # Первый доказывает, что файл вернули; второй — что витрина его подхватила.
    # Возврат без второго означает, что служба ещё держит прежний код в памяти.
    отданные = {п.get("artifact") for п in здоровье["checks"] if п.get("artifact")}
    запись = {
        "action": "rollback", "site": арг.site, "point": str(точка),
        "artifact_before_rollback": было,
        "artifact_after_rollback": _sha(АРТЕФАКТ),
        "expected_artifact": сохранено["artifact_sha256"],
        "served_artifact_after_rollback": sorted(отданные),
        "restored_manifest": сохранено.get("manifest_content"),
        "restart_ok": ок, "restart_output": вывод,
        "health": здоровье, "at_utc": _сейчас(),
    }
    запись["disk_fingerprint_match"] = (
        запись["artifact_after_rollback"] == сохранено["artifact_sha256"])
    запись["served_fingerprint_match"] = (
        отданные == {сохранено["artifact_sha256"]} if отданные else False)
    запись["verdict"] = (
        "ROLLED_BACK_VERIFIED"
        if (запись["disk_fingerprint_match"] and запись["served_fingerprint_match"]
            and ок and здоровье["ok"]) else "ROLLBACK_FAILED")
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
    у.add_argument("--expect-sha256", required=True,
                   help="ожидаемый sha256 артефакта; без него установка не начинается")
    у.add_argument("--design-version", required=True)
    у.add_argument("--commit", required=True)
    у.add_argument("--build-id", required=True)
    у.add_argument("--record")
    у.add_argument("--no-restart", action="store_true",
                   help="записать файлы и манифест без перезапуска юнита")
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
