"""Доступ к канонической редакционной очереди из канала, которым пользуется Qwen.

Зачем этот мост
---------------

Каноническое состояние редакционной работы живёт в оператора содержания:
`/var/lib/seo-content-operator/registry.json` (306 записей на 2026-10-06),
журнал решений, долговечные подавления, ворота качества. В канале, которым
Qwen действительно располагает — инструменты этого моста, — очереди не было ни
одного инструмента: он мог спросить факты (`editorial_facts`), состояние
витрины (`editorial_status`) и записать материал, но не мог ни ВЗЯТЬ задание,
ни УЗНАТЬ прежний вердикт, ни ЗАПИСАТЬ результат.

Следствие измерено: суточный цикл оператора пять дней подряд заканчивался
`NO_ACCESS_AUTHORING` — провайдер авторства не настроен, писать текст серверу
нечем. Текст писался в чужой сессии, и её единственной памятью были
собственные markdown-файлы. Каждый запуск заново выводил список работ, не знал
отвергнутых соответствий и повторял их.

Второй системы здесь не создаётся. Логика очереди живёт ОДНИМ модулем в
оператора (`seo_engine.content_operator.editorial_queue`), а мост вызывает её
отдельным процессом под интерпретатором оператора — тем же способом, которым
уже вызывается хранилище накладок (`factory.qwen.editorial._вызвать_store`), и
по той же причине: в моделях оператора `enum.StrEnum`, то есть нужен Python
3.11, а системный — 3.10.

Границы
-------

* Своего состояния мост не держит и копий не делает.
* Полезная нагрузка передаётся ФАЙЛОМ с JSON. Текст материала в командную
  строку не попадает ни при каких условиях.
* Корень оператора берётся из одного места (`КОРЕНЬ_ОПЕРАТОРА`) с
  переопределением через окружение: пока код очереди лежит в ветке ремонта,
  мост должен указывать на неё, а после переноса рантайма — на рабочую копию,
  и это не должно требовать правки кода.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile
from typing import Any


class ОчередьОтклонила(Exception):
    """Операция очереди не выполнена. Состояние не изменено."""


#: Корень кода оператора. Одно место на весь мост.
#:
#: По умолчанию — рабочая копия, из которой запускается суточный цикл
#: (`WorkingDirectory` юнита `seo-content-operator.service`). Пока модуль
#: очереди живёт только в ветке ремонта, путь задаётся переменной
#: `SEO_OPERATOR_ROOT`: иначе мост звал бы дерево, где нужного модуля нет, и
#: отказ выглядел бы как поломка очереди.
_ПО_УМОЛЧАНИЮ = "/home/claude/wt-seo-index-audit-20260930"

#: Записанный выбор корня оператора — ОДИН источник на оба канала.
#:
#: Переменной окружения мало. Она есть у юнита моста (drop-in установки) и
#: отсутствует в оболочке человека, поэтому путь командной строки — тот самый,
#: на который ссылается инструкция словами «нет инструмента, сделай командой», —
#: отказывал: «в дереве оператора … нет модуля очереди». Отказ правильный и
#: причину называл, но приходил там, где работа должна была идти. Измерено
#: 2026-10-06 на `queue-release`.
#:
#: Поэтому выбор пишется файлом рядом с состоянием фабрики, и его видят оба
#: канала. Переменная окружения по-прежнему главнее файла: ею пользуются
#: проверки и разовые прогоны.
ФАЙЛ_КОРНЯ = pathlib.Path(__file__).resolve().parents[2] / "var" / "state" / "seo-operator-root"


def КОРЕНЬ_ОПЕРАТОРА() -> pathlib.Path:
    """Переменная окружения → записанный выбор → умолчание."""
    из_среды = os.environ.get("SEO_OPERATOR_ROOT", "").strip()
    if из_среды:
        return pathlib.Path(из_среды)
    try:
        записано = ФАЙЛ_КОРНЯ.read_text(encoding="utf-8").strip()
    except OSError:
        записано = ""
    # Берётся только существующий каталог: записанный, но удалённый путь — это
    # не выбор, а след прошлого, и подсовывать его молча нельзя.
    if записано and pathlib.Path(записано).is_dir():
        return pathlib.Path(записано)
    return pathlib.Path(_ПО_УМОЛЧАНИЮ)


def ИНТЕРПРЕТАТОР() -> pathlib.Path:
    """Интерпретатор оператора.

    Виртуальное окружение заводится один раз на репозиторий, поэтому у ветки
    ремонта его может не быть; тогда берётся окружение рабочей копии —
    зависимости те же, а код подаётся через PYTHONPATH.
    """
    свой = КОРЕНЬ_ОПЕРАТОРА() / ".venv" / "bin" / "python"
    if свой.is_file():
        return свой
    return pathlib.Path(_ПО_УМОЛЧАНИЮ) / ".venv" / "bin" / "python"


_ВЫЗОВ = r"""
import datetime as dt
import json
import pathlib
import sys

