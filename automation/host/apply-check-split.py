#!/usr/bin/env python3
"""MOD-228: проверка с двумя предметами делится на режимы --static/--snapshot.

    python3 automation/host/apply-check-split.py \
        --repo var/site-repos/zonafilm-space --only sitemap_genres [--dry-run]

Зачем
-----

У части проверок ДВА предмета: статический (перечень разделов, правила) и
снимковый (данные витрины). Прежде они жили в одном прогоне: без снимка
проверка мерила статическую часть, печатала «НЕ ИЗМЕРЕНО» по второй и выходила
кодом 0. Договор состояний такого не знает:

* код 2 неверен — часть предмета ИЗМЕРЕНА, и правило MOD-221 валило бы выпуск;
* код 0 молча неверен — утверждается норма по тому, чего не смотрели;
* код 0 со строкой «НЕ ИЗМЕРЕНО» неверен иначе — раннер читает эту строку как
  пропуск ВСЕЙ проверки.

Решение принято линией ячейки 28.10: не пятое состояние и не новый счётчик
раннера, а разделение предметов. Один файл и два режима, а не два файла: в
обоих файлах пришлось бы держать копию загрузчика, а две копии расходятся
молча — как уже расходились адрес каталога данных (MOD-220) и имена проводки
(MOD-219).

Ворота — четыре мутации на копии, все обязательны
-------------------------------------------------

1. снимка нет: `--static` мерит (0 или 1), `--snapshot` даёт код 2;
2. снимок есть: обе половины мерят;
3. дефект внесён в статическую часть: `--static` даёт код 1 при любом снимке;
4. режим не указан: код **1** с внятной причиной, а не 2 — иначе раннер
   посчитает забытый режим пропуском, и ошибка набора станет «не измерено».
"""
from __future__ import annotations

import argparse
import ast
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

#: Разбор режима ставится ПЕРЕД загрузчиком: забытый режим не должен успеть
#: ничего загрузить.
РАЗБОР_РЕЖИМА = '''РЕЖИМ = sys.argv[1] if len(sys.argv) > 1 else ""
if РЕЖИМ not in ("--static", "--snapshot"):
    print("ДЕФЕКТ НАБОРА: режим не указан. Ожидается --static или --snapshot: "
          "у проверки два предмета, и молча проверить один значило бы объявить "
          "норму по второму.")
    sys.exit(1)

'''

#: Формы границы между предметами, измеренные по checks/*.py. У каждой своя
#: замена: имена переменных и место перехода у проверок разные.
ФОРМЫ = (
    (
        '''if not any(ДАННЫЕ.glob("*-catalog.json")):
    print(f"НЕ ИЗМЕРЕНО: жанры — снимка в {ДАННЫЕ} нет")
else:''',
        '''if РЕЖИМ == "--static":
    print(f"статических разделов карты: {len(статические)}")
    for пр in провалы:
        print(пр)
    sys.exit(1 if провалы else 0)

# Снимковая половина: без снимка мерить нечем — это ПРОПУСК, и правило
# MOD-221 обязано его валить вне CI.
if not any(ДАННЫЕ.glob("*-catalog.json")):
    print(f"НЕ ИЗМЕРЕНО: снимка в {ДАННЫЕ} нет — снимковая половина идёт на "
          "хосте площадки")
    sys.exit(2)
if True:''',
    ),
)

ЯКОРЬ_ДО_ЗАГРУЗЧИКА = "КОРЕНЬ = Path(__file__).resolve().parent.parent"


def _правка(файл: pathlib.Path) -> tuple[bool, str]:
    текст = файл.read_text(encoding="utf-8")
    if "РЕЖИМ not in" in текст:
        return False, "уже"
    подошли = [(я, з) for я, з in ФОРМЫ if текст.count(я) == 1]
    if not подошли:
        return False, "границы предметов известной формы нет"
    if текст.count(ЯКОРЬ_ДО_ЗАГРУЗЧИКА) != 1:
        return False, "места для разбора режима нет (КОРЕНЬ неоднозначен)"
    новый = текст.replace(ЯКОРЬ_ДО_ЗАГРУЗЧИКА,
                          РАЗБОР_РЕЖИМА + ЯКОРЬ_ДО_ЗАГРУЗЧИКА, 1)
    новый = новый.replace(подошли[0][0], подошли[0][1], 1)
    try:
        ast.parse(новый)
    except SyntaxError as сбой:
        return False, f"правка дала бы SyntaxError: {сбой.msg} (строка {сбой.lineno})"
    файл.write_text(новый, encoding="utf-8")
    return True, "разделено на режимы"


