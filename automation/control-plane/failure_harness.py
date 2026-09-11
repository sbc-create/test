#!/usr/bin/env python3
"""Failure-тест serving plane с собственным кодом возврата.

Прежняя версия завершалась exit 124 обёртки ssh, и «функционально прошёл»
приходилось трактовать вручную. Здесь так нельзя: таймаут — это FAIL, а не
повод для интерпретации, и восстановление Registry выполняется в finally,
даже если проверка упала посередине.

Незавершённая уборка блокирует PASS: оставленная лежать служба хуже
неудачного теста, потому что следующий прогон начнётся со сломанного мира.
"""
from __future__ import annotations

import json, os, ssl, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

ДОМЕНЫ = ["lordfilm47.space", "lordserial33.biz", "1lordserials1.online",
          "yummyani.site", "yummyani.org", "yummyani.biz",
          "zonafilm.space", "animedia.icu", "animedia.space"]
БАЗА = "http://127.0.0.1:8790"
РЕЛИЗ = "/srv/lords/.frontend"
ОТЧЁТ = Path("/srv/site-factory/control-plane-contracts/evidence/failure-harness.json")
ПРЕДЕЛ_СЕК = 300
ctx = ssl.create_default_context()

провалы: list[str] = []
журнал: list[dict] = []


def шаг(имя, условие, деталь=""):
    print("  %-54s %s %s" % (имя, "PASS" if условие else "FAIL", деталь),
          flush=True)
    журнал.append({"step": имя, "pass": bool(условие), "detail": str(деталь)})
    if not условие:
        провалы.append(имя)


def публичный(домен: str) -> int:
    try:
        зпр = urllib.request.Request(f"https://{домен}/",
                                     headers={"User-Agent": "fleet-harness/1.0"})
        with urllib.request.urlopen(зпр, timeout=20, context=ctx) as о:
            return о.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def сборки() -> dict:
    """build_id каждой витрины из развёрнутой проекции."""
    итог = {}
    for p in sorted(Path(РЕЛИЗ).glob("*-catalog.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            итог[p.stem] = d.get("build_id") or d.get("revision")
        except Exception:  # noqa: BLE001
            итог[p.stem] = None
    return итог


def pid_на_порту() -> int | None:
    р = subprocess.run(["bash", "-c",
                        "ss -lntp 2>/dev/null | grep 8790 | grep -oE 'pid=[0-9]+' "
                        "| cut -d= -f2 | head -1"],
                       capture_output=True, text=True)
    т = (р.stdout or "").strip()
    return int(т) if т.isdigit() else None


def поднять() -> bool:
    subprocess.Popen(
        ["setsid", "/srv/site-factory/control-api/current/.venv/bin/python",
         "-m", "factory.site_engine.api.server",
         "--root", "/srv/site-factory/repo",
         "--host", "127.0.0.1", "--port", "8790"],
        cwd="/srv/site-factory/control-api/current",
        env={**os.environ, "SITE_ENGINE_HTTP": "1", "SITE_ENGINE_ADMIN": "1",
             "SITE_ENGINE_API_ENABLED": "1"},
        stdout=open("/tmp/harness-registry.log", "ab"),
        stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        start_new_session=True)
    for _ in range(20):
        time.sleep(1)
        try:
            with urllib.request.urlopen(БАЗА + "/api/v1/ready", timeout=5) as о:
                if о.status == 200:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def main() -> int:
    t0 = time.time()
    остановлен = False
    try:
        до_коды = {д: публичный(д) for д in ДОМЕНЫ}
        до_сборки = сборки()
        шаг("до простоя: все публичные домены 200",
            all(к == 200 for к in до_коды.values()),
            f"{sum(1 for к in до_коды.values() if к == 200)}/{len(ДОМЕНЫ)}")

        pid = pid_на_порту()
        шаг("Registry найден по PID", pid is not None, str(pid))
        if pid is None:
            return 1
        os.kill(pid, 15)
        остановлен = True
        time.sleep(4)

        недоступен = True
        try:
            with urllib.request.urlopen(БАЗА + "/api/v1/sites", timeout=5):
                недоступен = False
        except Exception:  # noqa: BLE001
            pass
        шаг("Registry действительно недоступен", недоступен)

        во_коды = {д: публичный(д) for д in ДОМЕНЫ}
        шаг("во время простоя: все публичные домены 200",
            all(к == 200 for к in во_коды.values()),
            f"{sum(1 for к in во_коды.values() if к == 200)}/{len(ДОМЕНЫ)}")
        во_сборки = сборки()
        шаг("build_id витрин не изменился во время простоя",
            во_сборки == до_сборки)

        # Мутация при недоступном Registry обязана быть отвергнута, а не
        # применена вслепую и не молча потеряна.
        отвергнута = False
        try:
            зпр = urllib.request.Request(
                БАЗА + "/api/v1/internal/commands/register",
                data=b'{"site_id":"x"}', method="POST",
                headers={"Content-Type": "application/json"})
            urllib.request.urlopen(зпр, timeout=5)
        except Exception:  # noqa: BLE001
            отвергнута = True
        шаг("мутация при простое отклонена", отвергнута)

        if time.time() - t0 > ПРЕДЕЛ_СЕК:
            шаг("уложились в предел времени", False, "таймаут")
            return 1
    finally:
        # Восстановление обязательно, даже если проверка упала выше.
        if остановлен:
            поднялся = поднять()
            шаг("Registry восстановлен", поднялся)
        после_коды = {д: публичный(д) for д in ДОМЕНЫ}
        шаг("после восстановления: все публичные домены 200",
            all(к == 200 for к in после_коды.values()),
            f"{sum(1 for к in после_коды.values() if к == 200)}/{len(ДОМЕНЫ)}")
        шаг("build_id витрин не изменился после", сборки() == до_сборки)

        сходится = False
        try:
            with urllib.request.urlopen(БАЗА + "/api/v1/registry/snapshot",
                                        timeout=10) as о:
                сн = json.loads(о.read())
                сходится = сн.get("count") == 9
        except Exception:  # noqa: BLE001
            pass
        шаг("после восстановления snapshot сошёлся: 9", сходится)

        р = subprocess.run(["bash", "-c",
                            "ss -lnt 2>/dev/null | grep -c 8790"],
                           capture_output=True, text=True)
        шаг("слушатель ровно один", (р.stdout or "").strip() == "1",
            (р.stdout or "").strip())

        итог = {"verdict": "PASS" if not провалы else "FAIL",
                "failures": провалы, "steps": журнал,
                "duration_seconds": round(time.time() - t0, 1),
                "public_before": до_коды if "до_коды" in dir() else {},
                "public_after": после_коды}
        ОТЧЁТ.parent.mkdir(parents=True, exist_ok=True)
        ОТЧЁТ.write_text(json.dumps(итог, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print("\n  вердикт:", итог["verdict"], flush=True)
    return 0 if not провалы else 1


if __name__ == "__main__":
    sys.exit(main())