from seo_engine.content_operator.editorial_queue import EditorialQueue, QueueError

з = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
очередь = EditorialQueue()
op = з["op"]
try:
    if op == "next":
        итог = {"tasks": очередь.next_tasks(
            site=з["site"], limit=int(з.get("limit") or 1),
            owner=з["owner"],
            content_types=tuple(з.get("content_types") or ()))}
    elif op == "result":
        итог = очередь.record_result(
            task_id=з["task_id"], owner=з["owner"], outcome=з["outcome"],
            body=з.get("body") or "",
            source_urls=tuple(з.get("source_urls") or ()),
            source_published_at=з.get("source_published_at") or "",
            facts=tuple(з.get("facts") or ()),
            source_id=з.get("source_id") or "",
            canonical_url=з.get("canonical_url") or "",
            detail=з.get("detail") or "",
            label=з.get("label") or "")
    elif op == "find":
        итог = очередь.find(site=з["site"], canonical_url=з["canonical_url"],
                            content_type=з.get("content_type")
                            or "TITLE_DESCRIPTION")
    elif op == "register":
        итог = очередь.register(
            site=з["site"], canonical_url=з["canonical_url"],
            headline=з["headline"],
            content_type=з.get("content_type") or "TITLE_DESCRIPTION",
            work_id=з.get("work_id") or "",
            search_intent=з.get("search_intent") or "",
            priority_band=з.get("priority_band") or "P3",
            status=з.get("status") or "NEEDS_UPDATE",
            brief=з.get("brief") or None)
    elif op == "status":
        итог = очередь.status(site=з["site"])
    elif op == "reopen":
        итог = очередь.reopen(task_id=з["task_id"], reason=з["reason"],
                              status=з.get("status") or "NEEDS_UPDATE")
    elif op == "release":
        итог = очередь.release(task_id=з["task_id"], owner=з["owner"])
    else:
        raise QueueError(f"неизвестная операция {op!r}")
except QueueError as ош:
    print(json.dumps({"ok": False, "error": str(ош)}, ensure_ascii=False))
    raise SystemExit(0)
