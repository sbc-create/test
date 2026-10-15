#!/usr/bin/env python3
"""Плеер витрины на ЛОКАЛЬНОМ стенде: номер в запросе поставщику и игра.

Зачем. Витрина, которая ещё не живёт публично (нет записи A, нет сертификата),
проверяется только на стенде. Но проверять её надо теми же мерками, что живую:
номер в разметке — это ВХОД, а доказательство — номер в запросе к поставщику и
растущий `currentTime`. Иначе «плеер настроен» остаётся словами до самого
публичного запуска, а узнавать о пустом плеере в этот момент дорого.

Что делает: поднимает ячейку тем же способом, что остальные осмотры (функции
из `browser-audit-cell.py`), и отдаёт адрес стенда проверке
`publisher-id-check.py`, которая умеет работать по базовому адресу.

Данные берутся из доставленного набора, номер — из `config/player.json` самой
ячейки (его читает рантайм). Ничего не выдумывается: нет файла плеера — нет и
проверки, о чём инструмент говорит прямо.

    python3 automation/local/stand-player-check.py --site lords-10 \\
        --data var/k2-data/publish-stage8
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]


def _основной_осмотр():
    путь = КОРЕНЬ / "automation" / "local" / "browser-audit-cell.py"
    спец = importlib.util.spec_from_file_location("browser_audit_cell", путь)
    м = importlib.util.module_from_spec(спец)
    sys.modules[спец.name] = м
    спец.loader.exec_module(м)
    return м


def проверить(site_id: str, данные_исх: Path, порт: int) -> int:
    проект = КОРЕНЬ / "var" / "new-sites" / site_id
    конфиг = json.loads((проект / "config" / "site.json").read_text(encoding="utf-8"))
    плеер = проект / "config" / "player.json"
    if not плеер.is_file():
        print(f"{site_id}: нет {плеер} — плеер не настроен, проверять нечего "
              "(номер назначает владелец, выдумывать его нельзя)")
        return 2

    осн = _основной_осмотр()
    врем = Path(tempfile.mkdtemp(prefix=f"plr-{site_id}-"))
    данные = врем / "data"
    данные.mkdir()
    for ф in данные_исх.glob(f"{site_id}-*.json"):
        shutil.copy(ф, данные / ф.name)

    процесс, готово = осн.поднять(проект, конфиг, данные, порт)
    if not готово:
        вывод = (процесс.stdout.read() if процесс.stdout else b"").decode("utf-8", "replace")
        print(f"{site_id}: стенд не поднялся\n{вывод[-600:]}")
        процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)
        return 1

    try:
        г = subprocess.run(
            [sys.executable, str(КОРЕНЬ / "automation" / "local" / "publisher-id-check.py"),
             f"http://127.0.0.1:{порт}"],
            capture_output=True, text=True, timeout=900, cwd=str(КОРЕНЬ))
        print(f"=== {site_id} ({конфиг.get('domain')}), стенд 127.0.0.1:{порт}")
        print((г.stdout or "").strip() or (г.stderr or "").strip()[-600:])
        return г.returncode
    finally:
        процесс.terminate()
        try:
            процесс.wait(timeout=20)
        except Exception:  # noqa: BLE001
            процесс.kill()
        shutil.rmtree(врем, ignore_errors=True)


def main() -> int:
    р = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    р.add_argument("--site", action="append", required=True)
    р.add_argument("--data", required=True)
    р.add_argument("--port", type=int, default=19400)
    а = р.parse_args()
    плохо = 0
    for н, site_id in enumerate(а.site):
        код = проверить(site_id, Path(а.data), а.port + н)
        if код != 0:
            плохо += 1
    print(f"\nитог: витрин с неподтверждённым плеером {плохо} из {len(а.site)}")
    return 0 if плохо == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
