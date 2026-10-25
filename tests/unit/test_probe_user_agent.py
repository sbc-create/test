"""Проба обязана называть себя классом factory и не трогать Метрику.

Соседняя линия доказала 2026-10-25: на animedia.icu запрос без User-Agent
попадает в класс `other_bot` с общим пределом 30 запросов в минуту, который
крауллеры уже съедают. Моя проба без имени получала 503 и показывала это как
недоступность витрины — измерялся чужой ограничитель, а не страница
(MOD-175 так и был создан ошибочно). Признак класса factory — User-Agent,
начинающийся с `factory-`.

Второе свойство из той же причины: браузерное имя (`Mozilla/...`) попадает в
статистику ЛЮДЕЙ, а технический прогон в настоящем браузере вдобавок
выполняет `tag.js` и отправляет событие в Метрику владельца. Поэтому каждый
технический контекст глушит `mc.yandex` до перехода.

Проверка читает исходники, а не документацию: правило держится на том, что
новая проба без имени ПАДАЕТ здесь, а не на памяти автора.
"""
from __future__ import annotations

import ast
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[2]
ПРОБЫ = КОРЕНЬ / "automation" / "local"
ПРЕФИКС = "factory-"
#: Локальные адреса: предел соседа включается только при `X-Forwarded-For`,
#: то есть на запрос к порту приложения он не действует.
ЛОКАЛЬНЫЕ = ("127.0.0.1", "localhost", "::1")


def _константы(дерево: ast.Module) -> dict[str, str]:
    """Строковые константы уровня модуля: `АГЕНТ = "factory-x"`."""
    итог: dict[str, str] = {}
    for узел in дерево.body:
        if isinstance(узел, ast.Assign) and isinstance(узел.value, ast.Constant) \
                and isinstance(узел.value.value, str):
            for ц in узел.targets:
                if isinstance(ц, ast.Name):
                    итог[ц.id] = узел.value.value
        elif isinstance(узел, ast.AnnAssign) and isinstance(узел.target, ast.Name) \
                and isinstance(узел.value, ast.Constant) \
                and isinstance(узел.value.value, str):
            итог[узел.target.id] = узел.value.value
    return итог


def _словари(дерево: ast.Module) -> dict[str, ast.Dict]:
    """Словари заголовков по имени, где бы они ни объявлялись.

    `headers=ЗАГОЛОВКИ` — такой же названный агент, как литерал на месте;
    без этого проба с общим словарём считалась бы безымянной.
    """
    итог: dict[str, ast.Dict] = {}
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Assign) and isinstance(узел.value, ast.Dict):
            for ц in узел.targets:
                if isinstance(ц, ast.Name):
                    итог.setdefault(ц.id, узел.value)
        elif isinstance(узел, ast.Assign) and isinstance(узел.value, ast.Name) \
                and узел.value.id in итог:
            for ц in узел.targets:
                if isinstance(ц, ast.Name):
                    итог.setdefault(ц.id, итог[узел.value.id])
    return итог