def _прогон(корень: pathlib.Path, имя: str, режим: list, среда: dict):
    готово = subprocess.run(  # noqa: S603
        [sys.executable, f"checks/{имя}.py", *режим], cwd=корень,
        capture_output=True, text=True, timeout=1200,
        env={**os.environ, **среда, "PYTHONDONTWRITEBYTECODE": "1"})
    вывод = ((готово.stdout or "") + (готово.stderr or "")).strip()
    хвост = вывод.splitlines()[-1][:140] if вывод else "без вывода"
    return готово.returncode, хвост


def _мутации(копия: pathlib.Path, имя: str, снимок: str) -> list[str]:
    беды = []
    без = {"SITE_DATA_DIR": "/nonexistent-split-probe"}
    код, хвост = _прогон(копия, имя, ["--static"], без)
    if код not in (0, 1):
        беды.append(f"мутация 1, --static без снимка: код {код} — {хвост}")
    код, хвост = _прогон(копия, имя, ["--snapshot"], без)
    if код != 2:
        беды.append(f"мутация 1, --snapshot без снимка: код {код}, ожидался 2 — {хвост}")
    со = {"SITE_DATA_DIR": снимок}
    for режим in ("--static", "--snapshot"):
        код, хвост = _прогон(копия, имя, [режим], со)
        if код not in (0, 1):
            беды.append(f"мутация 2, {режим} со снимком: код {код} — {хвост}")
        elif "НЕ ИЗМЕРЕНО" in хвост:
            беды.append(f"мутация 2, {режим} со снимком: не измерила — {хвост}")
    код, хвост = _прогон(копия, имя, [], со)
    if код != 1:
        беды.append(f"мутация 4, без режима: код {код}, ожидался 1 — {хвост}")
    elif "ДЕФЕКТ НАБОРА" not in хвост:
        беды.append(f"мутация 4: причина не названа — {хвост}")
    return беды


def применить(репо: pathlib.Path, имя: str, писать: bool) -> tuple[str, str]:
    цель = репо / "checks" / f"{имя}.py"
    if not цель.is_file():
        return "refuse", f"нет {цель}"
    снимок = f"/srv/{репо.name}/data"
    if not pathlib.Path(снимок).is_dir():
        return "refuse", f"НЕ ИЗМЕРЕНО: снимка витрины нет ({снимок})"
    врем = pathlib.Path(tempfile.mkdtemp(prefix="split-"))
    try:
        копия = врем / "repo"
        shutil.copytree(репо, копия, symlinks=True,
                        ignore=shutil.ignore_patterns("__pycache__", ".git",
                                                      "var", "artifacts"))
        сделано, причина = _правка(копия / "checks" / f"{имя}.py")
        if not сделано:
            return ("skip", причина) if причина == "уже" else ("refuse", причина)
        беды = _мутации(копия, имя, снимок)
        # Мутация 3: дефект в статике обязан дать код 1.
        порченый = (копия / "checks" / f"{имя}.py").read_text(encoding="utf-8")
        если = 'if "/catalog/" not in статические:'
        if порченый.count(если) == 1:
            (копия / "checks" / f"{имя}.py").write_text(
                порченый.replace(если, 'if "/catalog/" in статические:', 1),
                encoding="utf-8")
            код, хвост = _прогон(копия, имя, ["--static"], {"SITE_DATA_DIR": снимок})
            if код != 1:
                беды.append(f"мутация 3, дефект в статике: код {код}, ожидался 1")
        else:
            беды.append("мутация 3 не поставлена: условия статики известной формы нет")
        if беды:
            return "refuse", "мутации не прошли: " + "; ".join(беды)
    finally:
        shutil.rmtree(врем, ignore_errors=True)
    if not писать:
        return "ok", "четыре мутации пройдены на копии; запись не велась"
    сделано, причина2 = _правка(цель)
    if not сделано:
        return "refuse", f"правка витрины не прошла: {причина2}"
    return "ok", ("разделено; четыре мутации пройдены. ОБЪЯВИТЕ ДВЕ СТРОКИ check "
                  "в run.sh: --static и --snapshot (вторая с обёрткой rc=2 → 0)")


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--only", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(репо, а.only, писать=not (а.check or а.dry_run))
    print(f"[{исход:6s}] {репо.name}/{а.only}: {пояснение}")
    return 2 if исход == "refuse" else 0


if __name__ == "__main__":
    sys.exit(main())
