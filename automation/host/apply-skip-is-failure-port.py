#!/usr/bin/env python3
"""MOD-226: правило «пропуск считается провалом» переносится на раннер витрины.

    python3 automation/host/apply-skip-is-failure-port.py \
        --repo var/site-repos/animedia-icu [--check] [--dry-run]

Что переносится и почему это работа, а не стиль
-----------------------------------------------

Измерено 28.10: из 21 раннера парка правило стоит у ОДНОГО — zonafilm.cc. У
остальных двадцати пропуск итог прогона не валит, и доказательный опыт это
показал прямо: на копии animedia-icu проверка без снимка печатает «НЕ
ИЗМЕРЕНО», раннер честно пишет «ПРОПУЩЕНО», `checks-measured` — «ПРОПУЩЕНО 1
из 1», а КОД РАННЕРА 0. То есть выпуск прошёл бы при неизмеренной проверке:
ложный зелёный живёт на уровне ИТОГА, а не строки.

Правило переносится дословно из zonafilm.cc, включая его причину: решение НЕ
зависит от того, нашёлся ли снимок, потому что иначе неверный адрес на площадке
выключал бы и проверки, и правило разом — ровно случай 1lordserials1 до
MOD-220. Единственное основание считать пропуск пропуском — положительный
признак раннера CI (`GITHUB_ACTIONS`), который задаёт сам GitHub.

Порядок важен: правило ставится ПОСЛЕ правки адреса данных (MOD-220). Иначе
fail-closed начнёт валить прогоны там, где адрес ещё выводится из имени
каталога, и причиной отказа будет наша же недоделка.

Ворота
------

Две мутации на ВРЕМЕННОЙ копии, обе обязательны. Раннер урезается до одной
проверки, которой намеренно не дают снимка, то есть она ПРОПУСКАЕТСЯ:

1. без `GITHUB_ACTIONS` раннер обязан завершиться кодом 1 (пропуск — провал);
2. с `GITHUB_ACTIONS=true` — кодом 0 (пропуск остаётся пропуском).

Если правило не действует, первая мутация даст 0, и инструмент откажет.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ЯКОРЬ = '''if [ "$skipped" -gt 0 ]; then
  say "checks-measured" "ПРОПУЩЕНО $skipped из $ran"
  printf '    | эти проверки исполнились, но измерить не смогли — итог о них не говорит ничего\\n'
else'''

ЗАМЕНА = '''if [ "$skipped" -gt 0 ]; then
  say "checks-measured" "ПРОПУЩЕНО $skipped из $ran"
  printf '    | эти проверки исполнились, но измерить не смогли — итог о них не говорит ничего\\n'
  # MOD-221/MOD-226. Пропуск — ПРОВАЛ, и единственное основание считать иначе —
  # положительный признак раннера CI: GITHUB_ACTIONS его раннер задаёт сам,
  # задавать никому не нужно. Решение НЕ зависит от того, нашёлся ли снимок:
  # иначе неверный адрес на площадке выключал бы и проверки, и правило разом
  # (случай 1lordserials1 до MOD-220), и выпуск оставался бы зелёным.
  # Резолвер здесь нужен только чтобы назвать путь в причине.
  snap_dir="$(python3 checks/_snapshot_dir.py 2>/dev/null || true)"
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    printf '    | раннер CI (GITHUB_ACTIONS): пропуск остаётся пропуском\\n'
  else
    if [ -n "$snap_dir" ]; then
      printf '    | снимки на месте (%s), и это не CI: пропуск считается провалом\\n' "$snap_dir"
    else
      printf '    | это не CI, а снимка по найденному адресу нет: пропуск считается провалом\\n'
    fi
    fail=1
  fi
else'''

ИСТОЧНИК_РЕЗОЛВЕРА = (pathlib.Path(__file__).resolve().parent
                      / "lords-checks" / "_snapshot_dir.py")


def _правка(репо: pathlib.Path) -> tuple[bool, str]:
    раннер = репо / "checks" / "run.sh"
    if not раннер.is_file():
        return False, f"нет {раннер}"
    текст = раннер.read_text(encoding="utf-8")
    if "пропуск считается провалом" in текст:
        return False, "уже"
    if текст.count(ЯКОРЬ) != 1:
        return False, (f"участка «пропуск» известного вида нет "
                       f"(встречается {текст.count(ЯКОРЬ)} раз)")
    раннер.write_text(текст.replace(ЯКОРЬ, ЗАМЕНА, 1), encoding="utf-8")
    резолвер = репо / "checks" / "_snapshot_dir.py"
    if not резолвер.is_file():
        if not ИСТОЧНИК_РЕЗОЛВЕРА.is_file():
            return False, f"нет источника резолвера {ИСТОЧНИК_РЕЗОЛВЕРА}"
        резолвер.write_bytes(ИСТОЧНИК_РЕЗОЛВЕРА.read_bytes())
    return True, "правлено"


def _урезать(репо: pathlib.Path, оставить: str) -> int:
    раннер = репо / "checks" / "run.sh"
    строки = раннер.read_text(encoding="utf-8").splitlines(keepends=True)
    оставлены, убрано = [], 0
    for с in строки:
        if re.match(r'\s*check\s+"', с) and оставить not in с:
            убрано += 1
            continue
        оставлены.append(с)
    раннер.write_text("".join(оставлены), encoding="utf-8")
    return убрано


def _найти_пропускающую(репо: pathlib.Path) -> str:
    """Имя проверки, которая без снимка даёт пропуск, а не падение."""
    раннер = (репо / "checks" / "run.sh").read_text(encoding="utf-8")
    for м in re.finditer(r'check\s+"([^"]+)"[^\n]*checks/([a-z0-9_]+)\.py', раннер):
        имя_в_раннере, файл = м.group(1), м.group(2)
        т = (репо / "checks" / f"{файл}.py").read_text(encoding="utf-8")
        if "НЕ ИЗМЕРЕНО" in т and "ДАННЫЕ" in т:
            return имя_в_раннере
    return ""


def _мутации(копия: pathlib.Path) -> list[str]:
    имя = _найти_пропускающую(копия)
    if not имя:
        return ["НЕ ИЗМЕРЕНО: в раннере нет проверки, дающей пропуск без снимка"]
    убрано = _урезать(копия, имя)
    беды: list[str] = []
    среда = {**os.environ, "SITE_DATA_DIR": "/nonexistent-snapshot-for-mutation",
             "PYTHONDONTWRITEBYTECODE": "1"}
    среда.pop("GITHUB_ACTIONS", None)
    без = subprocess.run(["bash", "checks/run.sh"], cwd=копия,  # noqa: S603
                         capture_output=True, text=True, timeout=1800, env=среда)
    if без.returncode == 0:
        беды.append(f"мутация 1 (не CI): код 0, ожидался 1 — правило не действует "
                    f"(урезано {убрано} проверок)")
    с_ци = subprocess.run(["bash", "checks/run.sh"], cwd=копия,  # noqa: S603
                          capture_output=True, text=True, timeout=1800,
                          env={**среда, "GITHUB_ACTIONS": "true"})
    if с_ци.returncode != 0:
        беды.append(f"мутация 2 (CI): код {с_ци.returncode}, ожидался 0")
    return беды


def применить(репо: pathlib.Path, писать: bool) -> tuple[str, str]:
    врем = pathlib.Path(tempfile.mkdtemp(prefix="mod221-port-"))
    try:
        копия = врем / "repo"
        shutil.copytree(репо, копия, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".git",
                                                      "var", "artifacts"))
        сделано, причина = _правка(копия)
        if not сделано:
            return ("skip", причина) if причина == "уже" else ("refuse", причина)
        беды = _мутации(копия)
        if беды:
            return "refuse", "; ".join(беды)
    finally:
        shutil.rmtree(врем, ignore_errors=True)
    if not писать:
        return "ok", "две мутации пройдены на копии; запись не велась"
    сделано, причина2 = _правка(репо)
    if not сделано:
        return "refuse", f"правка витрины не прошла: {причина2}"
    return "ok", "доставлено; две мутации пройдены на копии"


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(репо, писать=not (а.check or а.dry_run))
    print(f"[{исход:6s}] {репо.name}: {пояснение}")
    return 2 if исход == "refuse" else 0


if __name__ == "__main__":
    sys.exit(main())
