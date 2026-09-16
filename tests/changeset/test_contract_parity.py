"""Паритет контракта и реализации — машинно, а не по наличию файлов.

Совпадение имён файлов ничего не доказывает: расходятся не файлы, а поля,
значения перечислений, маршруты и коды ошибок. Каждая проверка здесь берёт
величину из РАБОТАЮЩЕГО кода и сравнивает с той же величиной из набора
контрактов; несовпадение — это отчёт о конкретном расхождении, а не «что-то
не сошлось».
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from factory.site_engine import contracts_version as CV
from factory.site_engine.changeset import api as API
from factory.site_engine.changeset import model as M

КОРЕНЬ = Path(__file__).resolve().parents[2]
НАБОР = КОРЕНЬ / "contracts/control-plane" / CV.ТЕКУЩИЙ


def _ч(имя: str):
    return json.loads((НАБОР / имя).read_text("utf-8"))


@pytest.fixture(scope="module")
def схема():
    return _ч("schemas/ChangeSet.v1.json")["properties"]


@pytest.fixture(scope="module")
def openapi():
    return _ч("openapi.json")


def _без_пустого(значения) -> set[str]:
    return {з for з in (значения or ()) if з is not None}


# --- сам набор ---------------------------------------------------------------

def test_набор_объявленной_версии_существует():
    assert НАБОР.is_dir(), f"код объявляет {CV.ТЕКУЩИЙ}, а набора нет: {НАБОР}"


def test_контрольные_суммы_сходятся():
    """Набор обязан описывать сам себя: иначе он описывает что-то другое."""
    суммы = _ч("checksums.json")
    расхождения = []
    for отн, ожидаемая in суммы["files"].items():
        ф = НАБОР / отн
        if not ф.is_file():
            расхождения.append((отн, "файла нет"))
            continue
        текущая = hashlib.sha256(ф.read_bytes()).hexdigest()
        if текущая != ожидаемая:
            расхождения.append((отн, "сумма не та"))
    лишние = {str(п.relative_to(НАБОР)) for п in НАБОР.rglob("*")
              if п.is_file() and п.name != "checksums.json"} - set(суммы["files"])
    assert not расхождения, расхождения
    assert not лишние, f"файлы вне описи: {sorted(лишние)}"


# --- перечисления ------------------------------------------------------------

def test_состояния_совпадают(схема):
    assert _без_пустого(схема["status"]["enum"]) == set(M.СОСТОЯНИЯ)


def test_состояния_перехода_совпадают():
    св = _ч("schemas/ChangeSetTransition.v1.json")["properties"]
    for имя in ("from_status", "to_status"):
        if "enum" in св.get(имя, {}):
            assert _без_пустого(св[имя]["enum"]) == set(M.СОСТОЯНИЯ), имя


def test_классы_риска_совпадают(схема):
    assert _без_пустого(схема["risk_class"]["enum"]) == set(M.КЛАССЫ_РИСКА)


def test_уровни_влияния_совпадают(схема):
    assert _без_пустого(схема["impact_level"]["enum"]) == set(M.УРОВНИ_ВЛИЯНИЯ)


def test_канонические_имена_программы_не_потеряны(схема):
    """Каждое каноническое имя ведёт в состояние, которое контракт знает."""
    объявленные = _без_пустого(схема["status"]["enum"])
    for имя, состояния in M.КАНОНИЧЕСКИЕ_ИМЕНА.items():
        отсутствуют = [с for с in состояния if с not in объявленные]
        assert not отсутствуют, (имя, отсутствуют)


# --- маршруты и параметры ----------------------------------------------------

def test_фильтры_списка_совпадают(openapi):
    объявленные = {p["name"] for p in
                   openapi["paths"]["/api/v1/changesets"]["get"]["parameters"]}
    assert объявленные == set(API.ФИЛЬТРЫ) | set(API.СЛУЖЕБНЫЕ)


def test_действия_совпадают(openapi):
    основа = "/api/v1/changesets/{changeset_id}/"
    объявленные = {п[len(основа):] for п in openapi["paths"]
                   if п.startswith(основа)}
    # transitions — чтение истории, а не действие над набором.
    assert объявленные - {"transitions"} == set(API.ДЕЙСТВИЯ)


def test_каждое_действие_принимает_условие_запроса(openapi):
    основа = "/api/v1/changesets/{changeset_id}/"
    без_условия, без_конфликта = [], []
    for путь, узел in openapi["paths"].items():
        if not путь.startswith(основа) or "post" not in узел:
            continue
        оп = узел["post"]
        имена = {p.get("name") for p in оп.get("parameters", [])}
        if "If-Match" not in имена:
            без_условия.append(путь)
        if "409" not in оп.get("responses", {}):
            без_конфликта.append(путь)
    assert not без_условия, без_условия
    assert not без_конфликта, без_конфликта


def test_чтение_набора_объявляет_версию_ресурса(openapi):
    отв = openapi["paths"]["/api/v1/changesets/{changeset_id}"]["get"]
    assert "ETag" in отв["responses"]["200"].get("headers", {})


# --- события -----------------------------------------------------------------

def test_каждое_событие_перехода_объявлено():
    каналы = _ч("asyncapi.json")["channels"]
    объявленные = {и.rsplit("/", 1)[-1] for и in каналы}
    события = {п.событие for п in M.ПЕРЕХОДЫ if п.событие}
    assert события <= объявленные, sorted(события - объявленные)


# --- ошибки ------------------------------------------------------------------

def _коды_из_кода() -> set[str]:
    """Коды ошибок, которые контур действительно умеет возвращать.

    Собираются разбором исходников, а не списком в тесте: список пришлось бы
    поддерживать вручную, и он разошёлся бы первым.
    """
    коды: set[str] = set()
    пакет = КОРЕНЬ / "factory/site_engine/changeset"
    for ф in sorted(пакет.glob("*.py")):
        дерево = ast.parse(ф.read_text("utf-8"), filename=str(ф))
        for узел in ast.walk(дерево):
            if not isinstance(узел, ast.Call):
                continue
            имя = getattr(узел.func, "id", None) or getattr(
                узел.func, "attr", None)
            if имя not in ("ChangeSetError", "_проблема", "Отказ"):
                continue
            позиция = 1 if имя == "_проблема" else 0
            if len(узел.args) > позиция:
                арг = узел.args[позиция]
                if isinstance(арг, ast.Constant) and isinstance(арг.value, str):
                    коды.add(арг.value)
    return коды


def test_каждый_возвращаемый_код_ошибки_объявлен():
    каталог = _ч("error-catalog.json")["errors"]
    объявленные = {з.get("error_code") or з.get("code") for з in каталог}
    из_кода = _коды_из_кода()
    assert из_кода, "разбор исходников не нашёл ни одного кода"
    отсутствуют = sorted(из_кода - объявленные)
    assert not отсутствуют, f"коды вне каталога ошибок: {отсутствуют}"


# --- эталонный клиент --------------------------------------------------------

def _клиент():
    """Клиент лежит в наборе контрактов, а не в пакете: он обязан работать
    без установки проекта, поэтому и импортируется по пути."""
    путь = КОРЕНЬ / "contracts/control-plane/clients/changeset_client.py"
    спец = importlib.util.spec_from_file_location("changeset_client", путь)
    м = importlib.util.module_from_spec(спец)
    спец.loader.exec_module(м)
    return м


def test_клиент_знает_ровно_те_же_действия():
    """Ни одного лишнего действия и ни одного забытого."""
    assert set(_клиент().ДЕЙСТВИЯ) == set(API.ДЕЙСТВИЯ)


def test_у_каждого_действия_клиента_есть_метод():
    к = _клиент()
    имена = {"validate": "валидировать", "approve": "одобрить",
             "reject": "отклонить", "revoke-approval": "отозвать_одобрение",
             "apply": "применить", "rollback": "откатить",
             "cancel": "отменить"}
    assert set(имена) == set(к.ДЕЙСТВИЯ), sorted(set(имена) ^ set(к.ДЕЙСТВИЯ))
    нет = [м for м in имена.values() if not hasattr(к.КлиентИзменений, м)]
    assert not нет, нет


def test_пути_клиента_объявлены_в_openapi(openapi):
    к = _клиент()
    основа = "/api/v1/changesets/{changeset_id}/"
    объявленные = {п[len(основа):] for п in openapi["paths"]
                   if п.startswith(основа)}
    нет = [д for д in к.ДЕЙСТВИЯ if д not in объявленные]
    assert not нет, нет
    assert к.БАЗА in openapi["paths"], к.БАЗА


def test_клиент_не_задаёт_состояние():
    """Состояние — вывод сервера. Клиент, умеющий его прислать, однажды
    пришлёт, и машина переходов окажется необязательной."""
    путь = КОРЕНЬ / "contracts/control-plane/clients/changeset_client.py"
    текст = путь.read_text("utf-8")
    подозрительные = [с for с in текст.splitlines()
                      if '"status"' in с and "#" not in с.split('"status"')[0]]
    assert not подозрительные, подозрительные


def test_клиент_обходится_стандартной_библиотекой():
    """Клиент с зависимостями перестаёт быть эталонным: его не берут в тесную
    среду, и он расходится с контрактом молча."""
    import ast
    путь = КОРЕНЬ / "contracts/control-plane/clients/changeset_client.py"
    дерево = ast.parse(путь.read_text("utf-8"))
    корни = set()
    for узел in ast.walk(дерево):
        if isinstance(узел, ast.Import):
            корни |= {a.name.split(".")[0] for a in узел.names}
        elif isinstance(узел, ast.ImportFrom) and узел.level == 0 and узел.module:
            корни.add(узел.module.split(".")[0])
    свои = корни - {"json", "urllib", "typing", "__future__", "ast"}
    assert not свои, f"внешние зависимости у эталонного клиента: {sorted(свои)}"
