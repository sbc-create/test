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
    elif op == "annul":
        итог = очередь.annul(task_id=з["task_id"], entry_at=з["entry_at"],
                             expect_outcome=з["expect_outcome"],
                             reason=з["reason"])
    elif op == "release":
        итог = очередь.release(task_id=з["task_id"], owner=з["owner"])
    elif op == "owns":
        итог = очередь.lease_check(task_id=з["task_id"], owner=з["owner"])
    elif op == "published":
        итог = очередь.note_publication(
            task_id=з["task_id"],
            canonical_url=з.get("canonical_url") or "",
            generation_id=з.get("generation_id") or "",
            content_digest=з.get("content_digest") or "",
            author=з.get("author") or "")
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
#: Виды материала, которым нужна ДОСТАВКА текста на страницу. Для них задание
#: без пути доставки выполнить нельзя ни при каком содержании.
ТРЕБУЮТ_ДОСТАВКИ = ("TITLE_DESCRIPTION",)


#: Формы пути карточки по семействам — те же, что в реестре. Берутся оттуда, а
#: не перечисляются здесь: разойдясь, два перечня дали бы разный ключ поиска
#: для одной страницы.


def нормализовать_адрес(site: str, canonical_url: str) -> tuple[str, str]:
    """Канонический абсолютный адрес страницы и пояснение. (адрес, заметка).

    Зачем. Очередь ищет существующее задание по адресу как по строке, и одна и
    та же страница, записанная двумя способами, даёт ДВА живых задания.
    Измерено 2026-10-09 на живом реестре: восемь групп дублей, в том числе
    `yummyani.org/anime/ledyanaya-stena-2` — `request-b74982172ba225a2` с
    относительным `/anime/ledyanaya-stena-2` и `request-fa190135f85d72c9` с
    абсолютным `https://yummyani.org/anime/ledyanaya-stena-2`. Это одна
    страница, два задания и два исполнителя, которые не знают друг о друге.

    Форма адреса берётся из реестра (`registry.адрес_тайтла`), а не
    перечисляется здесь: второй перечень разошёлся бы с первым, и ключ поиска
    стал бы зависеть от того, кто его считал. Неизвестная форма — не повод
    угадывать: адрес остаётся как передан, и заметка это называет.
    """
    сырой = (canonical_url or "").strip()
    if not сырой:
        return сырой, "адрес пуст"
    try:
        from factory.qwen import editorial as _ред
        from factory.qwen import registry as _реестр
        s = _ред._сайт(site)
    except Exception as ош:  # noqa: BLE001 — отказ реестра адрес не чинит
        return сырой, f"реестр не ответил ({ош}): адрес оставлен как передан"

    путь = сырой
    if сырой.lower().startswith(("http://", "https://")):
        без_схемы = сырой.split("://", 1)[1]
        хост, _, остаток = без_схемы.partition("/")
        if хост.lower().replace("www.", "") != s.domain.lower():
            return сырой, (f"хост {хост} не равен домену задания {s.domain}: "
                           "адрес не нормализуется, пусть решает очередь")
        путь = "/" + остаток

    формы = _реестр.ФОРМА_АДРЕСА.get(s.adapter)
    if not формы:
        return f"https://{s.domain}{путь}", (
            f"форма адреса семейства {s.adapter!r} не проверена: "
            "собран абсолютный адрес без приведения формы")

    # Слаг карточки — последний непустой кусок пути карточки. Страницы серий и
    # разделов под эту форму не подводятся: у них своя структура, и приводить
    # их к карточке значило бы подменить адрес задания.
    части = [к for к in путь.split("/") if к]
    корень_формы = формы.strip("/").split("/")[0] if "{slug}" in формы else ""
    if корень_формы and len(части) == 2 and части[0] == корень_формы:
        return _реестр.адрес_тайтла(s, части[1]), "приведён к форме семейства"
    return f"https://{s.domain}{путь}", "собран абсолютный адрес"


def доставка_описаний(site: str) -> tuple[bool, str]:
    """Сработает ли на этой площадке публикация описания. (можно, причина).

    Проверка стоит в мосте, а не в очереди: возможности семейства объявлены в
    реестре фабрики, и второй источник того же знания в модуле оператора
    разошёлся бы с первым. Критерий не придумывается здесь заново — берётся
    тот же, которым пользуется сама публикация: `registry.ТРЕБУЕТ_ВОЗМОЖНОСТИ`
    для операции `publish` (доставка И отображение).

    Зачем застава. Измерено 2026-10-09 по живой очереди: девять заданий на
    описание, закреплённых арендами, стоят у семейств, где доставки нет вовсе —
    три на lordfilm47.space (`lords`), два на an1mego.site и четыре на
    animeg0.site (`animego`). Текст для них написать можно, положить его
    некуда. Задание, которое нельзя выполнить, но можно получить, — это работа
    исполнителя, потраченная на отказ, и он возвращается к нему снова: за сутки
    до 2026-10-09 очередь выдала 203 задания и получила 45 результатов.
    """
    try:
        from factory.qwen import editorial as _ред
        from factory.qwen import registry as _реестр
    except ImportError as ош:  # pragma: no cover — реестр всегда рядом
        return True, f"реестр недоступен ({ош}): застава не применяется"
    try:
        s = _ред._сайт(site)
    except Exception as ош:  # noqa: BLE001 — отказ реестра заставой не считается
        return True, f"площадка {site!r} в реестре не разобрана ({ош})"
    if "publish" in _реестр.доступные_операции(s):
        return True, ""
    умеет = set(_реестр.возможности(s))
    нехватка = [в for в in _реестр.ТРЕБУЕТ_ВОЗМОЖНОСТИ["publish"] if в not in умеет]
    return False, (
        f"{site}: публикация описания на этой площадке не сработает — у "
        f"семейства {s.adapter!r} не объявлено {нехватка}. Текст написать "
        "можно, положить его некуда: задание невыполнимо, пока у площадки не "
        "появится читатель накладки в выпущенном рантайме")


