#!/usr/bin/env python3
"""След исполнителя с двумя противоположными вердиктами в одной записи.

Расхождение, которое это измеряет. В записи `/var/lib/site-cells/results/*.json`
вердикт стоит в ДВУХ местах: верхний `status` («исполнитель отработал, и
операция применена») и `outcome.status` («что именно сделано»). Верхний
вычисляется из нижнего:

    применено = итог.get("status") in queue.ПРИМЕНЁННЫЕ_ИСХОДЫ
    результат["status"] = "ok" if применено else "failed"

Набор `ПРИМЕНЁННЫЕ_ИСХОДЫ` со временем пополнялся. Поэтому запись, сделанная
прежним кодом, может нести `status: "failed"` при `outcome.status`, который
СЕГОДНЯ считается применённым. Пример измерен 13.10: `lords-02-data-628ccec1768f`
— верхний `failed`, а внизу `delivered`, `stage: live_verified`, и все шесть
шагов удачны (`warm_up.ready`, `promote.ready`, `verify.ok`).

Почему это важно, а не любопытно. Эти записи — источник истины для
`cell-status-reconcile.py` и прочих сведений: паспорту ячейки писать некому,
кроме исполнителя. Читатель, доверившийся верхнему полю на старой записи,
получает ВЕРДИКТ, ПРОТИВОПОЛОЖНЫЙ действительности. Это тот же класс, что
приёмка старше кода: поле выглядит вердиктом, а описывает прежнее правило.

Инструмент только читает. Он НЕ правит старые следы: запись исполнителя —
постоянные данные (docs/RUNTIME_DATA_OWNERSHIP.md), и переписывать историю
задним числом нельзя даже «чтобы согласовать». Выход — называть такие записи,
чтобы читатели их отличали.

    python3 automation/local/trace-verdict-audit.py
    python3 automation/local/trace-verdict-audit.py --site lords-02
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

СЛЕДЫ = Path("/var/lib/site-cells/results")

# Копия набора из factory/cell/queue.py. Копия — осознанная: инструмент должен
# читать следы и там, где устанавливаемого пакета рядом нет. Расхождение копии
# с источником проверяется ниже и само является находкой.
ПРИМЕНЁННЫЕ_ИСХОДЫ = ("activated", "delivered", "edited", "unchanged", "dry-run",
                      "checked", "applied", "nothing-to-do", "commented")


def набор_из_источника() -> tuple[str, ...] | None:
    """Набор из живого кода, если он доступен. None — не найден, не пустой."""
    for корень in (Path("/usr/local/lib/site-factory-cell"),
                   Path("/home/claude/wt-portable-site-cell-01")):
        ф = корень / "factory" / "cell" / "queue.py"
        if not ф.is_file():
            continue
        for строка in ф.read_text(encoding="utf-8", errors="replace").splitlines():
            if строка.startswith("ПРИМЕНЁННЫЕ_ИСХОДЫ"):
                пространство: dict[str, object] = {}
                текст = строка
                # Набор записан в две строки.
                все = ф.read_text(encoding="utf-8", errors="replace")
                i = все.index("ПРИМЕНЁННЫЕ_ИСХОДЫ")
                текст = все[i:все.index("\n\n", i)]
                exec(текст, пространство)  # noqa: S102 — свой же файл
                знач = пространство.get("ПРИМЕНЁННЫЕ_ИСХОДЫ")
                return tuple(знач) if isinstance(знач, tuple) else None
    return None


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--site", default=None, help="только одна ячейка")
    р.add_argument("--follow", default=str(СЛЕДЫ), help="каталог следов")
    а = р.parse_args()

    корень = Path(а.follow)
    if not корень.is_dir():
        print(f"каталога следов нет: {корень} — НЕ ИЗМЕРЕНО")
        return 2

    живой = набор_из_источника()
    if живой is None:
        print("набор применённых исходов в живом коде не найден: "
              "сверка копии НЕ ИЗМЕРЕНА")
    elif tuple(живой) != ПРИМЕНЁННЫЕ_ИСХОДЫ:
        print("РАСХОЖДЕНИЕ копии набора с живым кодом:")
        print(f"  в инструменте: {sorted(ПРИМЕНЁННЫЕ_ИСХОДЫ)}")
        print(f"  в коде:        {sorted(живой)}")
        print("  дальше считается по ЖИВОМУ набору")
    применённые = tuple(живой) if живой else ПРИМЕНЁННЫЕ_ИСХОДЫ

    противоречат: list[tuple[str, str, str, str, str]] = []
    согласны = нечитаемы = отказ_исключением = без_вердикта = 0
    исходы: Counter[str] = Counter()
    for ф in sorted(корень.glob("*.json")):
        try:
            d = json.loads(ф.read_text(encoding="utf-8"))
        except Exception as exc:                      # noqa: BLE001
            нечитаемы += 1
            print(f"нечитаемый след {ф.name}: {type(exc).__name__}")
            continue
        сайт = str(d.get("site_id") or "?")
        if а.site and сайт != а.site:
            continue
        верх = d.get("status")
        итог = d.get("outcome")
        низ = итог.get("status") if isinstance(итог, dict) else None
        if низ is None:
            # Отказ пишется исключением, и `outcome` у него не появляется вовсе
            # (`результат["status"] = "rejected"` и выход). Это устройство, а не
            # пробел измерения, и называть его «без вердикта» значит звать
            # читателя искать недостачу там, где её нет.
            if верх == "rejected":
                отказ_исключением += 1
            else:
                без_вердикта += 1
                print(f"след без вердикта {ф.name}: верх {верх!r}, outcome нет")
            continue
        if верх is None:
            без_вердикта += 1
            print(f"след без верхнего вердикта {ф.name}: низ {низ!r}")
            continue
        исходы[f"{верх}/{низ}"] += 1
        ожидаемый = "ok" if низ in применённые else "failed"
        if верх in ("rejected",):
            # Отказ записан исключением: нижнего вердикта у него может не быть
            # вовсе, и сравнивать нечего.
            согласны += 1
        elif верх != ожидаемый:
            этап = (итог.get("stage") if isinstance(итог, dict) else "") or ""
            противоречат.append((ф.name, сайт, str(d.get("operation")),
                                 f"верх {верх}, низ {низ}", этап))
        else:
            согласны += 1

    print(f"\nследов разобрано: {согласны + len(противоречат)}"
          f" (отказ исключением {отказ_исключением} — у них outcome не пишется"
          f" по устройству; без вердикта {без_вердикта}, нечитаемых {нечитаемы})")
    print(f"вердикты согласны: {согласны}")
    print(f"вердикты ПРОТИВОРЕЧАТ: {len(противоречат)}")
    for имя, сайт, оп, что, этап in противоречат:
        print(f"  {сайт:12} {оп:16} {что:34} stage={этап:14} {имя}")
    if противоречат:
        print("\nЧто это значит: верхнее поле этих записей написано прежним "
              "правилом и сегодня читается как провал удачной операции. "
              "Старые следы НЕ правятся — их читателям положено сверять "
              "`outcome.status` с набором применённых исходов.")
    print("\nвстреченные пары верх/низ:")
    for пара, сколько in sorted(исходы.items(), key=lambda x: -x[1]):
        print(f"  {сколько:5} {пара}")
    return 1 if противоречат else 0


if __name__ == "__main__":
    sys.exit(main())
