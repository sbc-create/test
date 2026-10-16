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

ФАЙЛЫ = ("src/lords-frontend.py", "src/animedia-frontend.py")  # Lords/Zona и Animedia
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


def _из_серий(n: int) -> str:
    """После «из»: «из 44 серий», «из 21 серии», «из 11 серий»."""
    return _число_мн(n, "серии", "серий", "серий")

'''
# Внутри f-строк — только вызов без строковых литералов: Python 3.10 на хосте
# не допускает тех же кавычек внутри f-строки, что и снаружи.
ШАБЛОНЫ = (
    ('{серий} серий{хвост}', '{_серий(серий)}{хвост}'),
    ('{len(сезоны)} сезона, ', '{_сезонов(len(сезоны))}, '),
    ('{сезон["eps"]} серий{хвост}', '{_серий(сезон["eps"])}{хвост}'),
    ('В сезоне {серий} серий', 'В сезоне {_серий(серий)}'),
    # Animedia (живой замер 16.10 20:45Z animedia.space: 16 из 30 форм неверны —
    # «Сезон 1 · 34 серий», «2 серий»; факты и описание — «Доступно N серий»).
    ('f"Доступно {avail} серий"', 'f"Доступно {_серий(avail)}"'),
    ('f"Вышло {total} серий"', 'f"Вышло {_серий(total)}"'),
    ('Вышло {доступно} из {заявлено} серий</span>', 'Вышло {доступно} из {_из_серий(заявлено)}</span>'),
    ('Доступно {avail_n} серий</span>', 'Доступно {_серий(avail_n)}</span>'),
)

# Число и слово в РАЗНЫХ частях f-строки (перенос строки между ними): «Всего в
# произведении {N} '\n f'серий · ». Отступ у ячеек разный — поэтому выражение.
ШАБЛОНЫ_RE = (
    (re.compile(r"""\{sum\(с\["eps"\] for с in сезоны\) or "\?"\} '(\s+)f'серий · """),
     r"""{_серий(sum(с["eps"] for с in сезоны)) if sum(с["eps"] for с in сезоны) else "? серий"} '\1f'· """),
)

# Своя вёрстка lordserial33.biz (src/lords02_view.py): «N из M серий». После «из»
# — родительный падеж: «из 44 серий», но «из 21 серии», «из 201 серии» (живой замер
# 16.10 20:20Z: «из 201 серий» на 6 карточках выборки). Функция склонения уже есть
# в модуле таксономии (Т.склонение, возвращает только слово); формы — родительного падежа.
ФАЙЛ_LORDS02 = "src/lords02_view.py"
РОД = "Т.склонение(заявлено, 'серии', 'серий', 'серий')"
ШАБЛОНЫ_LORDS02 = (
    ('f"{заявлено} серий доступно</span>")', 'f"{заявлено} {' + РОД + '} доступно</span>")'),
    ('f"{заявлено} серий</span>" if доступно < заявлено', 'f"{заявлено} {' + РОД + '}</span>" if доступно < заявлено'),
)


def править_lords02(корень: pathlib.Path, сухо: bool) -> None:
    п = корень / ФАЙЛ_LORDS02
    if not п.is_file():
        return
    текст = п.read_text(encoding="utf-8")
    итог = []
    for старое, новое in ШАБЛОНЫ_LORDS02:
        итог.append(f"{текст.count(старое)}× {старое[:30]}…")
        текст = текст.replace(старое, новое)
    print(f"{корень}: {ФАЙЛ_LORDS02}: " + "; ".join(итог))
    if not сухо and текст != п.read_text(encoding="utf-8"):
        compile(текст, str(п), "exec")
        п.write_text(текст, encoding="utf-8")


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


def файл_шаблона(корень: pathlib.Path) -> pathlib.Path | None:
    """Файл, который витрина исполняет: entrypoint из config/site.json, иначе первый из ФАЙЛЫ.
    У animedia-icu лежат оба (lords-frontend.py — наследство), исполняется animedia-frontend.py."""
    import json
    try:
        вход = json.loads((корень / "config/site.json").read_text(encoding="utf-8")).get("entrypoint")
    except (OSError, ValueError):
        вход = None
    if вход and f"src/{вход}" in ФАЙЛЫ and (корень / "src" / вход).is_file():
        return корень / "src" / вход
    return next((корень / ф for ф in ФАЙЛЫ if (корень / ф).is_file()), None)


def править(корень: pathlib.Path, сухо: bool) -> int:
    п = файл_шаблона(корень)
    if п is None:
        print(f"{корень}: нет ни одного из {ФАЙЛЫ}")
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
    недостающие = [б for б in re.split(r"\n(?=\ndef )", ФУНКЦИЯ.strip("\n"))
                   if б.strip() and re.search(r"def (\w+)\(", б).group(0) not in текст]
    if недостающие:
        if текст.count(ЯКОРЬ) != 1:
            print(f"{корень}: якорь «def всего_серий(» не найден ровно один раз")
            return 3
        блок = "\n\n\n".join(б.strip("\n") for б in недостающие)
        текст = текст.replace(ЯКОРЬ, "\n" + блок + "\n\n\n" + ЯКОРЬ.lstrip("\n"), 1)
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
            править_lords02(к, а.dry_run)
        if код == 0:
            код = max(код, внести_проверку(к, а.dry_run))
    return код


if __name__ == "__main__":
    sys.exit(главная(sys.argv[1:]))