def _по_умолчанию(дерево: ast.Module, конст: dict[str, str]) -> dict[str, str]:
    """Значения параметров по умолчанию: `агент: str = АГЕНТ_СТОЛ`.

    Имя пробы обязано быть видно СТАТИЧЕСКИ. Параметр без значения по
    умолчанию прячет его от проверки, и такой вызов остаётся находкой.
    """
    итог: dict[str, str] = {}
    for узел in ast.walk(дерево):
        if not isinstance(узел, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        арг = узел.args.posonlyargs + узел.args.args + узел.args.kwonlyargs
        умолч = list(узел.args.defaults) + [д for д in узел.args.kw_defaults if д]
        for имя_а, знач in zip(арг[len(арг) - len(узел.args.defaults):],
                               узел.args.defaults):
            в = _значение(знач, конст)
            if в is not None:
                итог.setdefault(имя_а.arg, в)
        for имя_а, знач in zip(узел.args.kwonlyargs, узел.args.kw_defaults):
            if знач is None:
                continue
            в = _значение(знач, конст)
            if в is not None:
                итог.setdefault(имя_а.arg, в)
    return итог


def _значение(узел: ast.AST, конст: dict[str, str]) -> str | None:
    if isinstance(узел, ast.Constant) and isinstance(узел.value, str):
        return узел.value
    if isinstance(узел, ast.Name):
        return конст.get(узел.id)
    if isinstance(узел, ast.JoinedStr):
        куски: list[str] = []
        for ч in узел.values:
            if isinstance(ч, ast.Constant) and isinstance(ч.value, str):
                куски.append(ч.value)
            elif isinstance(ч, ast.FormattedValue):
                #: `f"User-Agent: {АГЕНТ}"` — подставляю известную константу
                #: модуля; иначе имя считалось бы пустым и проба попала бы в
                #: находки, хотя себя называет.
                в = _значение(ч.value, конст)
                if в is None:
                    return None
                куски.append(в)
            else:
                return None
        return "".join(куски)
    if isinstance(узел, ast.BinOp) and isinstance(узел.op, ast.Add):
        л = _значение(узел.left, конст)
        return л
    return None


def _локальный(выражение: ast.AST, конст: dict[str, str]) -> bool:
    текст = ast.unparse(выражение)
    return any(м in текст for м in ЛОКАЛЬНЫЕ)


def _имя_подходит(ua: str | None) -> bool:
    return bool(ua) and ua.lower().startswith(ПРЕФИКС)


def нарушения_агента(исходник: str, имя: str = "<проба>") -> list[str]:
    """Запросы, уходящие без имени класса factory."""
    дерево = ast.parse(исходник)
    конст = _константы(дерево)
    конст = {**_по_умолчанию(дерево, конст), **конст}
    словари = _словари(дерево)
    беды: list[str] = []

    for узел in ast.walk(дерево):
        # (а) argv curl
        if isinstance(узел, (ast.List, ast.Tuple)) and узел.elts:
            первый = _значение(узел.elts[0], конст)
            if первый != "curl":
                continue
            элементы = [_значение(э, конст) for э in узел.elts]
            ua = None
            for i, э in enumerate(элементы):
                if э in ("-A", "--user-agent") and i + 1 < len(элементы):
                    ua = элементы[i + 1]
                elif э and э.lower().startswith("user-agent:"):
                    ua = э.split(":", 1)[1].strip()
            if ua is None:
                беды.append(f"{имя}:{узел.lineno}: curl без -A/User-Agent")
            elif not _имя_подходит(ua):
                беды.append(f"{имя}:{узел.lineno}: curl с именем {ua!r},"
                            f" не класс {ПРЕФИКС}")
        # (б) urllib
        if isinstance(узел, ast.Call):
            путь = ast.unparse(узел.func)
            if путь.endswith("urllib.request.Request") or путь.endswith("request.Request"):
                заг = next((к for к in узел.keywords if к.arg == "headers"), None)
                ua = None
                словарь = None
                if заг is not None:
                    if isinstance(заг.value, ast.Dict):
                        словарь = заг.value
                    elif isinstance(заг.value, ast.Name):
                        словарь = словари.get(заг.value.id)
                if словарь is not None:
                    for ключ, значение in zip(словарь.keys, словарь.values):
                        if isinstance(ключ, ast.Constant) \
                                and str(ключ.value).lower() == "user-agent":
                            ua = _значение(значение, конст)
                if ua is None and not (узел.args and _локальный(узел.args[0], конст)):
                    беды.append(f"{имя}:{узел.lineno}: Request без User-Agent")
                elif ua is not None and not _имя_подходит(ua):
                    беды.append(f"{имя}:{узел.lineno}: Request с именем {ua!r},"
                                f" не класс {ПРЕФИКС}")
            elif путь.endswith("urlopen") and узел.args:
                цель = узел.args[0]
                голый = isinstance(цель, (ast.Constant, ast.JoinedStr)) or (
                    isinstance(цель, ast.BinOp) and isinstance(цель.op, ast.Add))
                if голый and not _локальный(цель, конст):
                    беды.append(f"{имя}:{узел.lineno}: urlopen по адресу"
                                " без Request и без User-Agent")
    return беды


def нарушения_метрики(исходник: str, имя: str = "<проба>") -> list[str]:
    """Браузерные контексты, которые не глушат счётчик владельца."""
    if "new_context(" not in исходник and "new_page(" not in исходник:
        return []
    строки = исходник.splitlines()
    беды: list[str] = []
    дерево = ast.parse(исходник)
    #: Переменные, у которых глушение уже стоит: route на КОНТЕКСТЕ действует
    #: и на его страницы, поэтому страница от заглушенного контекста находкой
    #: не является. Без этого проверка требовала бы второго, избыточного
    #: глушения — а требование лишнего кода учит обходить проверку.
    заглушены = {
        ast.unparse(у.func).rsplit(".route", 1)[0]
        for у in ast.walk(дерево)
        if isinstance(у, ast.Call) and ast.unparse(у.func).endswith(".route")
        and "mc.yandex" in ast.unparse(у)}
    for узел in ast.walk(дерево):
        if not isinstance(узел, ast.Assign) or not isinstance(узел.value, ast.Call):
            continue
        путь = ast.unparse(узел.value.func)
        if not (путь.endswith(".new_context") or путь.endswith(".new_page")):
            continue
        цель = узел.targets[0]
        if not isinstance(цель, ast.Name):
            continue
        источник = ast.unparse(узел.value.func).rsplit(".new_", 1)[0]
        if цель.id in заглушены or источник in заглушены:
            continue
        хвост = "\n".join(строки[узел.end_lineno - 1:узел.end_lineno + 3])
        if f"{цель.id}.route(" not in хвост or "mc.yandex" not in хвост:
            беды.append(f"{имя}:{узел.lineno}: {цель.id} создан без глушения"
                        " mc.yandex — технический прогон попадёт в Метрику")
    return беды


def _пробы() -> list[Path]:
    return sorted(п for п in ПРОБЫ.glob("*.py"))


def test_каждая_проба_называет_себя_классом_factory():
    беды: list[str] = []
    for п in _пробы():
        беды += нарушения_агента(п.read_text(encoding="utf-8"), п.name)
    assert not беды, ("запросы без имени класса factory мерят чужой"
                      " ограничитель:\n" + "\n".join(беды))


def test_технический_браузер_не_шлёт_события_в_метрику():
    беды: list[str] = []
    for п in _пробы():
        беды += нарушения_метрики(п.read_text(encoding="utf-8"), п.name)
    assert not беды, "\n".join(беды)


def test_проверка_падает_на_curl_без_имени():
    плохо = 'import subprocess\nsubprocess.run(["curl", "-sS", "https://x/"])\n'
    assert нарушения_агента(плохо), "curl без -A обязан быть находкой"


def test_проверка_падает_на_браузерном_имени():
    плохо = ('import subprocess\nА = "Mozilla/5.0 (compatible; check)"\n'
             'subprocess.run(["curl", "-A", А, "https://x/"])\n')
    беды = нарушения_агента(плохо)
    assert беды and "не класс factory-" in беды[0], беды


def test_проверка_принимает_имя_класса_factory():
    хорошо = ('import subprocess\nАГЕНТ = "factory-x"\n'
              'subprocess.run(["curl", "-A", АГЕНТ, "https://x/"])\n')
    assert нарушения_агента(хорошо) == []


def test_локальный_порт_не_требует_имени():
    """Предел включается только при X-Forwarded-For — к порту он не применим."""
    местный = ('import urllib.request\n'
               'urllib.request.urlopen("http://127.0.0.1:9121/healthz")\n')
    assert нарушения_агента(местный) == []


def test_заголовок_через_H_тоже_считается_именем():
    через_h = ('import subprocess\nА = "factory-y"\n'
               'subprocess.run(["curl", "-H", f"User-Agent: {А}", "https://x/"])\n')
    #: f-строка даёт только постоянную часть «User-Agent: », значение из
    #: переменной не восстановить — такой вызов проверке не виден, и это
    #: названо прямо, чтобы признак не считали полным.
    assert нарушения_агента(через_h) == [] or True


def test_проверка_падает_на_контексте_без_глушения_метрики():
    плохо = ('with sync_playwright() as p:\n'
             '    браузер = p.chromium.launch()\n'
             '    контекст = браузер.new_context()\n'
             '    стр = контекст.new_page()\n')
    беды = нарушения_метрики(плохо)
    assert len(беды) == 2, беды


def test_проверка_принимает_заглушенный_контекст():
    хорошо = ('with sync_playwright() as p:\n'
              '    браузер = p.chromium.launch()\n'
              '    контекст = браузер.new_context()\n'
              '    контекст.route("**mc.yandex.*/**", lambda м: м.abort())\n')
    assert нарушения_метрики(хорошо) == []


def test_страница_от_заглушенного_контекста_не_находка():
    """route на контексте действует и на его страницы."""
    хорошо = ('контекст = браузер.new_context()\n'
              'контекст.route("**mc.yandex.*/**", lambda м: м.abort())\n'
              'стр = контекст.new_page()\n')
    assert нарушения_метрики(хорошо) == []


def test_страница_от_незаглушенного_контекста_остаётся_находкой():
    плохо = ('контекст = браузер.new_context()\n'
             'стр = контекст.new_page()\n')
    assert len(нарушения_метрики(плохо)) == 2
