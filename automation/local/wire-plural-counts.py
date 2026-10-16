#!/usr/bin/env python3
"""Число серий и сезонов в публичном тексте — с правильным склонением.

    python3 automation/local/wire-plural-counts.py --repo <рабочая копия ячейки> [--dry-run]

Живой замер 16.10 ~19:50Z (lordfilm47.space, 40 случайных карточек из карты):
11 из 37 вхождений «N серий» склонены неверно — «24 серий», «21 серий», «4 серий».
Шаблон Lords/Zona подставляет число в строку с жёстким «серий» и «сезона»: так
пишется блок «Серии» в фактах карточки, заголовок сезона в списке серий и
подпись страницы сезона. Ошибка видна посетителю на каждой карточке сериала,
где число кончается на 1–4.

Инструмент делает ровно две вещи в src/lords-frontend.py:
1. добавляет модульные функции `_число_мн`, `_серий(n)`, `_сезонов(n)` (если их нет);
2. заменяет шаблоны из таблицы `ШАБЛОНЫ` на вызов этой функции.
Тексты, числа и разметка не меняются — только форма слова при числе.
3. доставляет проверку checks/plural_counts.py (automation/host/plural_counts_check.py)
   и вносит её в checks/run.sh после строки records-plural (или public-wording).
Отсутствующий шаблон — не ошибка (наборы у семейств разные); итог печатается.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys

ПРОВЕРКА = pathlib.Path(__file__).resolve().parents[1] / "host" / "plural_counts_check.py"
СТРОКА_ПРОГОНА = ('check "plural-counts"      bash -c \'python3 checks/plural_counts.py; rc=$?; '
                  '[ "$rc" -eq 2 ] && exit 0; exit "$rc"\'')
ЯКОРЯ_ПРОГОНА = ('check "records-plural"', 'check "public-wording"')

ФАЙЛ = "src/lords-frontend.py"
ЯКОРЬ = "\ndef всего_серий("
ФУНКЦИЯ = '''
def _число_мн(n: int, одна: str, две: str, пять: str) -> str:
    """«1 серия», «2 серии», «5 серий», «21 серия», «11 серий»."""
    n = int(n)
    if 11 <= abs(n) % 100 <= 14:
        слово = пять
    elif abs(n) % 10 == 1:
        слово = одна
    elif 2 <= abs(n) % 10 <= 4:
        слово = две
    else:
        слово = пять
    return f"{n} {слово}"


def _серий(n: int) -> str:
    return _число_мн(n, "серия", "серии", "серий")


def _сезонов(n: int) -> str:
    return _число_мн(n, "сезон", "сезона", "сезонов")

'''
# Внутри f-строк — только вызов без строковых литералов: Python 3.10 на хосте
# не допускает тех же кавычек внутри f-строки, что и снаружи.
ШАБЛОНЫ = (
    ('{серий} серий{хвост}', '{_серий(серий)}{хвост}'),
    ('{len(сезоны)} сезона, ', '{_сезонов(len(сезоны))}, '),
    ('{сезон["eps"]} серий{хвост}', '{_серий(сезон["eps"])}{хвост}'),
    ('В сезоне {серий} серий', 'В сезоне {_серий(серий)}'),
)

# Число и слово в РАЗНЫХ частях f-строки (перенос строки между ними): «Всего в
# произведении {N} '\n f'серий · ». Отступ у ячеек разный — поэтому выражение.
ШАБЛОНЫ_RE = (
    (re.compile(r"""\{sum\(с\["eps"\] for с in сезоны\) or "\?"\} '(\s+)f'серий · """),
     r"""{_серий(sum(с["eps"] for с in сезоны)) if sum(с["eps"] for с in сезоны) else "? серий"} '\1f'· """),
)


def самопроверка() -> None:
    ns: dict = {}
    exec(ФУНКЦИЯ, ns)
    f = lambda n, *_: ns["_серий"](n)  # noqa: E731
    if ns["_сезонов"](3) != "3 сезона" or ns["_сезонов"](21) != "21 сезон":
        raise SystemExit("самопроверка: сезоны")
    ждём = {1: "1 серия", 2: "2 серии", 4: "4 серии", 5: "5 серий", 11: "11 серий", 12: "12 серий",
            21: "21 серия", 24: "24 серии", 52: "52 серии", 100: "100 серий", 111: "111 серий", 0: "0 серий"}
    for n, w in ждём.items():
        got = f(n, "серия", "серии", "серий")
        if got != w:
            raise SystemExit(f"самопроверка: {n} → «{got}», ждали «{w}»")


def править(корень: pathlib.Path, сухо: bool) -> int:
    п = корень / ФАЙЛ
    if not п.is_file():
        print(f"{корень}: нет {ФАЙЛ}")
        return 2
    текст = п.read_text(encoding="utf-8")
    было = текст
    итог = []
    for старое, новое in ШАБЛОНЫ:
        n = текст.count(старое)
        текст = текст.replace(старое, новое)
        итог.append(f"{n}× {старое}")
    for выр, замена in ШАБЛОНЫ_RE:
        текст, n = выр.subn(замена, текст)
        итог.append(f"{n}× «Всего в произведении N серий»")
    if текст == было:
        print(f"{корень}: шаблонов нет — " + "; ".join(итог))
        return 0
    if "def _число_мн(" not in текст:
        if текст.count(ЯКОРЬ) != 1:
            print(f"{корень}: якорь «def всего_серий(» не найден ровно один раз")
            return 3
        текст = текст.replace(ЯКОРЬ, "\n" + ФУНКЦИЯ.rstrip("\n") + "\n\n" + ЯКОРЬ.lstrip("\n"), 1)
    print(f"{корень}: " + "; ".join(итог))
    if сухо:
        return 0
    compile(текст, str(п), "exec")  # синтаксис — до записи, без .pyc в рабочей копии
    п.write_text(текст, encoding="utf-8")
    return 0


def внести_проверку(корень: pathlib.Path, сухо: bool) -> int:
    проверки = корень / "checks"
    if not проверки.is_dir():
        print(f"{корень}: каталога checks/ нет — проверка не доставлена")
        return 3
    прогон = проверки / "run.sh"
    т = прогон.read_text(encoding="utf-8") if прогон.is_file() else ""
    if "checks/plural_counts.py" in т:
        новый = т
    else:
        строки = т.split("\n")
        где = next((i for я in ЯКОРЯ_ПРОГОНА for i, с in enumerate(строки) if с.startswith(я)), None)
        if где is None:
            print(f"{корень}: ОТКАЗ — в checks/run.sh нет строки {ЯКОРЯ_ПРОГОНА}")
            return 3
        строки.insert(где + 1, СТРОКА_ПРОГОНА)
        новый = "\n".join(строки)
    if not сухо:
        shutil.copy2(ПРОВЕРКА, проверки / "plural_counts.py")
        if новый != т:
            прогон.write_text(новый, encoding="utf-8")
    print(f"{корень}: проверка checks/plural_counts.py " + ("уже в прогоне" if новый == т else "внесена в checks/run.sh"))
    return 0


def главная(argv: list[str]) -> int:
    р = argparse.ArgumentParser(description=__doc__)
    р.add_argument("--repo", action="append", required=True)
    р.add_argument("--dry-run", action="store_true")
    а = р.parse_args(argv)
    самопроверка()
    код = 0
    for r in а.repo:
        к = pathlib.Path(r).resolve()
        код = max(код, править(к, а.dry_run))
        if код == 0:
            код = max(код, внести_проверку(к, а.dry_run))
    return код


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
