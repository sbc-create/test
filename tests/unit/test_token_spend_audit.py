"""Учёт расхода токенов: ОДНО обращение к модели считается ОДИН раз.

Повод — собственная ошибка 25.10, найденная до того, как из чисел сделали
вывод. Первая редакция разбора снимала повторы по `uuid`, а одно обращение
пишется в стенограмму 2–3 строками (по блоку содержимого), и КАЖДАЯ строка
повторяет полный `message.usage`. Проверено на выборке: у `requestId` с тремя
строками все три несут одинаковые «вх 2 / вых 277 / запись 28 594 / чтение
10 834». Счёт по строкам завышал итог примерно в 1,85 раза (51 460 строк
против 27 751 обращения), и на таком основании нельзя было назвать ни одной
доли расхода.

Здесь закреплено: единица счёта — `requestId`; строка без него считается по
`uuid` и объявляется отдельным числом, а не растворяется в итоге.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import pathlib

КОРЕНЬ = pathlib.Path(__file__).resolve().parents[2]
_путь = КОРЕНЬ / "automation/local/token-spend-audit.py"
_спец = importlib.util.spec_from_file_location("token_spend_audit", _путь)
АУД = importlib.util.module_from_spec(_спец)
_спец.loader.exec_module(АУД)

ОКНО = (dt.datetime(2026, 10, 18, tzinfo=dt.timezone.utc),
        dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc))


def строка(ид: str, uuid: str, вых: int = 100, чт: int = 10_000,
           когда: str = "2026-10-25T10:00:00.000Z", **ещё) -> str:
    з = {"requestId": ид, "uuid": uuid, "timestamp": когда, "type": "assistant",
         "sessionId": "сеанс-1", "version": "2.1.292", "cwd": "/home/claude/wt-x",
         "message": {"model": "claude-opus-5-5",
                     "usage": {"input_tokens": 2, "output_tokens": вых,
                               "cache_creation_input_tokens": 500,
                               "cache_read_input_tokens": чт}}}
    з.update(ещё)
    return json.dumps(з, ensure_ascii=False)


def журнал(tmp_path: pathlib.Path, строки: list[str]) -> str:
    (tmp_path / "s.jsonl").write_text("\n".join(строки) + "\n", encoding="utf-8")
    return str(tmp_path / "s.jsonl")


def test_три_блока_одного_обращения_считаются_один_раз(tmp_path) -> None:
    итог = АУД.собрать(журнал(tmp_path, [строка("req-1", f"u{i}") for i in range(3)]), *ОКНО)
    assert итог["охват"]["строк_с_расходом"] == 1
    assert итог["охват"]["повторов_requestId"] == 2
    assert итог["своды"]["всего"]["чтение_кеша"] == 10_000, "расход посчитан трижды"


def test_разные_обращения_складываются(tmp_path) -> None:
    итог = АУД.собрать(журнал(tmp_path, [строка("req-1", "u1"), строка("req-2", "u2")]), *ОКНО)
    assert итог["охват"]["строк_с_расходом"] == 2
    assert итог["своды"]["всего"]["чтение_кеша"] == 20_000
    assert итог["охват"]["повторов_requestId"] == 0


def test_строка_без_requestId_считается_по_uuid_и_объявляется(tmp_path) -> None:
    """Молча растворять такие строки в итоге нельзя: их число названо."""
    итог = АУД.собрать(журнал(tmp_path, [строка(None, "u1"), строка(None, "u1"),
                                         строка(None, "u2")]), *ОКНО)
    assert итог["охват"]["строк_с_расходом"] == 2
    assert итог["охват"]["без_requestId"] == 2


def test_вне_окна_не_считается_и_объявляется(tmp_path) -> None:
    итог = АУД.собрать(журнал(tmp_path, [
        строка("req-1", "u1", когда="2026-10-25T10:00:00.000Z"),
        строка("req-2", "u2", когда="2026-10-01T10:00:00.000Z")]), *ОКНО)
    assert итог["охват"]["строк_с_расходом"] == 1 and итог["охват"]["вне_окна"] == 1


def test_подагенты_отделены_от_главных_сеансов(tmp_path) -> None:
    итог = АУД.собрать(журнал(tmp_path, [строка("req-1", "u1"),
                                         строка("req-2", "u2", isSidechain=True)]), *ОКНО)
    assert итог["своды"]["подагенты"]["обращений"] == 1
    assert итог["своды"]["главные"]["обращений"] == 1


def test_без_времени_не_попадает_в_окно(tmp_path) -> None:
    итог = АУД.собрать(журнал(tmp_path, [строка("req-1", "u1", когда="не время")]), *ОКНО)
    assert итог["охват"]["строк_с_расходом"] == 0 and итог["охват"]["без_времени"] == 1
