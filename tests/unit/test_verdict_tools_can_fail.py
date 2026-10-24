"""Инструмент, выносящий ВЕРДИКТ, обязан уметь закончиться ненулевым кодом.

ПОВОД. За одну ночь нашлось два инструмента, которые сообщали успех, не сделав
ничего (`playback-check.py`, класс 24), и один, который сообщал отказ, не умея
сделать ничего (класс 25). Нулевой код выхода у инструмента, который не умеет
вернуть другой, не доказывает ничего — и при этом выглядит убедительнее всего.

ЧТО ПРОВЕРЯЕТСЯ. Среди инструментов `automation/local` и `automation/host`
берутся те, что обращаются к сети или данным И печатают приговор (слова вроде
«НЕ ПРОЙДЕН», «РАСХОЖДЕНИЕ», «ВЫВОД:»). Каждый такой обязан иметь путь к
ненулевому коду выхода.

ЧЕГО ПРОВЕРКА НЕ ТРЕБУЕТ. Инструменты, которые просто докладывают состояние
(`network-state.py`, `ci-status.py`, `k2-cell-latency.py` и ещё тринадцать),
законно всегда возвращают ноль: их читают глазами, а не воротами. Поэтому
судятся только приговоры, а не все 190 замеров.

ИСТОРИЯ ЧИСЛА. Первая версия этого измерителя искала только `SystemExit(1)`
цифрой и насчитала 183 инструмента «без ненулевого кода» из 190. Это был
отрицательный результат от слепого измерителя: самый частый приём здесь —
`sys.exit(main())`, где код возвращает `main`, и цифрой он не виден. После
починки осталось 18, из них с приговором — 2. Поэтому ниже проверка умеет
читать возвраты функции, и это закреплено подменой.
"""
import ast
import pathlib

import pytest

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
КАТАЛОГИ = ("automation/local", "automation/host")
ПРИЗНАКИ_ЗАМЕРА = ("curl", "requests", "sync_playwright", "urlopen",
                   "subprocess.run")
ПРИГОВОРЫ = ("НЕ ПРОЙДЕН", "НЕ ГОДН", "ДЕФЕКТ", "РАСХОЖДЕНИЕ", "ОТКАЗ",
             "ПРОВАЛ", "НАРУШЕНИЕ", "НЕ СОВПА", "ВЫВОД:", "ПРОБЛЕМА",
             "НЕ ВЕРН", "ПОТЕРЯ", "НЕ ОБЪЯВЛЕН")


def _ненулевые_возвраты(узел):
    for у in ast.walk(узел):
        if isinstance(у, ast.Return) and у.value is not None:
            if isinstance(у.value, ast.Constant):
                знач = у.value.value
                if isinstance(знач, int) and знач != 0:
                    return True
                if isinstance(знач, str) and знач:
                    return True
            else:
                return True
    return False


def умеет_ненулевой(текст):
    """Есть ли у модуля путь к ненулевому коду выхода.

    Учитывается и `sys.exit(main())`: код берётся из возвратов `main`.
    """
    try:
        д = ast.parse(текст)
    except SyntaxError:
        return None
    функции = {у.name: у for у in ast.walk(д)
               if isinstance(у, ast.FunctionDef | ast.AsyncFunctionDef)}
    for у in ast.walk(д):
        выход = None
        if (isinstance(у, ast.Raise) and isinstance(у.exc, ast.Call)
                and isinstance(у.exc.func, ast.Name)
                and у.exc.func.id == "SystemExit"):
            выход = у.exc
        elif isinstance(у, ast.Call) and (
                (isinstance(у.func, ast.Attribute) and у.func.attr == "exit")
                or (isinstance(у.func, ast.Name) and у.func.id == "exit")):
            выход = у
        if выход is None or not выход.args:
            continue
        арг = выход.args[0]
        if isinstance(арг, ast.Constant):
            знач = арг.value
            if (isinstance(знач, int) and знач != 0) or (
                    isinstance(знач, str) and знач):
                return True
            continue
        if isinstance(арг, ast.Call) and isinstance(арг.func, ast.Name):
            ф = функции.get(арг.func.id)
            if ф is not None and _ненулевые_возвраты(ф):
                return True
            continue
        return True
    return False


def инструменты_с_приговором():
    найдено = []
    for к in КАТАЛОГИ:
        d = КОРЕНЬ / к
        if not d.is_dir():
            continue
        for ф in sorted(d.glob("*.py")):
            т = ф.read_text("utf-8", errors="replace")
            if not (any(п in т for п in ПРИЗНАКИ_ЗАМЕРА) and "print(" in т):
                continue
            if any(с in т for с in ПРИГОВОРЫ):
                найдено.append(ф)
    return найдено


@pytest.mark.parametrize("файл", инструменты_с_приговором(),
                         ids=lambda п: п.name)
def test_приговор_отражается_в_коде_выхода(файл):
    т = файл.read_text("utf-8", errors="replace")
    assert умеет_ненулевой(т) is not False, (
        f"{файл.relative_to(КОРЕНЬ)} печатает приговор, но не имеет пути к"
        " ненулевому коду выхода: поставленный в ворота, он будет всегда"
        " зелёным (docs/RECURRING_FAILURES.md, класс 24)")


def test_измеритель_видит_код_из_возврата_main():
    """Подмена: без этого проверка насчитала бы 183 нарушения вместо 2."""
    да = ("import sys\n"
          "def main():\n"
          "    if True:\n"
          "        return 1\n"
          "    return 0\n"
          "sys.exit(main())\n")
    нет = ("import sys\n"
           "def main():\n"
           "    print('готово')\n"
           "    return 0\n"
           "sys.exit(main())\n")
    assert умеет_ненулевой(да) is True
    assert умеет_ненулевой(нет) is False


def test_измеритель_видит_строку_в_systemexit():
    """`SystemExit("текст")` печатает текст и выходит кодом 1."""
    assert умеет_ненулевой('raise SystemExit("стоп")\n') is True
    assert умеет_ненулевой('raise SystemExit(0)\n') is False


def test_докладчики_не_судятся():
    """Инструмент без приговора в перечень не попадает.

    Иначе пришлось бы требовать ненулевой код у шестнадцати инструментов,
    которые просто докладывают состояние, и проверка стала бы шумом.
    """
    имена = {ф.name for ф in инструменты_с_приговором()}
    for докладчик in ("network-state.py", "ci-status.py", "k2-cell-latency.py"):
        путь = next((КОРЕНЬ / к / докладчик for к in КАТАЛОГИ
                     if (КОРЕНЬ / к / докладчик).is_file()), None)
        if путь is None:
            continue
        т = путь.read_text("utf-8", errors="replace")
        if not any(с in т for с in ПРИГОВОРЫ):
            assert докладчик not in имена, (
                f"{докладчик} не выносит приговора и судиться не должен")