def взять(*, site: str, owner: str, limit: int = 1,
          content_types: tuple[str, ...] = ()) -> dict[str, Any]:
    """Взять до `limit` заданий и закрепить их за `owner`.

    Задания на описание у площадки без доставки не выдаются вовсе: выдать их
    значит потратить работу исполнителя на заведомый отказ.
    """
    запрошены = tuple(content_types) or ТРЕБУЮТ_ДОСТАВКИ
    только_описания = all(в in ТРЕБУЮТ_ДОСТАВКИ for в in запрошены)
    можно, причина = доставка_описаний(site)
    if только_описания and not можно:
        return {"site": site, "owner": owner, "claimed": 0, "tasks": [],
                "blocked_reason": причина,
                "next_action": (
                    "задания на описание этой площадке не выдаются: "
                    + причина + ". Возьмите другую площадку или дождитесь "
                    "выпуска с читателем накладки")}
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
    адрес, заметка = нормализовать_адрес(site, canonical_url)
    итог = _вызвать({"op": "find", "site": site, "canonical_url": адрес,
                     "content_type": content_type})
    if адрес != canonical_url:
        итог["canonical_url_normalized"] = адрес
        итог["canonical_url_as_asked"] = canonical_url
        итог["normalization_note"] = заметка
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
    вид = str(поля.get("content_type") or "TITLE_DESCRIPTION")
    if вид in ТРЕБУЮТ_ДОСТАВКИ:
        можно, причина = доставка_описаний(site)
        if not можно:
            raise ОчередьОтклонила(
                причина + ". Задание не заведено: очередь не держит работу, "
                "которую нельзя выполнить")
    адрес, заметка = нормализовать_адрес(site, canonical_url)
    задание = {"op": "register", "site": site, "canonical_url": адрес,
               "headline": headline}
    for имя in ("content_type", "work_id", "search_intent", "priority_band",
                "status", "brief"):
        if имя in поля and поля[имя] not in (None, "", {}):
            задание[имя] = поля[имя]
    итог = _вызвать(задание)
    if адрес != canonical_url:
        итог["canonical_url_normalized"] = адрес
        итог["canonical_url_as_asked"] = canonical_url
        итог["normalization_note"] = заметка
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


def отменить(*, task_id: str, entry_at: str, expect_outcome: str,
             reason: str) -> dict[str, Any]:
    """Отменить ПОСЛЕДНИЙ записанный результат одного задания.

    Нужна, когда результат записан ошибочно: следы исхода снимаются, счётчик
    попыток и статус возвращаются к значениям до него, а история СОХРАНЯЕТСЯ и
    получает отметку об отмене. Записанный текст отмене не подлежит.
    """
    итог = _вызвать({"op": "annul", "task_id": task_id, "entry_at": entry_at,
                     "expect_outcome": expect_outcome, "reason": reason})
    итог["next_action"] = (
        "следы исхода сняты, история помечена; задание снова выдаётся через "
        "editorial_queue_next")
    return итог


def отпустить(*, task_id: str, owner: str) -> dict[str, Any]:
    return _вызвать({"op": "release", "task_id": task_id, "owner": owner})


def отметить_публикацию(*, task_id: str, canonical_url: str = "",
                        generation_id: str = "", content_digest: str = "",
                        author: str = "") -> dict[str, Any]:
    """След в журнале очереди о том, что текст задания опубликован.

    Статуса не меняет и публичной видимости не утверждает: подтверждение
    делает тот, кто читает страницу. Нужна, потому что публикация идёт другим
    инструментом, и до этого связи между заданием и его публичным результатом
    не было ни в одну сторону (измерено 2026-10-08 на
    animedia.space/title/detektivnoe-agentstvo-li/).
    """
    return _вызвать({"op": "published", "task_id": task_id,
                     "canonical_url": canonical_url,
                     "generation_id": generation_id,
                     "content_digest": content_digest, "author": author})


def моё_ли(*, task_id: str, owner: str) -> dict[str, Any]:
    """Моё ли это задание. Отвечает да/нет и ЧУЖОГО ИМЕНИ НЕ НАЗЫВАЕТ.

    Нужен потому, что единственным способом это узнать был пробный результат:
    отказ печатал имя действующего владельца, и это имя подставляли, чтобы отказ
    обойти. Измерено 2026-10-07: результаты по одним и тем же заданиям приходили
    под восемью разными именами.
    """
    return _вызвать({"op": "owns", "task_id": task_id, "owner": owner})


__all__ = ["ОчередьОтклонила", "КОРЕНЬ_ОПЕРАТОРА", "взять", "записать",
           "отметить_публикацию",
           "состояние", "отпустить", "моё_ли", "найти", "завести",
           "возобновить", "отменить"]
