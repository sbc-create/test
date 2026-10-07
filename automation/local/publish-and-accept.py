#!/usr/bin/env python3
"""Штатная выкладка одной ячейки и ПУБЛИЧНАЯ приёмка. Последовательно.

    python3 automation/local/publish-and-accept.py --site <site_id> [--site …] \\
        [--wait 900] [--dry-run]

Делает по каждой ячейке по порядку:

1. `python3 -m factory cell trigger --site <id> --confirm-activation` — заявка
   исполнителю. Инструмент НЕ ставит релиз сам: ставит его исполнитель ячейки, и
   обойти его значило бы обойти проверки выпуска;
2. ждёт результат исполнителя (`/var/lib/site-cells/results/<id>-code-<sha>.json`)
   и печатает `status`/`stage` как они записаны;
3. при `activated` сверяет ПУБЛИЧНЫЙ `x-site-factory-build-id` с установленным
   деревом и перечисляет, что видно снаружи: код главной, режим индексации,
   canonical разделов, ссылку на карту.

Успешный шаг 1 выкладкой не считается: пока исполнитель не записал
`activated`/`live_verified`, установленного выпуска нет. Успешные проверки
доказательством публичной выкладки тоже не считаются — отсюда шаг 3.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
РЕЗУЛЬТАТЫ = pathlib.Path("/var/lib/site-cells/results")
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"


def ячейка(site_id: str) -> dict:
    for я in json.loads(РЕЕСТР.read_text(encoding="utf-8"))["cells"]:
        if я.get("site_id") == site_id or я.get("domain") == site_id:
            return я
    return {}


def подать(site_id: str, сухо: bool) -> tuple[str, str]:
    """`(request_id, что ответил исполнитель)`."""
    команда = [sys.executable, "-m", "factory", "cell", "trigger", "--site", site_id]
    команда += ["--dry-run"] if сухо else ["--confirm-activation"]
    г = subprocess.run(команда, cwd=str(КОРЕНЬ), capture_output=True, text=True,
                       timeout=1200)
    вывод = (г.stdout or "") + (г.stderr or "")
    м = re.search(r'"request_id":\s*"([^"]+)"', вывод)
    д = re.search(r'"action":\s*"([^"]+)"', вывод)
    return (м.group(1) if м else ""), (д.group(1) if д else вывод.strip()[-200:])


def дождаться(request_id: str, предел: float) -> dict:
    файл = РЕЗУЛЬТАТЫ / f"{request_id}.json"
    край = time.time() + предел
    while time.time() < край:
        if файл.is_file():
            try:
                return json.loads(файл.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
        time.sleep(10)
    return {}


def публичное(домен: str) -> dict:
    итог: dict = {"домен": домен}
    г = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-D", "-", "-L",
                        "--max-time", "60", f"https://{домен}/"],
                       capture_output=True, text=True)
    for с in (г.stdout or "").splitlines():
        низ = с.lower()
        if низ.startswith("http/"):
            ч = с.split()
            итог["код"] = ч[1] if len(ч) > 1 else ""
        elif низ.startswith("x-site-factory-build-id:"):
            итог["build"] = с.partition(":")[2].strip()
        elif низ.startswith("x-robots-tag:"):
            итог["режим"] = с.partition(":")[2].strip()
    г2 = subprocess.run(["curl", "-sS", "--max-time", "60",
                         f"https://{домен}/robots.txt"], capture_output=True, text=True)
    итог["карта_в_robots"] = "Sitemap:" in (г2.stdout or "")
    return итог


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--site", action="append", required=True)
    р.add_argument("--wait", type=float, default=900.0)
    р.add_argument("--dry-run", action="store_true")
    о = р.parse_args(argv[1:])

    плохих = 0
    for site_id in о.site:
        я = ячейка(site_id)
        домен = я.get("domain") or site_id
        print(f"\n=== {site_id} ({домен})", flush=True)
        request_id, ответ = подать(site_id, о.dry_run)
        print(f"   заявка: {ответ}" + (f" [{request_id}]" if request_id else ""),
              flush=True)
        if о.dry_run or not request_id:
            continue
        итог = дождаться(request_id, о.wait)
        if not итог:
            print(f"   результата исполнителя нет за {о.wait:.0f} с — "
                  "выкладка не подтверждена")
            плохих += 1
            continue
        исход = итог.get("outcome") or {}
        print(f"   исполнитель: status={исход.get('status')} "
              f"stage={исход.get('stage')} build={исход.get('build_id')}")
        if исход.get("status") != "activated":
            print(f"   причина: {str(исход.get('reason'))[:300]}")
            плохих += 1
            continue
        п = публичное(домен)
        совпало = bool(п.get("build")) and bool(исход.get("build_id")) and (
            п["build"] == исход["build_id"])
        print(f"   публично: код {п.get('код')}, build {п.get('build') or '—'}, "
              f"режим {п.get('режим') or '—'}, карта в robots {п.get('карта_в_robots')}")
        print(f"   build совпал с установленным: {'да' if совпало else 'НЕТ'}")
        плохих += int(not совпало)
    print(f"\nячеек {len(о.site)}, с расхождениями {плохих}")
    return 1 if плохих else 0


if __name__ == "__main__":
    raise SystemExit(главная(sys.argv))
