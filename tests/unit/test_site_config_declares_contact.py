"""У каждой витрины объявлен адрес обратной связи, и он один на всю сеть.

Зачем проверка, если адрес уже расставлен
-----------------------------------------

Расставить значение один раз — не то же самое, что удержать его. Опрос всех
девятнадцати доменов 2026-09-29 показал: ни на одном не было ни ссылки
`mailto:`, ни адреса в тексте, ни страницы «Контакты». Каждая витрина была
собрана по образцу соседней, и ни в одном образце контакта не было — значит,
следующая витрина повторила бы то же самое, а заметили бы это снова только
после выкладки.

Поэтому правило живёт здесь, а не в памяти автора: конфигурация новой ячейки
получает адрес из `factory.cell.newsite.КОНТАКТ_СЕТИ`, а эта проверка следит,
что ни одна существующая витрина его не потеряла и не завела свой.

Почему один адрес на сеть
-------------------------

Посетитель пишет не домену, а проекту. Разные адреса на соседних доменах — это
письма, ушедшие туда, где их никто не читает, и узнать об этом неоткуда:
`mailto:` не отвечает кодом доставки.

Чего проверка НЕ делает
-----------------------

Она не подтверждает, что письма доходят. Правильная ссылка и доставка — разные
утверждения, и второе проверяется только отправкой письма живым человеком.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

КОРЕНЬ = Path(__file__).resolve().parents[2]
РЕЕСТР = КОРЕНЬ / "config" / "site-cells.json"

#: Витрины, у которых своего репозитория с конфигурацией ещё нет: местные
#: заготовки и стенды. Их отсутствие в проверке — не послабление, а признание
#: того, что проверять нечего: файла нет.
БЕЗ_РЕПОЗИТОРИЯ = {"pilot-local", "site-a", "site-b", "site-c"}


def _ячейки() -> list[dict]:
    данные = json.loads(РЕЕСТР.read_text(encoding="utf-8"))
    ячейки = данные.get("cells") or данные.get("sites") or []
    return ячейки if isinstance(ячейки, list) else list(ячейки.values())


def _адрес_сети() -> str:
    from factory.cell import newsite

    return newsite.КОНТАКТ_СЕТИ


def _конфигурации() -> list[tuple[str, Path, dict]]:
    итог = []
    for ячейка in _ячейки():
        site_id = ячейка.get("site_id") or ""
        if site_id in БЕЗ_РЕПОЗИТОРИЯ:
            continue
        путь = (ячейка.get("repo") or {}).get("path") or ""
        if not путь:
            continue
        файл = (КОРЕНЬ / путь) / "config" / "site.json"
        if not файл.is_file():
            continue
        итог.append((site_id, файл, json.loads(файл.read_text(encoding="utf-8"))))
    return итог


def test_адрес_сети_похож_на_адрес():
    """Значение по умолчанию — настоящий адрес, а не заглушка."""
    адрес = _адрес_сети()
    assert адрес and "@" in адрес and " " not in адрес, адрес
    assert not адрес.startswith("@") and not адрес.endswith("@"), адрес
    имя, _, домен = адрес.partition("@")
    assert имя and "." in домен, f"домен адреса выглядит неполным: {адрес}"


def test_у_каждой_витрины_объявлен_контакт():
    адрес = _адрес_сети()
    конфигурации = _конфигурации()
    assert конфигурации, "ни одной конфигурации витрины не нашлось — проверять нечего"
    без_контакта = [s for s, _, c in конфигурации
                    if not str(c.get("contact_email") or "").strip()]
    assert not без_контакта, (
        "витрины без адреса обратной связи: " + ", ".join(без_контакта)
        + f". Ожидался {адрес}: он один на всю сеть и подставляется "
        "factory.cell.newsite при создании ячейки.")


@pytest.mark.parametrize("site_id,файл,конфиг", _конфигурации(),
                         ids=lambda з: з if isinstance(з, str) else "")
def test_адрес_у_всех_один(site_id, файл, конфиг):
    """Свой адрес на отдельной витрине — потерянные письма, а не гибкость."""
    адрес = _адрес_сети()
    свой = str(конфиг.get("contact_email") or "").strip()
    assert свой == адрес, (
        f"{site_id}: contact_email {свой!r}, а у сети {адрес!r} ({файл}). "
        "Менять адрес можно только решением владельца и сразу во всех витринах.")


#: Файлы рантайма, где подвал может читать переменную адреса.
_РАНТАЙМЫ = ("animedia-frontend.py", "animego-frontend.py", "lords-frontend.py",
             "yummy-frontend.py")


def _репозитории():
    """Все репозитории витрин, у которых есть и run.py, и рантайм."""
    итог = []
    for site_id, файл, _ in _конфигурации():
        корень = файл.parent.parent
        run = корень / "run.py"
        if not run.is_file():
            continue
        рантаймы = [корень / "src" / имя for имя in _РАНТАЙМЫ
                    if (корень / "src" / имя).is_file()]
        # Витрина может нести вендоренный шаблон вместо src/ — берём и его.
        рантаймы += [p for p in (корень / "template").rglob("*frontend*.py")
                     if (корень / "template").is_dir()]
        if рантаймы:
            итог.append((site_id, run, рантаймы))
    return итог


def _связанные_имена(узел) -> set:
    """Имена, связанные В ЭТОЙ области видимости.

    Параметр функции связывает имя не хуже присваивания. Прежняя проверка
    искала `имя =` текстом ВЫШЕ строки запроса и потому объявляла ошибкой
    верный код: набор переменных, вынесенный в функцию `дополнения(config)`,
    читает конфигурацию через параметр.
    """
    имена: set = set()
    функция = isinstance(узел, (ast.FunctionDef, ast.AsyncFunctionDef))
    if функция:
        арг = узел.args
        for список in (арг.posonlyargs, арг.args, арг.kwonlyargs):
            имена.update(а.arg for а in список)
        for одиночный in (арг.vararg, арг.kwarg):
            if одиночный is not None:
                имена.add(одиночный.arg)
    for вложенный in ast.walk(узел):
        if функция and вложенный is not узел and isinstance(
                вложенный, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(вложенный, ast.Name) and isinstance(вложенный.ctx, ast.Store):
            имена.add(вложенный.id)
        elif isinstance(вложенный, (ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.ClassDef)):
            имена.add(вложенный.name)
        elif isinstance(вложенный, (ast.Import, ast.ImportFrom)):
            for псевдоним in вложенный.names:
                имена.add((псевдоним.asname or псевдоним.name).split(".")[0])
    return имена


def _запросы_контакта(текст: str) -> list:
    """Пары «имя, у которого спросили contact_email» → видимые ему имена."""
    дерево = ast.parse(текст)
    родитель = {}
    области = {}
    for узел in ast.walk(дерево):
        if isinstance(узел, (ast.FunctionDef, ast.AsyncFunctionDef)):
            области[узел] = _связанные_имена(узел)
        for ребёнок in ast.iter_child_nodes(узел):
            родитель[ребёнок] = узел
    модульные = _связанные_имена(дерево)
    итог = []
    for узел in ast.walk(дерево):
        if not (isinstance(узел, ast.Call)
                and isinstance(узел.func, ast.Attribute)
                and узел.func.attr == "get"
                and узел.args
                and isinstance(узел.args[0], ast.Constant)
                and узел.args[0].value == "contact_email"
                and isinstance(узел.func.value, ast.Name)):
            continue
        видно = set(модульные)
        текущий = родитель.get(узел)
        while текущий is not None:
            видно |= области.get(текущий, set())
            текущий = родитель.get(текущий)
        итог.append((узел.func.value.id, видно))
    return итог


def _порядок_в_main(текст: str) -> tuple:
    """Номера операторов `main`: где выставляется переменная и где `--check`."""
    дерево = ast.parse(текст)
    выставляют = {у.name for у in дерево.body
                  if isinstance(у, (ast.FunctionDef, ast.AsyncFunctionDef))
                  and "SITE_CONTACT_EMAIL" in (ast.get_source_segment(текст, у) or "")}
    главная = next((у for у in дерево.body
                    if isinstance(у, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and у.name == "main"), None)
    if главная is None:
        return (None, None)
    где_ставят = где_проверка = None
    for номер, оператор in enumerate(главная.body):
        отрывок = ast.get_source_segment(текст, оператор) or ""
        ставит = "SITE_CONTACT_EMAIL" in отрывок or any(
            isinstance(в, ast.Name) and в.id in выставляют
            for в in ast.walk(оператор))
        if ставит and где_ставят is None:
            где_ставят = номер
        if (где_проверка is None and isinstance(оператор, ast.If)
                and "check" in (ast.get_source_segment(текст, оператор.test) or "")
                and any(isinstance(в, ast.Return) for в in ast.walk(оператор))):
            где_проверка = номер
    return (где_ставят, где_проверка)


@pytest.mark.parametrize("site_id,run,рантаймы", _репозитории(),
                         ids=lambda з: з if isinstance(з, str) else "")
def test_кто_читает_переменную_тот_её_и_получает(site_id, run, рантаймы):
    """Рантайм читает SITE_CONTACT_EMAIL — значит run.py обязан её выставить.

    Дефект, из-за которого проверка появилась. В ветке animedia.space подвал
    читал переменную, а `run.py` её не выставлял: `contact_email` в
    `config/site.json` стоял, строка подвала стояла, проводки между ними не
    было. Строка «Обратная связь» вышла бы ПУСТОЙ на каждой странице — при
    зелёных `checks/run.sh`, потому что ни одна проверка витрины не смотрит на
    связь конфигурации с окружением.

    Нашла это чтением ветки сессия, которая ведёт выпуск той витрины, — до
    площадки дефект не дошёл. Но нашла ЧЕЛОВЕКОМ, а не проверкой: у меня
    четырнадцать витрин получили проводку в цикле, а пятнадцатая в список не
    попала, и отличить её было нечем.

    Отдельно проверяется ПОРЯДОК: выставление обязано стоять до раннего
    возврата `--check`, иначе проверка конфигурации этих строк не исполняет.
    Цена измерена на zonafilm.cc — там из-за иного имени переменной кандидат не
    поднялся, а `--check` этого не заметил.
    """
    читают = [p for p in рантаймы
              if "SITE_CONTACT_EMAIL" in p.read_text(encoding="utf-8", errors="replace")]
    if not читают:
        pytest.skip(f"{site_id}: рантайм не читает SITE_CONTACT_EMAIL")
    текст = run.read_text(encoding="utf-8")
    assert "SITE_CONTACT_EMAIL" in текст, (
        f"{site_id}: {читают[0].name} читает SITE_CONTACT_EMAIL, а {run} её не "
        "выставляет — строка «Обратная связь» выйдет пустой на каждой странице")
    assert "contact_email" in текст, (
        f"{site_id}: {run} выставляет переменную, но не из config/site.json — "
        "значение обязано приходить из конфигурации, а не из кода")
    # Порядок берётся по порядку ОПЕРАТОРОВ в `main`, а не по номерам строк:
    # набор переменных может быть вынесен в функцию, и тогда её определение
    # лежит в файле выше, а исполняется из `main` — по номерам строк это
    # выглядело бы как «выставлено до всего», а при переносе под `--check`
    # осталось бы незамеченным.
    где_ставят, где_проверка = _порядок_в_main(текст)
    assert где_ставят is not None, (
        f"{site_id}: в main() {run} нет ни строки, ни вызова, выставляющих "
        "SITE_CONTACT_EMAIL")
    if где_проверка is not None:
        assert где_ставят < где_проверка, (
            f"{site_id}: выставление SITE_CONTACT_EMAIL стоит ПОСЛЕ раннего "
            f"возврата --check (операторы {где_ставят + 1} и {где_проверка + 1} "
            "в main): проверка конфигурации эти строки не исполнит")


@pytest.mark.parametrize("site_id,run,рантаймы", _репозитории(),
                         ids=lambda з: з if isinstance(з, str) else "")
def test_имя_конфигурации_в_проводке_существует(site_id, run, рантаймы):
    """Переменная, у которой спрашивают `contact_email`, обязана быть присвоена.

    Тот же дефект, что сломал кандидата zonafilm.cc, повторился в
    animedia.space: проводка обратилась к `config`, а конфигурация в том файле
    называется `конфиг`. `py_compile` такое пропускает — это NameError при
    ВЫПОЛНЕНИИ, а не синтаксис; `checks/activate_scenarios.py` витрины его
    поймал, но только потому, что у той витрины есть сценарный прогон.

    Проверка смотрит на связь имён: то имя, у которого спрашивают
    `contact_email`, должно быть присвоено в этом же файле ВЫШЕ строки запроса.
    """
    текст = run.read_text(encoding="utf-8")
    запросы = _запросы_контакта(текст)
    if not запросы:
        pytest.skip(f"{site_id}: проводки contact_email в run.py нет")
    for имя, видно in запросы:
        assert имя in видно, (
            f"{site_id}: проводка спрашивает {имя}.get('contact_email'), а имя "
            f"{имя!r} в {run} не связано ни в своей области видимости, ни в "
            "охватывающих — это NameError при запуске, который py_compile не "
            "видит")
