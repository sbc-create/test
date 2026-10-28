#!/usr/bin/env python3
"""MOD-224: копирующий цикл проверки заменяется общим помощником.

    python3 automation/host/apply-snapshot-copy-helper.py \
        --repo var/site-repos/zonafilm-cc [--check] [--dry-run]

Что измерено
------------

Проверки, поднимающие витрину на копии снимка, копируют каталог данных
целиком. По парку таких 65 (замер владельца общего кода 28.10). У витрин с
живыми данными посетителей часть файлов имеет права 600 и принадлежит учётной
записи витрины — журнал правок редактора, хранилище оценок и комментариев;
копирование падает с `PermissionError`. Закрытость этих файлов ПРАВИЛЬНА, а
проверке они не нужны: ей нужен снимок каталога.

Счёт по витринам: у `zonafilm.cc` и `lordserials22.info` закрытых файлов НОЛЬ
(поэтому проверки там и проходят), у `1lordserials1.online` один, у
`lordserial33.biz` два. Проверка работает ровно там, где живых данных ещё нет.

Что делает инструмент
---------------------

Кладёт `checks/_snapshot_copy.py` и заменяет в проверках цикл копирования на
его вызов. Правило «что копировать, что подключать ссылкой, что пропускать» —
один факт о витрине, и 65 его копий разойдутся, как уже разошлись имена
подстановки токенов (MOD-216), имена проводки режима индексации (MOD-219) и
адрес каталога данных (MOD-220).

Ворота
------

Правка накладывается на ВРЕМЕННУЮ копию витрины, и каждая правленая проверка
там ЗАПУСКАЕТСЯ. По-настоящему правка идёт только если ни одна не дала отказа.
Это прямое следствие трёх изъянов точки вставки в соседнем инструменте: сухой
прогон говорил «будет сделано», а отказ видел только запуск.

Чего инструмент не делает: не меняет сути проверок, не трогает снимки, не
перезаписывает помощник, если он совпадает.
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import shutil
import subprocess
import sys
import tempfile

ПОМОЩНИК = "checks/_snapshot_copy.py"
ИСТОЧНИК = (pathlib.Path(__file__).resolve().parent
            / "lords-checks" / "_snapshot_copy.py")

ВЫЗОВ = '''        пропущено = _подготовить_данные(ДАННЫЕ, данные)
        строка = _строка_пропуска(пропущено)
        if строка:
            print(строка)'''

ОПРЕДЕЛЕНИЕ = '''

def _подготовить_данные(откуда, куда, **ключи):
    """Рабочая копия каталога данных общим помощником (MOD-224).

    `ключи` передаются помощнику как есть: `пропускать` — образцы имён, что не
    брать (проверка намеренно исключает карту сайта и `*.lock`), `только` —
    образцы того, что брать (проверке нужен лишь снимок каталога, `*.json`).
    """
    import importlib.util as _иу
    import pathlib as _пл
    путь = _пл.Path(__file__).resolve().parent / "_snapshot_copy.py"
    спец = _иу.spec_from_file_location("_snapshot_copy", путь)
    модуль = _иу.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль.подготовить(_пл.Path(откуда), _пл.Path(куда), **ключи)


def _строка_пропуска(пропущено):
    import importlib.util as _иу
    import pathlib as _пл
    путь = _пл.Path(__file__).resolve().parent / "_snapshot_copy.py"
    спец = _иу.spec_from_file_location("_snapshot_copy", путь)
    модуль = _иу.module_from_spec(спец)
    спец.loader.exec_module(модуль)
    return модуль.строка_пропуска(пропущено)
'''

#: Формы копирующего цикла, измеренные по checks/*.py zonafilm-cc.
ПРЕЖНИЕ_ЦИКЛЫ = (
    '''        пропущено = []
        for ф in ДАННЫЕ.iterdir():
            цель = данные / ф.name
            try:
                if ф.is_dir() or ф.stat().st_size > (4 << 20):
                    цель.symlink_to(ф)
                else:
                    shutil.copyfile(ф, цель)
            except (PermissionError, OSError):
                пропущено.append(ф.name)
        if пропущено:
            print(f"    | не читаются и пропущены: {', '.join(пропущено[:4])}")''',
    '''        пропущено = []
        for ф in ДАННЫЕ.iterdir():
            цель = данные / ф.name
            try:
                if ф.is_dir() or ф.stat().st_size > (4 << 20):
                    цель.symlink_to(ф)  # снимок только читается
                else:
                    shutil.copyfile(ф, цель)
            except (PermissionError, OSError):
                пропущено.append(ф.name)
        if пропущено:
            print(f"    | не читаются и пропущены: {', '.join(пропущено[:4])}")''',
    '''        пропущено = []
        for ф in ДАННЫЕ.iterdir():
            цель = данные / ф.name
            try:
                if ф.is_dir() or ф.stat().st_size > (4 << 20):
                    цель.symlink_to(ф)      # снимок только читается
                else:
                    shutil.copyfile(ф, цель)
            except (PermissionError, OSError):
                пропущено.append(ф.name)
        if пропущено:
            print(f"    | не читаются и пропущены: {', '.join(пропущено[:4])}")''',
)

#: Пары «копирующий цикл» → «его замена». Замена своя у каждой формы:
#: имена переменных и смысл отбора у проверок разные, и подставлять одну
#: замену всем значило бы менять поведение проверки.
#:
#: Формы 1–3 измерены по checks/*.py zonafilm.cc (цикл по iterdir), форма 4 —
#: по hub_description.py zonafilm12.site (copytree целиком с намеренными
#: исключениями), форма 5 — по www_redirect.py zonafilm12.site (берутся
#: только *.json).
ФОРМЫ = tuple(
    (ц, ВЫЗОВ) for ц in ПРЕЖНИЕ_ЦИКЛЫ
) + (
    ('''        shutil.copytree(данные, копия, symlinks=True,
                        ignore=shutil.ignore_patterns("*.lock", "sitemap"))''',
     '''        пропущено = _подготовить_данные(
            данные, копия, пропускать=("*.lock", "sitemap"))
        строка = _строка_пропуска(пропущено)
        if строка:
            print(строка)'''),
    ('''        for ф in ДАННЫЕ.glob("*.json"):
            shutil.copyfile(ф, данные / ф.name)''',
     '''        пропущено = _подготовить_данные(
            ДАННЫЕ, данные, только=("*.json",))
        строка = _строка_пропуска(пропущено)
        if строка:
            print(строка)'''),
)


def _место_вставки(текст: str) -> int:
    """После строки документации и после всех импортов из `__future__`."""
    try:
        дерево = ast.parse(текст)
    except SyntaxError:
        return -1
    строка = 0
    for узел in дерево.body:
        if (isinstance(узел, ast.Expr)
                and isinstance(getattr(узел, "value", None), ast.Constant)
                and isinstance(узел.value.value, str) and строка == 0):
            строка = getattr(узел, "end_lineno", узел.lineno)
            continue
        if isinstance(узел, ast.ImportFrom) and узел.module == "__future__":
            строка = max(строка, getattr(узел, "end_lineno", узел.lineno))
            continue
        break
    return строка


def _правка(путь: pathlib.Path) -> tuple[bool, str]:
    текст = путь.read_text(encoding="utf-8")
    if "_подготовить_данные(" in текст:
        return False, "уже"
    подошли = [(ц, з) for ц, з in ФОРМЫ if текст.count(ц) == 1]
    if not подошли:
        return False, "копирующего цикла известной формы нет"
    место = _место_вставки(текст)
    if место < 0:
        return False, "файл не разбирается"
    новый = текст.replace(подошли[0][0], подошли[0][1], 1)
    строки = новый.splitlines(keepends=True)
    строки.insert(место, ОПРЕДЕЛЕНИЕ.lstrip("\n"))
    новый = "".join(строки)
    try:
        ast.parse(новый)
    except SyntaxError as сбой:
        return False, f"правка дала бы SyntaxError: {сбой.msg} (строка {сбой.lineno})"
    путь.write_text(новый, encoding="utf-8")
    return True, "правлено"


def _наложить(репо: pathlib.Path,
              только: str = "") -> tuple[list[str], list[str]]:
    каталог = репо / "checks"
    (каталог / "_snapshot_copy.py").write_bytes(ИСТОЧНИК.read_bytes())
    правлены, отказы = [], []
    for f in sorted(каталог.glob("*.py")):
        if f.name.startswith("_"):
            continue
        # Одно семейство за раз — порядок, принятый с линией ячейки 28.10:
        # 65 проверок парка правятся не одним ходом, а семействами, каждое со
        # своим прогоном на копии.
        if только and not f.name.startswith(только):
            continue
        надо, причина = _правка(f)
        if надо:
            правлены.append(f.name)
        elif причина not in ("уже", "копирующего цикла известной формы нет"):
            отказы.append(f"{f.name}: {причина}")
    return правлены, отказы


def применить(репо: pathlib.Path, писать: bool,
              только: str = "") -> tuple[str, str]:
    if not ИСТОЧНИК.is_file():
        return "refuse", f"нет источника помощника {ИСТОЧНИК}"
    if not (репо / "checks").is_dir():
        return "refuse", f"нет {репо / 'checks'}"

    врем = pathlib.Path(tempfile.mkdtemp(prefix="snapshot-copy-"))
    try:
        копия = врем / "repo"
        shutil.copytree(репо, копия, symlinks=True,
                        ignore=shutil.ignore_patterns(
                            "__pycache__", ".git", "var", "artifacts"))
        правлены, отказы = _наложить(копия, только)
        if отказы:
            return "refuse", "; ".join(отказы)
        if not правлены:
            return "skip", ("копирующих циклов известной формы не нашлось"
                        + (f" среди «{только}*»" if только else ""))
        беды = []
        for имя in правлены:
            готово = subprocess.run(  # noqa: S603
                [sys.executable, f"checks/{имя}"], cwd=копия,
                capture_output=True, text=True, timeout=1200)
            if готово.returncode not in (0, 2):
                хвост = (готово.stdout + готово.stderr).strip().splitlines()
                беды.append(f"{имя}: код {готово.returncode}"
                            + (f" — {хвост[-1][:120]}" if хвост else ""))
        if беды:
            return "refuse", ("прогон правленых проверок на копии не зелёный: "
                              + "; ".join(беды))
    except subprocess.TimeoutExpired:
        return "refuse", "прогон на копии не уложился во время"
    finally:
        shutil.rmtree(врем, ignore_errors=True)

    if not писать:
        return "ok", (f"прогон на копии зелёный; будет правлено {len(правлены)}: "
                      + ", ".join(правлены))
    правлены2, отказы2 = _наложить(репо, только)
    if отказы2:
        return "refuse", "; ".join(отказы2)
    return "ok", (f"правлено и подтверждено прогоном {len(правлены2)}: "
                  + ", ".join(правлены2))


def main() -> int:
    р = argparse.ArgumentParser()
    р.add_argument("--repo", required=True)
    р.add_argument("--check", action="store_true")
    р.add_argument("--dry-run", action="store_true")
    р.add_argument("--only", default="",
                   help="префикс имени проверки: одно семейство за раз")
    а = р.parse_args()
    репо = pathlib.Path(а.repo).resolve()
    исход, пояснение = применить(репо, писать=not (а.check or а.dry_run),
                                 только=а.only)
    print(f"[{исход:6s}] {репо.name}: {пояснение}")
    if исход == "refuse":
        return 2
    if а.check:
        return 1 if исход == "ok" else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
