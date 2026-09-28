#!/usr/bin/env python3
"""Весь оставшийся порядок canary одной командой: Lords, затем Zona.

## Зачем это отдельный сценарий

Установка — только первый шаг из восьми. Дальше идут публичная проверка,
учебный откат, сверка восстановленного отпечатка и возврат кандидата вперёд, и
всё это для двух семейств. Просить владельца выполнить восемь команд подряд,
сверяя между ними числа глазами, — способ получить пропущенный шаг.

Здесь порядок записан целиком. Владелец запускает одну команду, получает
журнал каждого шага и вердикт. Ни один шаг не пропускается молча.

## Порядок для каждой витрины

    1. снять базовые отпечатки публичного домена
    2. установить кандидата штатным установщиком
    3. доказать, что домен отдаёт ИМЕННО новый артефакт
    4. обойти маршруты, сверить сущности, проверить границы серий
    5. откатить
    6. доказать, что вернулся ТОТ ЖЕ базовый отпечаток
    7. вернуть кандидата вперёд
    8. повторить короткую проверку

Любой провал на шагах 3-4 — немедленный откат и остановка. К Zona сценарий
переходит только после полного PASS Lords: это требование задания, а не
предпочтение.

## Чего сценарий не делает

Не трогает DNS, TLS, nginx, реестр, таймеры и соседние витрины. Не
раскатывает парк. Вся привилегированная работа — вызовы `lords-nova-canary.py`,
у которого свои проверки источника, отпечатка и доказанной цепочки.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# parents[2], а не [1]: файл лежит в automation/host/, и один уровень вверх
# даёт automation/, отчего пути складывались в automation/automation/host/.
# Та же ошибка на единицу уже была в установщике; здесь её поймал сухой
# прогон — ради этого он и нужен.
КОРЕНЬ = Path(__file__).resolve().parents[2]
УСТАНОВЩИК = КОРЕНЬ / "automation" / "host" / "lords-nova-canary.py"
ОТПЕЧАТКИ = КОРЕНЬ / "scripts" / "served_fingerprints.py"
ОБХОД = КОРЕНЬ / "scripts" / "route_crawl.py"
СУЩНОСТИ = КОРЕНЬ / "scripts" / "entity_parity.py"
АРХЕТИПЫ = КОРЕНЬ / "scripts" / "archetype_matrix.py"

ВИТРИНЫ = {
    "lords-01": {"domain": "lordfilm47.space",
                 "catalog": "/srv/lords/.frontend/lords-01-catalog.json"},
    "zona-01": {"domain": "zonafilm.space",
                "catalog": "/srv/lords/.frontend/zona-01-catalog.json"},
}

#: Пороги публичных ворот. Ноль значит ноль: одна карточка в никуда — это
#: дефект выкладки, а не допустимая доля.
ВОРОТА = {
    "ROUTE_FAILURES": 0, "SOFT_404": 0, "WRONG_ENTITY_200": 0,
    "BROKEN_INTERNAL_LINKS": 0, "REDIRECT_LOOPS": 0, "REDIRECT_CHAINS_GT1": 0,
}


def журнал(*ч) -> None:
    print("[canary-run]", *ч, flush=True)


def _запустить(команда: list, таймаут: int = 3600) -> tuple[int, str]:
    готово = subprocess.run([sys.executable, *команда], capture_output=True,
                            text=True, timeout=таймаут)
    return готово.returncode, (готово.stdout or "") + (готово.stderr or "")


def отпечатки(домен: str, метка: str, куда: Path) -> dict:
    адреса = []
    for путь in ("/", "/catalog/", "/new/"):
        адреса += ["--url", f"https://{домен}{путь}"]
    код, _ = _запустить([str(ОТПЕЧАТКИ), "--label", метка, *адреса, "--out", str(куда)])
    if код != 0 or not куда.is_file():
        return {}
    return json.loads(куда.read_text(encoding="utf-8"))


def объявленное(снимок: dict) -> dict:
    """Что домен объявил о себе. Пустой снимок — не «то же самое», а неизвестность."""
    страницы = снимок.get("pages") or []
    версии = {(с.get("declared") or {}).get("design_version") for с in страницы}
    арты = {(с.get("declared") or {}).get("artifact_sha256") for с in страницы}
    коды = {с.get("status") for с in страницы}
    return {"versions": sorted(в for в in версии if в),
            "artifacts": sorted(а for а in арты if а),
            "statuses": sorted(к for к in коды if к is not None)}


def проверить_публично(сайт: str, опис: dict, выход: Path, ярлык: str) -> dict:
    """Обход маршрутов, сверка сущностей и границы серий на ПУБЛИЧНОМ домене."""
    база = f"https://{опис['domain']}"
    итог: dict = {"base": база, "gates": {}, "ok": True}

    обход_файл = выход / f"{сайт}-{ярлык}-routes.json"
    код, вывод = _запустить([str(ОБХОД), "--base", база, "--catalog", опис["catalog"],
                             "--limit", str(опис.get("limit", 400)),
                             "--out", str(обход_файл)])
    if код == 0 and обход_файл.is_file():
        счёт = json.loads(обход_файл.read_text(encoding="utf-8"))["counters"]
        итог["routes"] = счёт
        for имя, предел in ВОРОТА.items():
            значение = счёт.get(имя, 0)
            прошло = значение <= предел
            итог["gates"][f"routes.{имя}"] = {"value": значение, "limit": предел, "ok": прошло}
            итог["ok"] &= прошло
    else:
        итог["routes_error"] = вывод[-400:]
        итог["ok"] = False

    сущ_файл = выход / f"{сайт}-{ярлык}-entities.json"
    код, вывод = _запустить([str(СУЩНОСТИ), "--base", база, "--catalog", опис["catalog"],
                             "--sample", str(опис.get("sample", 30)),
                             "--out", str(сущ_файл)])
    if код == 0 and сущ_файл.is_file():
        счёт = json.loads(сущ_файл.read_text(encoding="utf-8"))["counters"]
        итог["entities"] = счёт
        прошло = счёт.get("OK", 0) == счёт.get("CHECKED", -1)
        итог["gates"]["entities.all_ok"] = {
            "value": f'{счёт.get("OK")}/{счёт.get("CHECKED")}', "limit": "все", "ok": прошло}
        итог["ok"] &= прошло
    else:
        итог["entities_error"] = вывод[-400:]
        итог["ok"] = False

    if опис.get("archetypes") and опис.get("boundary_url"):
        арх_файл = выход / f"{сайт}-{ярлык}-archetypes.json"
        аргументы = [str(АРХЕТИПЫ), "--base", база, "--archetypes", опис["archetypes"],
                     "--boundary-url", опис["boundary_url"],
                     "--boundary-total", str(опис["boundary_total"]),
                     "--out", str(арх_файл)]
        if опис.get("points"):
            аргументы += ["--points", опис["points"]]
        код, вывод = _запустить(аргументы)
        if код == 0 and арх_файл.is_file():
            счёт = json.loads(арх_файл.read_text(encoding="utf-8"))["counters"]
            итог["archetypes"] = счёт
            прошло = (счёт.get("ARCHETYPES_OK") == счёт.get("ARCHETYPES_CHECKED")
                      and счёт.get("EPISODE_BOUNDARIES_OK") == счёт.get("EPISODE_BOUNDARIES_TOTAL")
                      and счёт.get("BEYOND_LAST_STATUS") == 404)
            итог["gates"]["archetypes.all_ok"] = {
                "value": счёт, "limit": "все и 404 за последней", "ok": прошло}
            итог["ok"] &= прошло
        else:
            итог["archetypes_error"] = вывод[-400:]
            итог["ok"] = False
    return итог


def установить(сайт: str, арг, запись: Path) -> tuple[bool, dict]:
    код, вывод = _запустить([
        str(УСТАНОВЩИК), "install", "--site", сайт,
        "--artifact", арг.artifact, "--expect-sha256", арг.expect_sha256,
        "--design-version", арг.design_version, "--commit", арг.commit,
        "--build-id", арг.build_id, "--record", str(запись)])
    отчёт = json.loads(запись.read_text(encoding="utf-8")) if запись.is_file() else {"raw": вывод[-600:]}
    return код == 0, отчёт


def откатить(сайт: str, точка: str, запись: Path) -> tuple[bool, dict]:
    код, вывод = _запустить([str(УСТАНОВЩИК), "rollback", "--site", сайт,
                             "--point", точка, "--record", str(запись)])
    отчёт = json.loads(запись.read_text(encoding="utf-8")) if запись.is_file() else {"raw": вывод[-600:]}
    return код == 0, отчёт


def сухой_прогон(сайт: str, арг, выход: Path) -> dict:
    """Всё, что проверяемо без единой записи и без root.

    Владелец вправе увидеть, что именно произойдёт, ДО того как выдаст права.
    Сухой прогон повторяет все проверки установщика — источник артефакта,
    отпечаток, доказанную цепочку «домен → nginx → порт → юнит → файл →
    манифест» — и снимает базовые отпечатки домена. Не делает ровно одного:
    не пишет.
    """
    опис = dict(ВИТРИНЫ[сайт])
    опис.update(арг.профили.get(сайт, {}))
    домен = опис["domain"]
    итог: dict = {"site": сайт, "domain": домен, "checks": [], "ok": True}

    def отметить(имя, ок, подробность=""):
        итог["checks"].append({"check": имя, "ok": bool(ок), "detail": str(подробность)[:200]})
        итог["ok"] &= bool(ок)
        журнал(f"   {'OK    ' if ок else 'ПРОВАЛ'} {имя}: {подробность}")

    журнал(f"{сайт}: сухой прогон, записей не будет")
    try:
        import importlib.util
        спец = importlib.util.spec_from_file_location("nova_canary", УСТАНОВЩИК)
        уст = importlib.util.module_from_spec(спец)
        спец.loader.exec_module(уст)
    except Exception as ош:  # noqa: BLE001
        отметить("установщик загружается", False, ош)
        return итог
    отметить("установщик загружается", True, УСТАНОВЩИК.name)

    if сайт not in уст.ВИТРИНЫ:
        отметить("витрина в перечне установщика", False, sorted(уст.ВИТРИНЫ))
        return итог
    отметить("витрина в перечне установщика", True, сайт)

    try:
        источник = уст.проверить_источник(Path(арг.artifact))
        отметить("источник артефакта разрешён", True, источник)
    except Exception as ош:  # noqa: BLE001
        отметить("источник артефакта разрешён", False, ош)
        return итог

    отпечаток = уст._sha(источник)
    отметить("отпечаток артефакта совпал с ожидаемым",
             отпечаток == арг.expect_sha256, отпечаток[:16])

    try:
        цепь = уст.доказать_цепочку(сайт, уст.ВИТРИНЫ[сайт])
        отметить("цепочка обслуживания доказана", цепь.get("verdict") == "PROVEN",
                 f"{цепь.get('unit')} ← 127.0.0.1:{цепь.get('upstream_port')}")
    except Exception as ош:  # noqa: BLE001
        отметить("цепочка обслуживания доказана", False, ош)

    база = объявленное(отпечатки(домен, "dry-baseline", выход / f"{сайт}-fp-dry.json"))
    отметить("домен отвечает и объявляет себя", bool(база["artifacts"]),
             f"версия {база['versions']} артефакт {[а[:12] for а in база['artifacts']]}")
    отметить("домен ещё не на кандидате", база["artifacts"] != [арг.expect_sha256],
             "иначе устанавливать нечего")

    каталог = Path(опис["catalog"])
    отметить("снимок каталога на месте", каталог.is_file(), каталог)
    боковой = каталог.with_name(каталог.name.replace("-catalog.json", "-details.json"))
    отметить("боковой файл подробностей на месте", боковой.is_file(), боковой)

    итог["would_restart_unit"] = уст.ВИТРИНЫ[сайт]["unit"]
    итог["would_write"] = [str(уст.АРТЕФАКТ),
                           str(уст.ФРОНТ / уст.ВИТРИНЫ[сайт]["manifest"])]
    журнал(f"   записал бы: {итог['would_write']}")
    журнал(f"   перезапустил бы: {итог['would_restart_unit']}")
    return итог


def провести(сайт: str, арг, выход: Path) -> dict:
    опис = dict(ВИТРИНЫ[сайт])
    опис.update(арг.профили.get(сайт, {}))
    домен = опис["domain"]
    шаги: list = []
    итог = {"site": сайт, "domain": домен, "steps": шаги,
            "started_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

    журнал(f"{сайт}: шаг 1 — базовые отпечатки {домен}")
    база = отпечатки(домен, "baseline", выход / f"{сайт}-fp-baseline.json")
    базовое = объявленное(база)
    шаги.append({"step": "baseline", "declared": базовое})
    if not базовое["artifacts"]:
        итог["verdict"] = "ABORT_NO_BASELINE"
        return итог
    журнал(f"   базовая версия {базовое['versions']} артефакт {[а[:12] for а in базовое['artifacts']]}")

    журнал(f"{сайт}: шаг 2 — установка кандидата")
    ок, установка = установить(сайт, арг, выход / f"{сайт}-install.json")
    шаги.append({"step": "install", "verdict": установка.get("verdict"),
                 "restart_ok": установка.get("restart_ok")})
    точка = установка.get("rollback_point")
    if not ок or установка.get("verdict") != "DEPLOYED_AND_VERIFIED":
        итог["verdict"] = "INSTALL_FAILED_NO_CHANGE"
        итог["install"] = установка
        return итог

    журнал(f"{сайт}: шаг 3 — домен обязан отдавать НОВЫЙ артефакт")
    после = отпечатки(домен, "candidate", выход / f"{сайт}-fp-candidate.json")
    кандидат = объявленное(после)
    сменилось = (кандидат["artifacts"] == [арг.expect_sha256]
                 and кандидат["versions"] == [арг.design_version])
    шаги.append({"step": "served_changed", "declared": кандидат, "ok": сменилось})
    журнал(f"   отдаёт версию {кандидат['versions']} артефакт {[а[:12] for а in кандидат['artifacts']]}")

    проверка = {}
    if сменилось:
        журнал(f"{сайт}: шаг 4 — публичные ворота")
        проверка = проверить_публично(сайт, опис, выход, "candidate")
        шаги.append({"step": "public_gates", "ok": проверка["ok"], "gates": проверка["gates"]})
        for имя, з in проверка["gates"].items():
            журнал(f"   {'OK ' if з['ok'] else 'ПРОВАЛ'} {имя}: {з['value']}")

    if not сменилось or not проверка.get("ok"):
        журнал(f"{сайт}: ворота не пройдены — откат и остановка")
        _, откат = откатить(сайт, точка, выход / f"{сайт}-rollback-forced.json")
        шаги.append({"step": "forced_rollback", "verdict": откат.get("verdict")})
        итог["verdict"] = "ROLLED_BACK_GATES_FAILED"
        итог["public_check"] = проверка
        return итог

    журнал(f"{сайт}: шаг 5 — учебный откат")
    ок, откат = откатить(сайт, точка, выход / f"{сайт}-rollback-drill.json")
    шаги.append({"step": "rollback_drill", "verdict": откат.get("verdict"),
                 "disk_match": откат.get("disk_fingerprint_match"),
                 "served_match": откат.get("served_fingerprint_match")})

    журнал(f"{сайт}: шаг 6 — сверка восстановленного отпечатка")
    возврат = объявленное(отпечатки(домен, "after-rollback", выход / f"{сайт}-fp-rollback.json"))
    совпал = (возврат["artifacts"] == базовое["artifacts"]
              and возврат["versions"] == базовое["versions"])
    шаги.append({"step": "baseline_restored", "declared": возврат, "ok": совпал})
    журнал(f"   {'базовый отпечаток вернулся' if совпал else 'ОТПЕЧАТОК НЕ СОВПАЛ'}")
    if not ок or откат.get("verdict") != "ROLLED_BACK_VERIFIED" or not совпал:
        итог["verdict"] = "ROLLBACK_DRILL_FAILED"
        return итог

    журнал(f"{сайт}: шаг 7 — возврат кандидата вперёд")
    ок, вперёд = установить(сайт, арг, выход / f"{сайт}-restore-forward.json")
    шаги.append({"step": "restore_forward", "verdict": вперёд.get("verdict")})
    if not ок or вперёд.get("verdict") != "DEPLOYED_AND_VERIFIED":
        итог["verdict"] = "RESTORE_FORWARD_FAILED"
        return итог

    журнал(f"{сайт}: шаг 8 — короткая проверка после возврата")
    финал = объявленное(отпечатки(домен, "final", выход / f"{сайт}-fp-final.json"))
    держит = (финал["artifacts"] == [арг.expect_sha256] and финал["statuses"] == [200])
    шаги.append({"step": "final_check", "declared": финал, "ok": держит})
    итог["verdict"] = "CANARY_ACTIVE_VERIFIED" if держит else "FINAL_CHECK_FAILED"
    итог["public_check"] = проверка
    итог["public_urls"] = [f"https://{домен}/", f"https://{домен}/catalog/"]
    return итог


def main(argv=None) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--artifact", required=True)
    р.add_argument("--expect-sha256", required=True)
    р.add_argument("--commit", required=True)
    р.add_argument("--build-id", required=True)
    р.add_argument("--design-version", default="1.1.0")
    р.add_argument("--out", required=True, help="каталог свидетельств")
    р.add_argument("--profiles", help="JSON с настройками витрин (архетипы, границы)")
    р.add_argument("--sites", default="lords-01,zona-01",
                   help="порядок витрин; Zona берётся только после PASS Lords")
    р.add_argument("--dry-run", action="store_true",
                   help="проверить всё проверяемое и НЕ ПИСАТЬ ничего; "
                        "запускается без root")
    арг = р.parse_args(argv)
    арг.профили = json.loads(Path(арг.profiles).read_text(encoding="utf-8")) if арг.profiles else {}

    выход = Path(арг.out)
    выход.mkdir(parents=True, exist_ok=True)
    порядок = [с.strip() for с in арг.sites.split(",") if с.strip()]
    неизвестные = [с for с in порядок if с not in ВИТРИНЫ]
    if неизвестные:
        print(f"ОТКАЗ: витрины вне перечня: {неизвестные}", file=sys.stderr)
        return 2

    сводка = {"started_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "artifact_sha256": арг.expect_sha256, "commit": арг.commit,
              "build_id": арг.build_id, "sites": []}
    if арг.dry_run:
        сводка["mode"] = "dry-run"
        for сайт in порядок:
            сводка["sites"].append(сухой_прогон(сайт, арг, выход))
        все_ок = all(с["ok"] for с in сводка["sites"])
        сводка["verdict"] = "DRY_RUN_READY" if все_ок else "DRY_RUN_BLOCKED"
        (выход / "canary-dry-run.json").write_text(
            json.dumps(сводка, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        журнал(f"ИТОГ сухого прогона: {сводка['verdict']}")
        журнал(f"свидетельства: {выход / 'canary-dry-run.json'}")
        return 0 if все_ок else 1

    for сайт in порядок:
        итог = провести(сайт, арг, выход)
        сводка["sites"].append(итог)
        журнал(f"{сайт}: ВЕРДИКТ {итог['verdict']}")
        if итог["verdict"] != "CANARY_ACTIVE_VERIFIED":
            журнал("остановка: к следующей витрине переход только после полного PASS")
            break

    сводка["finished_at_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    сводка["verdict"] = ("ALL_CANARIES_ACTIVE"
                         if len(сводка["sites"]) == len(порядок)
                         and all(с["verdict"] == "CANARY_ACTIVE_VERIFIED" for с in сводка["sites"])
                         else "INCOMPLETE")
    (выход / "canary-run.json").write_text(
        json.dumps(сводка, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    журнал(f"ИТОГ: {сводка['verdict']}")
    for с in сводка["sites"]:
        for u in с.get("public_urls", []):
            журнал(f"   доступно: {u}")
    журнал(f"свидетельства: {выход / 'canary-run.json'}")
    return 0 if сводка["verdict"] == "ALL_CANARIES_ACTIVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