print(json.dumps({"ok": True, "result": итог}, ensure_ascii=False))
"""


def _вызвать(задание: dict[str, Any], *, таймаут: int = 180) -> dict[str, Any]:
    корень = КОРЕНЬ_ОПЕРАТОРА()
    интерпретатор = ИНТЕРПРЕТАТОР()
    if not интерпретатор.is_file():
        raise ОчередьОтклонила(
            f"нет интерпретатора оператора {интерпретатор}: очередь читать нечем")
    модуль = корень / "seo_engine" / "content_operator" / "editorial_queue.py"
    if not модуль.is_file():
        raise ОчередьОтклонила(
            f"в дереве оператора {корень} нет модуля очереди {модуль.name}. "
            "Укажите корень с ремонтом через SEO_OPERATOR_ROOT или перенесите "
            "рантайм: молча отвечать «очередь пуста» нельзя")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json",
                                     delete=False) as ф:
        json.dump(задание, ф, ensure_ascii=False)
        файл = ф.name
    try:
        r = subprocess.run(
            [str(интерпретатор), "-c", _ВЫЗОВ, файл],
            cwd=str(корень), capture_output=True, text=True, timeout=таймаут,
            env={"PYTHONPATH": str(корень), "PATH": "/usr/bin:/bin",
                 "HOME": os.environ.get("HOME", "/home/claude")})
    except subprocess.TimeoutExpired as ош:
        raise ОчередьОтклонила(
            f"очередь не ответила за {таймаут} с: {ош}") from None
    finally:
        os.unlink(файл)
    if r.returncode != 0:
        raise ОчередьОтклонила(
            f"очередь отказала (код {r.returncode}): "
            f"{(r.stderr or r.stdout).strip()[-400:]}")
    try:
        ответ = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as ош:
        raise ОчередьОтклонила(
            f"очередь ответила неразборчиво: {r.stdout[:200]!r}") from ош
    if not ответ.get("ok"):
        raise ОчередьОтклонила(str(ответ.get("error") or "причина не названа"))
    return ответ["result"]


# --------------------------------------------------------------- операции
def взять(*, site: str, owner: str, limit: int = 1,
          content_types: tuple[str, ...] = ()) -> dict[str, Any]:
    """Взять до `limit` заданий и закрепить их за `owner`."""
    итог = _вызвать({"op": "next", "site": site, "owner": owner,
                     "limit": limit, "content_types": list(content_types)})
    задания = итог.get("tasks") or []
    return {
        "site": site,
        "owner": owner,
        "claimed": len(задания),
        "tasks": задания,
        "next_action": (
            "по каждому заданию: прочитать источники, написать текст и вызвать "
            "editorial_queue_result. Если источник не ответил — исход "
            "SOURCE_UNAVAILABLE, и задание уступит место другому"
            if задания else
            "свободных заданий нет: все либо закреплены, либо ждут срока "
            "повторной проверки. Это не ошибка и не повод заводить вторую очередь"),
    }


def записать(*, task_id: str, owner: str, outcome: str, **поля: Any) -> dict[str, Any]:
    """Записать результат задания. Статус выводит очередь, а не вызывающий."""
    задание = {"op": "result", "task_id": task_id, "owner": owner,
               "outcome": outcome}
    for имя in ("body", "source_urls", "source_published_at", "facts",
                "source_id", "canonical_url", "detail", "label"):
        if имя in поля and поля[имя] not in (None, ""):
            задание[имя] = поля[имя]
    итог = _вызвать(задание)
    итог["next_action"] = (
        "задание закрыто, можно брать следующее через editorial_queue_next"
        if not итог.get("next_attempt_at")
        else f"задание вернётся к работе не раньше {итог['next_attempt_at']}")
    return итог


def найти(*, site: str, canonical_url: str,
          content_type: str = "TITLE_DESCRIPTION") -> dict[str, Any]:
    """Есть ли задание по адресу. Аренды НЕ создаёт."""
    итог = _вызвать({"op": "find", "site": site, "canonical_url": canonical_url,
                     "content_type": content_type})
    итог["next_action"] = (
        "задание есть: работать по нему через editorial_queue_next (оно придёт "
        "в выдаче, когда подойдёт очередь) или записать результат по task_id"
        if итог.get("found") else
        "задания нет: завести его через editorial_queue_register с названием "
        "карточки; повторная регистрация вернёт то же задание")
    return итог


def завести(*, site: str, canonical_url: str, headline: str,
            **поля: Any) -> dict[str, Any]:
    """Завести задание по адресу. Идемпотентно: дубля не будет."""
    задание = {"op": "register", "site": site, "canonical_url": canonical_url,
               "headline": headline}
    for имя in ("content_type", "work_id", "search_intent", "priority_band",
                "status", "brief"):
        if имя in поля and поля[имя] not in (None, "", {}):
            задание[имя] = поля[имя]
    итог = _вызвать(задание)
    итог["next_action"] = (
        "задание заведено" if итог.get("created") else
        "задание уже существовало и возвращено как есть: статус, текст и "
        "происхождение не изменены")
    return итог


def состояние(*, site: str) -> dict[str, Any]:
    return _вызвать({"op": "status", "site": site})


def возобновить(*, task_id: str, reason: str,
                status: str = "NEEDS_UPDATE") -> dict[str, Any]:
    """Вернуть ОДНО задание в работу раньше срока. Аренды не создаёт."""
    итог = _вызвать({"op": "reopen", "task_id": task_id, "reason": reason,
                     "status": status})
    итог["next_action"] = (
        "задание снова выдаётся: взять его через editorial_queue_next и "
        "записать результат по task_id")
    return итог


def отпустить(*, task_id: str, owner: str) -> dict[str, Any]:
    return _вызвать({"op": "release", "task_id": task_id, "owner": owner})


__all__ = ["ОчередьОтклонила", "КОРЕНЬ_ОПЕРАТОРА", "взять", "записать",
           "состояние", "отпустить", "найти", "завести", "возобновить"]
